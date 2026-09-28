"""CBR listing and extraction through ``lsar`` and ``unar``."""

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from manga_tagger.archives.errors import MissingUnarError, UnreadableArchiveError


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:(?:/|$)")


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
        validate_cbr_member_name(name)
        entries.append((name, bool(entry.get("XADIsDirectory"))))
    return entries


def read_cbr_member(
    path: Path,
    member: str,
    *,
    entries: list[tuple[str, bool]] | None = None,
) -> bytes:
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
        UnreadableArchiveError: A declared member is unsafe, ``unar`` failed,
            or the requested member was not extracted as a regular file.
    """
    require_unarchiver()
    listed = list_cbr_entries(path) if entries is None else entries
    for listed_name, _is_dir in listed:
        validate_cbr_member_name(listed_name)
    validate_cbr_member_name(member)
    if not any(name == member and not is_dir for name, is_dir in listed):
        raise UnreadableArchiveError(f"{member} is not a file in {path.name}")
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
        validate_extracted_tree(temp)
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
        UnreadableArchiveError: A declared member is unsafe, ``unar`` failed,
            or extraction produced a link, special entry, or escaping path.
    """
    require_unarchiver()
    list_cbr_entries(path)
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
            ]
        )
        if result.returncode != 0:
            raise UnreadableArchiveError(f"unar could not extract {path.name}")
        validate_extracted_tree(temp)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return temp


def validate_cbr_member_name(name: str) -> None:
    """Reject a declared CBR member name that could escape extraction.

    Both slash styles are separators because CBRs can contain names written
    on a different platform than the host running Manga Tagger.
    """
    normalized = name.replace("\\", "/")
    if not normalized or "\x00" in normalized:
        raise UnreadableArchiveError("CBR contains an unsafe empty member name")
    if normalized.startswith("/") or _WINDOWS_DRIVE.match(normalized):
        raise UnreadableArchiveError(f"CBR contains an unsafe member name: {name}")
    components = normalized.split("/")
    if components[-1] == "":
        components.pop()
    if not components or any(part in {"", ".", ".."} for part in components):
        raise UnreadableArchiveError(f"CBR contains an unsafe member name: {name}")


def validate_extracted_tree(root: Path) -> None:
    """Accept only contained regular files and real directories under ``root``."""
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise UnreadableArchiveError("CBR extraction directory is unreadable") from exc

    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    metadata = entry.stat(follow_symlinks=False)
                    relative = path.relative_to(root)
                    if stat.S_ISLNK(metadata.st_mode):
                        raise UnreadableArchiveError(
                            "CBR extraction contains an unsafe symbolic link: "
                            f"{relative}"
                        )
                    if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
                        raise UnreadableArchiveError(
                            f"CBR extraction contains an unsafe hard link: {relative}"
                        )
                    if not (
                        stat.S_ISREG(metadata.st_mode)
                        or stat.S_ISDIR(metadata.st_mode)
                    ):
                        raise UnreadableArchiveError(
                            f"CBR extraction contains a non-regular entry: {relative}"
                        )
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(resolved_root):
                        raise UnreadableArchiveError(
                            "CBR extraction escaped its temporary directory: "
                            f"{relative}"
                        )
                    if stat.S_ISDIR(metadata.st_mode):
                        pending.append(path)
        except UnreadableArchiveError:
            raise
        except OSError as exc:
            raise UnreadableArchiveError("CBR extraction is unreadable") from exc


def _stdout(result: subprocess.CompletedProcess[bytes]) -> bytes:
    stdout = result.stdout
    if isinstance(stdout, str):
        return stdout.encode()
    return stdout or b""


def _extracted_file(temp: Path, member: str) -> Path:
    basename = Path(member.replace("\\", "/")).name
    candidate = temp / basename
    if candidate.is_file() and not candidate.is_symlink():
        return candidate
    files = [
        item for item in temp.rglob("*") if item.is_file() and not item.is_symlink()
    ]
    if len(files) == 1:
        return files[0]
    raise UnreadableArchiveError(f"extracted member {member} was not found")
