"""Nautiljon wrapper search, volume list, and series load."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from urllib.parse import quote, urlparse

import httpx

from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service_types import Candidate, IssueCandidate
from manga_tagger.providers.text import (
    count_text,
    first_url,
    join_names,
    nonblank,
    plain_summary,
    put,
    year_text,
)

_SLUG_PATH = re.compile(r"/mangas/([^/]+)\.html(?:$|\?)")
_VOLUME_PATH = re.compile(r"/volume-(\d+),\d+\.html(?:$|\?)", re.I)
_LEGACY_VOLUME_PATH = re.compile(r"/mangas/volumes/[^/]+,(\d+)\.html(?:$|\?)", re.I)
_ROLE_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")
_ORIGINE_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
_VF_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_PROVIDER = "nautiljon"
_NOT_FOUND = "nautiljon: could not find an issue"


def search(
    query: str,
    *,
    base_url: str,
    api_key: str,
    title_languages: Sequence[str],
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return Nautiljon series candidates for ``query``."""
    del title_languages
    body = send(
        client,
        _PROVIDER,
        "GET",
        _join(base_url, "/v1/search"),
        params=[("q", query)],
        extra_headers={"X-Api-Key": api_key},
        cancel=cancel,
    )
    if not isinstance(body, dict):
        raise ProviderResponseError("nautiljon: response was not an object")
    if "results" not in body:
        raise ProviderResponseError("nautiljon: results were missing")
    results = body["results"]
    if results is None or results == []:
        return []
    if not isinstance(results, list):
        raise ProviderResponseError("nautiljon: results were not a list")
    candidates: list[Candidate] = []
    for item in results:
        candidate = _candidate(item)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def list_issues(
    match_id: str,
    *,
    base_url: str,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None = None,
) -> list[IssueCandidate]:
    """Return tankōbon rows from series ``volumeUrls``, enriched per volume."""
    body = send(
        client,
        _PROVIDER,
        "GET",
        _join(base_url, f"/v1/series/{quote(match_id, safe='+')}"),
        extra_headers={"X-Api-Key": api_key},
        cancel=cancel,
    )
    if not isinstance(body, dict):
        raise ProviderResponseError("nautiljon: response was not an object")
    urls = body.get("volumeUrls")
    if not isinstance(urls, list):
        return []
    numbers: list[str] = []
    seen: set[str] = set()
    for item in urls:
        number = _volume_number_from_url(item)
        if number is None or number in seen:
            continue
        seen.add(number)
        numbers.append(number)
    issues: list[IssueCandidate] = []
    for number in numbers:
        title = f"Tome {number}"
        date = ""
        summary = ""
        cover = ""
        volume = _volume_body(
            match_id,
            number,
            base_url=base_url,
            api_key=api_key,
            client=client,
            cancel=cancel,
            require=False,
        )
        if volume is not None:
            date = _volume_date_label(volume.get("releaseDateVf"))
            summary = plain_summary(volume.get("description")) or ""
            cover = _volume_cover(volume.get("cover"))
        issues.append(
            IssueCandidate(
                id=number,
                number=number,
                title=title,
                date=date,
                cover=cover,
                summary=summary,
            )
        )
    return issues


def _volume_date_label(value: object) -> str:
    text = nonblank(value)
    if text is None:
        return ""
    match = _VF_DATE.fullmatch(text)
    if match is None:
        return ""
    _day, month, year = match.groups()
    return f"{int(year):04d}-{int(month):02d}"


def _volume_cover(value: object) -> str:
    cover = first_url(value)
    if cover and not cover.startswith("https://"):
        return ""
    return cover


