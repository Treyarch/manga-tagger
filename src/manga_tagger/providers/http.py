"""One catalog request. No client, timeout, sleep, or retry lives here."""

from collections.abc import Callable, Mapping

import httpx

from manga_tagger.providers.constants import USER_AGENT
from manga_tagger.providers.errors import (
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)


def send(
    client: httpx.Client,
    provider: str,
    method: str,
    url: str,
    *,
    params: list[tuple[str, str]] | None = None,
    json_body: Mapping[str, object] | None = None,
    extra_headers: Mapping[str, str] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> object:
    """Send one request and return its JSON body.

    Args:
        client: Caller-owned HTTP client.
        provider: Catalog id, included in failure messages.
        method: HTTP method.
        url: Absolute URL.
        params: Query pairs. Repeated keys stay repeated.
        json_body: JSON object for a POST body.
        extra_headers: Headers merged over the manga-tagger user agent.
        cancel: Checked once, immediately before the request.

    Returns:
        The decoded JSON value.

    Raises:
        ProviderCancelledError: ``cancel`` returned true.
        ProviderTimeoutError: The client raised ``httpx.TransportError``.
        ProviderRateLimitError: The status is 429.
        ProviderResponseError: Any other HTTP error, or a body that is not JSON.
    """
    if cancel is not None and cancel():
        raise ProviderCancelledError(f"{provider}: cancelled before the request")
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    kwargs: dict[str, object] = {"headers": headers}
    if params is not None:
        kwargs["params"] = params
    if json_body is not None:
        kwargs["json"] = json_body
    try:
        response = client.request(method, url, **kwargs)
    except httpx.TransportError as exc:
        raise ProviderTimeoutError(f"{provider}: request failed") from exc
    if response.status_code == 429:
        raise ProviderRateLimitError(f"{provider}: rate limited")
    if response.status_code >= 400:
        raise ProviderResponseError(f"{provider}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderResponseError(f"{provider}: response was not JSON") from exc
