"""Parse ComicInfo Web URLs into catalog provider identity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from manga_tagger.providers.errors import ProviderResponseError

_MD_TITLE = re.compile(
    r"^/title/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:/|$)",
)
_ANILIST = re.compile(r"^/manga/([0-9]+)(?:/|$)")
_MAL = re.compile(r"^/manga/([0-9]+)(?:/|$)")
_CV_VOLUME = re.compile(r"/4050-([0-9]+)(?:/|$)")
_CV_ISSUE = re.compile(r"/4000-([0-9]+)(?:/|$)")
_NJ_SERIES = re.compile(r"^/mangas/([^/]+)\.html(?:$|\?)", re.I)
_NJ_VOLUME = re.compile(r"^/mangas/[^/]+/volume-([0-9]+),[0-9]+\.html(?:$|\?)", re.I)
_NJ_LEGACY_VOLUME = re.compile(
    r"^/mangas/volumes/([^/,]+),([0-9]+)\.html(?:$|\?)", re.I
)
_NJ_NESTED_SLUG = re.compile(r"^/mangas/([^/]+)/", re.I)


@dataclass(frozen=True)
class WebIdentity:
    """Catalog identity recovered from a ComicInfo Web URL.

    Attributes:
        provider: Catalog id such as ``mangadex``.
        match_id: Series or volume id for that provider.
        issue_id: Comic Vine issue id when ``Web`` is an issue URL.
        volume_number: Nautiljon volume number when ``Web`` is a volume URL.
    """

    provider: str
    match_id: str
    issue_id: str = ""
    volume_number: str = ""


def parse_web(web: str) -> WebIdentity:
    """Return provider identity from a ComicInfo ``Web`` URL.

    Args:
        web: Absolute HTTPS catalog URL, or blank.

    Returns:
        Parsed identity.

    Raises:
        ProviderResponseError: ``web`` is blank, not https, or not a known shape.
    """
    text = web.strip()
    if not text:
        raise ProviderResponseError("web url is missing")
    try:
        parsed = urlparse(text)
    except ValueError as exc:
        raise ProviderResponseError("web url is not a catalog link") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ProviderResponseError("web url is not a catalog link")
    host = parsed.hostname.casefold()
    path = parsed.path or "/"

    if host in {"mangadex.org", "www.mangadex.org"}:
        match = _MD_TITLE.search(path)
        if match is None:
            raise ProviderResponseError("web url is not a catalog link")
        return WebIdentity(provider="mangadex", match_id=match.group(1).lower())

    if host in {"anilist.co", "www.anilist.co"}:
        match = _ANILIST.search(path)
        if match is None:
            raise ProviderResponseError("web url is not a catalog link")
        return WebIdentity(provider="anilist", match_id=match.group(1))

    if host in {"myanimelist.net", "www.myanimelist.net"}:
        match = _MAL.search(path)
        if match is None:
            raise ProviderResponseError("web url is not a catalog link")
        return WebIdentity(provider="jikan", match_id=match.group(1))

    if host in {"comicvine.gamespot.com", "www.comicvine.gamespot.com"}:
        issue = _CV_ISSUE.search(path)
        if issue is not None:
            return WebIdentity(
                provider="comicvine",
                match_id="",
                issue_id=issue.group(1),
            )
        volume = _CV_VOLUME.search(path)
        if volume is not None:
            return WebIdentity(provider="comicvine", match_id=volume.group(1))
        raise ProviderResponseError("web url is not a catalog link")

    if host in {"nautiljon.com", "www.nautiljon.com"}:
        series = _NJ_SERIES.search(path)
        if series is not None:
            return WebIdentity(provider="nautiljon", match_id=series.group(1))
        legacy = _NJ_LEGACY_VOLUME.search(path)
        if legacy is not None:
            return WebIdentity(
                provider="nautiljon",
                match_id=legacy.group(1),
                volume_number=str(int(legacy.group(2))),
            )
        volume = _NJ_VOLUME.search(path)
        nested = _NJ_NESTED_SLUG.search(path)
        if volume is not None and nested is not None:
            return WebIdentity(
                provider="nautiljon",
                match_id=nested.group(1),
                volume_number=str(int(volume.group(1))),
            )
        raise ProviderResponseError("web url is not a catalog link")

    raise ProviderResponseError("web url is not a catalog link")
