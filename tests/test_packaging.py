from configparser import ConfigParser
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


def test_desktop_entry_matches_launcher_contract() -> None:
    parser = ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(REPOSITORY / "assets" / "manga-tagger.desktop", encoding="utf-8")

    entry = parser["Desktop Entry"]
    assert dict(entry) == {
        "Type": "Application",
        "Name": "Manga Tagger",
        "Comment": "Tag and rename manga files",
        "Exec": "manga-tagger",
        "Icon": "manga-tagger",
        "Terminal": "true",
        "Categories": "Utility;",
        "Keywords": "manga;tagger;cbz;cbr;",
    }


def test_launcher_icons_are_present() -> None:
    svg = REPOSITORY / "assets" / "manga-tagger.svg"
    png = REPOSITORY / "assets" / "manga-tagger-512.png"

    assert svg.read_text(encoding="utf-8").startswith("<?xml")
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
