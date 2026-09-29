"""Limits shared by every catalog request."""

PROVIDER_IDS: tuple[str, ...] = (
    "mangadex",
    "anilist",
    "jikan",
    "comicvine",
    "nautiljon",
)
RESULT_LIMIT = 10
USER_AGENT = "manga-tagger"
