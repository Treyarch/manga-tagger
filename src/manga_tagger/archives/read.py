"""Partial reads of CBZ and CBR archives."""

import os
import zipfile
from pathlib import Path

from manga_tagger.archives.cbr import list_cbr_entries, read_cbr_member
from manga_tagger.archives.comicinfo import ComicInfo, resolve_cover_index
from manga_tagger.archives.errors import NoPageImagesError, UnreadableArchiveError

_PAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def list_pages(path: os.PathLike[str] | str) -> list[str]:
    """Return page-image member names in reading order.

    Listing uses the zip central directory or ``lsar -json``. It does not
    read member bodies and does not extract the archive.

    Args:
        path: Path of a ``.cbz`` or ``.cbr``.

    Returns:
        Member names sorted by Unicode code point after backslashes are
        replaced with ``/``.

    Raises:
        UnreadableArchiveError: The file is missing or not an archive.
        NoPageImagesError: The archive contains no page images.
        MissingUnarError: A ``.cbr`` needs ``unar`` or ``lsar`` and one is absent.
    """
    archive = Path(path)
    names = _member_names(archive)
    pages = [name for name in names if _is_page(name)]
    pages.sort(key=lambda name: name.replace("\\", "/"))
    if not pages:
        raise NoPageImagesError(f"{archive.name} contains no page images")
    return pages


def read_zip_comic_info(path: os.PathLike[str] | str) -> ComicInfo:
    """Read ComicInfo from a zip file, ignoring the filename extension.

    Save writes the new archive to a temporary name that is not ``.cbz`` and
    reads it back before replacing the original.

    Args:
        path: Path of a zip archive.

    Returns:
        The parsed ComicInfo, or an empty model when the member is absent.

    Raises:
        UnreadableArchiveError: The zip or the XML cannot be read.
    """
    archive = Path(path)
    with _open_cbz(archive) as zip_file:
        data = _read_root_comicinfo(zip_file)
    if data is None:
        return ComicInfo.empty()
    return ComicInfo.from_bytes(data)


def read_comic_info(path: os.PathLike[str] | str) -> ComicInfo:
    """Read root ``ComicInfo.xml``, or an empty model when it is absent.

    Args:
        path: Path of a ``.cbz`` or ``.cbr``.

    Returns:
        The parsed ComicInfo. A missing member does not read any page image.

    Raises:
        UnreadableArchiveError: The archive or the XML cannot be read.
        MissingUnarError: A ``.cbr`` needs ``unar`` or ``lsar`` and one is absent.
    """
    archive = Path(path)
    if _kind(archive) == "cbz":
        return read_zip_comic_info(archive)
    return _read_cbr_comicinfo(archive)


def read_page(path: os.PathLike[str] | str, index: int) -> bytes:
    """Return one page's uncompressed bytes.

    Args:
        path: Path of a ``.cbz`` or ``.cbr``.
        index: Reading-order index, starting at 0.

    Returns:
        The page image bytes.

    Raises:
        UnreadableArchiveError: The archive cannot be read, or ``index`` is
            outside the page list.
        NoPageImagesError: The archive contains no page images.
        MissingUnarError: A ``.cbr`` needs ``unar`` or ``lsar`` and one is absent.
    """
    archive = Path(path)
    pages = list_pages(archive)
    if index < 0 or index >= len(pages):
        raise UnreadableArchiveError(f"page index {index} is outside the page list")
    member = pages[index]
    if _kind(archive) == "cbz":
        with _open_cbz(archive) as zip_file:
            try:
                return zip_file.read(member)
            except KeyError as exc:
                raise UnreadableArchiveError(
                    f"{archive.name} is missing {member}"
                ) from exc
    return read_cbr_member(archive, member)


def cover_index(path: os.PathLike[str] | str) -> int:
    """Return the cover's reading-order index without reading image bytes.

    Args:
        path: Path of a ``.cbz`` or ``.cbr``.

    Returns:
        The ``FrontCover`` page index, or ``0`` when Pages does not name one.

    Raises:
        UnreadableArchiveError: The archive cannot be read.
        NoPageImagesError: The archive contains no page images.
        MissingUnarError: A ``.cbr`` needs ``unar`` or ``lsar`` and one is absent.
    """
    archive = Path(path)
    pages = list_pages(archive)
    info = read_comic_info(archive)
    return resolve_cover_index(info.pages(), len(pages))


def _member_names(path: Path) -> list[str]:
    kind = _kind(path)
    if kind == "cbz":
        with _open_cbz(path) as zip_file:
            return [info.filename for info in zip_file.infolist() if not info.is_dir()]
    names: list[str] = []
    for name, is_dir in list_cbr_entries(path):
        if not is_dir:
            names.append(name)
    return names


def _read_root_comicinfo(zip_file: zipfile.ZipFile) -> bytes | None:
    for info in zip_file.infolist():
        if info.filename == "ComicInfo.xml":
            return zip_file.read(info)
    return None


def _read_cbr_comicinfo(path: Path) -> ComicInfo:
    for name, is_dir in list_cbr_entries(path):
        if not is_dir and name == "ComicInfo.xml":
            return ComicInfo.from_bytes(read_cbr_member(path, name))
    return ComicInfo.empty()


def _is_page(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.endswith("/"):
        return False
    suffix = Path(normalized).suffix.lower()
    return suffix in _PAGE_EXTENSIONS


def _kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".cbz":
        return "cbz"
    if suffix == ".cbr":
        return "cbr"
    raise UnreadableArchiveError(f"{path.name} is not a .cbz or .cbr file")


def _open_cbz(path: Path) -> zipfile.ZipFile:
    if not path.is_file():
        raise UnreadableArchiveError(f"{path} is not a file")
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise UnreadableArchiveError(f"{path.name} is not a readable CBZ") from exc
