"""Shared candidate types so provider modules do not import the service."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One search hit.

    Attributes:
        id: Catalog id. Decimal digits for AniList, Jikan, and Comic Vine.
            A MangaDex UUID for MangaDex.
        title: Preferred series title.
        year: Start or publish year, or ``""``.
        credit: First author, staff, or publisher name, or ``""``.
        count: Issue or volume count, or ``""``.
        summary: Plain synopsis or deck, or ``""``.
        cover: Absolute HTTPS cover URL, or ``""`` when missing.
    """

    id: str
    title: str
    year: str
    credit: str
    count: str
    summary: str
    cover: str


@dataclass(frozen=True)
class IssueCandidate:
    """One issue or tankōbon row for Select Issue.

    Attributes:
        id: Comic Vine issue id, or Nautiljon volume number as text.
        number: Display and match key.
        title: Issue or volume title, or ``""``.
        date: ``YYYY-MM`` or year, or ``""``.
        cover: Absolute HTTPS cover URL, or ``""``.
        summary: Plain synopsis, or ``""``.
    """

    id: str
    number: str
    title: str
    date: str
    cover: str
    summary: str
