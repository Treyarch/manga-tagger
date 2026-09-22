"""Atomic ComicInfo saves and CBR-to-CBZ conversion."""

import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path

from manga_tagger.archives.cbr import extract_cbr
from manga_tagger.archives.comicinfo import BATCH_FIELDS, ComicInfo
from manga_tagger.archives.errors import (
    ArchiveError,
    BatchFieldError,
    ConvertTargetExistsError,
    UnreadableArchiveError,
)
from manga_tagger.archives.read import _kind, _open_cbz, read_zip_comic_info
from manga_tagger.archives.results import FileResult, failure
from manga_tagger.archives.zip_store import add_stored, write_updated_zip

_DIR_ATTR = (0o40755 << 16) | 0x10
_FILE_ATTR = 0o644 << 16


def save_comic_info(
    path: os.PathLike[str] | str,
    patch: Mapping[str, str | None],
    *,
    write_number: bool,
    keep_cbr_original: bool,
) -> Path:
    """Write a ComicInfo patch for one archive.

    A ``.cbz`` is replaced atomically. A ``.cbr`` becomes a sibling ``.cbz``.
    ``Number`` is written only when ``write_number`` is true. ``Volume`` is
    written only when the patch includes it.

    Args:
        path: Archive to update.
        patch: Owned element names mapped to text, or ``None`` / ``""`` to
            remove that element. Absent names are left as they are.
        write_number: When false, a ``Number`` entry in ``patch`` is ignored.
        keep_cbr_original: When false, delete a ``.cbr`` after its ``.cbz``
            reads back. Ignored for a ``.cbz``.

    Returns:
        The archive that now holds the metadata. A CBR save returns the
        ``.cbz`` path.

    Raises:
        ArchiveError: The patch is invalid, the archive cannot be written, or
            the ``.cbz`` is in place but the ``.cbr`` could not be removed.
        ConvertTargetExistsError: The sibling ``.cbz`` of a ``.cbr`` exists.
    """
    archive = Path(path)
    kind = _kind(archive)
    if kind == "cbr":
        return _save_cbr(
            archive,
            patch,
            write_number=write_number,
            keep_cbr_original=keep_cbr_original,
        )
    _save_cbz(archive, patch, write_number=write_number)
    return archive


def save_many(
    paths: list[os.PathLike[str] | str],
    patch: Mapping[str, str | None],
    *,
    keep_cbr_original: bool,
) -> list[FileResult]:
    """Write shared series fields to each archive.

    Any key outside the shared set raises ``BatchFieldError`` before a file
    is written. One failure leaves that file unchanged and the loop continues.

    Args:
        paths: Archives, in the order the results should follow.
        patch: Shared fields only.
        keep_cbr_original: Passed through to each CBR save.

    Returns:
        One result per path. A success carries the output ``.cbz`` path.

    Raises:
        BatchFieldError: ``patch`` contains a field this function does not write.
    """
    extra = sorted(set(patch) - BATCH_FIELDS)
    if extra:
        names = ", ".join(extra)
        raise BatchFieldError(f"batch save cannot write {names}")
    results: list[FileResult] = []
    for raw in paths:
        archive = Path(raw)
        try:
            output = save_comic_info(
                archive,
                patch,
                write_number=False,
                keep_cbr_original=keep_cbr_original,
            )
        except Exception as exc:
            results.append(failure(archive, exc))
        else:
            results.append(FileResult(path=archive, output_path=output))
    return results


def convert_cbr(
    path: os.PathLike[str] | str,
    *,
    keep_cbr_original: bool,
) -> Path:
    """Convert a ``.cbr`` to a sibling ``.cbz`` without changing ComicInfo.

    Args:
        path: The ``.cbr`` to convert.
        keep_cbr_original: When false, delete the ``.cbr`` after the ``.cbz``
            reads back.

    Returns:
        The new ``.cbz`` path.

    Raises:
        UnreadableArchiveError: ``path`` is not a ``.cbr`` or cannot be extracted.
        ConvertTargetExistsError: The sibling ``.cbz`` already exists.
        ArchiveError: The ``.cbz`` is complete and the ``.cbr`` is still present.
        MissingUnarError: ``unar`` or ``lsar`` is not on PATH.
    """
    archive = Path(path)
    if _kind(archive) != "cbr":
        raise UnreadableArchiveError(f"{archive.name} is not a .cbr file")
    return _save_cbr(
        archive,
        {},
        write_number=False,
        keep_cbr_original=keep_cbr_original,
    )


