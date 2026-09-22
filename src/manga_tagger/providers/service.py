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
from manga_tagger.providers.query import parse_number
from manga_tagger.providers.service_types import Candidate

_PROVIDERS = frozenset({"mangadex", "anilist", "jikan", "comicvine"})
_NUMERIC_ID = re.compile(r"[1-9]\d*")
_COMICVINE_KEY = "The Comic Vine API key is not set"


def search(
    provider: str,
    query: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    api_key: str = "",
    cancel: Callable[[], bool] | None = None,
) -> list[Candidate]:
    """Return at most 10 candidates from one catalog.

    An empty query returns no candidates and sends no request. This function
    does not open or write an archive.

    Args:
        provider: ``mangadex``, ``anilist``, ``jikan``, or ``comicvine``.
        query: Search text, usually from ``build_query``.
        title_languages: Title codes walked before the original title.
        client: Caller-owned HTTP client. This module does not set a timeout.
        api_key: Comic Vine key. Blank disables that catalog.
        cancel: Checked once, immediately before the request.

    Returns:
        Candidates in API order. An empty list is not an error.
    """
    _require_provider(provider)
    if query.strip() == "":
        return []
    _require_comicvine_key(provider, api_key)
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
    else:
        found = comicvine_search(
            query,
            api_key=api_key,
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
    cancel: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """Return a form patch for one series. Does not write an archive.

    Args:
        provider: ``mangadex``, ``anilist``, ``jikan``, or ``comicvine``.
        match_id: Catalog id. Comic Vine ids do not include the ``4050-`` prefix.
        filename_stem: Filename with its extension already removed. Supplies
            ``Number`` when it has a volume marker.
        title_languages: Title codes walked before the original title.
        client: Caller-owned HTTP client.
        api_key: Comic Vine key. Blank disables that catalog.
        cancel: Checked once, immediately before the request.

    Returns:
        ComicInfo element names mapped to strings. ``Volume`` is never included.
    """
    _require_provider(provider)
    _require_match_id(provider, match_id)
    _require_comicvine_key(provider, api_key)
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
    else:
        patch = comicvine_load(
            match_id,
            api_key=api_key,
            title_languages=title_languages,
            client=client,
            cancel=cancel,
        )
    number = parse_number(filename_stem)
    if number is not None:
        patch["Number"] = number
    return patch


def _require_provider(provider: str) -> None:
    if provider not in _PROVIDERS:
        raise ProviderResponseError(f"{provider}: unknown provider")


def _require_comicvine_key(provider: str, api_key: str) -> None:
    if provider == "comicvine" and api_key.strip() == "":
        raise ProviderUnavailableError(_COMICVINE_KEY)


def _require_match_id(provider: str, match_id: str) -> None:
    if (
        match_id.strip() == ""
        or any(char.isspace() for char in match_id)
        or any(char in match_id for char in "/?#")
    ):
        raise ProviderResponseError(f"{provider}: match id is invalid")
    if (
        provider != "mangadex"
        and match_id != "0"
        and _NUMERIC_ID.fullmatch(match_id) is None
    ):
        raise ProviderResponseError(f"{provider}: match id is invalid")
