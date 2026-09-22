"""CBR listing and extraction through ``lsar`` and ``unar``."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from manga_tagger.archives.errors import MissingUnarError, UnreadableArchiveError


def find_executable(name: str) -> str | None:
    """Return a PATH entry for ``name``, or ``None`` when it is absent.

    Args:
        name: Executable name, such as ``unar`` or ``lsar``.

    Returns:
        The absolute path ``shutil.which`` would return.
    """
    return shutil.which(name)


def run_command(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a command without a shell and capture its output.

    Args:
        args: Program and arguments.

    Returns:
        The completed process. A non-zero status is not raised here.
    """
    return subprocess.run(args, check=False, capture_output=True)


def require_unarchiver() -> None:
    """Raise when ``unar`` or ``lsar`` is not on PATH.

    Raises:
        MissingUnarError: Either executable is absent. The message names ``unar``.
    """
    if find_executable("unar") is None or find_executable("lsar") is None:
        raise MissingUnarError("unar was not found on PATH")


def list_cbr_entries(path: Path) -> list[tuple[str, bool]]:
    """List CBR members with ``lsar -json`` and do not extract the archive.

    Args:
        path: Path of the ``.cbr``.

    Returns:
        ``(member name, is directory)`` in ``lsar`` order.

    Raises:
        MissingUnarError: ``unar`` or ``lsar`` is absent.
        UnreadableArchiveError: ``lsar`` failed or its JSON is unusable.
    """
    require_unarchiver()
    result = run_command(["lsar", "-json", str(path)])
    if result.returncode != 0:
        raise UnreadableArchiveError(f"lsar could not read {path.name}")
    payload = _stdout(result)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise UnreadableArchiveError("lsar did not return JSON") from exc
    contents = data.get("lsarContents") if isinstance(data, dict) else None
    if not isinstance(contents, list):
        raise UnreadableArchiveError("lsar JSON is missing lsarContents")
    entries: list[tuple[str, bool]] = []
    for entry in contents:
        if not isinstance(entry, dict):
            raise UnreadableArchiveError("lsar entry is not an object")
        name = entry.get("XADFileName")
        if not isinstance(name, str):
            raise UnreadableArchiveError("lsar entry XADFileName is not a string")
        entries.append((name, bool(entry.get("XADIsDirectory"))))
    return entries


def read_cbr_member(path: Path, member: str) -> bytes:
    """Extract one CBR member with ``unar`` and return its bytes.

    The temporary directory is created beside ``path`` and removed afterwards,
    including when ``unar`` fails.

    Args:
        path: Path of the ``.cbr``.
        member: ``XADFileName`` to extract.

    Returns:
        The extracted file bytes.

    Raises:
        MissingUnarError: ``unar`` or ``lsar`` is absent.
        UnreadableArchiveError: ``unar`` failed or the member was not extracted.
    """
    require_unarchiver()
    temp = Path(tempfile.mkdtemp(prefix=".manga-tagger-", dir=path.parent))
    try:
        result = run_command(
            [
                "unar",
                "-quiet",
                "-no-directory",
                "-output-directory",
                str(temp),
                str(path),
                member,
            ]
        )
        if result.returncode != 0:
            raise UnreadableArchiveError(
                f"unar could not read {member} from {path.name}"
            )
        return _extracted_file(temp, member).read_bytes()
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def extract_cbr(path: Path) -> Path:
    """Extract a CBR into a temporary directory beside the archive.

    Args:
        path: Path of the ``.cbr``.

    Returns:
        The temporary directory. The caller deletes it after the ``.cbz`` is
        in place, or the directory is already gone when this function raises.

    Raises:
        MissingUnarError: ``unar`` or ``lsar`` is absent.
        UnreadableArchiveError: ``unar`` failed.
    """
    require_unarchiver()
    temp = Path(tempfile.mkdtemp(prefix=".manga-tagger-", dir=path.parent))
    try:
        result = run_command(
            ["unar", "-quiet", "-output-directory", str(temp), str(path)]
        )
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    if result.returncode != 0:
        shutil.rmtree(temp, ignore_errors=True)
        raise UnreadableArchiveError(f"unar could not extract {path.name}")
    return temp


def _stdout(result: subprocess.CompletedProcess[bytes]) -> bytes:
    stdout = result.stdout
    if isinstance(stdout, str):
        return stdout.encode()
    return stdout or b""


def _extracted_file(temp: Path, member: str) -> Path:
    basename = Path(member.replace("\\", "/")).name
    candidate = temp / basename
    if candidate.is_file():
        return candidate
    files = [item for item in temp.rglob("*") if item.is_file()]
    if len(files) == 1:
        return files[0]
    raise UnreadableArchiveError(f"extracted member {member} was not found")
