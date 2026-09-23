"""MangaDex search and series load."""

from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.constants import RESULT_LIMIT
from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service_types import Candidate
from manga_tagger.providers.text import (
    catalog_id,
    count_text,
    integer_text,
    join_names,
    nonblank,
    plain_summary,
    put,
    year_text,
)

_BASE = "https://api.mangadex.org"
_CONTENT_RATINGS = ("safe", "suggestive", "erotica", "pornographic")


def search(
    query: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return MangaDex candidates for ``query``."""
    params = [
        ("title", query),
        ("limit", str(RESULT_LIMIT)),
        ("order[relevance]", "desc"),
    ]
    params.extend(("contentRating[]", rating) for rating in _CONTENT_RATINGS)
    params.append(("includes[]", "author"))
    params.append(("includes[]", "cover_art"))
    body = send(
        client,
        "mangadex",
        "GET",
        f"{_BASE}/manga",
        params=params,
        cancel=cancel,
    )
    data = _search_data(body)
    candidates: list[Candidate] = []
    for item in data:
        candidate = _candidate(item, title_languages)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def load(
    match_id: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a ComicInfo patch for one MangaDex series."""
    body = send(
        client,
        "mangadex",
        "GET",
        f"{_BASE}/manga/{match_id}",
        params=[("includes[]", "author"), ("includes[]", "artist")],
        cancel=cancel,
    )
    if not isinstance(body, dict) or body.get("result") != "ok":
        raise ProviderResponseError("mangadex: load result was not ok")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ProviderResponseError("mangadex: load record was missing")
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}
    chosen = _choose_title(attributes, title_languages)
    if chosen is None:
        raise ProviderResponseError("mangadex: record has no usable title")
    title, language = chosen
    patch = {
        "Series": title,
        "Title": title,
        "LanguageISO": language,
        "Web": f"https://mangadex.org/title/{match_id}",
        "Manga": "YesAndRightToLeft",
    }
    relationships = data.get("relationships")
    if not isinstance(relationships, list):
        relationships = []
    put(patch, "Writer", join_names(_names(relationships, "author")))
    artists = join_names(_names(relationships, "artist"))
    put(patch, "Penciller", artists)
    put(patch, "CoverArtist", artists)
    put(patch, "Genre", join_names(_genres(attributes.get("tags"))))
    put(
        patch,
        "Summary",
        plain_summary(_description(attributes, title_languages)),
    )
    year = integer_text(attributes.get("year"))
    if year is not None:
        patch["Year"] = year
    return patch


def _search_data(body: object) -> list[object]:
    if not isinstance(body, dict) or "data" not in body:
        raise ProviderResponseError("mangadex: search data was missing")
    data = body["data"]
    if data == []:
        return []
    if not isinstance(data, list):
        raise ProviderResponseError("mangadex: search data was not a list")
    return data


def _candidate(item: object, languages: Sequence[str]) -> Candidate | None:
    if not isinstance(item, dict):
        return None
    identity = catalog_id(item.get("id"))
    attributes = item.get("attributes")
    if identity is None or not isinstance(attributes, dict):
        return None
    chosen = _choose_title(attributes, languages)
    if chosen is None:
        return None
    title, _language = chosen
    relationships = item.get("relationships")
    if not isinstance(relationships, list):
        relationships = []
    authors = _names(relationships, "author")
    credit = authors[0] if authors else None
    return Candidate(
        id=identity,
        title=title,
        year=year_text(integer_text(attributes.get("year"))),
        credit=nonblank(credit) or "",
        count=count_text(attributes.get("lastVolume")),
        summary=plain_summary(_description(attributes, languages)) or "",
        cover=_cover_url(identity, relationships),
    )


def _cover_url(manga_id: str, relationships: list[object]) -> str:
    chosen: str | None = None
    for item in relationships:
        if not isinstance(item, dict) or item.get("type") != "cover_art":
            continue
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            continue
        filename = nonblank(attributes.get("fileName"))
        if filename is None:
            continue
        url = f"https://uploads.mangadex.org/covers/{manga_id}/{filename}.256.jpg"
        volume = attributes.get("volume")
        if volume is None or nonblank(volume) is None:
            return url
        if chosen is None:
            chosen = url
    return chosen or ""


def _choose_title(
    attributes: dict[str, object], languages: Sequence[str]
) -> tuple[str, str] | None:
    for code in languages:
        found = _lookup(attributes, code)
        if found:
            return found, code
    original = attributes.get("originalLanguage")
    if isinstance(original, str) and original:
        found = _lookup(attributes, original)
        if found:
            return found, original
    title_map = attributes.get("title")
    if isinstance(title_map, dict):
        for code, value in title_map.items():
            text = nonblank(value)
            if text:
                return text, str(code)
    return None


def _lookup(attributes: dict[str, object], code: str) -> str | None:
    title_map = attributes.get("title")
    if isinstance(title_map, dict):
        found = nonblank(title_map.get(code))
        if found:
            return found
    alt_titles = attributes.get("altTitles")
    if isinstance(alt_titles, list):
        for entry in alt_titles:
            if isinstance(entry, dict):
                found = nonblank(entry.get(code))
                if found:
                    return found
    return None


def _description(attributes: dict[str, object], languages: Sequence[str]) -> str | None:
    description = attributes.get("description")
    if not isinstance(description, dict):
        return None

    def take(code: str) -> str | None:
        return nonblank(description.get(code))

    for code in languages:
        found = take(code)
        if found:
            return found
    original = attributes.get("originalLanguage")
    if isinstance(original, str) and original:
        found = take(original)
        if found:
            return found
    english = take("en")
    if english:
        return english
    for value in description.values():
        found = nonblank(value)
        if found:
            return found
    return None


def _genres(tags: object) -> list[str]:
    if not isinstance(tags, list):
        return []
    names: list[str] = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        attributes = tag.get("attributes")
        if not isinstance(attributes, dict) or attributes.get("group") != "genre":
            continue
        label = _tag_label(attributes.get("name"))
        if label:
            names.append(label)
    return names


def _tag_label(name: object) -> str | None:
    if not isinstance(name, dict):
        return None
    english = nonblank(name.get("en"))
    if english:
        return english
    for value in name.values():
        found = nonblank(value)
        if found:
            return found
    return None


def _names(relationships: list[object], rel_type: str) -> list[str]:
    names: list[str] = []
    for item in relationships:
        if not isinstance(item, dict) or item.get("type") != rel_type:
            continue
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            continue
        name = nonblank(attributes.get("name"))
        if name:
            names.append(name)
    return names
