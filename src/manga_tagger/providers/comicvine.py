"""Comic Vine volume search, issue list, and issue load."""

from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.constants import RESULT_LIMIT
from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service_types import Candidate, IssueCandidate
from manga_tagger.providers.text import (
    catalog_id,
    count_text,
    first_url,
    join_names,
    nonblank,
    plain_summary,
    put,
    role_pieces,
    year_text,
)

_SEARCH_URL = "https://comicvine.gamespot.com/api/search/"
_VOLUME_URL = "https://comicvine.gamespot.com/api/volume/4050-{match_id}/"
_ISSUES_URL = "https://comicvine.gamespot.com/api/issues/"
_ISSUE_URL = "https://comicvine.gamespot.com/api/issue/4000-{issue_id}/"
_ISSUE_PAGE = 100
_WRITER = frozenset({"writer"})
_PENCILLER = frozenset({"penciler", "penciller", "artist"})
_INKER = frozenset({"inker"})
_COVER = frozenset({"cover", "cover artist"})
_NOT_FOUND = "comicvine: could not find an issue"


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
            (
                "field_list",
                "id,name,start_year,publisher,image,"
                "count_of_issues,deck,description",
            ),
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


def list_issues(
    series_id: str,
    *,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[IssueCandidate]:
    """Return Comic Vine issues for one volume id."""
    issues: list[IssueCandidate] = []
    offset = 0
    while True:
        body = send(
            client,
            "comicvine",
            "GET",
            _ISSUES_URL,
            params=[
                ("api_key", api_key),
                ("format", "json"),
                ("filter", f"volume:{series_id}"),
                (
                    "field_list",
                    "id,issue_number,name,image,cover_date,description",
                ),
                ("limit", str(_ISSUE_PAGE)),
                ("offset", str(offset)),
            ],
            cancel=cancel,
        )
        results = _results(body, search=True)
        if not isinstance(results, list):
            break
        for item in results:
            issue = _issue_candidate(item)
            if issue is not None:
                issues.append(issue)
        total = _total_results(body)
        offset += _ISSUE_PAGE
        if total is None or offset >= total or len(results) == 0:
            break
    return issues


def load(
    match_id: str,
    *,
    api_key: str,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a ComicInfo patch for one Comic Vine volume (series context)."""
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
    return _volume_patch(results)


def load_issue(
    issue_id: str,
    *,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a ComicInfo patch for one Comic Vine issue."""
    body = send(
        client,
        "comicvine",
        "GET",
        _ISSUE_URL.format(issue_id=issue_id),
        params=[
            ("api_key", api_key),
            ("format", "json"),
            (
                "field_list",
                (
                    "id,issue_number,name,description,cover_date,"
                    "site_detail_url,person_credits,volume,image"
                ),
            ),
        ],
        cancel=cancel,
    )
    results = _results(body, search=False)
    if not isinstance(results, dict):
        raise ProviderResponseError("comicvine: load record was missing")
    return _issue_patch(results)


def resolve_issue_id(
    series_id: str,
    preferred_number: str,
    *,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> str:
    """Return the issue id whose number matches ``preferred_number``."""
    target = normalize_number(preferred_number)
    for issue in list_issues(
        series_id, api_key=api_key, client=client, cancel=cancel
    ):
        if normalize_number(issue.number) == target:
            return issue.id
    raise ProviderResponseError(_NOT_FOUND)


def normalize_number(value: str) -> str:
    """Drop leading zeros on the integer part of an issue number."""
    text = value.strip()
    if "." in text:
        whole, frac = text.split(".", 1)
        whole = whole.lstrip("0") or "0"
        return f"{whole}.{frac}"
    return text.lstrip("0") or "0"


def _volume_patch(results: dict[str, object]) -> dict[str, str]:
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


def _issue_patch(results: dict[str, object]) -> dict[str, str]:
    volume = results.get("volume")
    series = None
    if isinstance(volume, dict):
        series = nonblank(volume.get("name"))
    issue_title = nonblank(results.get("name"))
    if series is None and issue_title is None:
        raise ProviderResponseError("comicvine: record has no usable title")
    series_name = series or issue_title or ""
    number = _issue_number_text(results.get("issue_number"))
    if number is None:
        raise ProviderResponseError(_NOT_FOUND)
    patch: dict[str, str] = {
        "Series": series_name,
        "Title": issue_title or series_name,
        "Number": number,
        "Manga": "No",
    }
    put(patch, "Summary", plain_summary(results.get("description")))
    _apply_cover_date(patch, results.get("cover_date"))
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


def _total_results(body: object) -> int | None:
    if not isinstance(body, dict):
        return None
    value = body.get("number_of_total_results")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


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
        year=year_text(item.get("start_year")),
        credit=nonblank(credit) or "",
        count=count_text(item.get("count_of_issues")),
        summary=(
            plain_summary(item.get("deck"))
            or plain_summary(item.get("description"))
            or ""
        ),
        cover=_image_cover(item.get("image")),
    )


def _issue_candidate(item: object) -> IssueCandidate | None:
    if not isinstance(item, dict):
        return None
    identity = catalog_id(item.get("id"))
    number = _issue_number_text(item.get("issue_number"))
    if identity is None or number is None:
        return None
    return IssueCandidate(
        id=identity,
        number=number,
        title=nonblank(item.get("name")) or "",
        date=_cover_date_label(item.get("cover_date")),
        cover=_image_cover(item.get("image")),
        summary=plain_summary(item.get("description")) or "",
    )


def _image_cover(image: object) -> str:
    if not isinstance(image, dict):
        return ""
    return first_url(
        image.get("super_url"),
        image.get("medium_url"),
        image.get("small_url"),
        image.get("thumb_url"),
    )


def _issue_number_text(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = str(value)
        if text.endswith(".0"):
            text = text[:-2]
        return text
    return nonblank(value)


def _cover_date_label(value: object) -> str:
    text = nonblank(value)
    if text is None:
        return ""
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    if len(text) >= 4 and text[:4].isdigit():
        return text[:4]
    return ""


def _apply_cover_date(patch: dict[str, str], value: object) -> None:
    text = nonblank(value)
    if text is None:
        return
    parts = text.split("-")
    if not parts or not parts[0].isdigit():
        return
    patch["Year"] = str(int(parts[0]))
    if len(parts) >= 2 and parts[1].isdigit():
        patch["Month"] = str(int(parts[1]))
    if len(parts) >= 3 and parts[2].isdigit():
        patch["Day"] = str(int(parts[2]))


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
