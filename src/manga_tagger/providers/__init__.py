"""Catalog search and ComicInfo form patches.

The public functions do not read config, open an archive, or write a file.
"""

from manga_tagger.providers.constants import PROVIDER_IDS, RESULT_LIMIT
from manga_tagger.providers.cover import (
    CoverRef,
    resolve_cover,
    resolve_cover_from_web,
)
from manga_tagger.providers.errors import (
    ProviderCancelledError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from manga_tagger.providers.query import build_query, parse_number
from manga_tagger.providers.service import list_issues, load, search
from manga_tagger.providers.service_types import Candidate, IssueCandidate
from manga_tagger.providers.web_id import WebIdentity, parse_web

__all__ = [
    "RESULT_LIMIT",
    "PROVIDER_IDS",
    "Candidate",
    "CoverRef",
    "IssueCandidate",
    "ProviderCancelledError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "WebIdentity",
    "build_query",
    "list_issues",
    "load",
    "parse_number",
    "parse_web",
    "resolve_cover",
    "resolve_cover_from_web",
    "search",
]
