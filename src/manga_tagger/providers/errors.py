"""Errors raised while searching a catalog or loading a form patch."""


class ProviderError(Exception):
    """Base class for catalog failures. None of these write a file."""


class ProviderUnavailableError(ProviderError):
    """Comic Vine was selected and the API key is blank."""


class ProviderCancelledError(ProviderError):
    """``cancel`` returned true immediately before a request."""


class ProviderTimeoutError(ProviderError):
    """The HTTP client raised a transport error, including a timeout."""


class ProviderRateLimitError(ProviderError):
    """The catalog responded with HTTP 429."""


class ProviderResponseError(ProviderError):
    """The provider name, id, status, or body cannot be used."""
