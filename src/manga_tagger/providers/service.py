"""Search one catalog and load one series into a ComicInfo form patch."""

import re
from collections.abc import Callable, Sequence

import httpx

from manga_tagger.providers.anilist import load as anilist_load
from manga_tagger.providers.anilist import search as anilist_search
from manga_tagger.providers.comicvine import list_issues as comicvine_list_issues
from manga_tagger.providers.comicvine import load as comicvine_load
from manga_tagger.providers.comicvine import load_issue as comicvine_load_issue
from manga_tagger.providers.comicvine import resolve_issue_id as comicvine_resolve
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
from manga_tagger.providers.nautiljon import list_issues as nautiljon_list_issues
from manga_tagger.providers.nautiljon import load as nautiljon_load
from manga_tagger.providers.nautiljon import search as nautiljon_search
from manga_tagger.providers.query import parse_number
from manga_tagger.providers.service_types import Candidate, IssueCandidate

_PROVIDERS = frozenset({"mangadex", "anilist", "jikan", "comicvine", "nautiljon"})
_ISSUE_PROVIDERS = frozenset({"comicvine", "nautiljon"})
_NUMERIC_ID = re.compile(r"[1-9]\d*")
_COMICVINE_KEY = "The Comic Vine API key is not set"
_NAUTILJON_BASE = "The Nautiljon base URL is not set"
_NAUTILJON_KEY = "The Nautiljon API key is not set"
_PROVIDER_DISABLED = "{provider}: provider is disabled"
_SLUG_PROVIDERS = frozenset({"mangadex", "nautiljon"})
_CV_NOT_FOUND = "comicvine: could not find an issue"
_NJ_NOT_FOUND = "nautiljon: could not find an issue"


