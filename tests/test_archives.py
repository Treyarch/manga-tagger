"""Hermetic tests for archive reads, ComicInfo saves, rename, and posters."""

import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from lxml import etree
from PIL import Image

from manga_tagger.archives import (
    OFFERED_RENAME_TEMPLATE,
    ArchiveError,
    BatchFieldError,
    ComicPage,
    ConvertTargetExistsError,
    MissingUnarError,
    NoPageImagesError,
    RenameConflictError,
    RenameFieldError,
    RenameTemplateError,
    UnreadableArchiveError,
)
from manga_tagger.archives import cbr as cbr_mod
from manga_tagger.archives import (
    convert_cbr,
    cover_index,
    list_pages,
    plan_rename,
    read_comic_info,
    read_page,
    rename_in_directory,
    resolve_cover_index,
)
from manga_tagger.archives import save as save_mod
from manga_tagger.archives import save_comic_info, save_many, write_poster

FOLDER = "01 - La tueuse aux yeux d\u2019argent"
STORED = b"stored-image-bytes-0123456789"
DEFLATED = b"\x00" * 400
_ORIGINAL_ZIP = zipfile.ZipFile

needs_unar = pytest.mark.skipif(
    shutil.which("unar") is None or shutil.which("lsar") is None,
    reason="unar is not on PATH",
)


class RecordingZipFile(_ORIGINAL_ZIP):
    """ZipFile that records member bodies opened for reading."""

    reads: list[str] = []

    def open(self, name, mode="r", pwd=None, *, force_zip64=False):  # type: ignore[no-untyped-def]
        if mode == "r":
            if isinstance(name, zipfile.ZipInfo):
                RecordingZipFile.reads.append(name.filename)
            else:
                RecordingZipFile.reads.append(str(name))
        return super().open(name, mode, pwd, force_zip64=force_zip64)


def _record(monkeypatch: pytest.MonkeyPatch) -> None:
    RecordingZipFile.reads = []
    monkeypatch.setattr(zipfile, "ZipFile", RecordingZipFile)


def _xml_bytes() -> bytes:
    root = etree.Element("ComicInfo", custom="keep")
    etree.SubElement(root, "Title").text = "The slayer"
    etree.SubElement(root, "Series").text = "Claymore"
    etree.SubElement(root, "Number").text = "1"
    etree.SubElement(root, "Volume").text = "1"
    etree.SubElement(root, "PageCount").text = "2"
    etree.SubElement(root, "Manga").text = "Yes"
    strange = etree.SubElement(root, "Strange", extra="1")
    strange.text = "hello"
    pages = etree.SubElement(root, "Pages")
    etree.SubElement(
        pages,
        "Page",
        Image="0",
        Type="FrontCover",
        ImageWidth="10",
        ImageHeight="20",
        Bonus="x",
    )
    etree.SubElement(pages, "Page", Image="1", Type="InnerCover")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def _build_cbz(path: Path, xml: bytes | None) -> None:
    with _ORIGINAL_ZIP(path, "w") as archive:
        stored = zipfile.ZipInfo(f"{FOLDER}/b.jpg")
        stored.compress_type = zipfile.ZIP_STORED
        archive.writestr(stored, STORED)
        if xml is not None:
            archive.writestr("ComicInfo.xml", xml)
        deflated = zipfile.ZipInfo(f"{FOLDER}/a.jpg")
        deflated.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(deflated, DEFLATED)
        archive.writestr("notes.txt", b"keep-me")
        archive.mkdir(FOLDER)


def _simple_cbz(path: Path, **fields: str) -> None:
    root = etree.Element("ComicInfo")
    for name, value in fields.items():
        etree.SubElement(root, name).text = value
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    with _ORIGINAL_ZIP(path, "w") as archive:
        archive.writestr("ComicInfo.xml", xml)
        archive.writestr("page.jpg", b"page-bytes")


def _member_rows(path: Path) -> list[tuple[str, int, int, int, int, bytes]]:
    with _ORIGINAL_ZIP(path) as archive:
        rows = []
        for info in archive.infolist():
            body = b"" if info.is_dir() else archive.read(info)
            rows.append(
                (
                    info.filename,
                    info.compress_type,
                    info.CRC,
                    info.file_size,
                    info.compress_size,
                    body,
                )
            )
        return rows


