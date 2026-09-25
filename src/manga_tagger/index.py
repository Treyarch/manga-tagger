"""SQLite library index, recursive scan, and cover thumbnails."""

import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from manga_tagger.archives.comicinfo import OWNED_ELEMENTS, resolve_cover_index
from manga_tagger.archives.errors import (
    MissingUnarError,
    NoPageImagesError,
    UnreadableArchiveError,
)
from manga_tagger.archives.poster import encode_jpeg
from manga_tagger.archives.read import list_pages, read_comic_info, read_page

_THUMB_WIDTH = 256
_THUMB_QUALITY = 80
_ARCHIVE_SUFFIXES = {".cbz", ".cbr"}

_TEXT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Title", "title"),
    ("Series", "series"),
    ("Number", "number"),
    ("Volume", "volume"),
    ("Count", "count"),
    ("Publisher", "publisher"),
    ("PageCount", "page_count"),
    ("LanguageISO", "language_iso"),
    ("AgeRating", "age_rating"),
    ("Manga", "manga"),
    ("Genre", "genre"),
    ("Summary", "summary"),
    ("Web", "web"),
    ("CommunityRating", "community_rating"),
    ("Notes", "notes"),
    ("Year", "year"),
    ("Month", "month"),
    ("Day", "day"),
    ("Writer", "writer"),
    ("Penciller", "penciller"),
    ("Inker", "inker"),
    ("CoverArtist", "cover_artist"),
)

_SCHEMA = """
CREATE TABLE volumes (
  path TEXT PRIMARY KEY,
  root TEXT NOT NULL,
  name TEXT NOT NULL,
  extension TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  status TEXT NOT NULL,
  error_type TEXT NOT NULL,
  error_message TEXT NOT NULL,
  cover_index INTEGER,
  archive_page_count INTEGER,
  title TEXT NOT NULL,
  series TEXT NOT NULL,
  number TEXT NOT NULL,
  volume TEXT NOT NULL,
  count TEXT NOT NULL,
  publisher TEXT NOT NULL,
  page_count TEXT NOT NULL,
  language_iso TEXT NOT NULL,
  age_rating TEXT NOT NULL,
  manga TEXT NOT NULL,
  genre TEXT NOT NULL,
  summary TEXT NOT NULL,
  web TEXT NOT NULL,
  community_rating TEXT NOT NULL,
  notes TEXT NOT NULL,
  year TEXT NOT NULL,
  month TEXT NOT NULL,
  day TEXT NOT NULL,
  writer TEXT NOT NULL,
  penciller TEXT NOT NULL,
  inker TEXT NOT NULL,
  cover_artist TEXT NOT NULL
);
"""


class LibraryIndexError(Exception):
    """The index database cannot be used, or a path that must be absolute is not."""


class IndexVersionError(LibraryIndexError):
    """``user_version`` is neither 0, 1, nor 2. The schema is left unchanged."""


@dataclass(frozen=True)
class Volume:
    """One indexed archive."""

    path: str
    root: str
    name: str
    extension: str
    size: int
    mtime_ns: int
    status: str
    error_type: str
    error_message: str
    cover_index: int | None
    archive_page_count: int | None
    title: str
    series: str
    number: str
    volume: str
    count: str
    publisher: str
    page_count: str
    language_iso: str
    age_rating: str
    manga: str
    genre: str
    summary: str
    web: str
    community_rating: str
    notes: str
    year: str
    month: str
    day: str
    writer: str
    penciller: str
    inker: str
    cover_artist: str


@dataclass(frozen=True)
class ScanResult:
    """What one scan inserted, skipped, and deleted."""

    written: tuple[str, ...]
    unchanged: tuple[str, ...]
    failed: tuple[str, ...]
    deleted: tuple[str, ...]
    skipped_or_incomplete: tuple[str, ...]
    cancelled: bool


