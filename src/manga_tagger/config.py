"""Resolve app paths and read or write the TOML config file."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import tomli_w

_KNOWN_KEYS = (
    "library_roots",
    "keep_cbr_original",
    "comicvine_api_key",
    "nautiljon_base_url",
    "nautiljon_api_key",
    "title_languages",
    "theme",
)
_THEMES = frozenset({"system", "light", "dark"})
_DEFAULT_LANGUAGES = ["fr", "en"]


class ConfigError(Exception):
    """The TOML file cannot be parsed, or a PUT value has the wrong JSON type."""


@dataclass
class AppPaths:
    """Config file, index file, and thumbnail directory for this platform."""

    config: Path
    index: Path
    thumbnails: Path


@dataclass
class AppConfig:
    """The seven known keys plus unknown keys from the last successful load."""

    path: Path
    library_roots: list[str] = field(default_factory=list)
    keep_cbr_original: bool = False
    comicvine_api_key: str = ""
    nautiljon_base_url: str = ""
    nautiljon_api_key: str = ""
    title_languages: list[str] = field(default_factory=lambda: list(_DEFAULT_LANGUAGES))
    theme: str = "system"
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return the seven known keys."""
        return {
            "library_roots": list(self.library_roots),
            "keep_cbr_original": self.keep_cbr_original,
            "comicvine_api_key": self.comicvine_api_key,
            "nautiljon_base_url": self.nautiljon_base_url,
            "nautiljon_api_key": self.nautiljon_api_key,
            "title_languages": list(self.title_languages),
            "theme": self.theme,
        }


def app_paths(platform: str, env: Mapping[str, str], home: Path) -> AppPaths:
    """Return the config, index, and thumbnail paths for ``platform``.

    Args:
        platform: ``sys.platform``, such as ``linux``, ``darwin``, or ``win32``.
        env: Environment values. A blank or relative path variable is ignored.
        home: The user's home directory.

    Returns:
        Absolute paths. This function does not read the process environment.
    """
    home = Path(home)
    if platform == "darwin":
        support = home / "Library" / "Application Support" / "manga-tagger"
        return AppPaths(
            config=support / "config.toml",
            index=support / "index.db",
            thumbnails=home / "Library" / "Caches" / "manga-tagger" / "covers",
        )
    if platform == "win32":
        roaming = _env_dir(env, "APPDATA") or (home / "AppData" / "Roaming")
        local = _env_dir(env, "LOCALAPPDATA") or (home / "AppData" / "Local")
        config_dir = roaming / "manga-tagger"
        return AppPaths(
            config=config_dir / "config.toml",
            index=config_dir / "index.db",
            thumbnails=local / "manga-tagger" / "covers",
        )
    config_root = _env_dir(env, "XDG_CONFIG_HOME") or (home / ".config")
    data_root = _env_dir(env, "XDG_DATA_HOME") or (home / ".local" / "share")
    cache_root = _env_dir(env, "XDG_CACHE_HOME") or (home / ".cache")
    return AppPaths(
        config=config_root / "manga-tagger" / "config.toml",
        index=data_root / "manga-tagger" / "index.db",
        thumbnails=cache_root / "manga-tagger" / "covers",
    )