def _flags(path: Path) -> dict[str, int]:
    with _ORIGINAL_ZIP(path) as archive:
        return {info.filename: info.flag_bits for info in archive.infolist()}


def _field(path: Path, name: str) -> str | None:
    return read_comic_info(path).field_text(name)


def _png(size: tuple[int, int], color: tuple[int, ...]) -> bytes:
    image = Image.new("RGBA" if len(color) == 4 else "RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image_cbz(path: Path, images: list[tuple[str, bytes]], xml: bytes | None) -> None:
    with _ORIGINAL_ZIP(path, "w") as archive:
        if xml is not None:
            archive.writestr("ComicInfo.xml", xml)
        for name, payload in images:
            archive.writestr(name, payload)


def _stub_cbr(
    monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]
) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
        calls.append(list(args))
        if args[0] == "lsar":
            contents = [
                {"XADFileName": name, "XADIsDirectory": name.endswith("/")}
                for name in files
            ]
            payload = json.dumps({"lsarContents": contents}).encode()
            return subprocess.CompletedProcess(args, 0, payload, b"")
        output = Path(args[args.index("-output-directory") + 1])
        if "-no-directory" in args:
            member = args[-1]
            target = output / Path(member).name
            target.write_bytes(files[member])
        else:
            for name, payload in files.items():
                if name.endswith("/"):
                    (output / name).mkdir(parents=True, exist_ok=True)
                    continue
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(cbr_mod, "find_executable", lambda _name: "/usr/bin/unar")
    monkeypatch.setattr(cbr_mod, "run_command", run)
    return calls


def test_partial_reads_follow_filename_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "book.cbz"
    _build_cbz(archive, _xml_bytes())
    _record(monkeypatch)

    pages = list_pages(archive)
    assert pages == [f"{FOLDER}/a.jpg", f"{FOLDER}/b.jpg"]
    assert RecordingZipFile.reads == []

    RecordingZipFile.reads = []
    info = read_comic_info(archive)
    assert info.field_text("Series") == "Claymore"
    assert RecordingZipFile.reads == ["ComicInfo.xml"]
    assert info.pages()[0].type == "FrontCover"
    assert info.pages()[0].image == "0"

    RecordingZipFile.reads = []
    assert read_page(archive, 1) == STORED
    assert RecordingZipFile.reads == [f"{FOLDER}/b.jpg"]

    original = archive.read_bytes()
    with pytest.raises(UnreadableArchiveError):
        read_page(archive, 2)
    assert archive.read_bytes() == original


def test_backslash_names_sort_as_slashes(tmp_path: Path) -> None:
    archive = tmp_path / "book.cbz"
    with _ORIGINAL_ZIP(archive, "w") as zip_file:
        zip_file.writestr(zipfile.ZipInfo("b\\a.jpg"), b"one")
        zip_file.writestr(zipfile.ZipInfo("a.jpg"), b"two")
    assert list_pages(archive) == ["a.jpg", "b\\a.jpg"]