def list_volumes(
    db_path: os.PathLike[str] | str,
    *,
    under: os.PathLike[str] | str | None = None,
) -> list[Volume]:
    """Return indexed volumes without scanning the library.

    Args:
        db_path: SQLite database. A missing file is created empty.
        under: Absolute path. ``None`` returns every row. Otherwise a row is
            kept when its path is that path or a file inside it.

    Returns:
        Rows ordered by path, including failed volumes.

    Raises:
        LibraryIndexError: ``under`` is relative, or the database cannot be opened.
        IndexVersionError: The schema version is not 1.
    """
    if under is not None and not Path(under).is_absolute():
        raise LibraryIndexError(f"{under} is not absolute")
    prefix = Path(under).resolve() if under is not None else None
    with _session(db_path) as connection:
        rows = connection.execute("SELECT * FROM volumes ORDER BY path").fetchall()
    volumes = [_volume(row) for row in rows]
    if prefix is None:
        return volumes
    return [volume for volume in volumes if _inside(Path(volume.path), prefix)]


def scan(
    db_path: os.PathLike[str] | str,
    cache_dir: os.PathLike[str] | str,
    roots: Sequence[os.PathLike[str] | str],
    *,
    cancel: Callable[[], bool] | None = None,
) -> ScanResult:
    """Index ``.cbz`` and ``.cbr`` files under ``roots``.

    Each file is committed on its own. Cancel and an incomplete root skip
    pruning. Page-image bodies are not read.

    Args:
        db_path: SQLite database.
        cache_dir: Thumbnail directory. Files for pruned paths are removed.
        roots: Absolute library roots, in priority order.
        cancel: Called before each file and before pruning. True stops the scan.

    Returns:
        Written, unchanged, failed, and deleted paths, plus skipped or
        incomplete roots.

    Raises:
        LibraryIndexError: A root is relative, or the database cannot be opened.
        IndexVersionError: The schema version is not 1.
    """
    resolved_roots = _absolute_paths(roots, "root")
    cache = Path(cache_dir)
    written: list[str] = []
    unchanged: list[str] = []
    failed: list[str] = []
    seen: set[str] = set()
    statuses: list[tuple[Path, str]] = []
    cancelled = False

    with _session(db_path) as connection:
        for root in resolved_roots:
            if _cancelled(cancel):
                cancelled = True
                break
            if not root.is_dir():
                statuses.append((root, "skipped"))
                continue
            status = _walk_root(
                connection,
                root,
                seen,
                written,
                unchanged,
                failed,
                cancel,
            )
            if status == "cancelled":
                cancelled = True
                break
            statuses.append((root, status))
        if not cancelled and _cancelled(cancel):
            cancelled = True
        deleted: list[str] = []
        if not cancelled and all(status != "incomplete" for _root, status in statuses):
            deleted = _prune(connection, cache, resolved_roots, statuses, seen)
    skipped = tuple(
        str(root) for root, status in statuses if status in {"skipped", "incomplete"}
    )
    return ScanResult(
        written=tuple(written),
        unchanged=tuple(unchanged),
        failed=tuple(failed),
        deleted=tuple(deleted),
        skipped_or_incomplete=skipped,
        cancelled=cancelled,
    )


def refresh_volume(
    db_path: os.PathLike[str] | str,
    path: os.PathLike[str] | str,
    roots: Sequence[os.PathLike[str] | str],
) -> Volume | None:
    """Re-read one archive and return its row.

    A missing file, a non-archive, or a path outside every root loses its row.
    Thumbnails are left in place. Other rows are not walked or pruned.

    Args:
        db_path: SQLite database.
        path: Absolute archive path.
        roots: Current library roots, in priority order.

    Returns:
        The updated row, or ``None`` when the path is no longer a volume.

    Raises:
        LibraryIndexError: ``path`` or a root is relative.
        IndexVersionError: The schema version is not 1.
    """
    archive = _one_absolute(path)
    resolved_roots = _absolute_paths(roots, "root")
    owner = next((root for root in resolved_roots if _inside(archive, root)), None)
    with _session(db_path) as connection:
        if owner is None or not _is_archive(archive) or not archive.is_file():
            with connection:
                connection.execute(
                    "DELETE FROM volumes WHERE path = ?", (str(archive),)
                )
            return None
        _index_file(connection, archive, owner, [], [], [])
        row = connection.execute(
            "SELECT * FROM volumes WHERE path = ?", (str(archive),)
        ).fetchone()
    if row is None:
        return None
    return _volume(row)


