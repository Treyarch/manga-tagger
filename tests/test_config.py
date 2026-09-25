"""Config paths and the TOML file."""

import tomllib
from pathlib import Path

import pytest

from manga_tagger.config import (
    ConfigError,
    app_paths,
    apply_put,
    load_config,
    save_config,
)


def test_missing_config_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    config = load_config(path)
    assert config.library_roots == []
    assert config.keep_cbr_original is False
    assert config.comicvine_api_key == ""
    assert config.nautiljon_base_url == ""
    assert config.nautiljon_api_key == ""
    assert config.title_languages == ["fr", "en"]
    assert config.theme == "system"
    assert config.extra == {}
    assert not path.exists()
    save_config(path, config)
    saved = tomllib.loads(path.read_text(encoding="utf-8"))
    assert set(saved) == {
        "library_roots",
        "keep_cbr_original",
        "comicvine_api_key",
        "nautiljon_base_url",
        "nautiljon_api_key",
        "title_languages",
        "theme",
    }


def test_relative_root_is_dropped_and_file_is_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'library_roots = ["relative", "/abs", "/abs"]\n'
        'keep_cbr_original = "no"\n'
        "theme = 1\n",
        encoding="utf-8",
    )
    before = path.read_bytes()
    config = load_config(path)
    assert config.library_roots == [str(Path("/abs").resolve())]
    assert config.keep_cbr_original is False
    assert config.theme == "system"
    assert path.read_bytes() == before


def test_unknown_key_survives_a_theme_change(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('theme = "dark"\ncustom = "keep"\n', encoding="utf-8")
    config = load_config(path)
    updated = apply_put(config, {"theme": "light"})
    save_config(path, updated)
    saved = tomllib.loads(path.read_text(encoding="utf-8"))
    assert saved["custom"] == "keep"
    assert saved["theme"] == "light"
    neon = apply_put(updated, {"theme": "neon"})
    assert neon.theme == "system"
    languages = apply_put(config, {"title_languages": ["fr", 1, "ja"]})
    assert languages.title_languages == ["fr", "ja"]
    empty = apply_put(config, {"title_languages": []})
    assert empty.title_languages == []


def test_invalid_toml_names_the_path(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("theme = [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="could not be parsed") as raised:
        load_config(path)
    assert str(path) in str(raised.value)


def test_put_rejects_wrong_json_types(tmp_path: Path) -> None:
    config = load_config(tmp_path / "config.toml")
    with pytest.raises(ConfigError):
        apply_put(config, {"library_roots": "/books"})
    with pytest.raises(ConfigError):
        apply_put(config, {"keep_cbr_original": "yes"})
    with pytest.raises(ConfigError):
        apply_put(config, {"comicvine_api_key": 5})
    with pytest.raises(ConfigError):
        apply_put(config, {"nautiljon_base_url": 5})
    with pytest.raises(ConfigError):
        apply_put(config, {"nautiljon_api_key": 5})
    with pytest.raises(ConfigError):
        apply_put(config, {"title_languages": "fr"})


def test_app_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    linux = app_paths("linux", {}, home)
    assert linux.config == home / ".config" / "manga-tagger" / "config.toml"
    assert linux.index == home / ".local" / "share" / "manga-tagger" / "index.db"
    assert linux.thumbnails == home / ".cache" / "manga-tagger" / "covers"

    xdg = tmp_path / "xdg"
    replaced = app_paths(
        "linux",
        {"XDG_CONFIG_HOME": str(xdg), "XDG_DATA_HOME": "relative"},
        home,
    )
    assert replaced.config == xdg / "manga-tagger" / "config.toml"
    assert replaced.index == linux.index
    assert replaced.thumbnails == linux.thumbnails

    other = app_paths("freebsd", {}, home)
    assert other.config == linux.config

    mac = app_paths("darwin", {}, home)
    assert mac.config == (
        home / "Library" / "Application Support" / "manga-tagger" / "config.toml"
    )
    assert mac.index == (
        home / "Library" / "Application Support" / "manga-tagger" / "index.db"
    )
    assert mac.thumbnails == home / "Library" / "Caches" / "manga-tagger" / "covers"

    windows = app_paths("win32", {}, home)
    assert windows.config == (
        home / "AppData" / "Roaming" / "manga-tagger" / "config.toml"
    )
    assert windows.index == home / "AppData" / "Roaming" / "manga-tagger" / "index.db"
    assert windows.thumbnails == home / "AppData" / "Local" / "manga-tagger" / "covers"
    appdata = tmp_path / "Roaming"
    local = tmp_path / "Local"
    custom = app_paths(
        "win32",
        {"APPDATA": str(appdata), "LOCALAPPDATA": str(local)},
        home,
    )
    assert custom.config == appdata / "manga-tagger" / "config.toml"
    assert custom.index == appdata / "manga-tagger" / "index.db"
    assert custom.thumbnails == local / "manga-tagger" / "covers"
    blank = app_paths("linux", {"XDG_CONFIG_HOME": "  "}, home)
    assert blank.config == linux.config
