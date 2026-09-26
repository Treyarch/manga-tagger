"""Resolve a full-size catalog cover URL and suggested filename."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import httpx

from manga_tagger.providers import anilist as anilist_mod
from manga_tagger.providers import comicvine as comicvine_mod
from manga_tagger.providers import jikan as jikan_mod
from manga_tagger.providers import mangadex as mangadex_mod
from manga_tagger.providers import nautiljon as nautiljon_mod
from manga_tagger.providers.errors import ProviderResponseError
from manga_tagger.providers.http import send
from manga_tagger.providers.service import (
    _require_comicvine_key,
    _require_enabled,
    _require_match_id,
    _require_nautiljon,
    _require_provider,
)
from manga_tagger.providers.text import first_url, nonblank
from manga_tagger.providers.web_id import WebIdentity, parse_web

_MD_BASE = "https://api.mangadex.org"
_ANILIST_COVER_QUERY = """
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    coverImage { extraLarge large }
  }
}
""".strip()


@dataclass(frozen=True)
class CoverRef:
    """Full-size cover image reference.

    Attributes:
        url: Absolute HTTPS image URL.
        filename: Basename for the archive member leaf.
    """

    url: str
    filename: str


def resolve_cover(
    provider: str,
    match_id: str,
    *,
    client: httpx.Client,
    number: str = "",
    issue_id: str = "",
    api_key: str = "",
    nautiljon_base_url: str = "",
    nautiljon_api_key: str = "",
    enabled_providers: Sequence[str] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> CoverRef:
    """Return a full-size cover URL and filename for one catalog record.

    Args:
        provider: Catalog id.
        match_id: Series or volume id. May be blank when ``issue_id`` is set
            for Comic Vine.
        client: Caller-owned HTTP client.
        number: Preferred volume/issue number when the catalog has per-volume
            covers.
        issue_id: Comic Vine issue id when ``Web`` pointed at an issue.
        api_key: Comic Vine key.
        nautiljon_base_url: Nautiljon wrapper origin.
        nautiljon_api_key: Nautiljon wrapper key.
        enabled_providers: When set, providers outside this list are unavailable.
        cancel: Checked before each request.

    Returns:
        Full-size cover reference.

    Raises:
        ProviderResponseError: Identity or payload is unusable.
        ProviderUnavailableError: Provider disabled or missing keys.
    """
    _require_provider(provider)
    _require_enabled(provider, enabled_providers)
    if provider == "comicvine" and issue_id.strip():
        _require_comicvine_key(provider, api_key)
        _require_match_id(provider, issue_id.strip())
        return _comicvine_issue_cover(
            issue_id.strip(), api_key=api_key, client=client, cancel=cancel
        )
    _require_match_id(provider, match_id)
    _require_comicvine_key(provider, api_key)
    _require_nautiljon(provider, nautiljon_base_url, nautiljon_api_key)

    if provider == "mangadex":
        return _mangadex_cover(match_id, number=number, client=client, cancel=cancel)
    if provider == "anilist":
        return _anilist_cover(match_id, client=client, cancel=cancel)
    if provider == "jikan":
        return _jikan_cover(match_id, client=client, cancel=cancel)
    if provider == "comicvine":
        return _comicvine_volume_cover(
            match_id,
            number=number,
            api_key=api_key,
            client=client,
            cancel=cancel,
        )
    return _nautiljon_cover(
        match_id,
        number=number,
        base_url=nautiljon_base_url,
        api_key=nautiljon_api_key,
        client=client,
        cancel=cancel,
    )


def resolve_cover_from_web(
    web: str,
    *,
    client: httpx.Client,
    number: str = "",
    api_key: str = "",
    nautiljon_base_url: str = "",
    nautiljon_api_key: str = "",
    enabled_providers: Sequence[str] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> CoverRef:
    """Parse ``web`` and resolve a full-size cover."""
    identity = parse_web(web)
    preferred = number.strip() or identity.volume_number
    return resolve_cover(
        identity.provider,
        identity.match_id,
        client=client,
        number=preferred,
        issue_id=identity.issue_id,
        api_key=api_key,
        nautiljon_base_url=nautiljon_base_url,
        nautiljon_api_key=nautiljon_api_key,
        enabled_providers=enabled_providers,
        cancel=cancel,
    )


def filename_from_url(url: str) -> str:
    """Return a sanitized basename from an image URL path."""
    path = unquote(urlparse(url).path)
    name = PurePosixPath(path).name
    if not name or name in {".", ".."}:
        raise ProviderResponseError("cover filename is missing")
    if "/" in name or "\\" in name or ".." in name or any(ord(c) < 32 for c in name):
        raise ProviderResponseError("cover filename is illegal")
    return name


def _ref(url: str, filename: str | None = None) -> CoverRef:
    text = nonblank(url)
    if text is None or not text.startswith("https://"):
        raise ProviderResponseError("cover url is missing")
    leaf = filename if filename else filename_from_url(text)
    if not leaf:
        raise ProviderResponseError("cover filename is missing")
    return CoverRef(url=text, filename=leaf)


def _mangadex_cover(
    match_id: str,
    *,
    number: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> CoverRef:
    body = send(
        client,
        "mangadex",
        "GET",
        f"{_MD_BASE}/manga/{match_id}",
        params=[("includes[]", "cover_art")],
        cancel=cancel,
    )
    if not isinstance(body, dict) or body.get("result") != "ok":
        raise ProviderResponseError("mangadex: load result was not ok")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ProviderResponseError("mangadex: load record was missing")
    relationships = data.get("relationships")
    if not isinstance(relationships, list):
        relationships = []
    file_name = mangadex_mod.choose_cover_filename(relationships, number=number)
    if number.strip():
        matching = _matching_mangadex_cover(relationships, number)
        offset = 0
        while matching is None:
            covers = send(
                client,
                "mangadex",
                "GET",
                f"{_MD_BASE}/cover",
                params=[
                    ("manga[]", match_id),
                    ("limit", "100"),
                    ("offset", str(offset)),
                ],
                cancel=cancel,
            )
            if (
                not isinstance(covers, dict)
                or covers.get("result") != "ok"
                or not isinstance(covers.get("data"), list)
            ):
                raise ProviderResponseError("mangadex: cover list was missing")
            records = covers["data"]
            matching = _matching_mangadex_cover(records, number)
            offset += len(records)
            total = covers.get("total")
            if not records or not isinstance(total, int) or offset >= total:
                break
        file_name = matching or file_name
    if file_name is None:
        raise ProviderResponseError("mangadex: cover is missing")
    url = f"https://uploads.mangadex.org/covers/{match_id}/{file_name}"
    return _ref(url, file_name)


def _matching_mangadex_cover(records: list[object], number: str) -> str | None:
    matches = []
    for item in records:
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            continue
        volume = nonblank(attributes.get("volume"))
        if volume is not None and mangadex_mod._volume_matches(volume, number.strip()):
            matches.append(item)
    return mangadex_mod.choose_cover_filename(matches, number=number)


def _anilist_cover(
    match_id: str,
    *,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> CoverRef:
    media_id = int(match_id)
    body = anilist_mod._post(
        client,
        {"query": _ANILIST_COVER_QUERY, "variables": {"id": media_id}},
        cancel,
    )
    data = body.get("data") if isinstance(body, dict) else None
    media = data.get("Media") if isinstance(data, dict) else None
    if not isinstance(media, dict):
        raise ProviderResponseError("anilist: load record was missing")
    cover = media.get("coverImage")
    if not isinstance(cover, dict):
        raise ProviderResponseError("anilist: cover is missing")
    url = first_url(cover.get("extraLarge"), cover.get("large"))
    return _ref(url)


def _jikan_cover(
    match_id: str,
    *,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> CoverRef:
    body = send(
        client,
        "jikan",
        "GET",
        f"https://api.jikan.moe/v4/manga/{match_id}/full",
        cancel=cancel,
    )
    if not isinstance(body, dict):
        raise ProviderResponseError("jikan: load record was missing")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ProviderResponseError("jikan: load record was missing")
    url = jikan_mod._cover_url(data)
    return _ref(url)


def _comicvine_issue_cover(
    issue_id: str,
    *,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> CoverRef:
    body = send(
        client,
        "comicvine",
        "GET",
        comicvine_mod._ISSUE_URL.format(issue_id=issue_id),
        params=[
            ("api_key", api_key),
            ("format", "json"),
            ("field_list", "image"),
        ],
        cancel=cancel,
    )
    results = comicvine_mod._results(body, search=False)
    if not isinstance(results, dict):
        raise ProviderResponseError("comicvine: load record was missing")
    url = comicvine_mod._image_cover(results.get("image"))
    return _ref(url)


def _comicvine_volume_cover(
    match_id: str,
    *,
    number: str,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> CoverRef:
    if number.strip():
        try:
            resolved = comicvine_mod.resolve_issue_id(
                match_id,
                number.strip(),
                api_key=api_key,
                client=client,
                cancel=cancel,
            )
        except ProviderResponseError:
            resolved = None
        if resolved:
            return _comicvine_issue_cover(
                resolved, api_key=api_key, client=client, cancel=cancel
            )
    body = send(
        client,
        "comicvine",
        "GET",
        comicvine_mod._VOLUME_URL.format(match_id=match_id),
        params=[
            ("api_key", api_key),
            ("format", "json"),
            ("field_list", "image"),
        ],
        cancel=cancel,
    )
    results = comicvine_mod._results(body, search=False)
    if not isinstance(results, dict):
        raise ProviderResponseError("comicvine: load record was missing")
    url = comicvine_mod._image_cover(results.get("image"))
    return _ref(url)


def _nautiljon_cover(
    match_id: str,
    *,
    number: str,
    base_url: str,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> CoverRef:
    from urllib.parse import quote

    body = send(
        client,
        "nautiljon",
        "GET",
        nautiljon_mod._join(base_url, f"/v1/series/{quote(match_id, safe='+')}"),
        extra_headers={"X-Api-Key": api_key},
        cancel=cancel,
    )
    if not isinstance(body, dict):
        raise ProviderResponseError("nautiljon: load record was missing")
    preferred = number.strip()
    if preferred and preferred.isdigit():
        volume = nautiljon_mod._volume_body(
            match_id,
            preferred,
            base_url=base_url,
            api_key=api_key,
            client=client,
            cancel=cancel,
            require=False,
        )
        if volume is not None:
            cover = nautiljon_mod._volume_cover(volume.get("cover"))
            if cover:
                return _ref(cover)
    cover = first_url(body.get("cover"))
    if cover and not cover.startswith("https://"):
        cover = ""
    return _ref(cover)


# Re-export for callers that only need parse.
__all__ = [
    "CoverRef",
    "WebIdentity",
    "filename_from_url",
    "parse_web",
    "resolve_cover",
    "resolve_cover_from_web",
]
