"""AniList search and series load."""

from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service_types import Candidate
from manga_tagger.providers.text import (
    anilist_title,
    catalog_id,
    count_text,
    first_url,
    has_word,
    integer_text,
    join_names,
    nonblank,
    plain_summary,
    put,
    year_text,
)

_URL = "https://graphql.anilist.co"
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
_WRITER = frozenset({"story", "creator"})
_ART = frozenset({"art", "artist", "illustration", "illustrator"})

_SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      coverImage { large }
      startDate { year }
      volumes
      chapters
      description
      staff(perPage: 1, sort: RELEVANCE) {
        edges { node { name { full } } }
      }
    }
  }
}
""".strip()

_LOAD_QUERY = """
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    id
    title { romaji english native }
    description
    genres
    siteUrl
    volumes
    countryOfOrigin
    startDate { year month day }
    staff(perPage: 25, sort: RELEVANCE) {
      edges { role node { name { full } } }
    }
  }
}
""".strip()


def search(
    query: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return AniList manga candidates for ``query``."""
    body = _post(
        client,
        {"query": _SEARCH_QUERY, "variables": {"search": query}},
        cancel,
    )
    media = _search_media(body)
    candidates: list[Candidate] = []
    for item in media:
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
    """Return a ComicInfo patch for one AniList manga."""
    body = _post(
        client,
        {"query": _LOAD_QUERY, "variables": {"id": int(match_id)}},
        cancel,
    )
    media = _load_media(body)
    chosen = anilist_title(
        media.get("title"), title_languages, media.get("countryOfOrigin")
    )
    if chosen is None:
        raise ProviderResponseError("anilist: record has no usable title")
    title, language = chosen
    patch: dict[str, str] = {
        "Series": title,
        "Title": title,
        "Manga": "YesAndRightToLeft",
    }
    put(patch, "LanguageISO", language)
    put(patch, "Genre", join_names(_strings(media.get("genres"))))
    put(patch, "Summary", plain_summary(media.get("description")))
    put(patch, "Web", nonblank(media.get("siteUrl")))
    put(patch, "Count", count_text(media.get("volumes")) or None)
    _dates(patch, media.get("startDate"))
    writers, artists = _credits(_staff(media))
    put(patch, "Writer", join_names(writers))
    artist_text = join_names(artists)
    put(patch, "Penciller", artist_text)
    put(patch, "CoverArtist", artist_text)
    return patch


def _post(
    client: httpx.Client,
    json_body: dict[str, object],
    cancel: Callable[[], bool] | None,
) -> object:
    body = send(
        client,
        "anilist",
        "POST",
        _URL,
        json_body=json_body,
        extra_headers=_HEADERS,
        cancel=cancel,
    )
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            raise ProviderResponseError("anilist: response contained errors")
    return body


def _search_media(body: object) -> list[object]:
    if not isinstance(body, dict):
        raise ProviderResponseError("anilist: search body was not an object")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ProviderResponseError("anilist: search data was missing")
    page = data.get("Page")
    if not isinstance(page, dict) or "media" not in page:
        raise ProviderResponseError("anilist: search media was missing")
    media = page["media"]
    if media is None or media == []:
        return []
    if not isinstance(media, list):
        raise ProviderResponseError("anilist: search media was not a list")
    return media


def _load_media(body: object) -> dict[str, object]:
    if not isinstance(body, dict):
        raise ProviderResponseError("anilist: load body was not an object")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ProviderResponseError("anilist: load data was missing")
    media = data.get("Media")
    if not isinstance(media, dict):
        raise ProviderResponseError("anilist: load record was missing")
    return media


def _candidate(item: object, languages: Sequence[str]) -> Candidate | None:
    if not isinstance(item, dict):
        return None
    identity = catalog_id(item.get("id"))
    if identity is None:
        return None
    chosen = anilist_title(item.get("title"), languages, item.get("countryOfOrigin"))
    if chosen is None:
        return None
    title, _language = chosen
    start = item.get("startDate")
    year = start.get("year") if isinstance(start, dict) else None
    cover_image = item.get("coverImage")
    cover = ""
    if isinstance(cover_image, dict):
        cover = first_url(cover_image.get("large"))
    return Candidate(
        id=identity,
        title=title,
        year=year_text(year),
        credit=nonblank(_first_staff_name(item)) or "",
        count=count_text(item.get("volumes"), item.get("chapters")),
        summary=plain_summary(item.get("description")) or "",
        cover=cover,
    )


def _first_staff_name(item: dict[str, object]) -> str | None:
    for _role, name in _staff(item):
        return name
    return None


def _staff(item: dict[str, object]) -> list[tuple[str, str]]:
    staff = item.get("staff")
    if not isinstance(staff, dict):
        return []
    edges = staff.get("edges")
    if not isinstance(edges, list):
        return []
    found: list[tuple[str, str]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if not isinstance(node, dict):
            continue
        name_obj = node.get("name")
        if not isinstance(name_obj, dict):
            continue
        full = nonblank(name_obj.get("full"))
        if not full:
            continue
        role = edge.get("role")
        found.append((role if isinstance(role, str) else "", full))
    return found


def _credits(staff: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    writers: list[str] = []
    artists: list[str] = []
    for role, name in staff:
        if has_word(role, _WRITER):
            writers.append(name)
        if has_word(role, _ART):
            artists.append(name)
    return writers, artists


def _dates(patch: dict[str, str], start: object) -> None:
    if not isinstance(start, dict):
        return
    year = integer_text(start.get("year"))
    month = integer_text(start.get("month"))
    day = integer_text(start.get("day"))
    if year is not None:
        patch["Year"] = year
    if month is not None:
        patch["Month"] = month
    if day is not None:
        patch["Day"] = day


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
