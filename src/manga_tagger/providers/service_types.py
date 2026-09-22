"""Shared candidate type so provider modules do not import the service."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One search hit.

    Attributes:
        id: Catalog id. Decimal digits for AniList, Jikan, and Comic Vine.
            A MangaDex UUID for MangaDex.
        title: Preferred series title.
        detail: Year and first credit joined with ``", "``, or ``""``.
    """

    id: str
    title: str
    detail: str
