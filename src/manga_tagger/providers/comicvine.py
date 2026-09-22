"""Comic Vine volume search and series load."""

from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.constants import RESULT_LIMIT
from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service_types import Candidate
from manga_tagger.providers.text import (
    catalog_id,
    detail_text,
    join_names,
    nonblank,
    plain_summary,
    put,
    role_pieces,
)

_SEARCH_URL = "https://comicvine.gamespot.com/api/search/"
_VOLUME_URL = "https://comicvine.gamespot.com/api/volume/4050-{match_id}/"
_WRITER = frozenset({"writer"})
_PENCILLER = frozenset({"penciler", "penciller", "artist"})
_INKER = frozenset({"inker"})
_COVER = frozenset({"cover", "cover artist"})


def search(
    query: str,
    *,
    api_key: str,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return Comic Vine volume candidates for ``query``."""
    del title_languages
    body = send(
        client,
        "comicvine",
        "GET",
        _SEARCH_URL,
        params=[
            ("api_key", api_key),
            ("format", "json"),
            ("resources", "volume"),
            ("query", query),
            ("limit", str(RESULT_LIMIT)),
            ("field_list", "id,name,start_year,publisher"),
        ],
        cancel=cancel,
    )
    results = _results(body, search=True)
    if not isinstance(results, list):
        return []
    candidates: list[Candidate] = []
    for item in results:
        candidate = _candidate(item)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def load(
    match_id: str,
    *,
    api_key: str,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a ComicInfo patch for one Comic Vine volume."""
    del title_languages
    body = send(
        client,
        "comicvine",
        "GET",
        _VOLUME_URL.format(match_id=match_id),
        params=[
            ("api_key", api_key),
            ("format", "json"),
            (
                "field_list",
                (
                    "name,start_year,publisher,description,deck,"
                    "site_detail_url,person_credits"
                ),
            ),
        ],
        cancel=cancel,
    )
    results = _results(body, search=False)
    if not isinstance(results, dict):
        raise ProviderResponseError("comicvine: load record was missing")
    title = nonblank(results.get("name"))
    if title is None:
        raise ProviderResponseError("comicvine: record has no usable title")
    patch: dict[str, str] = {
        "Series": title,
        "Title": title,
        "Manga": "No",
    }
    publisher = results.get("publisher")
    if isinstance(publisher, dict):
        put(patch, "Publisher", nonblank(publisher.get("name")))
    summary = plain_summary(results.get("description"))
    if summary is None:
        summary = plain_summary(results.get("deck"))
    put(patch, "Summary", summary)
    year = _year(results.get("start_year"))
    if year is not None:
        patch["Year"] = year
    put(patch, "Web", nonblank(results.get("site_detail_url")))
    writers, pencillers, inkers, covers = _credits(results.get("person_credits"))
    put(patch, "Writer", join_names(writers))
    put(patch, "Penciller", join_names(pencillers))
    put(patch, "Inker", join_names(inkers))
    put(patch, "CoverArtist", join_names(covers))
    return patch


def _results(body: object, *, search: bool) -> object:
    if not isinstance(body, dict):
        raise ProviderResponseError("comicvine: response was not an object")
    status = body.get("status_code")
    if body.get("error") != "OK" or isinstance(status, bool) or status not in (1, "1"):
        raise ProviderResponseError("comicvine: request was not OK")
    if "results" not in body:
        raise ProviderResponseError("comicvine: results were missing")
    results = body["results"]
    if search and (results is None or results == []):
        return []
    if search and not isinstance(results, list):
        raise ProviderResponseError("comicvine: results were not a list")
    if not search and not isinstance(results, dict):
        raise ProviderResponseError("comicvine: load record was missing")
    return results


def _candidate(item: object) -> Candidate | None:
    if not isinstance(item, dict):
        return None
    identity = catalog_id(item.get("id"))
    title = nonblank(item.get("name"))
    if identity is None or title is None:
        return None
    publisher = item.get("publisher")
    credit = publisher.get("name") if isinstance(publisher, dict) else None
    return Candidate(
        id=identity,
        title=title,
        detail=detail_text(item.get("start_year"), credit),
    )


def _year(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    return nonblank(value)


def _credits(
    people: object,
) -> tuple[list[str], list[str], list[str], list[str]]:
    writers: list[str] = []
    pencillers: list[str] = []
    inkers: list[str] = []
    covers: list[str] = []
    if not isinstance(people, list):
        return writers, pencillers, inkers, covers
    for person in people:
        if not isinstance(person, dict):
            continue
        name = nonblank(person.get("name"))
        if name is None:
            continue
        pieces = role_pieces(person.get("role"))
        if pieces & _WRITER:
            writers.append(name)
        if pieces & _PENCILLER:
            pencillers.append(name)
        if pieces & _INKER:
            inkers.append(name)
        if pieces & _COVER:
            covers.append(name)
    return writers, pencillers, inkers, covers