def forget_volume(
    db_path: os.PathLike[str] | str,
    cache_dir: os.PathLike[str] | str,
    path: os.PathLike[str] | str,
) -> None:
    """Delete one volume row and its thumbnail files.

    Args:
        db_path: SQLite database.
        cache_dir: Thumbnail directory.
        path: Absolute archive path. A path that is not indexed is a success.

    Raises:
        LibraryIndexError: ``path`` is relative.
        IndexVersionError: The schema version is not 1.
    """
    archive = _one_absolute(path)
    with _session(db_path) as connection:
        with connection:
            connection.execute("DELETE FROM volumes WHERE path = ?", (str(archive),))
    _delete_thumbnails(Path(cache_dir), archive)


def thumbnail_for(
    db_path: os.PathLike[str] | str,
    cache_dir: os.PathLike[str] | str,
    path: os.PathLike[str] | str,
) -> Path | None:
    """Return a cached cover JPEG, building it from the cover page when needed.

    Args:
        db_path: SQLite database.
        cache_dir: Thumbnail directory. Created when a thumbnail is built.
        path: Absolute archive path.

    Returns:
        The JPEG path for an ``ok`` row, or ``None`` when the row is missing
        or failed.

    Raises:
        LibraryIndexError: ``path`` is relative, or the JPEG cannot be encoded.
        IndexVersionError: The schema version is not 1.
    """
    archive = _one_absolute(path)
    with _session(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM volumes WHERE path = ?", (str(archive),)
        ).fetchone()
    if row is None or row["status"] != "ok":
        return None
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    digest = _digest(archive)
    filename = f"{digest}-{row['mtime_ns']}-{row['size']}.jpg"
    dest = cache / filename
    if dest.is_file():
        _delete_thumbnails(cache, archive, keep=filename)
        return dest
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".manga-tagger-", suffix=".partial", dir=cache
    )
    os.close(descriptor)
    temp = Path(temp_name)
    try:
        cover = row["cover_index"]
        payload = read_page(archive, 0 if cover is None else int(cover))
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    try:
        jpeg = encode_jpeg(payload, width=_THUMB_WIDTH, quality=_THUMB_QUALITY)
        temp.write_bytes(jpeg)
        os.replace(temp, dest)
    except Exception as exc:
        temp.unlink(missing_ok=True)
        raise LibraryIndexError(
            f"thumbnail for {archive.name} could not be encoded"
        ) from exc
    _delete_thumbnails(cache, archive, keep=filename)
    return dest


