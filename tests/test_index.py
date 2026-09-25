"""Hermetic tests for the SQLite library index."""

import os
import sqlite3
import zipfile
from pathlib import Path

import pytest
from lxml import etree
from PIL import Image

from manga_tagger import index as index_mod
from manga_tagger.archives import cbr as cbr_mod
from manga_tagger.index import (
    IndexVersionError,
    LibraryIndexError,
    forget_volume,
    list_volumes,
    refresh_volume,
    scan,
    thumbnail_for,
)

_ORIGINAL_ZIP = zipfile.ZipFile


class RecordingZipFile(_ORIGINAL_ZIP):
    """ZipFile that records constructions and member bodies opened for reading."""

    opens = 0
    reads: list[str] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        RecordingZipFile.opens += 1
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def open(self, name, mode="r", pwd=None, *, force_zip64=False):  # type: ignore[no-untyped-def]
        if mode == "r":
            if isinstance(name, zipfile.ZipInfo):
                RecordingZipFile.reads.append(name.filename)
            else:
                RecordingZipFile.reads.append(str(name))
        return super().open(name, mode, pwd, force_zip64=force_zip64)


def _record(monkeypatch: pytest.MonkeyPatch) -> None:
    RecordingZipFile.opens = 0
    RecordingZipFile.reads = []
    monkeypatch.setattr(zipfile, "ZipFile", RecordingZipFile)


def _cbz(path: Path, *, pages: int = 2, **fields: str) -> None:
    root = etree.Element("ComicInfo")
    for name, value in fields.items():
        etree.SubElement(root, name).text = value
    pages_el = etree.SubElement(root, "Pages")
    etree.SubElement(pages_el, "Page", Image="0", Type="FrontCover")
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ORIGINAL_ZIP(path, "w") as archive:
        archive.writestr("ComicInfo.xml", xml)
        for index in range(pages):
            archive.writestr(f"{index}.jpg", f"page-{index}".encode())


def _png(path: Path, size: tuple[int, int], color: tuple[int, ...]) -> None:
    mode = "RGBA" if len(color) == 4 else "RGB"
    image = Image.new(mode, size, color)
    buffer_path = path
    buffer_path.parent.mkdir(parents=True, exist_ok=True)
    payload = __import__("io").BytesIO()
    image.save(payload, format="PNG")
    root = etree.Element("ComicInfo")
    etree.SubElement(root, "Series").text = "Claymore"
    pages = etree.SubElement(root, "Pages")
    etree.SubElement(pages, "Page", Image="0", Type="FrontCover")
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    with _ORIGINAL_ZIP(path, "w") as archive:
        archive.writestr("ComicInfo.xml", xml)
        archive.writestr("cover.png", payload.getvalue())


def test_list_volumes_creates_an_empty_index_without_scanning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "library"
    library.mkdir()
    _cbz(library / "book.cbz", Series="Claymore")
    database = tmp_path / "data" / "index.db"

    def forbid_scan(path: object) -> None:
        raise AssertionError(f"walked {path}")

    monkeypatch.setattr(index_mod.os, "scandir", forbid_scan)
    _record(monkeypatch)
    assert list_volumes(database) == []
    assert database.is_file()
    assert RecordingZipFile.opens == 0
    assert (library / "book.cbz").is_file()


def test_list_volumes_orders_rows_and_filters_under(tmp_path: Path) -> None:
    books = tmp_path / "books"
    extra = tmp_path / "books-extra"
    _cbz(books / "nested" / "b.cbz", Series="Inside")
    _cbz(books / "a.cbz", Series="Root")
    bad = extra / "bad.cbz"
    bad.parent.mkdir()
    bad.write_bytes(b"not a zip")
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    scan(database, cache, [books, extra])
    rows = list_volumes(database)
    assert [row.status for row in rows] == ["failed", "ok", "ok"]
    assert [row.path for row in rows] == sorted(row.path for row in rows)
    under_books = list_volumes(database, under=books)
    assert {Path(row.path).name for row in under_books} == {"a.cbz", "b.cbz"}
    assert list_volumes(database, under=books / "a.cbz")[0].name == "a.cbz"
    with pytest.raises(LibraryIndexError):
        list_volumes(database, under="books")


