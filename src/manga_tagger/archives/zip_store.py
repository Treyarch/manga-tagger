"""Write ZIP members without recompressing copied pages."""

import struct
import zipfile
import zlib
from pathlib import Path

from manga_tagger.archives.errors import UnreadableArchiveError

_UTF8_FLAG = 1 << 11
_DATA_DESCRIPTOR_FLAG = 1 << 3
_LOCAL_HEADER_SIZE = 30
_LOCAL_SIGNATURE = b"PK\x03\x04"


class _Utf8ZipInfo(zipfile.ZipInfo):
    """ZipInfo that always stores the member name as UTF-8."""

    def _encodeFilenameFlags(self) -> tuple[bytes, int]:
        return self.filename.encode("utf-8"), self.flag_bits | _UTF8_FLAG


def read_compressed_payload(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Return one member's compressed bytes without decoding them.

    Args:
        archive: An open zip whose central directory is already loaded.
        info: The member to copy.

    Returns:
        The compressed payload. Its length is ``info.compress_size``.

    Raises:
        UnreadableArchiveError: The local header or payload is truncated.
    """
    fileobj = archive.fp
    if fileobj is None:
        raise UnreadableArchiveError("archive is closed")
    with archive._lock:
        fileobj.seek(info.header_offset)
        header = fileobj.read(_LOCAL_HEADER_SIZE)
        if len(header) != _LOCAL_HEADER_SIZE or not header.startswith(_LOCAL_SIGNATURE):
            raise UnreadableArchiveError(
                f"{info.filename} has a truncated local header"
            )
        name_len, extra_len = struct.unpack_from("<HH", header, 26)
        fileobj.seek(name_len + extra_len, 1)
        payload = fileobj.read(info.compress_size)
    if len(payload) != info.compress_size:
        raise UnreadableArchiveError(f"{info.filename} is truncated")
    return payload


def append_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, payload: bytes
) -> None:
    """Append a member using ``payload`` as the already-compressed body."""
    if len(payload) != info.compress_size:
        raise UnreadableArchiveError(f"{info.filename} payload size does not match")
    archive._writecheck(info)
    archive._didModify = True
    with archive._lock:
        if archive._seekable:
            archive.fp.seek(archive.start_dir)
        info.header_offset = archive.fp.tell()
        archive.filelist.append(info)
        archive.NameToInfo[info.filename] = info
        archive.fp.write(info.FileHeader())
        archive.fp.write(payload)
        archive.start_dir = archive.fp.tell()


def add_stored(
    archive: zipfile.ZipFile,
    name: str,
    data: bytes,
    *,
    date_time: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0),
    external_attr: int = 0,
) -> None:
    """Add an uncompressed member with the UTF-8 name flag set."""
    info = _Utf8ZipInfo(filename=name, date_time=date_time)
    info.compress_type = zipfile.ZIP_STORED
    info.CRC = zlib.crc32(data) & 0xFFFFFFFF
    info.compress_size = len(data)
    info.file_size = len(data)
    info.flag_bits = _UTF8_FLAG
    info.external_attr = external_attr
    append_member(archive, info, data)


def copy_member(
    source: zipfile.ZipFile, dest: zipfile.ZipFile, info: zipfile.ZipInfo
) -> None:
    """Copy one member unchanged, forcing the UTF-8 name flag."""
    payload = read_compressed_payload(source, info)
    copied = _Utf8ZipInfo(filename=info.filename, date_time=info.date_time)
    copied.compress_type = info.compress_type
    copied.CRC = info.CRC
    copied.compress_size = info.compress_size
    copied.file_size = info.file_size
    copied.flag_bits = (info.flag_bits | _UTF8_FLAG) & ~_DATA_DESCRIPTOR_FLAG
    copied.external_attr = info.external_attr
    copied.internal_attr = info.internal_attr
    copied.create_system = info.create_system
    copied.create_version = info.create_version
    copied.extract_version = info.extract_version
    copied.comment = info.comment
    copied.extra = b""
    append_member(dest, copied, payload)


def write_updated_zip(
    source: Path,
    dest: Path,
    comicinfo: bytes | None,
    *,
    had_comicinfo: bool,
) -> None:
    """Write ``dest`` by copying ``source`` and replacing root ComicInfo.

    Args:
        source: Existing CBZ.
        dest: Temporary zip path. Must not be an open archive name.
        comicinfo: New ``ComicInfo.xml`` bytes, or ``None`` to omit the member.
        had_comicinfo: When true, the new member keeps the original position.
            When false and ``comicinfo`` is set, the new member is written first.
    """
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(dest, "w") as out:
        infos = list(src.infolist())
        if not had_comicinfo:
            if comicinfo is not None:
                add_stored(out, "ComicInfo.xml", comicinfo)
            for info in infos:
                copy_member(src, out, info)
            return
        placed = False
        for info in infos:
            if info.filename == "ComicInfo.xml":
                if not placed and comicinfo is not None:
                    date_time = info.date_time
                    add_stored(
                        out,
                        "ComicInfo.xml",
                        comicinfo,
                        date_time=date_time,
                        external_attr=info.external_attr,
                    )
                    placed = True
                continue
            copy_member(src, out, info)
        if comicinfo is not None and not placed:
            add_stored(out, "ComicInfo.xml", comicinfo)