def _save_cbz(
    path: Path,
    patch: Mapping[str, str | None],
    *,
    write_number: bool,
) -> None:
    if not path.is_file():
        raise UnreadableArchiveError(f"{path} is not a file")
    with _open_cbz(path) as zip_file:
        had_comicinfo = any(
            info.filename == "ComicInfo.xml" for info in zip_file.infolist()
        )
        if had_comicinfo:
            data = zip_file.read("ComicInfo.xml")
            model = ComicInfo.from_bytes(data)
        else:
            model = ComicInfo.empty()
    applied = model.apply_patch(patch, write_number=write_number)
    comic_bytes = model.to_bytes()

    def writer(temp: Path) -> None:
        write_updated_zip(
            path,
            temp,
            comic_bytes,
            had_comicinfo=had_comicinfo,
        )

    _commit_cbz(temp_dir=path.parent, dest=path, writer=writer, applied=applied)


def _save_cbr(
    path: Path,
    patch: Mapping[str, str | None],
    *,
    write_number: bool,
    keep_cbr_original: bool,
) -> Path:
    if not path.is_file():
        raise UnreadableArchiveError(f"{path} is not a file")
    target = path.with_suffix(".cbz")
    if target.exists():
        raise ConvertTargetExistsError(f"{target.name} already exists")
    extracted = extract_cbr(path)
    try:
        comic_path = extracted / "ComicInfo.xml"
        had_comicinfo = comic_path.is_file()
        if had_comicinfo:
            model = ComicInfo.from_bytes(comic_path.read_bytes())
        else:
            model = ComicInfo.empty()
        applied = model.apply_patch(patch, write_number=write_number)
        write_comic = had_comicinfo or bool(applied)
        comic_bytes = model.to_bytes() if write_comic else None

        def writer(temp: Path) -> None:
            _write_tree_zip(extracted, temp, comic_bytes, had_comicinfo=had_comicinfo)

        _commit_cbz(
            temp_dir=path.parent,
            dest=target,
            writer=writer,
            applied=applied,
        )
    finally:
        shutil.rmtree(extracted, ignore_errors=True)
    if not keep_cbr_original:
        try:
            path.unlink()
        except OSError as exc:
            raise ArchiveError(
                f"{target.name} is complete and {path.name} is still present"
            ) from exc
    return target


def _commit_cbz(
    *,
    temp_dir: Path,
    dest: Path,
    writer: Callable[[Path], None],
    applied: Mapping[str, str | None],
) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=".manga-tagger-",
        suffix=".partial",
        dir=temp_dir,
    )
    os.close(descriptor)
    temp = Path(name)
    try:
        writer(temp)
        saved = read_zip_comic_info(temp)
        _verify_patch(saved, applied)
        os.replace(temp, dest)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _verify_patch(saved: ComicInfo, applied: Mapping[str, str | None]) -> None:
    for name, value in applied.items():
        actual = saved.field_text(name)
        if value is None:
            if actual is not None:
                raise ArchiveError("ComicInfo.xml read-back did not match the patch")
        elif actual != value:
            raise ArchiveError("ComicInfo.xml read-back did not match the patch")


def _write_tree_zip(
    tree: Path,
    dest: Path,
    comic_bytes: bytes | None,
    *,
    had_comicinfo: bool,
) -> None:
    members = _tree_members(tree)
    members.pop("ComicInfo.xml", None)
    ordered = sorted(members)
    with zipfile.ZipFile(dest, "w") as archive:
        if comic_bytes is not None and not had_comicinfo:
            add_stored(archive, "ComicInfo.xml", comic_bytes)
        placed = had_comicinfo is False or comic_bytes is None
        for name in ordered:
            if (
                comic_bytes is not None
                and had_comicinfo
                and not placed
                and name > "ComicInfo.xml"
            ):
                add_stored(archive, "ComicInfo.xml", comic_bytes)
                placed = True
            source = members[name]
            if source is None:
                add_stored(archive, name, b"", external_attr=_DIR_ATTR)
            else:
                add_stored(
                    archive,
                    name,
                    source.read_bytes(),
                    external_attr=_FILE_ATTR,
                )
        if comic_bytes is not None and had_comicinfo and not placed:
            add_stored(archive, "ComicInfo.xml", comic_bytes)


def _tree_members(tree: Path) -> dict[str, Path | None]:
    members: dict[str, Path | None] = {}
    for dirpath, _dirnames, filenames in os.walk(tree):
        relative = Path(dirpath).relative_to(tree)
        if relative != Path("."):
            members[relative.as_posix() + "/"] = None
        for filename in filenames:
            arcname = (relative / filename).as_posix()
            members[arcname] = Path(dirpath) / filename
    return members