def load_config(path: Path) -> AppConfig:
    """Read UTF-8 TOML. A missing file returns defaults and is not created.

    Args:
        path: Config file path.

    Returns:
        Known keys after the load fallbacks, plus unknown keys.

    Raises:
        ConfigError: The file exists and the TOML could not be parsed.
    """
    if not path.exists():
        return AppConfig(path=path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: the TOML could not be parsed") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the TOML could not be parsed")
    extra = {key: value for key, value in data.items() if key not in _KNOWN_KEYS}
    roots = data.get("library_roots", [])
    languages = data.get("title_languages", list(_DEFAULT_LANGUAGES))
    return AppConfig(
        path=path,
        library_roots=_clean_roots(roots) if isinstance(roots, list) else [],
        keep_cbr_original=(
            data["keep_cbr_original"]
            if isinstance(data.get("keep_cbr_original"), bool)
            else False
        ),
        comicvine_api_key=(
            data["comicvine_api_key"]
            if isinstance(data.get("comicvine_api_key"), str)
            else ""
        ),
        nautiljon_base_url=(
            data["nautiljon_base_url"]
            if isinstance(data.get("nautiljon_base_url"), str)
            else ""
        ),
        nautiljon_api_key=(
            data["nautiljon_api_key"]
            if isinstance(data.get("nautiljon_api_key"), str)
            else ""
        ),
        title_languages=_clean_languages(languages, fallback=True),
        theme=_load_theme(data.get("theme", "system")),
        extra=extra,
    )


def save_config(path: Path, config: AppConfig) -> None:
    """Create the parent directory and write UTF-8 TOML.

    Unknown keys from the last load are written back. Comments are not kept.

    Args:
        path: Destination. A failed write leaves an existing file unchanged.
        config: Config to store.
    """
    payload: dict[str, object] = config.to_dict()
    payload.update(config.extra)
    text = tomli_w.dumps(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def apply_put(config: AppConfig, updates: Mapping[str, object]) -> AppConfig:
    """Return config with a partial PUT applied. Does not touch the file.

    Args:
        config: In-memory config. Omitted keys stay.
        updates: Keys the client sent.

    Returns:
        A new config. ``library_roots`` replaces that list wholesale.

    Raises:
        ConfigError: A provided value has the wrong JSON type.
    """
    current = config.to_dict()
    for key, value in updates.items():
        if key not in _KNOWN_KEYS:
            continue
        current[key] = _put_value(key, value)
    return AppConfig(
        path=config.path,
        library_roots=list(current["library_roots"]),  # type: ignore[arg-type]
        keep_cbr_original=bool(current["keep_cbr_original"]),
        comicvine_api_key=str(current["comicvine_api_key"]),
        nautiljon_base_url=str(current["nautiljon_base_url"]),
        nautiljon_api_key=str(current["nautiljon_api_key"]),
        title_languages=list(current["title_languages"]),  # type: ignore[arg-type]
        theme=str(current["theme"]),
        extra=dict(config.extra),
    )


def _put_value(key: str, value: object) -> object:
    if key == "library_roots":
        if not isinstance(value, list):
            raise ConfigError("library_roots must be a list")
        return _clean_roots(value)
    if key == "keep_cbr_original":
        if not isinstance(value, bool):
            raise ConfigError("keep_cbr_original must be a boolean")
        return value
    if key == "comicvine_api_key":
        if not isinstance(value, str):
            raise ConfigError("comicvine_api_key must be a string")
        return value
    if key == "nautiljon_base_url":
        if not isinstance(value, str):
            raise ConfigError("nautiljon_base_url must be a string")
        return value
    if key == "nautiljon_api_key":
        if not isinstance(value, str):
            raise ConfigError("nautiljon_api_key must be a string")
        return value
    if key == "title_languages":
        if not isinstance(value, list):
            raise ConfigError("title_languages must be a list")
        return _clean_languages(value, fallback=False)
    if isinstance(value, str) and value in _THEMES:
        return value
    return "system"


def _clean_roots(values: list[object]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        path = Path(item)
        if not path.is_absolute():
            continue
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        kept.append(resolved)
    return kept


def _clean_languages(values: object, *, fallback: bool) -> list[str]:
    if not isinstance(values, list):
        return list(_DEFAULT_LANGUAGES) if fallback else []
    return [item for item in values if isinstance(item, str)]


def _load_theme(value: object) -> str:
    if not isinstance(value, str):
        return "system"
    return value


def _env_dir(env: Mapping[str, str], key: str) -> Path | None:
    raw = env.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    path = Path(text)
    if not path.is_absolute():
        return None
    return path