def test_scan_indexes_archives_and_ignores_other_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cbr_mod, "find_executable", lambda _name: None)
    root = tmp_path / "root"
    _cbz(root / "nest" / "Book.CBZ", Series="Claymore", Number="1", Title="One")
    (root / "note.txt").write_text("nope")
    (root / "page.pdf").write_bytes(b"%PDF")
    (root / ".manga-tagger-save.partial").write_bytes(b"temp")
    cbr = root / "other.cbr"
    cbr.write_bytes(b"cbr")
    database = tmp_path / "index.db"
    result = scan(database, tmp_path / "cache", [root])
    rows = {row.name: row for row in list_volumes(database)}
    assert set(rows) == {"Book.CBZ", "other.cbr"}
    book = rows["Book.CBZ"]
    assert book.extension == "cbz"
    assert book.status == "ok"
    assert book.series == "Claymore"
    assert book.number == "1"
    assert book.title == "One"
    assert book.volume == ""
    assert book.cover_index == 0
    assert book.archive_page_count == 2
    assert book.error_type == ""
    failed = rows["other.cbr"]
    assert failed.status == "failed"
    assert failed.error_type == "MissingUnarError"
    assert "unar" in failed.error_message
    assert failed.cover_index is None
    assert failed.series == ""
    assert str(cbr.resolve()) in result.failed
    assert not (root / "nest" / "Book-poster.jpg").exists()
    assert not (tmp_path / "cache").exists()


def test_symlinks_and_root_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record(monkeypatch)
    parent = tmp_path / "parent"
    child = parent / "child"
    outside = tmp_path / "outside"
    _cbz(child / "real.cbz", Series="Claymore")
    _cbz(outside / "gone.cbz", Series="Outside")
    (child / "alias.cbz").symlink_to(child / "real.cbz")
    (child / "leak.cbz").symlink_to(outside / "gone.cbz")
    (child / "loop").symlink_to(child, target_is_directory=True)
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    first = scan(database, cache, [child])
    rows = list_volumes(database)
    assert len(rows) == 1
    assert rows[0].path == str((child / "real.cbz").resolve())
    assert rows[0].root == str(child.resolve())
    assert rows[0].series == "Claymore"
    assert str((outside / "gone.cbz").resolve()) not in {row.path for row in rows}
    opens_after_first = RecordingZipFile.opens

    second = scan(database, cache, [parent, child])
    assert second.written == ()
    assert str((child / "real.cbz").resolve()) in second.unchanged
    assert RecordingZipFile.opens == opens_after_first
    assert list_volumes(database)[0].root == str(parent.resolve())
    assert first.cancelled is False


def test_failed_archive_does_not_stop_the_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a-bad.cbz").write_bytes(b"nope")
    _cbz(root / "b-good.cbz", Series="Claymore", Title="Kept", Number="2")
    (root / "c-empty.cbz").parent.mkdir(exist_ok=True)
    with _ORIGINAL_ZIP(root / "c-empty.cbz", "w") as archive:
        archive.writestr("notes.txt", b"no pages")
    database = tmp_path / "index.db"
    _record(monkeypatch)
    scan(database, tmp_path / "cache", [root])
    rows = {row.name: row for row in list_volumes(database)}
    assert rows["a-bad.cbz"].error_type == "UnreadableArchiveError"
    assert rows["c-empty.cbz"].error_type == "NoPageImagesError"
    assert rows["b-good.cbz"].status == "ok"
    assert rows["b-good.cbz"].title == "Kept"
    assert rows["b-good.cbz"].archive_page_count == 2
    assert "ComicInfo.xml" in RecordingZipFile.reads
    assert not any(name.endswith(".jpg") for name in RecordingZipFile.reads)

    RecordingZipFile.opens = 0
    RecordingZipFile.reads = []
    scan(database, tmp_path / "cache", [root])
    assert RecordingZipFile.opens == 2
    assert RecordingZipFile.reads == []

    os.utime(root / "b-good.cbz", ns=(1_000_000_000, 1_000_000_000))
    RecordingZipFile.opens = 0
    RecordingZipFile.reads = []
    scan(database, tmp_path / "cache", [root])
    assert RecordingZipFile.reads == ["ComicInfo.xml"]
    assert list_volumes(database, under=root / "a-bad.cbz")[0].status == "failed"


