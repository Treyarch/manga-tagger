"""MyAnimeList search and series load through Jikan."""

from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.constants import RESULT_LIMIT
from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service_types import Candidate
from manga_tagger.providers.text import (
    catalog_id,
    count_text,
    first_url,
    has_word,
    jikan_title,
    join_names,
    nonblank,
    plain_summary,
    put,
    year_text,
)

_SEARCH_URL = "https://api.tenrai.org/v1/manga"
_WRITER = frozenset({"story"})
_ART = frozenset({"art", "artist"})


def search(
    query: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return Jikan manga candidates for ``query``."""
    body = send(
        client,
        "jikan",
        "GET",
        _SEARCH_URL,
        params=[
            ("q", query),
            ("limit", str(RESULT_LIMIT)),
            ("sfw", "false"),
        ],
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
    """Return a ComicInfo patch for one Jikan manga."""
    body = send(
        client,
        "jikan",
        "GET",
        f"{_SEARCH_URL}/{match_id}/full",
        cancel=cancel,
    )
    data = _load_data(body)
    chosen = jikan_title(data.get("titles"), title_languages)
    if chosen is None:
        raise ProviderResponseError("jikan: record has no usable title")
    title, language = chosen
    patch: dict[str, str] = {
        "Series": title,
        "Title": title,
        "Manga": "YesAndRightToLeft",
    }
    put(patch, "LanguageISO", language)
    put(patch, "Publisher", _publisher(data.get("serializations")))
    put(patch, "Genre", join_names(_genre_names(data.get("genres"))))
    put(patch, "Summary", plain_summary(data.get("synopsis")))
    put(patch, "Web", nonblank(data.get("url")))
    put(patch, "Count", count_text(data.get("volumes")) or None)
    _dates(patch, data)
    writers, artists = _credits(data.get("authors"))
    put(patch, "Writer", join_names(writers))
    artist_text = join_names(artists)
    put(patch, "Penciller", artist_text)
    put(patch, "CoverArtist", artist_text)
    return patch


def _search_data(body: object) -> list[object]:
    if not isinstance(body, dict) or "data" not in body:
        raise ProviderResponseError("jikan: search data was missing")
    data = body["data"]
    if data == []:
        return []
    if not isinstance(data, list):
        raise ProviderResponseError("jikan: search data was not a list")
    return data


def _load_data(body: object) -> dict[str, object]:
    if not isinstance(body, dict) or "data" not in body:
        raise ProviderResponseError("jikan: load data was missing")
    data = body["data"]
    if not isinstance(data, dict):
        raise ProviderResponseError("jikan: load data was not an object")
    return data


def _candidate(item: object, languages: Sequence[str]) -> Candidate | None:
    if not isinstance(item, dict):
        return None
    identity = catalog_id(item.get("mal_id"))
    if identity is None:
        return None
    chosen = jikan_title(item.get("titles"), languages)
    if chosen is None:
        return None
    title, _language = chosen
    source = _published_from(item)
    year = source.get("year") if source is not None else None
    authors = item.get("authors")
    credit = None
    if isinstance(authors, list) and authors and isinstance(authors[0], dict):
        credit = authors[0].get("name")
    return Candidate(
        id=identity,
        title=title,
        year=year_text(year),
        credit=nonblank(credit) or "",
        count=count_text(item.get("volumes"), item.get("chapters")),
        summary=plain_summary(item.get("synopsis")) or "",
        cover=_cover_url(item),
    )


def _cover_url(item: dict[str, object]) -> str:
    images = item.get("images")
    if not isinstance(images, dict):
        return ""
    jpg = images.get("jpg")
    if not isinstance(jpg, dict):
        return ""
    return first_url(jpg.get("image_url"), jpg.get("small_image_url"))


def _publisher(serializations: object) -> str | None:
    if not isinstance(serializations, list) or not serializations:
        return None
    first = serializations[0]
    if not isinstance(first, dict):
        return None
    return nonblank(first.get("name"))


def _genre_names(genres: object) -> list[str]:
    if not isinstance(genres, list):
        return []
    names: list[str] = []
    for genre in genres:
        if isinstance(genre, dict):
            name = nonblank(genre.get("name"))
            if name:
                names.append(name)
    return names


def _dates(patch: dict[str, str], data: dict[str, object]) -> None:
    source = _published_from(data)
    if source is None:
        return
    for key, field in (("year", "Year"), ("month", "Month"), ("day", "Day")):
        rendered = _component(source.get(key))
        if rendered is not None:
            patch[field] = rendered


def _published_from(data: dict[str, object]) -> dict[str, object] | None:
    published = data.get("published")
    if not isinstance(published, dict):
        return None
    prop = published.get("prop")
    if not isinstance(prop, dict):
        return None
    source = prop.get("from")
    if not isinstance(source, dict):
        return None
    return source


def _component(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    return nonblank(value)


def _credits(authors: object) -> tuple[list[str], list[str]]:
    if not isinstance(authors, list):
        return [], []
    writers: list[str] = []
    artists: list[str] = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        name = nonblank(author.get("name"))
        if not name:
            continue
        role = author.get("type")
        if has_word(role, _WRITER):
            writers.append(name)
        if has_word(role, _ART):
            artists.append(name)
    return writers, artists
