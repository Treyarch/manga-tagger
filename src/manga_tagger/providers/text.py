"""Shared title, summary, credit, and date formatting."""

import html
import re

_WORD = re.compile(r"[^\W_]+", flags=re.UNICODE)
_WHITESPACE = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]*>")

_COUNTRY_LANGUAGE = {"JP": "ja", "KR": "ko", "CN": "zh", "TW": "zh"}
_JIKAN_SLOTS = {"fr": "French", "en": "English"}
_JIKAN_LANGUAGE = {"French": "fr", "English": "en", "Japanese": "ja"}


def plain_summary(value: object) -> str | None:
    """Return HTML-stripped summary text, or ``None`` when it is empty."""
    if not isinstance(value, str):
        return None
    text = html.unescape(value).replace("\u00a0", " ")
    text = _TAG.sub("", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text or None


def join_names(names: list[str]) -> str | None:
    """Join credit or genre names in order, skipping blanks and repeats."""
    unique: list[str] = []
    for name in names:
        if not isinstance(name, str):
            continue
        cleaned = name.strip()
        if not cleaned or cleaned in unique:
            continue
        unique.append(cleaned)
    if not unique:
        return None
    return ", ".join(unique)


def has_word(role: object, words: frozenset[str]) -> bool:
    """Return whether ``role`` contains one of ``words`` as a whole word."""
    if not isinstance(role, str):
        return False
    tokens = {token.casefold() for token in _WORD.findall(role)}
    return any(word.casefold() in tokens for word in words)


def role_pieces(role: object) -> set[str]:
    """Return Comic Vine role pieces split on commas."""
    if not isinstance(role, str):
        return set()
    return {piece.strip().casefold() for piece in role.split(",") if piece.strip()}


def nonblank(value: object) -> str | None:
    """Return a stripped string, or ``None`` when ``value`` is not usable text."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def integer_text(value: object) -> str | None:
    """Return a decimal string for an integer, without zero padding."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return str(value)


def detail_text(year: object, credit: object) -> str:
    """Join the year and the first credit that the search payload has."""
    parts: list[str] = []
    rendered_year = _detail_year(year)
    if rendered_year:
        parts.append(rendered_year)
    rendered_credit = nonblank(credit)
    if rendered_credit:
        parts.append(rendered_credit)
    return ", ".join(parts)


def catalog_id(value: object) -> str | None:
    """Return a catalog id as a string."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    return nonblank(value)


def put(patch: dict[str, str], key: str, value: str | None) -> None:
    """Store ``value`` when it is non-blank."""
    if value:
        patch[key] = value


def anilist_title(
    title: object, languages: list[str] | tuple[str, ...], country: object
) -> tuple[str, str | None] | None:
    """Return AniList's preferred title and optional ``LanguageISO`` code."""
    if not isinstance(title, dict):
        return None
    for code in languages:
        if code != "en":
            continue
        english = nonblank(title.get("english"))
        if english:
            return english, "en"
    native = nonblank(title.get("native"))
    if native:
        language = _COUNTRY_LANGUAGE.get(country) if isinstance(country, str) else None
        return native, language
    romaji = nonblank(title.get("romaji"))
    if romaji:
        return romaji, None
    return None


def jikan_title(
    titles: object, languages: list[str] | tuple[str, ...]
) -> tuple[str, str | None] | None:
    """Return Jikan's preferred title and optional ``LanguageISO`` code."""
    if not isinstance(titles, list):
        return None

    def find(type_name: str) -> str | None:
        for item in titles:
            if not isinstance(item, dict) or item.get("type") != type_name:
                continue
            found = nonblank(item.get("title"))
            if found:
                return found
        return None

    for code in languages:
        slot = _JIKAN_SLOTS.get(code)
        if slot is None:
            continue
        found = find(slot)
        if found:
            return found, _JIKAN_LANGUAGE[slot]
    for type_name in ("Japanese", "Default"):
        found = find(type_name)
        if found:
            return found, _JIKAN_LANGUAGE.get(type_name)
    return None


def _detail_year(year: object) -> str | None:
    if isinstance(year, bool):
        return None
    if isinstance(year, int):
        return str(year)
    return nonblank(year)
