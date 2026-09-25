"""Fetch allow-listed remote cover images for the Matches dialog."""

from urllib.parse import urlparse

import httpx

from manga_tagger.providers.constants import USER_AGENT

ALLOWED_COVER_HOSTS = frozenset(
    {"uploads.mangadex.org", "www.nautiljon.com", "nautiljon.com"}
)


class RemoteCoverError(Exception):
    """The cover URL is illegal or the download failed."""


def remote_cover_bytes(
    url: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[bytes, str]:
    """Return image bytes and a media type for an allow-listed cover URL.

    Args:
        url: Absolute HTTPS cover URL.
        client: Optional caller-owned client. When omitted, one request uses a
            short-lived client with a 15 second timeout.

    Returns:
        ``(payload, media_type)``.

    Raises:
        RemoteCoverError: The URL is not https on an allow-listed host, the
            response is not an image, or the download fails.
    """
    _require_allowed(url)
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=15.0, follow_redirects=True)
    assert client is not None
    try:
        try:
            response = client.get(url, headers={"User-Agent": USER_AGENT})
        except httpx.TransportError as exc:
            raise RemoteCoverError("cover download failed") from exc
        final = str(response.url)
        _require_allowed(final)
        if response.status_code >= 400:
            raise RemoteCoverError(f"cover HTTP {response.status_code}")
        media = (response.headers.get("content-type") or "").split(";")[0].strip()
        if not media.startswith("image/"):
            raise RemoteCoverError("cover was not an image")
        payload = response.content
        if not payload:
            raise RemoteCoverError("cover was empty")
        return payload, media
    finally:
        if own_client:
            client.close()


def _require_allowed(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_COVER_HOSTS:
        raise RemoteCoverError("cover url is not allowed")
    if parsed.username is not None or parsed.password is not None:
        raise RemoteCoverError("cover url is not allowed")