def _walk_root(
    connection: sqlite3.Connection,
    root: Path,
    seen: set[str],
    written: list[str],
    unchanged: list[str],
    failed: list[str],
    cancel: Callable[[], bool] | None,
) -> str:
    visited: set[Path] = set()

    def walk(directory: Path) -> str:
        try:
            resolved = directory.resolve()
        except OSError:
            return "incomplete"
        if resolved in visited:
            return "full"
        if not _inside(resolved, root):
            return "full"
        visited.add(resolved)
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return "incomplete"
        entries.sort(key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            if entry.is_symlink():
                status = _follow_link(
                    connection,
                    path,
                    root,
                    seen,
                    written,
                    unchanged,
                    failed,
                    cancel,
                    walk,
                )
                if status != "full":
                    return status
                continue
            if entry.is_dir(follow_symlinks=False):
                status = walk(path)
                if status != "full":
                    return status
                continue
            if entry.is_file(follow_symlinks=False) and _is_archive_name(entry.name):
                status = _index_file(
                    connection,
                    path,
                    root,
                    written,
                    unchanged,
                    failed,
                    seen,
                    cancel,
                )
                if status != "full":
                    return status
        return "full"

    return walk(root)


def _follow_link(
    connection: sqlite3.Connection,
    path: Path,
    root: Path,
    seen: set[str],
    written: list[str],
    unchanged: list[str],
    failed: list[str],
    cancel: Callable[[], bool] | None,
    walk: Callable[[Path], str],
) -> str:
    try:
        target = path.resolve()
    except OSError:
        return "full"
    if not _inside(target, root):
        return "full"
    if target.is_dir():
        return walk(path)
    if _is_archive_name(path.name) and target.is_file():
        return _index_file(
            connection,
            target,
            root,
            written,
            unchanged,
            failed,
            seen,
            cancel,
        )
    return "full"


def _index_file(
    connection: sqlite3.Connection,
    path: Path,
    root: Path,
    written: list[str],
    unchanged: list[str],
    failed: list[str],
    seen: set[str] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> str:
    if _cancelled(cancel):
        return "cancelled"
    try:
        archive = path.resolve()
    except OSError:
        return "full"
    key = str(archive)
    if seen is not None and key in seen:
        return "full"
    if not _inside(archive, root):
        return "full"
    try:
        stat = archive.stat()
    except OSError:
        return "full"
    if seen is not None:
        seen.add(key)
    existing = connection.execute(
        "SELECT status, size, mtime_ns, root FROM volumes WHERE path = ?",
        (key,),
    ).fetchone()
    root_key = str(root)
    if (
        existing is not None
        and existing["status"] == "ok"
        and existing["size"] == stat.st_size
        and existing["mtime_ns"] == stat.st_mtime_ns
    ):
        if existing["root"] != root_key:
            with connection:
                connection.execute(
                    "UPDATE volumes SET root = ? WHERE path = ?",
                    (root_key, key),
                )
        unchanged.append(key)
        return "full"
    try:
        pages = list_pages(archive)
        info = read_comic_info(archive)
    except (UnreadableArchiveError, NoPageImagesError, MissingUnarError) as exc:
        _upsert_failed(connection, archive, root, stat, exc)
        failed.append(key)
        return "full"
    texts = {
        column: _text(info.field_text(element)) for element, column in _TEXT_COLUMNS
    }
    _upsert_ok(
        connection,
        archive,
        root,
        stat,
        cover_index=resolve_cover_index(info.pages(), len(pages)),
        page_count=len(pages),
        texts=texts,
    )
    written.append(key)
    return "full"


def _prune(
    connection: sqlite3.Connection,
    cache: Path,
    roots: list[Path],
    statuses: list[tuple[Path, str]],
    seen: set[str],
) -> list[str]:
    requested = {str(root) for root in roots}
    fully_walked = {str(root) for root, status in statuses if status == "full"}
    rows = connection.execute("SELECT path, root FROM volumes").fetchall()
    deleted: list[str] = []
    for row in rows:
        path = row["path"]
        root = row["root"]
        drop = root not in requested or (root in fully_walked and path not in seen)
        if not drop:
            continue
        with connection:
            connection.execute("DELETE FROM volumes WHERE path = ?", (path,))
        _delete_thumbnails(cache, Path(path))
        deleted.append(path)
    deleted.sort()
    return deleted


def _upsert_ok(
    connection: sqlite3.Connection,
    archive: Path,
    root: Path,
    stat: os.stat_result,
    *,
    cover_index: int,
    page_count: int,
    texts: dict[str, str],
) -> None:
    columns = [
        "path",
        "root",
        "name",
        "extension",
        "size",
        "mtime_ns",
        "status",
        "error_type",
        "error_message",
        "cover_index",
        "archive_page_count",
        *[column for _element, column in _TEXT_COLUMNS],
    ]
    values: list[object] = [
        str(archive),
        str(root),
        archive.name,
        archive.suffix.lower().lstrip("."),
        stat.st_size,
        stat.st_mtime_ns,
        "ok",
        "",
        "",
        cover_index,
        page_count,
        *[texts[column] for _element, column in _TEXT_COLUMNS],
    ]
    _replace(connection, columns, values)


def _upsert_failed(
    connection: sqlite3.Connection,
    archive: Path,
    root: Path,
    stat: os.stat_result,
    exc: Exception,
) -> None:
    columns = [
        "path",
        "root",
        "name",
        "extension",
        "size",
        "mtime_ns",
        "status",
        "error_type",
        "error_message",
        "cover_index",
        "archive_page_count",
        *[column for _element, column in _TEXT_COLUMNS],
    ]
    values: list[object] = [
        str(archive),
        str(root),
        archive.name,
        archive.suffix.lower().lstrip("."),
        stat.st_size,
        stat.st_mtime_ns,
        "failed",
        type(exc).__name__,
        str(exc),
        None,
        None,
        *["" for _element, _column in _TEXT_COLUMNS],
    ]
    _replace(connection, columns, values)


def _replace(
    connection: sqlite3.Connection,
    columns: list[str],
    values: list[object],
) -> None:
    placeholders = ", ".join("?" for _ in columns)
    names = ", ".join(columns)
    with connection:
        connection.execute(
            f"INSERT OR REPLACE INTO volumes ({names}) VALUES ({placeholders})",
            values,
        )


@contextmanager
def _session(db_path: os.PathLike[str] | str) -> Iterator[sqlite3.Connection]:
    """Open one connection and close it when the block ends."""
    connection = _connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _connect(db_path: os.PathLike[str] | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            readonly = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise LibraryIndexError(f"{path} could not be opened") from exc
        try:
            version = int(readonly.execute("PRAGMA user_version").fetchone()[0])
        finally:
            readonly.close()
        if version not in {0, 1, 2}:
            raise IndexVersionError(f"{path} has schema version {version}")
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error as exc:
        raise LibraryIndexError(f"{path} could not be opened") from exc
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version == 0:
        connection.executescript(_SCHEMA)
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    elif version == 1:
        connection.execute(
            "ALTER TABLE volumes ADD COLUMN count TEXT NOT NULL DEFAULT ''"
        )
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    elif version != 2:
        connection.close()
        raise IndexVersionError(f"{path} has schema version {version}")
    return connection


def _volume(row: sqlite3.Row) -> Volume:
    values = {key: row[key] for key in row.keys()}
    return Volume(**values)


def _text(value: str | None) -> str:
    if value is None:
        return ""
    return value


def _absolute_paths(
    paths: Sequence[os.PathLike[str] | str],
    label: str,
) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            raise LibraryIndexError(f"{label} {path} is not absolute")
        resolved.append(path.resolve())
    return resolved


def _one_absolute(path: os.PathLike[str] | str) -> Path:
    archive = Path(path)
    if not archive.is_absolute():
        raise LibraryIndexError(f"{archive} is not absolute")
    return archive.resolve()


def _inside(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _is_archive(path: Path) -> bool:
    return path.is_file() and _is_archive_name(path.name)


def _is_archive_name(name: str) -> bool:
    return Path(name).suffix.lower() in _ARCHIVE_SUFFIXES


def _cancelled(cancel: Callable[[], bool] | None) -> bool:
    return cancel is not None and cancel()


def _digest(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def _delete_thumbnails(cache: Path, archive: Path, *, keep: str | None = None) -> None:
    if not cache.is_dir():
        return
    prefix = _digest(archive) + "-"
    for entry in cache.iterdir():
        if entry.name.startswith(prefix) and entry.name != keep:
            entry.unlink()


if tuple(element for element, _column in _TEXT_COLUMNS) != OWNED_ELEMENTS:
    raise RuntimeError("index columns do not match ComicInfo fields")