def test_cancel_keeps_committed_rows_and_skips_prune(tmp_path: Path) -> None:
    root = tmp_path / "root"
    other = tmp_path / "other"
    _cbz(root / "a.cbz", Series="A")
    _cbz(root / "b.cbz", Series="B")
    _cbz(other / "c.cbz", Series="C")
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    scan(database, cache, [root, other])
    (root / "b.cbz").unlink()
    calls = {"count": 0}

    def cancel() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    result = scan(database, cache, [root], cancel=cancel)
    assert result.cancelled is True
    assert result.deleted == ()
    names = {row.name for row in list_volumes(database)}
    assert names == {"a.cbz", "b.cbz", "c.cbz"}


def test_finished_scan_prunes_rows_and_thumbnails(tmp_path: Path) -> None:
    stable = tmp_path / "stable"
    removed = tmp_path / "removed"
    offline = tmp_path / "offline"
    _cbz(stable / "keep.cbz", Series="Keep")
    _cbz(stable / "drop.cbz", Series="Drop")
    _cbz(removed / "old.cbz", Series="Old")
    _cbz(offline / "stay.cbz", Series="Stay")
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    scan(database, cache, [stable, removed, offline])
    drop = next(row for row in list_volumes(database) if row.name == "drop.cbz")
    digest = __import__("hashlib").sha256(drop.path.encode()).hexdigest()
    cache.mkdir()
    stale = cache / f"{digest}-1-1.jpg"
    stale.write_bytes(b"thumb")
    (stable / "drop.cbz").unlink()
    offline_file = offline / "stay.cbz"
    offline_file.unlink()
    offline.rmdir()
    result = scan(database, cache, [stable, offline])
    names = {row.name: row for row in list_volumes(database)}
    assert "drop.cbz" not in names
    assert "old.cbz" not in names
    assert names["keep.cbz"].series == "Keep"
    assert names["stay.cbz"].root == str(offline.resolve())
    assert str((stable / "drop.cbz").resolve()) in result.deleted
    assert str(removed.resolve()) not in result.skipped_or_incomplete
    assert str(offline.resolve()) in result.skipped_or_incomplete
    assert not stale.exists()

    emptied = scan(database, cache, [])
    assert list_volumes(database) == []
    assert emptied.deleted
    assert emptied.cancelled is False


def test_unreadable_directory_is_not_pruned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    other = tmp_path / "other"
    _cbz(root / "stay.cbz", Series="Stay")
    _cbz(other / "gone.cbz", Series="Gone")
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    scan(database, cache, [root, other])
    (other / "gone.cbz").unlink()
    real_scandir = os.scandir

    def scandir(path: object) -> object:
        if Path(str(path)).resolve() == other.resolve():
            raise PermissionError("blocked")
        return real_scandir(path)

    monkeypatch.setattr(index_mod.os, "scandir", scandir)
    result = scan(database, cache, [root, other])
    names = {row.name for row in list_volumes(database)}
    assert names == {"stay.cbz", "gone.cbz"}
    assert result.deleted == ()
    assert str(other.resolve()) in result.skipped_or_incomplete


