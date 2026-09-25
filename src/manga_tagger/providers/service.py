"""Search one catalog and load one series into a ComicInfo form patch."""

import re
from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.anilist import load as anilist_load
from manga_tagger.providers.anilist import search as anilist_search
from manga_tagger.providers.comicvine import load as comicvine_load
from manga_tagger.providers.comicvine import search as comicvine_search
from manga_tagger.providers.constants import RESULT_LIMIT
from manga_tagger.providers.errors import (
    ProviderResponseError,
    ProviderUnavailableError,
)
from manga_tagger.providers.jikan import load as jikan_load
from manga_tagger.providers.jikan import search as jikan_search
from manga_tagger.providers.mangadex import load as mangadex_load
from manga_tagger.providers.mangadex import search as mangadex_search
from manga_tagger.providers.nautiljon import load as nautiljon_load
from manga_tagger.providers.nautiljon import search as nautiljon_search
from manga_tagger.providers.query import parse_number
from manga_tagger.providers.service_types import Candidate

_PROVIDERS = frozenset({"mangadex", "anilist", "jikan", "comicvine", "nautiljon"})
_NUMERIC_ID = re.compile(r"[1-9]\d*")
_COMICVINE_KEY = "The Comic Vine API key is not set"
_NAUTILJON_BASE = "The Nautiljon base URL is not set"
_NAUTILJON_KEY = "The Nautiljon API key is not set"
_SLUG_PROVIDERS = frozenset({"mangadex", "nautiljon"})


def search(
    provider: str,
    query: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    api_key: str = "",
    nautiljon_base_url: str = "",
    nautiljon_api_key: str = "",
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return at most 10 candidates from one catalog.

    An empty query returns no candidates and sends no request. This function
    does not open or write an archive.

    Args:
        provider: Catalog id such as ``mangadex`` or ``nautiljon``.
        query: Search text, usually from ``build_query``.
        title_languages: Title codes walked before the original title.
        client: Caller-owned HTTP client. This module does not set a timeout.
        api_key: Comic Vine key. Blank disables that catalog.
        nautiljon_base_url: Nautiljon wrapper origin. Blank disables that catalog.
        nautiljon_api_key: Nautiljon wrapper key. Blank disables that catalog.
        cancel: Checked once, immediately before each request.

    Returns:
        Candidates in API order. An empty list is not an error.
    """
    _require_provider(provider)
    if query.strip() == "":
        return []
    _require_comicvine_key(provider, api_key)
    _require_nautiljon(provider, nautiljon_base_url, nautiljon_api_key)
    if provider == "mangadex":
        found = mangadex_search(
            query, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "anilist":
        found = anilist_search(
            query, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "jikan":
        found = jikan_search(
            query, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "comicvine":
        found = comicvine_search(
            query,
            api_key=api_key,
            title_languages=title_languages,
            client=client,
            cancel=cancel,
        )
    else:
        found = nautiljon_search(
            query,
            base_url=nautiljon_base_url,
            api_key=nautiljon_api_key,
            title_languages=title_languages,
            client=client,
            cancel=cancel,
        )
    return found[:RESULT_LIMIT]


def load(
    provider: str,
    match_id: str,
    *,
    filename_stem: str,
    title_languages: Sequence[str],
    client: httpx.Client,
    api_key: str = "",
    nautiljon_base_url: str = "",
    nautiljon_api_key: str = "",
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a form patch for one series. Does not write an archive.

    Args:
        provider: Catalog id such as ``mangadex`` or ``nautiljon``.
        match_id: Catalog id. Comic Vine ids do not include the ``4050-`` prefix.
        filename_stem: Filename with its extension already removed. Supplies
            ``Number`` when it has a volume marker.
        title_languages: Title codes walked before the original title.
        client: Caller-owned HTTP client.
        api_key: Comic Vine key. Blank disables that catalog.
        nautiljon_base_url: Nautiljon wrapper origin. Blank disables that catalog.
        nautiljon_api_key: Nautiljon wrapper key. Blank disables that catalog.
        cancel: Checked once, immediately before each request.

    Returns:
        ComicInfo element names mapped to strings. ``Volume`` is never included.
    """
    _require_provider(provider)
    _require_match_id(provider, match_id)
    _require_comicvine_key(provider, api_key)
    _require_nautiljon(provider, nautiljon_base_url, nautiljon_api_key)
    number = parse_number(filename_stem)
    if provider == "mangadex":
        patch = mangadex_load(
            match_id, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "anilist":
        patch = anilist_load(
            match_id, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "jikan":
        patch = jikan_load(
            match_id, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "comicvine":
        patch = comicvine_load(
            match_id,
            api_key=api_key,
            title_languages=title_languages,
            client=client,
            cancel=cancel,
        )
    else:
        patch = nautiljon_load(
            match_id,
            base_url=nautiljon_base_url,
            api_key=nautiljon_api_key,
            title_languages=title_languages,
            client=client,
            volume_number=number,
            cancel=cancel,
        )
    if number is not None:
        patch["Number"] = number
    return patch


def _require_provider(provider: str) -> None:
    if provider not in _PROVIDERS:
        raise ProviderResponseError(f"{provider}: unknown provider")


def _require_comicvine_key(provider: str, api_key: str) -> None:
    if provider == "comicvine" and api_key.strip() == "":
        raise ProviderUnavailableError(_COMICVINE_KEY)


def _require_nautiljon(provider: str, base_url: str, api_key: str) -> None:
    if provider != "nautiljon":
        return
    if base_url.strip() == "":
        raise ProviderUnavailableError(_NAUTILJON_BASE)
    if api_key.strip() == "":
        raise ProviderUnavailableError(_NAUTILJON_KEY)


def _require_match_id(provider: str, match_id: str) -> None:
    if (
        match_id.strip() == ""
        or any(char.isspace() for char in match_id)
        or any(char in match_id for char in "/?#")
    ):
        raise ProviderResponseError(f"{provider}: match id is invalid")
    if provider in _SLUG_PROVIDERS:
        return
    if match_id != "0" and _NUMERIC_ID.fullmatch(match_id) is None:
        raise ProviderResponseError(f"{provider}: match id is invalid")