def _rating_text(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return text or None
    return nonblank(value)
def load(
    match_id: str,
    *,
    base_url: str,
    api_key: str,
    title_languages: Sequence[str],
    client: httpx.Client,
    volume_number: str | None = None,
    require_volume: bool = False,
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a ComicInfo patch for one Nautiljon series.

    When ``require_volume`` is true, a missing or 404 volume raises
    ``ProviderResponseError``. When false, a volume 404 leaves the series patch.
    """
    body = send(
        client,
        _PROVIDER,
        "GET",
        _join(base_url, f"/v1/series/{quote(match_id, safe='+')}"),
        extra_headers={"X-Api-Key": api_key},
        cancel=cancel,
    )
    if not isinstance(body, dict):
        raise ProviderResponseError("nautiljon: response was not an object")
    chosen = _preferred_title(body, title_languages)
    if chosen is None:
        raise ProviderResponseError("nautiljon: record has no usable title")
    title, language = chosen
    infos = body.get("infos")
    if not isinstance(infos, dict):
        infos = {}
    extra = body.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    patch: dict[str, str] = {
        "Series": title,
        "Title": title,
        "Manga": "YesAndRightToLeft",
    }
    if language is not None:
        patch["LanguageISO"] = language
    put(patch, "Summary", plain_summary(body.get("synopsis")))
    put(
        patch,
        "Publisher",
        nonblank(infos.get("editeurVf")) or nonblank(infos.get("editeurVo")),
    )
    year = nonblank(infos.get("anneeVf")) or _origine_year(infos.get("origine"))
    put(patch, "Year", year)
    genres = _string_list(infos.get("genres"))
    themes = _string_list(infos.get("themes"))
    put(patch, "Genre", join_names([*genres, *themes]))
    put(patch, "Writer", join_names(_auteur_names(infos.get("auteurs"))))
    dessinateur = nonblank(extra.get("Dessinateur"))
    put(patch, "Penciller", dessinateur)
    put(patch, "CoverArtist", dessinateur)
    put(patch, "AgeRating", nonblank(infos.get("ageConseille")))
    put(patch, "Web", nonblank(body.get("sourceUrl")))
    volume = _volume_body(
        match_id,
        volume_number,
        base_url=base_url,
        api_key=api_key,
        client=client,
        cancel=cancel,
        require=require_volume,
    )
    if volume is not None:
        summary = plain_summary(volume.get("description"))
        if summary is not None:
            patch["Summary"] = summary
        _apply_vf_date(patch, volume.get("releaseDateVf"))
        put(patch, "CommunityRating", _rating_text(volume.get("rating")))
        if volume_number is not None:
            patch["Number"] = volume_number
    elif require_volume:
        raise ProviderResponseError(_NOT_FOUND)
    return patch


def _volume_body(
    match_id: str,
    volume_number: str | None,
    *,
    base_url: str,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
    require: bool,
) -> dict[str, object] | None:
    if volume_number is None or not volume_number.isdigit():
        if require:
            raise ProviderResponseError(_NOT_FOUND)
        return None
    number = int(volume_number)
    if number < 1:
        if require:
            raise ProviderResponseError(_NOT_FOUND)
        return None
    try:
        body = send(
            client,
            _PROVIDER,
            "GET",
            _join(
                base_url,
                f"/v1/series/{quote(match_id, safe='+')}/volumes/{number}",
            ),
            extra_headers={"X-Api-Key": api_key},
            cancel=cancel,
        )
    except ProviderResponseError as exc:
        if str(exc) == "nautiljon: HTTP 404":
            if require:
                raise ProviderResponseError(_NOT_FOUND) from exc
            return None
        raise
    if not isinstance(body, dict):
        raise ProviderResponseError("nautiljon: volume response was not an object")
    return body


def _volume_number_from_url(value: object) -> str | None:
    text = nonblank(value)
    if text is None:
        return None
    path = urlparse(text).path
    match = _VOLUME_PATH.search(path)
    if match is None and "/volume-" not in path.casefold():
        match = _LEGACY_VOLUME_PATH.search(path)
    if match is None:
        return None
    return str(int(match.group(1)))


def _candidate(item: object) -> Candidate | None:
    if not isinstance(item, dict):
        return None
    title = nonblank(item.get("title"))
    slug = _slug_from_url(item.get("url"))
    if title is None or slug is None:
        return None
    cover = first_url(item.get("cover"))
    if cover and not cover.startswith("https://"):
        cover = ""
    return Candidate(
        id=slug,
        title=title,
        year=year_text(item.get("dateVo")),
        credit="",
        count=count_text(item.get("issues")),
        summary=plain_summary(item.get("description")) or "",
        cover=cover,
    )


def _preferred_title(
    body: dict[str, object], languages: Sequence[str]
) -> tuple[str, str | None] | None:
    infos = body.get("infos")
    if not isinstance(infos, dict):
        infos = {}
    french = nonblank(body.get("title"))
    original = nonblank(infos.get("titreOriginal"))
    for code in languages:
        if code == "fr" and french is not None:
            return french, "fr"
        if code == "ja" and original is not None:
            return original, "ja"
    if french is not None:
        return french, None
    return None


def _slug_from_url(value: object) -> str | None:
    text = nonblank(value)
    if text is None:
        return None
    path = urlparse(text).path
    match = _SLUG_PATH.search(path)
    if match is None:
        return None
    return match.group(1)


def _auteur_names(value: object) -> list[str]:
    names: list[str] = []
    for item in _string_list(value):
        cleaned = _ROLE_SUFFIX.sub("", item).strip()
        if cleaned:
            names.append(cleaned)
    return names


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        text = nonblank(item)
        if text is not None:
            names.append(text)
    return names


def _origine_year(value: object) -> str | None:
    text = nonblank(value)
    if text is None:
        return None
    match = _ORIGINE_YEAR.search(text)
    if match is None:
        return None
    return match.group(1)


def _apply_vf_date(patch: dict[str, str], value: object) -> None:
    text = nonblank(value)
    if text is None:
        return
    match = _VF_DATE.fullmatch(text)
    if match is None:
        return
    day, month, year = match.groups()
    patch["Year"] = str(int(year))
    patch["Month"] = str(int(month))
    patch["Day"] = str(int(day))


def _join(base_url: str, path: str) -> str:
    return base_url.strip().rstrip("/") + path
