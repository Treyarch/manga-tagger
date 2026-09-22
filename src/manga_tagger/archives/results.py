"""Per-file results for batch save and rename."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileResult:
    """One archive in a batch save or rename.

    ``output_path`` is the written or planned path when the entry succeeded.
    ``error_type`` is the exception class name when it failed.
    """

    path: Path
    output_path: Path | None = None
    error_type: str = ""
    error_message: str = ""

    @property
    def ok(self) -> bool:
        """Return true when this file has no error."""
        return self.error_type == ""


def failure(path: Path, exc: BaseException) -> FileResult:
    """Build a failed result from an exception."""
    return FileResult(
        path=path,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )
