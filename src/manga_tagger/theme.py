"""Read the active Omarchy palette without modifying desktop state."""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path


_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_COLOR_FIELDS = (
    "background",
    "dark_background",
    "lighter_background",
    "foreground",
    "dark_foreground",
    "accent",
    "selection",
    "red",
    "yellow",
    "orange",
)


@dataclass(frozen=True)
class SystemTheme:
    """The semantic colors Manga Tagger consumes from Omarchy."""

    mode: str
    background: str
    dark_background: str
    lighter_background: str
    foreground: str
    dark_foreground: str
    accent: str
    selection: str
    red: str
    yellow: str
    orange: str

    def to_dict(self) -> dict[str, str]:
        """Return the JSON-compatible API representation."""
        return asdict(self)


def omarchy_colors_path(home: Path) -> Path:
    """Return Omarchy's generated active-palette path for ``home``."""
    return home / ".local" / "state" / "omarchy" / "current" / "theme" / "colors.toml"


def read_omarchy_theme(path: Path) -> SystemTheme | None:
    """Read a complete canonical Omarchy palette, or return ``None``.

    Omarchy generates this file before exposing a theme as current. Invalid or
    incomplete user themes must not prevent Manga Tagger from starting.
    """
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return None
    mode = data.get("mode")
    if mode not in {"light", "dark"}:
        return None
    colors: dict[str, str] = {}
    for field in _COLOR_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or _HEX_COLOR.fullmatch(value) is None:
            return None
        colors[field] = value.lower()
    return SystemTheme(mode=mode, **colors)


def read_system_theme() -> SystemTheme | None:
    """Read the active supported desktop palette for this process."""
    if not sys.platform.startswith("linux"):
        return None
    return read_omarchy_theme(omarchy_colors_path(Path.home()))
