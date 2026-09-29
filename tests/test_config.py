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
    assert config.excluded_folders == []
    assert config.scan_subfolders is True
    assert config.keep_cbr_original is True
    assert config.write_poster_on_save is True
    assert config.auto_save_metadata_on_switch is False
    assert config.comicvine_api_key == ""
    assert config.nautiljon_base_url == ""
    assert config.nautiljon_api_key == ""
    assert config.title_languages == ["fr", "en"]
    assert config.enabled_providers == [
        "mangadex",
        "anilist",
        "jikan",
        "comicvine",
        "nautiljon",
    ]
    assert config.animate_interface is False
    assert config.theme == "system"
    assert config.extra == {}
    assert not path.exists()
    save_config(path, config)
    saved = tomllib.loads(path.read_text(encoding="utf-8"))
    assert set(saved) == {
        "library_roots",
        "excluded_folders",
        "scan_subfolders",
        "keep_cbr_original",
        "write_poster_on_save",
        "auto_save_metadata_on_switch",
        "comicvine_api_key",
        "nautiljon_base_url",
        "nautiljon_api_key",
        "title_languages",
        "enabled_providers",
        "theme",
        "animate_interface",
    }


def test_relative_root_is_dropped_and_file_is_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'library_roots = ["relative", "/abs", "/abs"]\n'
        'excluded_folders = ["relative-extra", "/abs/Extras", "/abs/Extras"]\n'
        'scan_subfolders = "yes"\n'
        'keep_cbr_original = "no"\n'
        'write_poster_on_save = "no"\n'
        'auto_save_metadata_on_switch = "yes"\n'
        "theme = 1\n",
        encoding="utf-8",
    )
    before = path.read_bytes()
    config = load_config(path)
    assert config.library_roots == [str(Path("/abs").resolve())]
    assert config.excluded_folders == [str(Path("/abs/Extras").resolve())]
    assert config.scan_subfolders is True
    assert config.keep_cbr_original is True
    assert config.write_poster_on_save is True
    assert config.auto_save_metadata_on_switch is False
    assert config.animate_interface is False
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
    providers = apply_put(
        config,
        {"enabled_providers": ["nautiljon", "nope", "nautiljon", 1, "mangadex"]},
    )
    assert providers.enabled_providers == ["nautiljon", "mangadex"]
    none = apply_put(config, {"enabled_providers": []})
    assert none.enabled_providers == []


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
        apply_put(config, {"excluded_folders": "/books/Extras"})
    with pytest.raises(ConfigError):
        apply_put(config, {"scan_subfolders": "yes"})
    with pytest.raises(ConfigError):
        apply_put(config, {"keep_cbr_original": "yes"})
    with pytest.raises(ConfigError):
        apply_put(config, {"write_poster_on_save": "yes"})
    with pytest.raises(ConfigError):
        apply_put(config, {"auto_save_metadata_on_switch": "yes"})
    with pytest.raises(ConfigError):
        apply_put(config, {"comicvine_api_key": 5})
    with pytest.raises(ConfigError):
        apply_put(config, {"nautiljon_base_url": 5})
    with pytest.raises(ConfigError):
        apply_put(config, {"nautiljon_api_key": 5})
    with pytest.raises(ConfigError):
        apply_put(config, {"title_languages": "fr"})
    with pytest.raises(ConfigError):
        apply_put(config, {"enabled_providers": "mangadex"})
    off = apply_put(
        config,
        {
            "keep_cbr_original": False,
            "write_poster_on_save": False,
            "auto_save_metadata_on_switch": True,
            "excluded_folders": ["/books/Extras", "relative"],
            "scan_subfolders": False,
        },
    )
    assert off.keep_cbr_original is False
    assert off.write_poster_on_save is False
    assert off.auto_save_metadata_on_switch is True
    assert off.excluded_folders == [str(Path("/books/Extras").resolve())]
    assert off.scan_subfolders is False


def test_enabled_providers_load_fallbacks(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('enabled_providers = "mangadex"\n', encoding="utf-8")
    config = load_config(path)
    assert config.enabled_providers == [
        "mangadex",
        "anilist",
        "jikan",
        "comicvine",
        "nautiljon",
    ]
    path.write_text("enabled_providers = []\n", encoding="utf-8")
    empty = load_config(path)
    assert empty.enabled_providers == []


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


@pytest.mark.parametrize("value", [True, False])
def test_motion_config_round_trip_and_partial_updates(tmp_path: Path, value: bool) -> None:
    path = tmp_path / "config.toml"
    path.write_text('custom = "preserved"\n', encoding="utf-8")
    config = apply_put(load_config(path), {"animate_interface": value})
    config = apply_put(config, {"theme": "dark"})
    save_config(path, config)
    loaded = load_config(path)
    assert loaded.animate_interface is value
    assert loaded.to_dict()["animate_interface"] is value
    assert loaded.extra == {"custom": "preserved"}


@pytest.mark.parametrize("literal", ['"true"', '1', '[]', '{}'])
def test_motion_invalid_stored_type_defaults_off(tmp_path: Path, literal: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(f"animate_interface = {literal}\n", encoding="utf-8")
    assert load_config(path).animate_interface is False


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
def test_motion_put_rejects_non_booleans(tmp_path: Path, value: object) -> None:
    config = load_config(tmp_path / "config.toml")
    with pytest.raises(ConfigError, match="animate_interface must be a boolean"):
        apply_put(config, {"animate_interface": value})
    assert config.animate_interface is False
