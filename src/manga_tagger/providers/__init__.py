"""Catalog search and ComicInfo form patches.

The public functions do not read config, open an archive, or write a file.
"""

from manga_tagger.providers.constants import RESULT_LIMIT
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

__all__ = [
    "RESULT_LIMIT",
    "Candidate",
    "IssueCandidate",
    "ProviderCancelledError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "build_query",
    "list_issues",
    "load",
    "parse_number",
    "search",
]
