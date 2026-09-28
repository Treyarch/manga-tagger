"""Cover writes preserve existing payloads and XML and commit atomically."""

import io
import struct
import zipfile
from pathlib import Path

import pytest
from lxml import etree
from PIL import Image

from manga_tagger.archives import (
    ArchiveError,
    ConvertTargetExistsError,
    NoPageImagesError,
    cover_index,
    insert_cover_page,
    list_pages,
)
from manga_tagger.archives import pages as pages_mod
from manga_tagger.archives import read_comic_info, read_page, replace_cover_page
from manga_tagger.archives import save as save_mod
from manga_tagger.archives.pages import cover_member_name


@pytest.fixture
def image_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (8, 12), "red").save(stream, "JPEG")
    return stream.getvalue()


def build(
    path, names=("book/01.jpg", "book/02.jpg", "book/03.jpg"), cover=1, namespace=""
):
    prefix = f' xmlns="{namespace}"' if namespace else ""
    xml = f"""<ComicInfo{prefix} custom="keep"><Series>Original</Series><Web>old</Web>
      <PageCount>{len(names)}</PageCount><Extra>keep</Extra><Pages custom="keep">
      <Page Image="0" Type="Story" DoublePage="true" Bookmark="start"><Extra/></Page>
      <Page Image="1" Type="{'FrontCover' if cover == 1 else 'Story'}" ImageWidth="12"/>
      <Page Image="2" Type="BackCover" Bonus="keep"/>
      <Page Image="invalid" Type="FrontCover" Custom="keep"/>
      <Other/></Pages></ComicInfo>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.comment = b"archive comment"
        for i, name in enumerate(names):
            archive.writestr(
                name, bytes([i + 1]) * 1000, compress_type=zipfile.ZIP_DEFLATED
            )
        archive.writestr("ComicInfo.xml", xml)
        archive.writestr("notes.txt", b"notes")


def raw_members(path):
    """Capture compressed payloads and metadata without ZipFile decompression."""
    data = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        result = {}
        for info in archive.infolist():
            start = info.header_offset
            name_len, extra_len = struct.unpack_from("<HH", data, start + 26)
            offset = start + 30 + name_len + extra_len
            result[info.filename] = (
                info.compress_type,
                info.CRC,
                info.file_size,
                info.compress_size,
                data[offset : offset + info.compress_size],
            )
        return result


@pytest.mark.parametrize(
    "writer,delta", [(insert_cover_page, 1), (replace_cover_page, 0)]
)
@pytest.mark.parametrize("namespace", ["", "urn:comic-info"])
def test_write_cover_preserves_compressed_members_and_xml(
    tmp_path, image_bytes, writer, delta, namespace
):
    path = tmp_path / "book.cbz"
    build(path, namespace=namespace)
    before = raw_members(path)
    result = writer(path, image_bytes, "provider.jpg", keep_cbr_original=True)
    assert result == path
    pages = list_pages(path)
    assert len(pages) == 3 + delta
    assert pages[0] == "book/!provider.jpg"
    assert cover_index(path) == 0
    assert read_page(path, 0) == image_bytes
    after = raw_members(path)
    for name, raw in before.items():
        if name == "ComicInfo.xml" or (delta == 0 and name == "book/02.jpg"):
            continue
        assert after[name] == raw
    assert ("book/02.jpg" in after) == bool(delta)
    assert after[pages[0]][0] == zipfile.ZIP_STORED
    model = read_comic_info(path)
    assert model.field_text("PageCount") == str(3 + delta)
    assert model.field_text("Series") == "Original"
    root = etree.fromstring(model.to_bytes())
    ns = {"c": namespace} if namespace else {}
    p = "c:" if namespace else ""
    assert root.get("custom") == "keep"
    assert root.find(f"{p}Extra", ns).text == "keep"
    tree = root.find(f"{p}Pages", ns)
    assert tree.get("custom") == "keep"
    entries = tree.findall(f"{p}Page", ns)
    assert [e.get("Image") for e in entries if e.get("Type") == "FrontCover"] == ["0"]
    old_first = next(e for e in entries if e.get("Bookmark") == "start")
    assert old_first.get("Image") == "1" and old_first.get("DoublePage") == "true"
    assert old_first.find(f"{p}Extra", ns) is not None
    assert tree.find(f"{p}Other", ns) is not None
    back = next(e for e in entries if e.get("Type") == "BackCover")
    assert back.get("Image") == str(2 + delta)


@pytest.mark.parametrize(
    "pages,anchor",
    [
        (["a/01.jpg", "z/cover.jpg"], "z/cover.jpg"),
        (["a\\01.jpg", "z\\cover.jpg"], "z\\cover.jpg"),
        ([" !01.jpg", "z.jpg"], "z.jpg"),
        (["!!!01.jpg", "02.jpg"], "02.jpg"),
    ],
)
def test_name_is_bounded_and_sorts_first(pages, anchor):
    name = cover_member_name(pages, "provider.jpg", anchor=anchor)
    assert name.endswith("provider.jpg")
    assert name < min(p.replace("\\", "/") for p in pages)


def test_naming_collision_sanitization_and_unrepresentable_names():
    assert (
        cover_member_name(["z.jpg"], "../../cover.jpg", members=["z.jpg", "cover.jpg/"])
        == "!cover.jpg"
    )
    with pytest.raises(ArchiveError):
        cover_member_name(["\x01.jpg"], "cover.jpg")
    for name in ["", "..", "foo..jpg", "a.svg", "a\x00.jpg"]:
        with pytest.raises(ArchiveError):
            cover_member_name(["a.jpg"], name)


@pytest.mark.parametrize("writer", [insert_cover_page, replace_cover_page])
def test_first_page_cover_and_missing_comicinfo(tmp_path, image_bytes, writer):
    path = tmp_path / "book.cbz"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.jpg", b"old")
    writer(path, image_bytes, "cover.jpg", keep_cbr_original=True)
    assert read_page(path, 0) == image_bytes
    assert cover_index(path) == 0
    assert len(list_pages(path)) == (2 if writer is insert_cover_page else 1)


@pytest.mark.parametrize("writer", [insert_cover_page, replace_cover_page])
def test_failures_do_not_touch_original(tmp_path, image_bytes, writer, monkeypatch):
    path = tmp_path / "book.cbz"
    build(path)
    before = path.read_bytes()
    for data in [b"", b"html masquerading as image", image_bytes[:100]]:
        with pytest.raises(ArchiveError):
            writer(path, data, "cover.jpg", keep_cbr_original=True)
        assert path.read_bytes() == before

    def fail(*args, **kwargs):
        raise ArchiveError("verification failed")

    monkeypatch.setattr(save_mod, "_verify_patch", fail)
    with pytest.raises(ArchiveError, match="verification"):
        writer(path, image_bytes, "cover.jpg", keep_cbr_original=True)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize("writer", [insert_cover_page, replace_cover_page])
def test_empty_archive_rejected(tmp_path, image_bytes, writer):
    path = tmp_path / "book.cbz"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("notes.txt", b"hello")
    before = path.read_bytes()
    with pytest.raises(NoPageImagesError):
        writer(path, image_bytes, "cover.jpg", keep_cbr_original=True)
    assert path.read_bytes() == before


@pytest.mark.parametrize("keep", [False, True])
@pytest.mark.parametrize("writer", [insert_cover_page, replace_cover_page])
def test_cbr_conversion_and_cleanup(tmp_path, image_bytes, writer, keep, monkeypatch):
    original = tmp_path / "book.cbr"
    original.write_bytes(b"original rar")
    tree = tmp_path / "extracted"
    tree.mkdir()
    (tree / "01.jpg").write_bytes(b"old page")
    calls = []

    def extract(path):
        calls.append(path)
        return tree

    monkeypatch.setattr(pages_mod, "extract_cbr", extract)
    result = writer(original, image_bytes, "cover.jpg", keep_cbr_original=keep)
    assert calls == [original]
    assert result == original.with_suffix(".cbz")
    assert read_page(result, 0) == image_bytes
    assert original.exists() == keep
    assert not tree.exists()
    if not keep:
        original.write_bytes(b"another rar")
    with pytest.raises(ConvertTargetExistsError):
        writer(original, image_bytes, "cover.jpg", keep_cbr_original=keep)
    assert original.read_bytes() in [b"original rar", b"another rar"]
    assert calls == [original]


def test_cbr_failure_preserves_original(tmp_path, image_bytes, monkeypatch):
    original = tmp_path / "book.cbr"
    original.write_bytes(b"original")
    tree = tmp_path / "extracted"
    tree.mkdir()
    (tree / "page.jpg").write_bytes(b"old")
    monkeypatch.setattr(pages_mod, "extract_cbr", lambda _: tree)

    def fail(*args, **kwargs):
        raise ArchiveError("verification failed")

    monkeypatch.setattr(save_mod, "_verify_patch", fail)
    with pytest.raises(ArchiveError):
        insert_cover_page(original, image_bytes, "new.jpg", keep_cbr_original=False)
    assert original.read_bytes() == b"original"
    assert not original.with_suffix(".cbz").exists()
    assert not tree.exists()


def test_cbz_write_does_not_decompress_kept_pages(tmp_path, image_bytes, monkeypatch):
    path = tmp_path / "book.cbz"
    build(path)
    original_open = zipfile.ZipFile.open
    reads = []

    def record(self, name, mode="r", *args, **kwargs):
        if mode == "r":
            reads.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
        return original_open(self, name, mode, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", record)
    insert_cover_page(path, image_bytes, "new.jpg", keep_cbr_original=True)
    assert reads and set(reads) == {"ComicInfo.xml"}


def test_cbr_rejects_extracted_symlinks(tmp_path, image_bytes, monkeypatch):
    original = tmp_path / "book.cbr"
    original.write_bytes(b"original")
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"untouched")
    tree = tmp_path / "extracted"
    tree.mkdir()
    (tree / "page.jpg").symlink_to(outside)
    monkeypatch.setattr(pages_mod, "extract_cbr", lambda _: tree)
    with pytest.raises(ArchiveError, match="symbolic link"):
        replace_cover_page(original, image_bytes, "new.jpg", keep_cbr_original=False)
    assert original.read_bytes() == b"original"
    assert outside.read_bytes() == b"untouched"
    assert not original.with_suffix(".cbz").exists()


@pytest.mark.parametrize("writer", [insert_cover_page, replace_cover_page])
@pytest.mark.parametrize(
    "format,filename",
    [
        ("WEBP", "provider.webp"),
        ("PNG", "provider.png"),
        ("GIF", "provider.gif"),
        ("WEBP", "provider.jpg"),
    ],
)
def test_non_jpeg_cover_is_converted_without_resizing(
    tmp_path, writer, format, filename
):
    path = tmp_path / "book.cbz"
    build(path)
    source = io.BytesIO()
    Image.new("RGB", (80, 120), "red").save(source, format=format)
    writer(path, source.getvalue(), filename, keep_cbr_original=True)
    assert list_pages(path)[0] == "book/!provider.jpg"
    with Image.open(io.BytesIO(read_page(path, 0))) as cover:
        cover.load()
        assert cover.format == "JPEG"
        assert cover.mode == "RGB"
        assert cover.size == (80, 120)
        assert cover.getpixel((40, 60))[0] > 240


@pytest.mark.parametrize("filename", ["cover.jpg", "cover.jpeg", "cover.webp"])
def test_jpeg_bytes_are_preserved_regardless_of_extension(
    tmp_path, image_bytes, filename
):
    path = tmp_path / "book.cbz"
    build(path)
    insert_cover_page(path, image_bytes, filename, keep_cbr_original=True)
    assert list_pages(path)[0] == "book/!cover.jpg"
    assert read_page(path, 0) == image_bytes


@pytest.mark.parametrize("format", ["PNG", "WEBP", "GIF"])
def test_transparent_cover_gets_white_background(tmp_path, format):
    path = tmp_path / "book.cbz"
    build(path)
    source = io.BytesIO()
    Image.new("RGBA", (20, 30), (0, 0, 0, 0)).save(source, format=format)
    insert_cover_page(
        path, source.getvalue(), "cover." + format.lower(), keep_cbr_original=True
    )
    with Image.open(io.BytesIO(read_page(path, 0))) as cover:
        assert cover.getpixel((10, 15)) == (255, 255, 255)


def test_conversion_applies_orientation_and_uses_first_animation_frame(tmp_path):
    path = tmp_path / "book.cbz"
    build(path)
    source = io.BytesIO()
    image = Image.new("RGB", (20, 30), "red")
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, format="PNG", exif=exif)
    replace_cover_page(path, source.getvalue(), "rotated.png", keep_cbr_original=True)
    with Image.open(io.BytesIO(read_page(path, 0))) as cover:
        assert cover.size == (30, 20)
        assert cover.getexif().get(274, 1) == 1
    source = io.BytesIO()
    image.save(
        source,
        format="GIF",
        save_all=True,
        append_images=[Image.new("RGB", (20, 30), "blue")],
    )
    replace_cover_page(path, source.getvalue(), "animated.gif", keep_cbr_original=True)
    with Image.open(io.BytesIO(read_page(path, 0))) as cover:
        red, _, blue = cover.getpixel((10, 15))
        assert red > 240 and blue < 10


def test_failed_jpeg_conversion_leaves_archive_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "book.cbz"
    build(path)
    original = path.read_bytes()
    source = io.BytesIO()
    Image.new("RGB", (8, 12)).save(source, format="WEBP")

    def fail(*args, **kwargs):
        raise OSError("encoding failed")

    monkeypatch.setattr(Image.Image, "save", fail)
    with pytest.raises(ArchiveError):
        insert_cover_page(path, source.getvalue(), "cover.webp", keep_cbr_original=True)
    assert path.read_bytes() == original


@pytest.mark.parametrize("writer", [insert_cover_page, replace_cover_page])
def test_cbr_cover_is_converted_to_jpeg(tmp_path, monkeypatch, writer):
    path = tmp_path / "book.cbr"
    path.write_bytes(b"original")
    tree = tmp_path / "extracted"
    tree.mkdir()
    (tree / "01.jpg").write_bytes(b"old")
    monkeypatch.setattr(pages_mod, "extract_cbr", lambda _: tree)
    source = io.BytesIO()
    Image.new("RGB", (8, 12), "red").save(source, format="WEBP")
    output = writer(path, source.getvalue(), "cover.webp", keep_cbr_original=True)
    assert list_pages(output)[0].endswith("cover.jpg")
    with Image.open(io.BytesIO(read_page(output, 0))) as cover:
        assert cover.format == "JPEG"
