"""Sibling cover posters."""

import io
import os
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from manga_tagger.archives.read import cover_index, read_page

_POSTER_WIDTH = 600
_POSTER_QUALITY = 85


def write_poster(path: os.PathLike[str] | str) -> Path:
    """Write ``{stem}-poster.jpg`` from the cover page only.

    The JPEG is 600 pixels wide, or the cover's own width when that is
    smaller. An alpha channel is composited onto white. The archive is not
    modified. An existing poster is replaced by a rename in the same directory.

    Args:
        path: Archive whose cover becomes the poster.

    Returns:
        The poster path.

    Raises:
        UnreadableArchiveError: The archive or the cover page cannot be read.
        NoPageImagesError: The archive contains no page images.
        MissingUnarError: A ``.cbr`` needs ``unar`` or ``lsar`` and one is absent.
    """
    archive = Path(path)
    index = cover_index(archive)
    payload = read_page(archive, index)
    jpeg = encode_jpeg(payload, width=_POSTER_WIDTH, quality=_POSTER_QUALITY)
    dest = archive.with_name(f"{archive.stem}-poster.jpg")
    _write_bytes(dest, jpeg)
    return dest


def encode_jpeg(payload: bytes, *, width: int, quality: int) -> bytes:
    """Encode image bytes as a JPEG no wider than ``width``.

    Smaller images are not enlarged. An alpha channel is composited onto white.

    Args:
        payload: Encoded image bytes.
        width: Maximum width in pixels.
        quality: JPEG quality.

    Returns:
        The JPEG bytes.

    Raises:
        UnreadableArchiveError: The image cannot be decoded.
    """
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            prepared = _fit_width(_to_rgb(image), width)
            buffer = io.BytesIO()
            prepared.save(buffer, format="JPEG", quality=quality)
            return buffer.getvalue()
    except (OSError, UnidentifiedImageError) as exc:
        raise UnreadableArchiveError("image could not be encoded") from exc


def _to_rgb(image: Image.Image) -> Image.Image:
    if _has_alpha(image):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if image.mode == "RGB":
        return image
    return image.convert("RGB")


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _fit_width(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image
    height = round(image.height * width / image.width)
    if height < 1:
        height = 1
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _write_bytes(dest: Path, payload: bytes) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=".manga-tagger-",
        suffix=".partial",
        dir=dest.parent,
    )
    os.close(descriptor)
    temp = Path(name)
    try:
        temp.write_bytes(payload)
        os.replace(temp, dest)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
