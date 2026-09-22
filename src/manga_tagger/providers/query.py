"""Search text and tankōbon number parsed from a filename stem."""

import re
from dataclasses import dataclass

_ASCII_SPACE = re.compile(r"[ \t\r\n\f\v]+")
_SEPARATORS = " ._-"
_SEP = r"[ ._-]"
_NUMBER = r"(\d+(?:\.\d+)?)"
_PAREN_TAGS = frozenset(
    {
        "digital",
        "digital-hd",
        "web",
        "c2c",
        "raw",
        "fixed",
        "fr",
        "en",
        "jp",
        "jap",
        "vf",
        "vo",
    }
)

# Longer chapter words come first so "chapter" is not read as "ch".
_CHAPTER = re.compile(
    rf"(?:^|{_SEP})(?:chapter|chapitre|chap|ch)\.?(?:{_SEP})*{_NUMBER}$",
    re.IGNORECASE,
)
# ``vol`` before bare ``v``, and ``tome`` before bare ``t``.
_VOLUME = (
    re.compile(
        rf"(?:^|{_SEP})(?:volume|vol)\.?(?:{_SEP})*{_NUMBER}$",
        re.IGNORECASE,
    ),
    re.compile(rf"(?:^|{_SEP})tome\.?(?:{_SEP})*{_NUMBER}$", re.IGNORECASE),
    re.compile(rf"(?:^|{_SEP})v(?:{_SEP})*{_NUMBER}$", re.IGNORECASE),
    re.compile(rf"(?:^|{_SEP})t\.?(?:{_SEP})*{_NUMBER}$", re.IGNORECASE),
    re.compile(rf"(?:^|{_SEP})#(?:{_SEP})*{_NUMBER}$", re.IGNORECASE),
    re.compile(rf"{_SEP}{_NUMBER}$"),
)


@dataclass(frozen=True)
class _ParsedStem:
    query: str
    number: str | None


def build_query(series: str, filename_stem: str) -> str:
    """Return the catalog search string.

    Args:
        series: Existing series title. A non-blank value is trimmed and used
            as-is, including any digits.
        filename_stem: Filename with its extension already removed.

    Returns:
        The trimmed series, or the stem after release tags and one volume or
        chapter suffix are removed.
    """
    stripped = series.strip()
    if stripped:
        return stripped
    return _parse_stem(filename_stem).query


def parse_number(filename_stem: str) -> str | None:
    """Return the tankōbon number stored for ``filename_stem``.

    Args:
        filename_stem: Filename with its extension already removed.

    Returns:
        The number with leading zeros removed from the integer part, or
        ``None`` when the stem has no volume marker. A chapter suffix returns
        ``None``.
    """
    return _parse_stem(filename_stem).number


def _parse_stem(filename_stem: str) -> _ParsedStem:
    stripped = _strip_tags(filename_stem)
    chapter = _CHAPTER.search(stripped)
    if chapter is not None:
        return _ParsedStem(_remainder(stripped, chapter), None)
    for pattern in _VOLUME:
        match = pattern.search(stripped)
        if match is not None:
            return _ParsedStem(_remainder(stripped, match), _normalize(match.group(1)))
    return _ParsedStem(stripped, None)


def _strip_tags(stem: str) -> str:
    text = stem.strip()
    text = _remove_brackets(text)
    text = _remove_release_parens(text)
    return _ASCII_SPACE.sub(" ", text).strip()


def _remove_brackets(text: str) -> str:
    while True:
        updated = _remove_one_bracket(text)
        if updated is None:
            return text
        text = updated


def _remove_one_bracket(text: str) -> str | None:
    start_at = 0
    while True:
        start = text.find("[", start_at)
        if start == -1:
            return None
        end = text.find("]", start + 1)
        if end == -1:
            return None
        interior = text[start + 1 : end]
        if "[" in interior:
            start_at = start + 1
            continue
        return text[:start] + text[end + 1 :]


def _remove_release_parens(text: str) -> str:
    while True:
        updated = _remove_one_release_paren(text)
        if updated is None:
            return text
        text = updated


def _remove_one_release_paren(text: str) -> str | None:
    start_at = 0
    while True:
        start = text.find("(", start_at)
        if start == -1:
            return None
        end = text.find(")", start + 1)
        if end == -1:
            return None
        interior = text[start + 1 : end]
        if "(" in interior:
            start_at = start + 1
            continue
        if _paren_is_tag(interior):
            return text[:start] + text[end + 1 :]
        start_at = end + 1


def _paren_is_tag(interior: str) -> bool:
    trimmed = interior.strip()
    if re.fullmatch(r"\d{4}", trimmed):
        return True
    return trimmed.casefold() in _PAREN_TAGS


def _remainder(text: str, match: re.Match[str]) -> str:
    head = text[: match.start()].rstrip(_SEPARATORS)
    return _ASCII_SPACE.sub(" ", head).strip()


def _normalize(token: str) -> str:
    if "." in token:
        whole, fraction = token.split(".", 1)
        return f"{int(whole)}.{fraction}"
    return str(int(token))
