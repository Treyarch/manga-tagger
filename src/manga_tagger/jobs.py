"""One background worker. Jobs run first in, first out."""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from manga_tagger.providers.errors import ProviderCancelledError

Progress = Callable[[int, int], None]
Cancel = Callable[[], bool]
JobFunction = Callable[[Cancel, Progress], object]


class JobNotFoundError(Exception):
    """GET or cancel names an id this process did not start."""


class JobBusyError(Exception):
    """``start`` while a job is queued or running."""


class JobCancelled(Exception):
    """The job saw cancel before the next file, poster, or provider request.

    Attributes:
        result: Partial entries already finished, when the job had any.
    """

    def __init__(self, result: object = None) -> None:
        self.result = result
        super().__init__("cancelled")


@dataclass
class Job:
    """One queued or finished unit of work."""

    id: str
    name: str
    state: str
    error_type: str = ""
    error_message: str = ""
    result: object = None
    completed: int = 0
    total: int = 0
    cancel_requested: bool = False


class JobRunner:
    """Run one job at a time on a single worker thread.

    Args:
        inline: When true, ``start`` runs the job on the caller thread and
            returns it in a terminal state. Tests use this and do not sleep.
        hold: When true, the worker thread is not started until ``release``.
            A queued job can be cancelled before its function is called.
    """

    def __init__(self, *, inline: bool = False, hold: bool = False) -> None:
        self.inline = inline
        self._jobs: dict[str, Job] = {}
        self._queue: list[tuple[Job, JobFunction]] = []
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._next_id = 1
        self._stop = False
        self._thread: threading.Thread | None = None
        if not inline and not hold:
            self._start_thread()

    def start(self, name: str, fn: JobFunction) -> Job:
        """Queue ``fn`` unless a job is already queued or running.

        Args:
            name: Header name, such as ``Scan`` or ``Save``.
            fn: Called with ``cancel`` and ``progress``.

        Returns:
            The job. An inline run has already reached a terminal state.

        Raises:
            JobBusyError: A job is queued or running. ``fn`` is not called.
        """
        with self._lock:
            if self._busy():
                raise JobBusyError("a job is already queued or running")
            job = Job(id=str(self._next_id), name=name, state="queued")
            self._next_id += 1
            self._jobs[job.id] = job
            if not self.inline:
                self._queue.append((job, fn))
                self._wake.notify()
        if self.inline:
            self._execute(job, fn)
        return job

    def cancel(self, job_id: str) -> Job:
        """Cancel a queued job or ask a running job to stop.

        Args:
            job_id: Id returned by ``start``.

        Returns:
            The job. A queued job is ``cancelled`` and its function is not called.

        Raises:
            JobNotFoundError: This process did not start ``job_id``.
        """
        with self._lock:
            job = self._require(job_id)
            if job.state == "queued":
                job.state = "cancelled"
                self._queue = [item for item in self._queue if item[0].id != job.id]
            elif job.state == "running":
                job.cancel_requested = True
            return job

    def get(self, job_id: str) -> Job:
        """Return a job this process started.

        Raises:
            JobNotFoundError: The id is unknown.
        """
        with self._lock:
            return self._require(job_id)

    def current(self) -> Job | None:
        """Return the running job, or the queued job, or ``None``."""
        with self._lock:
            for job in self._jobs.values():
                if job.state == "running":
                    return job
            for job in self._jobs.values():
                if job.state == "queued":
                    return job
            return None

    def release(self) -> None:
        """Start a worker that was created with ``hold``."""
        if self.inline or self._thread is not None:
            return
        self._start_thread()

    def shutdown(self) -> None:
        """Cancel queued jobs, ask the running job to stop, and join the worker."""
        with self._lock:
            self._stop = True
            self._queue.clear()
            for job in self._jobs.values():
                if job.state == "queued":
                    job.state = "cancelled"
                elif job.state == "running":
                    job.cancel_requested = True
            self._wake.notify_all()
        if self._thread is not None:
            self._thread.join()

    def _start_thread(self) -> None:
        self._thread = threading.Thread(
            target=self._loop, name="manga-tagger-jobs", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        while True:
            with self._lock:
                while not self._queue and not self._stop:
                    self._wake.wait()
                if self._stop and not self._queue:
                    return
                job, fn = self._queue.pop(0)
                if job.state == "cancelled" or self._stop:
                    job.state = "cancelled"
                    continue
            self._execute(job, fn)

    def _execute(self, job: Job, fn: JobFunction) -> None:
        with self._lock:
            if job.state == "cancelled" or self._stop:
                job.state = "cancelled"
                return
            job.state = "running"

        def cancel() -> bool:
            with self._lock:
                return job.cancel_requested or job.state == "cancelled"

        def progress(completed: int, total: int) -> None:
            with self._lock:
                job.completed = completed
                job.total = total

        try:
            result = fn(cancel, progress)
        except (JobCancelled, ProviderCancelledError) as exc:
            with self._lock:
                job.state = "cancelled"
                job.result = getattr(exc, "result", None)
                job.error_type = ""
                job.error_message = ""
        except Exception as exc:
            with self._lock:
                job.state = "failed"
                job.error_type = type(exc).__name__
                job.error_message = str(exc)
        else:
            with self._lock:
                job.state = "succeeded"
                job.result = result
                job.error_type = ""
                job.error_message = ""

    def _busy(self) -> bool:
        return any(job.state in {"queued", "running"} for job in self._jobs.values())

    def _require(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"job {job_id} was not started")
        return job