def search(
    provider: str,
    query: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    api_key: str = "",
    nautiljon_base_url: str = "",
    nautiljon_api_key: str = "",
    enabled_providers: Sequence[str] | None = None,
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
        enabled_providers: When set, providers outside this list are unavailable.
            ``None`` treats every known provider as enabled.
        cancel: Checked once, immediately before each request.

    Returns:
        Candidates in API order. An empty list is not an error.
    """
    _require_provider(provider)
    _require_enabled(provider, enabled_providers)
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


def list_issues(
    provider: str,
    series_id: str,
    *,
    title_languages: Sequence[str],
    client: httpx.Client,
    api_key: str = "",
    nautiljon_base_url: str = "",
    nautiljon_api_key: str = "",
    enabled_providers: Sequence[str] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> list[IssueCandidate]:
    """Return issues or volumes for one series id.

    MangaDex, AniList, and Jikan return an empty list and send no request.
    """
    del title_languages
    _require_provider(provider)
    _require_enabled(provider, enabled_providers)
    _require_match_id(provider, series_id)
    _require_comicvine_key(provider, api_key)
    _require_nautiljon(provider, nautiljon_base_url, nautiljon_api_key)
    if provider not in _ISSUE_PROVIDERS:
        return []
    if provider == "comicvine":
        return comicvine_list_issues(
            series_id, api_key=api_key, client=client, cancel=cancel
        )
    return nautiljon_list_issues(
        series_id,
        base_url=nautiljon_base_url,
        api_key=nautiljon_api_key,
        client=client,
        cancel=cancel,
    )


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
    enabled_providers: Sequence[str] | None = None,
    cancel: Callable[[], bool] | None = None,
    issue_id: str = "",
    number: str | None = None,
) -> dict[str, str]:
    """Return a form patch for one series or issue. Does not write an archive.

    Args:
        provider: Catalog id such as ``mangadex`` or ``nautiljon``.
        match_id: Catalog series id. Comic Vine ids do not include ``4050-``.
        filename_stem: Filename with its extension already removed.
        title_languages: Title codes walked before the original title.
        client: Caller-owned HTTP client.
        api_key: Comic Vine key. Blank disables that catalog.
        nautiljon_base_url: Nautiljon wrapper origin. Blank disables that catalog.
        nautiljon_api_key: Nautiljon wrapper key. Blank disables that catalog.
        enabled_providers: When set, providers outside this list are unavailable.
            ``None`` treats every known provider as enabled.
        cancel: Checked once, immediately before each request.
        issue_id: Comic Vine issue id or Nautiljon volume number when set.
        number: Preferred issue/volume number from the form when non-blank.

    Returns:
        ComicInfo element names mapped to strings.
    """
    _require_provider(provider)
    _require_enabled(provider, enabled_providers)
    _require_match_id(provider, match_id)
    _require_comicvine_key(provider, api_key)
    _require_nautiljon(provider, nautiljon_base_url, nautiljon_api_key)
    issue = issue_id.strip()
    preferred = _preferred_number(number, filename_stem)

    if provider == "comicvine":
        return _load_comicvine(
            match_id,
            issue_id=issue,
            preferred_number=preferred,
            api_key=api_key,
            client=client,
            cancel=cancel,
        )
    if provider == "nautiljon":
        return _load_nautiljon(
            match_id,
            issue_id=issue,
            preferred_number=preferred,
            title_languages=title_languages,
            base_url=nautiljon_base_url,
            api_key=nautiljon_api_key,
            client=client,
            cancel=cancel,
        )

    if provider == "mangadex":
        patch = mangadex_load(
            match_id, title_languages=title_languages, client=client, cancel=cancel
        )
    elif provider == "anilist":
        patch = anilist_load(
            match_id, title_languages=title_languages, client=client, cancel=cancel
        )
    else:
        patch = jikan_load(
            match_id, title_languages=title_languages, client=client, cancel=cancel
        )
    stem_number = parse_number(filename_stem)
    if stem_number is not None:
        patch["Number"] = stem_number
    return patch


def _load_comicvine(
    match_id: str,
    *,
    issue_id: str,
    preferred_number: str | None,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> dict[str, str]:
    resolved = issue_id
    if resolved == "":
        if preferred_number is None:
            raise ProviderResponseError(_CV_NOT_FOUND)
        resolved = comicvine_resolve(
            match_id,
            preferred_number,
            api_key=api_key,
            client=client,
            cancel=cancel,
        )
    else:
        _require_match_id("comicvine", resolved)
    patch = comicvine_load_issue(
        resolved, api_key=api_key, client=client, cancel=cancel
    )
    volume = comicvine_load(
        match_id,
        api_key=api_key,
        title_languages=(),
        client=client,
        cancel=cancel,
    )
    if "Count" in volume:
        patch["Count"] = volume["Count"]
    return patch


def _load_nautiljon(
    match_id: str,
    *,
    issue_id: str,
    preferred_number: str | None,
    title_languages: Sequence[str],
    base_url: str,
    api_key: str,
    client: httpx.Client,
    cancel: Callable[[], bool] | None,
) -> dict[str, str]:
    volume = issue_id if issue_id != "" else preferred_number
    if volume is None or volume.strip() == "":
        raise ProviderResponseError(_NJ_NOT_FOUND)
    volume = volume.strip()
    if not volume.isdigit() or int(volume) < 1:
        raise ProviderResponseError(_NJ_NOT_FOUND)
    volume = str(int(volume))
    return nautiljon_load(
        match_id,
        base_url=base_url,
        api_key=api_key,
        title_languages=title_languages,
        client=client,
        volume_number=volume,
        require_volume=True,
        cancel=cancel,
    )


def _preferred_number(number: str | None, filename_stem: str) -> str | None:
    if number is not None:
        trimmed = number.strip()
        if trimmed != "":
            return trimmed
    return parse_number(filename_stem)


def _require_provider(provider: str) -> None:
    if provider not in _PROVIDERS:
        raise ProviderResponseError(f"{provider}: unknown provider")


def _require_enabled(
    provider: str, enabled_providers: Sequence[str] | None
) -> None:
    if enabled_providers is None:
        return
    if provider not in enabled_providers:
        raise ProviderUnavailableError(
            _PROVIDER_DISABLED.format(provider=provider)
        )


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
