"""Omarchy palette parsing."""

from pathlib import Path

import pytest

from manga_tagger.theme import omarchy_colors_path, read_omarchy_theme


PALETTE = """\
mode = "dark"
background = "#05182e"
dark_background = "#031222"
lighter_background = "#0a2540"
foreground = "#f6dcac"
dark_foreground = "#3f8f8a"
accent = "#faa968"
selection = "#134e5a"
red = "#f85525"
yellow = "#e97b3c"
orange = "#faa968"
"""


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_reads_complete_palette_and_normalizes_hex(tmp_path: Path, mode: str) -> None:
    path = tmp_path / "colors.toml"
    path.write_text(
        PALETTE.replace('mode = "dark"', f'mode = "{mode}"').replace(
            "#faa968", "#FAA968"
        ),
        encoding="utf-8",
    )
    theme = read_omarchy_theme(path)
    assert theme is not None
    assert theme.mode == mode
    assert theme.background == "#05182e"
    assert theme.accent == "#faa968"
    assert theme.to_dict()["orange"] == "#faa968"


@pytest.mark.parametrize(
    "text",
    [
        "mode = [",
        PALETTE.replace('mode = "dark"', 'mode = "sepia"'),
        PALETTE.replace('accent = "#faa968"\n', ""),
        PALETTE.replace("#faa968", "rgb(250, 169, 104)"),
        PALETTE.replace('red = "#f85525"', "red = 12"),
    ],
)
def test_invalid_or_incomplete_palette_is_unavailable(
    tmp_path: Path, text: str
) -> None:
    path = tmp_path / "colors.toml"
    path.write_text(text, encoding="utf-8")
    assert read_omarchy_theme(path) is None


def test_missing_palette_is_unavailable(tmp_path: Path) -> None:
    assert read_omarchy_theme(tmp_path / "missing.toml") is None
    assert omarchy_colors_path(tmp_path) == (
        tmp_path / ".local/state/omarchy/current/theme/colors.toml"
    )