def test_cover_index_uses_front_cover_without_reading_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "book.cbz"
    _build_cbz(archive, _xml_bytes())
    _record(monkeypatch)
    assert cover_index(archive) == 0
    assert RecordingZipFile.reads == ["ComicInfo.xml"]

    missing_pages = tmp_path / "missing-pages.cbz"
    root = etree.Element("ComicInfo")
    etree.SubElement(root, "Series").text = "Claymore"
    _build_cbz(
        missing_pages, etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    )
    RecordingZipFile.reads = []
    assert cover_index(missing_pages) == 0
    assert all(not name.endswith(".jpg") for name in RecordingZipFile.reads)

    no_front = tmp_path / "no-front.cbz"
    root = etree.Element("ComicInfo")
    pages = etree.SubElement(root, "Pages")
    etree.SubElement(pages, "Page", Image="0", Type="InnerCover")
    _build_cbz(no_front, etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert cover_index(no_front) == 0

    later = tmp_path / "later.cbz"
    root = etree.Element("ComicInfo")
    pages = etree.SubElement(root, "Pages")
    etree.SubElement(pages, "Page", Image="1", Type="FrontCover")
    _build_cbz(later, etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert cover_index(later) == 1
    assert resolve_cover_index((ComicPage(image="9", type="FrontCover"),), 2) == 0


def test_save_copies_members_and_keeps_unknown_xml(tmp_path: Path) -> None:
    archive = tmp_path / "book.cbz"
    _build_cbz(archive, _xml_bytes())
    before = _member_rows(archive)
    assert before[1][0] == "ComicInfo.xml"
    assert {row[0]: row[1] for row in before}[f"{FOLDER}/a.jpg"] == zipfile.ZIP_DEFLATED
    assert {row[0]: row[1] for row in before}[f"{FOLDER}/b.jpg"] == zipfile.ZIP_STORED

    save_comic_info(
        archive,
        {"Series": "Claymore II"},
        write_number=False,
        keep_cbr_original=False,
    )

    after = _member_rows(archive)
    assert [row[0] for row in after] == [row[0] for row in before]
    for old, new in zip(before, after, strict=True):
        if old[0] == "ComicInfo.xml":
            continue
        assert new == old
    flags = _flags(archive)
    assert flags[f"{FOLDER}/a.jpg"] & (1 << 11)
    assert flags["notes.txt"] & (1 << 11)
    root = etree.fromstring(after[1][5])
    assert root.get("custom") == "keep"
    strange = next(child for child in root if etree.QName(child).localname == "Strange")
    assert strange.get("extra") == "1"
    assert strange.text == "hello"
    page = next(child for child in root if etree.QName(child).localname == "Pages")[0]
    assert page.get("Bonus") == "x"
    assert page.get("ImageWidth") == "10"
    assert _field(archive, "Series") == "Claymore II"
    assert _field(archive, "Volume") == "1"
    assert _field(archive, "Manga") == "Yes"
    assert _field(archive, "PageCount") == "2"


def test_patch_volume_number_and_page_count(tmp_path: Path) -> None:
    archive = tmp_path / "book.cbz"
    _simple_cbz(
        archive, Series="Claymore", Number="1", Volume="1", PageCount="2", Manga="Yes"
    )
    save_comic_info(
        archive,
        {"Volume": None, "Number": "9"},
        write_number=False,
        keep_cbr_original=False,
    )
    assert _field(archive, "Volume") is None
    assert _field(archive, "Number") == "1"

    save_comic_info(
        archive,
        {"Number": "4", "PageCount": "99"},
        write_number=True,
        keep_cbr_original=False,
    )
    assert _field(archive, "Number") == "4"
    assert _field(archive, "PageCount") == "99"


def test_missing_comicinfo_reads_empty_and_is_written_first(tmp_path: Path) -> None:
    archive = tmp_path / "book.cbz"
    _build_cbz(archive, None)
    info = read_comic_info(archive)
    assert info.field_text("Series") is None
    assert info.pages() == ()
    before_names = [row[0] for row in _member_rows(archive)]

    save_comic_info(
        archive,
        {"Series": "Claymore"},
        write_number=True,
        keep_cbr_original=False,
    )
    names = [row[0] for row in _member_rows(archive)]
    assert names[0] == "ComicInfo.xml"
    assert names[1:] == before_names
    root = etree.fromstring(_member_rows(archive)[0][5])
    assert [etree.QName(child).localname for child in root] == ["Series"]
    assert root.find("Series").text == "Claymore"  # type: ignore[union-attr]


def test_failed_save_leaves_the_original_and_removes_the_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "book.cbz"
    _simple_cbz(archive, Series="Claymore", Number="1")
    original = archive.read_bytes()
    seen: list[Path] = []

    def fail_readback(path: Path) -> None:
        seen.append(Path(path))
        raise RuntimeError("read-back failed")

    monkeypatch.setattr(save_mod, "read_zip_comic_info", fail_readback)
    with pytest.raises(RuntimeError, match="read-back failed"):
        save_comic_info(
            archive,
            {"Series": "Other"},
            write_number=False,
            keep_cbr_original=False,
        )
    assert archive.read_bytes() == original
    assert len(seen) == 1
    assert seen[0].parent == archive.parent
    assert not seen[0].name.endswith(".cbz")
    assert not seen[0].name.endswith(".cbr")
    assert not seen[0].exists()
    assert list(tmp_path.iterdir()) == [archive]


def test_save_many_writes_shared_fields_only(tmp_path: Path) -> None:
    first = tmp_path / "a.cbz"
    second = tmp_path / "b.cbz"
    _simple_cbz(first, Title="One", Series="Old", Number="1", Volume="3", Writer="A")
    _simple_cbz(second, Title="Two", Series="Old", Number="2", Volume="4", Writer="B")
    results = save_many(
        [first, second],
        {"Series": "Claymore", "Writer": "Norihiro Yagi", "Manga": "YesAndRightToLeft"},
        keep_cbr_original=False,
    )
    assert [item.ok for item in results] == [True, True]
    for path, number, volume, title in (
        (first, "1", "3", "One"),
        (second, "2", "4", "Two"),
    ):
        assert _field(path, "Series") == "Claymore"
        assert _field(path, "Writer") == "Norihiro Yagi"
        assert _field(path, "Manga") == "YesAndRightToLeft"
        assert _field(path, "Number") == number
        assert _field(path, "Volume") == volume
        assert _field(path, "Title") == title

    untouched = [path.read_bytes() for path in (first, second)]
    with pytest.raises(BatchFieldError):
        save_many(
            [first, second], {"Series": "Nope", "Title": "X"}, keep_cbr_original=False
        )
    with pytest.raises(BatchFieldError):
        save_many([first, second], {"Number": "8"}, keep_cbr_original=False)
    assert [path.read_bytes() for path in (first, second)] == untouched


def test_save_many_keeps_going_after_one_failure(tmp_path: Path) -> None:
    first = tmp_path / "a.cbz"
    missing = tmp_path / "missing.cbz"
    _simple_cbz(first, Series="Old", Title="Stay")
    results = save_many(
        [first, missing],
        {"Series": "Claymore"},
        keep_cbr_original=False,
    )
    assert results[0].ok
    assert results[0].output_path == first
    assert results[1].error_type == "UnreadableArchiveError"
    assert not missing.exists()
    assert _field(first, "Series") == "Claymore"
    assert _field(first, "Title") == "Stay"


def _rename_case(root: Path, filename: str, **fields: str) -> Path:
    folder = root / filename
    folder.mkdir()
    _simple_cbz(folder / filename, **fields)
    return folder


def test_rename_in_directory(tmp_path: Path) -> None:
    folder = tmp_path / "basic"
    folder.mkdir()
    archive = folder / "old.cbz"
    _simple_cbz(archive, Series="Claymore", Number="1", Title="One")
    poster = folder / "old-poster.jpg"
    poster.write_bytes(b"poster")
    original = archive.read_bytes()
    nested = folder / "nested"
    nested.mkdir()
    _simple_cbz(nested / "nested.cbz", Series="Claymore", Number="9")
    blank = folder / "blank.cbz"
    _simple_cbz(blank, Series="Claymore", Number="")

    results = rename_in_directory(folder, OFFERED_RENAME_TEMPLATE)
    by_name = {item.path.name: item for item in results}
    assert [item.path.name for item in results] == ["blank.cbz", "old.cbz"]
    assert by_name["old.cbz"].output_path == folder / "Claymore v01.cbz"
    assert (folder / "Claymore v01.cbz").read_bytes() == original
    assert (folder / "Claymore v01-poster.jpg").read_bytes() == b"poster"
    assert not poster.exists()
    assert by_name["blank.cbz"].error_type == "RenameFieldError"
    assert blank.exists()
    assert (nested / "nested.cbz").exists()

    half_dir = _rename_case(tmp_path, "half.cbz", Series="Claymore", Number="1.5")
    renamed = rename_in_directory(half_dir, OFFERED_RENAME_TEMPLATE)
    assert renamed[0].output_path == half_dir / "Claymore v1.5.cbz"

    wide_dir = _rename_case(tmp_path, "wide.CBZ", Series="Claymore", Number="100")
    padded = rename_in_directory(wide_dir, OFFERED_RENAME_TEMPLATE)
    assert padded[0].output_path == wide_dir / "Claymore v100.CBZ"

    exact_dir = _rename_case(tmp_path, "exact.cbz", Series="Claymore", Number="1.50")
    kept = rename_in_directory(exact_dir, "{Series} v{Number}")
    assert kept[0].output_path == exact_dir / "Claymore v1.50.cbz"

    slash_dir = _rename_case(tmp_path, "slash.cbz", Series="Clay/more", Number="1")
    slashed = rename_in_directory(slash_dir, OFFERED_RENAME_TEMPLATE)
    assert slashed[0].output_path == slash_dir / "Clay-more v01.cbz"


def test_rename_collisions_and_invalid_templates(tmp_path: Path) -> None:
    left = tmp_path / "left.cbz"
    right = tmp_path / "right.cbz"
    _simple_cbz(left, Series="Claymore", Number="1")
    _simple_cbz(right, Series="Claymore", Number="1")
    results = rename_in_directory(tmp_path, OFFERED_RENAME_TEMPLATE)
    assert [item.error_type for item in results] == [
        "RenameConflictError",
        "RenameConflictError",
    ]
    assert left.exists() and right.exists()
    assert all(isinstance(item, object) for item in results)
    assert results[0].error_type == RenameConflictError.__name__

    blocked = tmp_path / "blocked"
    blocked.mkdir()
    source = blocked / "old.cbz"
    _simple_cbz(source, Series="Claymore", Number="1")
    (blocked / "Claymore v01-poster.jpg").write_bytes(b"taken")
    blocked_result = rename_in_directory(blocked, OFFERED_RENAME_TEMPLATE)
    assert blocked_result[0].error_type == "RenameConflictError"
    assert source.exists()
    assert (blocked / "Claymore v01-poster.jpg").read_bytes() == b"taken"

    for template in (
        "{Series} v{Number:02}.cbz",
        "{NotAField}",
        "{Series",
        "",
    ):
        before = sorted(path.name for path in tmp_path.iterdir())
        with pytest.raises(RenameTemplateError):
            rename_in_directory(tmp_path, template)
        assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_poster_targets_conflict_without_renaming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cbz = tmp_path / "old.cbz"
    cbr = tmp_path / "other.cbr"
    _simple_cbz(cbz, Series="Claymore", Number="1")
    cbr.write_bytes(b"cbr-bytes")
    xml = etree.tostring(
        etree.Element("ComicInfo"),
        xml_declaration=True,
        encoding="UTF-8",
    )
    root = etree.Element("ComicInfo")
    etree.SubElement(root, "Series").text = "Claymore"
    etree.SubElement(root, "Number").text = "1"
    _stub_cbr(
        monkeypatch,
        {
            "ComicInfo.xml": etree.tostring(
                root, xml_declaration=True, encoding="UTF-8"
            ),
            "page.jpg": b"page",
        },
    )
    results = rename_in_directory(tmp_path, OFFERED_RENAME_TEMPLATE)
    assert [item.error_type for item in results] == [
        "RenameConflictError",
        "RenameConflictError",
    ]
    assert cbz.read_bytes()
    assert cbr.read_bytes() == b"cbr-bytes"
    assert xml is not None


def test_plan_rename_writes_nothing(tmp_path: Path) -> None:
    archive = tmp_path / "old.cbz"
    _simple_cbz(archive, Series="Claymore", Number="1")
    poster = tmp_path / "old-poster.jpg"
    poster.write_bytes(b"poster")
    original = archive.read_bytes()
    planned = plan_rename(tmp_path, OFFERED_RENAME_TEMPLATE)
    assert planned[0].output_path == tmp_path / "Claymore v01.cbz"
    assert archive.read_bytes() == original
    assert poster.read_bytes() == b"poster"
    assert not (tmp_path / "Claymore v01.cbz").exists()


def test_write_poster_uses_the_cover_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wide = _png((800, 400), (255, 0, 0))
    other = _png((10, 10), (0, 255, 0))
    archive = tmp_path / "book.cbz"
    root = etree.Element("ComicInfo")
    pages = etree.SubElement(root, "Pages")
    etree.SubElement(pages, "Page", Image="1", Type="FrontCover")
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    _image_cbz(archive, [("a.png", other), ("b.png", wide)], xml)
    original = archive.read_bytes()
    _record(monkeypatch)
    poster = write_poster(archive)
    assert archive.read_bytes() == original
    page_reads = [name for name in RecordingZipFile.reads if name != "ComicInfo.xml"]
    assert page_reads == ["b.png"]
    with Image.open(poster) as image:
        assert image.size == (600, 300)
        center = (image.width // 2, image.height // 2)
        red, green, blue = image.getpixel(center)[:3]
        assert red >= 250 and green <= 5 and blue <= 5

    narrow = tmp_path / "narrow.cbz"
    _image_cbz(narrow, [("cover.png", _png((100, 40), (0, 0, 255)))], None)
    narrow_poster = write_poster(narrow)
    with Image.open(narrow_poster) as image:
        assert image.size == (100, 40)

    alpha = tmp_path / "alpha.cbz"
    _image_cbz(alpha, [("cover.png", _png((800, 20), (0, 0, 0, 0)))], None)
    alpha_poster = write_poster(alpha)
    with Image.open(alpha_poster) as image:
        assert image.size == (600, 15)
        center = (image.width // 2, image.height // 2)
        pixel = image.getpixel(center)[:3]
        assert all(channel >= 250 for channel in pixel)


def test_cbr_list_and_member_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "book.cbr"
    archive.write_bytes(b"not-a-rar")
    calls = _stub_cbr(
        monkeypatch,
        {
            "dir/": b"",
            "dir/b.jpg": b"bee",
            "dir/a.jpg": b"ay",
            "ComicInfo.xml": b"<ComicInfo><Series>Claymore</Series></ComicInfo>",
        },
    )
    assert list_pages(archive) == ["dir/a.jpg", "dir/b.jpg"]
    assert [call[0] for call in calls] == ["lsar"]
    assert calls[0] == ["lsar", "-json", str(archive)]

    calls.clear()
    assert read_page(archive, 0) == b"ay"
    unar = next(call for call in calls if call[0] == "unar")
    assert unar[:4] == ["unar", "-quiet", "-no-directory", "-output-directory"]
    temp = Path(unar[4])
    assert temp.parent == archive.parent
    assert not temp.name.endswith((".cbz", ".cbr"))
    assert unar[5:] == [str(archive), "dir/a.jpg"]
    assert not temp.exists()
    assert read_comic_info(archive).field_text("Series") == "Claymore"

    def fail(args: list[str]) -> subprocess.CompletedProcess[bytes]:
        calls.append(list(args))
        if args[0] == "lsar":
            payload = json.dumps(
                {"lsarContents": [{"XADFileName": "a.jpg", "XADIsDirectory": False}]}
            ).encode()
            return subprocess.CompletedProcess(args, 0, payload, b"")
        return subprocess.CompletedProcess(args, 1, b"", b"nope")

    monkeypatch.setattr(cbr_mod, "run_command", fail)
    calls.clear()
    with pytest.raises(UnreadableArchiveError):
        read_page(archive, 0)
    failed = next(call for call in calls if call[0] == "unar")
    assert not Path(failed[4]).exists()


def test_cbr_lsar_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "book.cbr"
    archive.write_bytes(b"cbr")
    monkeypatch.setattr(cbr_mod, "find_executable", lambda _name: "/usr/bin/lsar")

    def run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
        stdout = responses[0]
        return subprocess.CompletedProcess(args, 0, stdout, b"")

    responses = [b"not-json"]
    monkeypatch.setattr(cbr_mod, "run_command", run)
    with pytest.raises(UnreadableArchiveError):
        list_pages(archive)
    responses[0] = b"{}"
    with pytest.raises(UnreadableArchiveError):
        list_pages(archive)
    responses[0] = json.dumps({"lsarContents": [{"XADFileName": 1}]}).encode()
    with pytest.raises(UnreadableArchiveError):
        list_pages(archive)


def test_missing_unar_does_not_block_cbz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cbr_mod, "find_executable", lambda _name: None)
    cbr = tmp_path / "book.cbr"
    cbr.write_bytes(b"cbr")
    cbz = tmp_path / "book.cbz"
    _simple_cbz(cbz, Series="Claymore")
    with pytest.raises(MissingUnarError, match="unar"):
        list_pages(cbr)
    assert list_pages(cbz) == ["page.jpg"]
    save_comic_info(
        cbz, {"Series": "Next"}, write_number=False, keep_cbr_original=False
    )
    assert _field(cbz, "Series") == "Next"


def test_convert_and_cbr_save_with_stubbed_unar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xml = (
        b"<?xml version='1.0' encoding='UTF-8'?>"
        b"<ComicInfo><Series>Claymore</Series><Number>1</Number></ComicInfo>"
    )
    calls = _stub_cbr(monkeypatch, {"ComicInfo.xml": xml, "page.jpg": b"img"})
    archive = tmp_path / "Foo.cbr"
    archive.write_bytes(b"original-cbr")
    output = convert_cbr(archive, keep_cbr_original=False)
    assert output == tmp_path / "Foo.cbz"
    assert not archive.exists()
    assert _field(output, "Series") == "Claymore"
    with _ORIGINAL_ZIP(output) as zip_file:
        assert zip_file.read("page.jpg") == b"img"
    unar = next(call for call in calls if call[0] == "unar")
    assert unar[:3] == ["unar", "-quiet", "-output-directory"]
    assert "-no-directory" not in unar
    assert not Path(unar[3]).exists()

    kept = tmp_path / "Bar.cbr"
    kept.write_bytes(b"keep-me")
    calls.clear()
    converted = convert_cbr(kept, keep_cbr_original=True)
    assert kept.read_bytes() == b"keep-me"
    assert converted == tmp_path / "Bar.cbz"

    patched = tmp_path / "Baz.cbr"
    patched.write_bytes(b"baz")
    saved = save_comic_info(
        patched,
        {"Series": "Renamed"},
        write_number=False,
        keep_cbr_original=False,
    )
    assert _field(saved, "Series") == "Renamed"
    assert _field(saved, "Number") == "1"
    assert not patched.exists()


def test_existing_cbz_blocks_cbr_convert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cbr = tmp_path / "Foo.cbr"
    cbz = tmp_path / "Foo.cbz"
    cbr.write_bytes(b"cbr")
    cbz.write_bytes(b"cbz")

    def fail(args: list[str]) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError(args)

    monkeypatch.setattr(cbr_mod, "find_executable", lambda _name: "/usr/bin/unar")
    monkeypatch.setattr(cbr_mod, "run_command", fail)
    with pytest.raises(ConvertTargetExistsError):
        convert_cbr(cbr, keep_cbr_original=False)
    assert cbr.read_bytes() == b"cbr"
    assert cbz.read_bytes() == b"cbz"


def test_cbr_delete_failure_keeps_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xml = b"<ComicInfo><Series>Claymore</Series></ComicInfo>"
    _stub_cbr(monkeypatch, {"ComicInfo.xml": xml, "page.jpg": b"img"})
    archive = tmp_path / "Foo.cbr"
    archive.write_bytes(b"cbr")
    real_unlink = Path.unlink

    def unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == "Foo.cbr":
            raise OSError("busy")
        real_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(ArchiveError, match="complete") as caught:
        convert_cbr(archive, keep_cbr_original=False)
    assert "still present" in str(caught.value)
    assert archive.read_bytes() == b"cbr"
    assert (tmp_path / "Foo.cbz").is_file()
    assert _field(tmp_path / "Foo.cbz", "Series") == "Claymore"


def test_empty_archive_and_bad_zip(tmp_path: Path) -> None:
    empty = tmp_path / "empty.cbz"
    with _ORIGINAL_ZIP(empty, "w") as archive:
        archive.writestr("notes.txt", b"nope")
    with pytest.raises(NoPageImagesError):
        list_pages(empty)
    missing = tmp_path / "missing.cbz"
    with pytest.raises(UnreadableArchiveError):
        list_pages(missing)
    bad = tmp_path / "bad.cbz"
    bad.write_bytes(b"not a zip")
    with pytest.raises(UnreadableArchiveError):
        read_comic_info(bad)


@needs_unar
def test_convert_with_unar_on_path(tmp_path: Path) -> None:
    source = tmp_path / "Foo.cbr"
    _simple_cbz(source, Series="Claymore", Number="1")
    # The bytes are a zip with a .cbr name. unar detects the format.
    output = convert_cbr(source, keep_cbr_original=False)
    assert output == tmp_path / "Foo.cbz"
    assert not source.exists()
    assert _field(output, "Series") == "Claymore"