def test_refresh_and_forget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    changed = root / "changed.cbz"
    sibling = root / "sibling.cbz"
    _cbz(changed, Series="Before")
    _cbz(sibling, Series="Sibling")
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    scan(database, cache, [root])
    _cbz(changed, Series="After")

    real_scandir = os.scandir

    def forbid_library_walk(path: object) -> object:
        resolved = Path(str(path)).resolve()
        library = root.resolve()
        if resolved == library or library in resolved.parents:
            raise AssertionError(f"walked {path}")
        return real_scandir(path)

    monkeypatch.setattr(index_mod.os, "scandir", forbid_library_walk)
    updated = refresh_volume(database, changed, [root])
    assert updated is not None
    assert updated.series == "After"
    assert next(
        row.series for row in list_volumes(database) if row.name == "sibling.cbz"
    ) == ("Sibling")
    missing = root / "missing.cbz"
    _png(missing, (20, 10), (0, 0, 0))
    refresh_volume(database, missing, [root])
    thumb = thumbnail_for(database, cache, missing)
    assert thumb is not None and thumb.is_file()
    missing.unlink()
    assert refresh_volume(database, missing, [root]) is None
    assert thumb.is_file()
    forget_volume(database, cache, missing)
    assert list_volumes(database, under=missing) == []
    assert not thumb.exists()
    forget_volume(database, cache, missing)


def test_thumbnail_uses_the_cover_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    wide = root / "wide.cbz"
    narrow = root / "narrow.cbz"
    alpha = root / "alpha.cbz"
    _png(wide, (800, 400), (255, 0, 0))
    _png(narrow, (100, 40), (0, 0, 255))
    _png(alpha, (800, 20), (0, 0, 0, 0))
    database = tmp_path / "index.db"
    cache = tmp_path / "cache"
    scan(database, cache, [root])
    assert list_volumes(database)
    assert not cache.exists()
    assert not (root / "wide-poster.jpg").exists()
    original = wide.read_bytes()
    _record(monkeypatch)
    poster = thumbnail_for(database, cache, wide)
    assert poster is not None
    assert wide.read_bytes() == original
    page_reads = [name for name in RecordingZipFile.reads if name != "ComicInfo.xml"]
    assert page_reads == ["cover.png"]
    with Image.open(poster) as image:
        assert image.size == (256, 128)
        red, green, blue = image.getpixel((image.width // 2, image.height // 2))[:3]
        assert red >= 250 and green <= 5 and blue <= 5

    narrow_thumb = thumbnail_for(database, cache, narrow)
    assert narrow_thumb is not None
    with Image.open(narrow_thumb) as image:
        assert image.size == (100, 40)
    alpha_thumb = thumbnail_for(database, cache, alpha)
    assert alpha_thumb is not None
    with Image.open(alpha_thumb) as image:
        assert image.size[0] == 256
        pixel = image.getpixel((image.width // 2, image.height // 2))[:3]
        assert all(channel >= 250 for channel in pixel)

    RecordingZipFile.opens = 0
    RecordingZipFile.reads = []
    assert thumbnail_for(database, cache, wide) == poster
    assert RecordingZipFile.opens == 0
    failed = root / "bad.cbz"
    failed.write_bytes(b"nope")
    scan(database, cache, [root])
    assert thumbnail_for(database, cache, failed) is None


def test_relative_root_raises_before_a_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_scan(path: object) -> None:
        raise AssertionError(path)

    monkeypatch.setattr(index_mod.os, "scandir", forbid_scan)
    with pytest.raises(LibraryIndexError):
        scan(tmp_path / "index.db", tmp_path / "cache", ["library"])


def test_user_version_is_refused(tmp_path: Path) -> None:
    database = tmp_path / "index.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE volumes (path TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO volumes (path) VALUES ('sentinel')")
    connection.execute("PRAGMA user_version = 3")
    connection.commit()
    connection.close()
    with pytest.raises(IndexVersionError):
        list_volumes(database)
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert connection.execute("SELECT path FROM volumes").fetchone()[0] == "sentinel"
    connection.close()


def test_user_version_1_gains_count(tmp_path: Path) -> None:
    database = tmp_path / "index.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
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
    )
    connection.execute(
        """
        INSERT INTO volumes VALUES (
          '/books/a.cbz', '/books', 'a.cbz', 'cbz', 1, 1, 'ok', '', '',
          0, 1, '', '', '', '', '', '', '', '', '', '', '', '', '', '',
          '', '', '', '', '', '', ''
        )
        """
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()
    rows = list_volumes(database)
    assert rows[0].count == ""
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    connection.close()
