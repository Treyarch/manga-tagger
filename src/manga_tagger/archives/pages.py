"""Replace or insert a cover page image in an archive."""

from __future__ import annotations

import io
import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps, UnidentifiedImageError

from manga_tagger.archives.cbr import extract_cbr
from manga_tagger.archives.comicinfo import ComicInfo, resolve_cover_index
from manga_tagger.archives.errors import (
    ArchiveError,
    ConvertTargetExistsError,
    NoPageImagesError,
    UnreadableArchiveError,
)
from manga_tagger.archives.read import (
    _is_page,
    _kind,
    _open_cbz,
    cover_index,
    list_pages,
)
from manga_tagger.archives.save import _commit_cbz, _write_tree_zip
from manga_tagger.archives.zip_store import add_stored, copy_member


def replace_cover_page(
    path: os.PathLike[str] | str,
    image_bytes: bytes,
    filename: str,
    *,
    keep_cbr_original: bool,
) -> Path:
    """Replace the cover page with ``image_bytes`` as reading-order index 0.

    Args:
        path: Archive to update.
        image_bytes: New cover image body.
        filename: Scraper basename for the new member leaf.
        keep_cbr_original: When false, delete a ``.cbr`` after its ``.cbz``
            reads back.

    Returns:
        The archive that holds the pages. A CBR write returns the ``.cbz``.
    """
    return _write_cover(
        Path(path),
        image_bytes,
        filename,
        replace=True,
        keep_cbr_original=keep_cbr_original,
    )


def insert_cover_page(
    path: os.PathLike[str] | str,
    image_bytes: bytes,
    filename: str,
    *,
    keep_cbr_original: bool,
) -> Path:
    """Insert ``image_bytes`` as reading-order index 0 without removing pages.

    Args:
        path: Archive to update.
        image_bytes: New cover image body.
        filename: Scraper basename for the new member leaf.
        keep_cbr_original: When false, delete a ``.cbr`` after its ``.cbz``
            reads back.

    Returns:
        The archive that holds the pages. A CBR write returns the ``.cbz``.
    """
    return _write_cover(
        Path(path),
        image_bytes,
        filename,
        replace=False,
        keep_cbr_original=keep_cbr_original,
    )


def cover_member_name(
    pages: list[str],
    filename: str,
    *,
    remove: str | None = None,
    anchor: str | None = None,
    members: list[str] | None = None,
) -> str:
    """Keep the provider basename and choose a bounded, collision-free page zero."""
    leaf = _sanitize_leaf(filename)
    remaining = [name.replace("\\", "/") for name in pages if name != remove]
    occupied = {
        name.replace("\\", "/").rstrip("/")
        for name in (members if members is not None else pages)
        if name != remove
    }
    anchor = (anchor or remove or pages[0]).replace("\\", "/")
    parent = PurePosixPath(anchor).parent
    if parent.is_absolute() or ".." in parent.parts:
        raise ArchiveError("cover directory is unsafe")
    directory = "" if str(parent) == "." else f"{parent}/"
    minimum = min(remaining) if remaining else None
    # Each prefix need be no longer than the longest existing name plus one.
    bound = max((len(name) for name in occupied), default=0) + 1
    for folder, prefix in [(directory, "!"), ("", "!"), ("", " ")]:
        for count in range(bound + 1):
            candidate = folder + prefix * count + leaf
            if len(candidate.encode("utf-8")) > 65535:
                break
            if (minimum is None or candidate < minimum) and candidate not in occupied:
                return candidate
    raise ArchiveError("cannot name the cover before the existing pages")


def _write_cover(
    archive: Path,
    image_bytes: bytes,
    filename: str,
    *,
    replace: bool,
    keep_cbr_original: bool,
) -> Path:
    filename = str(PurePosixPath(_sanitize_leaf(filename)).with_suffix(".jpg"))
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise ArchiveError("cover image format is unsupported")
            image.load()
            if image.format != "JPEG":
                rgba = ImageOps.exif_transpose(image).convert("RGBA")
                rgb = Image.new("RGB", rgba.size, "white")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
                buffer = io.BytesIO()
                rgb.save(buffer, format="JPEG", quality=95, subsampling=0)
                image_bytes = buffer.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise ArchiveError("cover image is invalid") from exc
    kind = _kind(archive)
    if kind == "cbr":
        return _write_cover_cbr(
            archive,
            image_bytes,
            filename,
            replace=replace,
            keep_cbr_original=keep_cbr_original,
        )
    _write_cover_cbz(archive, image_bytes, filename, replace=replace)
    return archive


def _write_cover_cbz(
    path: Path,
    image_bytes: bytes,
    filename: str,
    *,
    replace: bool,
) -> None:
    if not path.is_file():
        raise UnreadableArchiveError(f"{path} is not a file")
    pages = list_pages(path)
    removed: str | None = None
    removed_index = 0
    current_cover = cover_index(path)
    if replace:
        removed_index = current_cover
        removed = pages[removed_index]
    with _open_cbz(path) as source:
        members = source.namelist()
    member = cover_member_name(
        pages, filename, remove=removed, anchor=pages[current_cover], members=members
    )
    model, had_comicinfo = _load_model(path)
    new_count = len(pages) if replace else len(pages) + 1
    _apply_cover_comicinfo(
        model,
        replace=replace,
        removed_index=removed_index,
        page_count=new_count,
    )
    comic_bytes = model.to_bytes()

    def writer(temp: Path) -> None:
        _write_cover_zip(
            path,
            temp,
            comic_bytes,
            had_comicinfo=had_comicinfo,
            remove=removed,
            add_name=member,
            add_data=image_bytes,
        )

    _commit_cbz(
        temp_dir=path.parent,
        dest=path,
        writer=writer,
        applied={"PageCount": str(new_count)},
    )


def _write_cover_cbr(
    path: Path,
    image_bytes: bytes,
    filename: str,
    *,
    replace: bool,
    keep_cbr_original: bool,
) -> Path:
    if not path.is_file():
        raise UnreadableArchiveError(f"{path} is not a file")
    target = path.with_suffix(".cbz")
    if target.exists():
        raise ConvertTargetExistsError(f"{target.name} already exists")
    extracted = extract_cbr(path)
    try:
        extracted_members = list(extracted.rglob("*"))
        if any(item.is_symlink() for item in extracted_members):
            raise ArchiveError("cover archive contains unsafe symbolic links")
        members = [item.relative_to(extracted).as_posix() for item in extracted_members]
        pages = sorted(
            name for name in members if (extracted / name).is_file() and _is_page(name)
        )
        if not pages:
            raise NoPageImagesError(f"{path.name} contains no page images")
        comic_path = extracted / "ComicInfo.xml"
        had_comicinfo = comic_path.is_file()
        model = (
            ComicInfo.from_bytes(comic_path.read_bytes())
            if had_comicinfo
            else ComicInfo.empty()
        )
        current_cover = resolve_cover_index(model.pages(), len(pages))
        removed_index = current_cover if replace else 0
        removed = pages[removed_index] if replace else None
        member = cover_member_name(
            pages,
            filename,
            remove=removed,
            anchor=pages[current_cover],
            members=members,
        )
        new_count = len(pages) if replace else len(pages) + 1
        _apply_cover_comicinfo(
            model,
            replace=replace,
            removed_index=removed_index,
            page_count=new_count,
        )
        comic_bytes = model.to_bytes()
        if removed is not None:
            victim = extracted / Path(*removed.replace("\\", "/").split("/"))
            if victim.is_file():
                victim.unlink()
        dest_file = extracted / Path(*member.split("/"))
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(image_bytes)

        def writer(temp: Path) -> None:
            _write_tree_zip(extracted, temp, comic_bytes, had_comicinfo=had_comicinfo)

        _commit_cbz(
            temp_dir=path.parent,
            dest=target,
            writer=writer,
            applied={"PageCount": str(new_count)},
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


def _apply_cover_comicinfo(
    model: ComicInfo,
    *,
    replace: bool,
    removed_index: int,
    page_count: int,
) -> None:
    model.apply_patch({"PageCount": str(page_count)}, write_number=False)
    model.update_cover_pages(removed_index=removed_index if replace else None)


def _load_model(path: Path) -> tuple[ComicInfo, bool]:
    with _open_cbz(path) as zip_file:
        had = any(info.filename == "ComicInfo.xml" for info in zip_file.infolist())
        if had:
            return ComicInfo.from_bytes(zip_file.read("ComicInfo.xml")), True
    return ComicInfo.empty(), False


def _write_cover_zip(
    source: Path,
    dest: Path,
    comicinfo: bytes,
    *,
    had_comicinfo: bool,
    remove: str | None,
    add_name: str,
    add_data: bytes,
) -> None:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(dest, "w") as out:
        out.comment = src.comment
        infos = list(src.infolist())
        if not had_comicinfo:
            add_stored(out, "ComicInfo.xml", comicinfo)
            for info in infos:
                if remove is not None and info.filename == remove:
                    continue
                copy_member(src, out, info)
            add_stored(out, add_name, add_data)
            return
        placed = False
        for info in infos:
            if info.filename == "ComicInfo.xml":
                if not placed:
                    add_stored(
                        out,
                        "ComicInfo.xml",
                        comicinfo,
                        date_time=info.date_time,
                        external_attr=info.external_attr,
                    )
                    placed = True
                continue
            if remove is not None and info.filename == remove:
                continue
            copy_member(src, out, info)
        if not placed:
            add_stored(out, "ComicInfo.xml", comicinfo)
        add_stored(out, add_name, add_data)


def _sanitize_leaf(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1].strip()
    if not name or name in {".", ".."} or ".." in name:
        raise ArchiveError("cover filename is illegal")
    if any(ord(char) < 32 for char in name) or not _is_page(name):
        raise ArchiveError("cover filename must have a supported image extension")
    return name
