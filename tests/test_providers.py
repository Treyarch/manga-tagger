"""Hermetic catalog search and form-patch tests."""

import json

import httpx
import pytest

from manga_tagger.providers import (
    Candidate,
    IssueCandidate,
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    build_query,
    list_issues,
    load,
    parse_number,
    search,
)

MD_ID = "6b1eb93e-473a-4ab3-9922-1a66d2a29a4b"
_FORBIDDEN = (
    "Pages",
    "PageCount",
    "Notes",
)


def test_query_and_number_table() -> None:
    rows = (
        ("[Group] Claymore v02 (Digital)", "Claymore", "2"),
        ("Claymore Tome 03", "Claymore", "3"),
        ("Claymore T.01", "Claymore", "1"),
        ("Foo (Bar) v01", "Foo (Bar)", "1"),
        ("Monster 01", "Monster", "1"),
        ("Claymore_Vol_02", "Claymore", "2"),
        ("20th Century Boys v01", "20th Century Boys", "1"),
        ("v01", "", "1"),
        ("Claymore", "Claymore", None),
        ("Claymore Chapter 12", "Claymore", None),
        ("Claymore Chapitre 03", "Claymore", None),
        ("Claymore Ch.12", "Claymore", None),
        ("c01", "c01", None),
        ("Claymore v1.5", "Claymore", "1.5"),
        ("Claymore v1.50", "Claymore", "1.50"),
        ("Claymore v0.5", "Claymore", "0.5"),
        ("Claymore v00", "Claymore", "0"),
        ("[Group (Digital)] Claymore", "Claymore", None),
        ("Claymore (2020)", "Claymore", None),
        ("Claymore (FR) v02", "Claymore", "2"),
    )
    for stem, query, number in rows:
        assert build_query("", stem) == query
        assert build_query("   ", stem) == query
        assert parse_number(stem) == number


def test_series_query_keeps_its_text() -> None:
    assert (
        build_query("20th Century Boys", "20th Century Boys v01") == "20th Century Boys"
    )
    assert build_query("  20th Century Boys  ", "ignored v01") == "20th Century Boys"
    assert parse_number("20th Century Boys v01") == "1"


def test_blank_query_sends_nothing() -> None:
    cancelled: list[str] = []

    def cancel() -> bool:
        cancelled.append("cancel")
        return True

    with _forbid_client() as client:
        for provider in ("mangadex", "anilist", "jikan", "comicvine", "nautiljon"):
            for query in ("", "   "):
                assert (
                    search(
                        provider,
                        query,
                        title_languages=["fr", "en"],
                        client=client,
                        api_key="",
                        nautiljon_base_url="",
                        nautiljon_api_key="",
                        cancel=cancel,
                    )
                    == []
                )
    assert cancelled == []


def test_unknown_provider_sends_nothing() -> None:
    with _forbid_client() as client:
        with pytest.raises(ProviderResponseError, match="other"):
            search(
                "other",
                "",
                title_languages=["en"],
                client=client,
            )
        with pytest.raises(ProviderResponseError, match="other"):
            load(
                "other",
                "1",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
            )


def test_mangadex_search_request_and_detail() -> None:
    body = {
        "data": [
            {
                "id": MD_ID,
                "attributes": {
                    "title": {"fr": "Titre", "en": "Title"},
                    "year": 2001,
                    "lastVolume": "27",
                    "description": {
                        "fr": "<p>Une histoire.</p>",
                        "en": "<p>A story.</p>",
                    },
                    "originalLanguage": "ja",
                },
                "relationships": [
                    {"type": "author"},
                    {"type": "author", "attributes": {"name": "Norihiro Yagi"}},
                    {
                        "type": "cover_art",
                        "attributes": {"fileName": "cover-file.jpg"},
                    },
                ],
            },
            {
                "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "attributes": {"title": {"en": "Bare"}, "originalLanguage": "ja"},
                "relationships": [],
            },
            {"id": "no-title", "attributes": {"title": {"en": "   "}}},
        ]
    }
    client, seen = _client(body)
    with client:
        found = search(
            "mangadex",
            "Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert found == [
        Candidate(
            id=MD_ID,
            title="Titre",
            year="2001",
            credit="Norihiro Yagi",
            count="27",
            summary="Une histoire.",
            cover=(
                f"https://uploads.mangadex.org/covers/{MD_ID}/cover-file.jpg.256.jpg"
            ),
        ),
        Candidate(
            id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            title="Bare",
            year="",
            credit="",
            count="",
            summary="",
            cover="",
        ),
    ]
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "GET"
    assert _bare(request) == "https://api.mangadex.org/manga"
    assert request.headers["user-agent"] == "manga-tagger"
    assert request.url.params.get("title") == "Claymore"
    assert request.url.params.get("limit") == "10"
    assert request.url.params.get("order[relevance]") == "desc"
    assert request.url.params.get_list("contentRating[]") == [
        "safe",
        "suggestive",
        "erotica",
        "pornographic",
    ]
    assert request.url.params.get_list("includes[]") == ["author", "cover_art"]


def test_search_keeps_ten_titled_hits() -> None:
    data: list[dict[str, object]] = [
        {"id": "skip", "attributes": {"title": {}}},
    ]
    data.extend(
        {
            "id": f"id-{index}",
            "attributes": {"title": {"en": f"Title {index}"}},
        }
        for index in range(11)
    )
    client, seen = _client({"data": data})
    with client:
        found = search("mangadex", "Query", title_languages=["en"], client=client)
    assert [item.id for item in found] == [f"id-{index}" for index in range(10)]
    assert seen[0].url.params.get("limit") == "10"


def test_mangadex_load_french_title_and_credits() -> None:
    body = {
        "result": "ok",
        "data": {
            "id": MD_ID,
            "attributes": {
                "title": {"fr": "Titre", "en": "Title"},
                "originalLanguage": "ja",
                "year": 2001,
                "lastVolume": "27",
                "description": {"fr": "Résumé", "en": "English blurb"},
                "tags": [
                    {"attributes": {"group": "theme", "name": {"en": "School Life"}}},
                    {"attributes": {"group": "genre", "name": {"en": "Action"}}},
                    {"attributes": {"group": "genre", "name": {"en": "Drama"}}},
                    {
                        "attributes": {
                            "group": "genre",
                            "name": {"en": "  ", "ja": "冒険"},
                        }
                    },
                ],
            },
            "relationships": [
                {"type": "author"},
                {"type": "author", "attributes": {"name": "Norihiro Yagi"}},
                {"type": "artist", "attributes": {"name": "Takeshi Obata"}},
                {"type": "cover_art", "attributes": {"name": "Ignored"}},
            ],
        },
    }
    client, seen = _client(body)
    with client:
        patch = load(
            "mangadex",
            MD_ID,
            filename_stem="Claymore v02",
            title_languages=["fr", "en"],
            client=client,
        )
    _assert_patch(patch)
    assert patch["Series"] == "Titre"
    assert patch["Title"] == "Titre"
    assert patch["LanguageISO"] == "fr"
    assert patch["Manga"] == "YesAndRightToLeft"
    assert patch["Genre"] == "Action, Drama, 冒険"
    assert "School Life" not in patch["Genre"]
    assert patch["Summary"] == "Résumé"
    assert patch["Year"] == "2001"
    assert "Month" not in patch
    assert "Day" not in patch
    assert patch["Writer"] == "Norihiro Yagi"
    assert patch["Penciller"] == "Takeshi Obata"
    assert patch["CoverArtist"] == "Takeshi Obata"
    assert patch["Web"] == f"https://mangadex.org/title/{MD_ID}"
    assert "Publisher" not in patch
    assert patch["Number"] == "2"
    assert patch["Count"] == "27"
    request = seen[0]
    assert _bare(request) == f"https://api.mangadex.org/manga/{MD_ID}"
    assert request.url.params.get_list("includes[]") == ["author", "artist"]
    assert request.headers["user-agent"] == "manga-tagger"


def test_mangadex_original_language_and_no_artist() -> None:
    body = {
        "result": "ok",
        "data": {
            "id": MD_ID,
            "attributes": {
                "title": {"ja": "クレイモア"},
                "originalLanguage": "ja",
                "description": {"en": "English blurb", "ja": "あらすじ"},
            },
            "relationships": [
                {"type": "author", "attributes": {"name": "Norihiro Yagi"}},
            ],
        },
    }
    client, _seen = _client(body)
    with client:
        patch = load(
            "mangadex",
            MD_ID,
            filename_stem="Claymore",
            title_languages=["fr"],
            client=client,
        )
    assert patch["Series"] == "クレイモア"
    assert patch["LanguageISO"] == "ja"
    assert patch["Summary"] == "あらすじ"
    assert patch["Writer"] == "Norihiro Yagi"
    assert "Penciller" not in patch
    assert "CoverArtist" not in patch
    assert "Number" not in patch
    assert "Publisher" not in patch
    assert patch["Manga"] == "YesAndRightToLeft"


def test_mangadex_alt_title_then_first_title() -> None:
    alt = {
        "result": "ok",
        "data": {
            "id": MD_ID,
            "attributes": {
                "title": {"en": "English"},
                "altTitles": [{"ja": "別"}, {"fr": "Français"}],
                "originalLanguage": "ja",
            },
        },
    }
    client, _seen = _client(alt)
    with client:
        patch = load(
            "mangadex",
            MD_ID,
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert patch["Title"] == "Français"
    assert patch["LanguageISO"] == "fr"

    fallback = {
        "result": "ok",
        "data": {
            "id": MD_ID,
            "attributes": {
                "title": {"ko": "한국어", "zh": "中文"},
                "originalLanguage": "ja",
            },
        },
    }
    client, _seen = _client(fallback)
    with client:
        patch = load(
            "mangadex",
            MD_ID,
            filename_stem="Claymore Chapter 12",
            title_languages=["fr"],
            client=client,
        )
    assert patch["Series"] == "한국어"
    assert patch["LanguageISO"] == "ko"
    assert "Number" not in patch


def test_mangadex_empty_and_bad_search_bodies() -> None:
    client, seen = _client({"data": []})
    with client:
        assert (
            search("mangadex", "Claymore", title_languages=["en"], client=client) == []
        )
    assert len(seen) == 1
    client, seen = _client({"result": "ok"})
    with client:
        with pytest.raises(ProviderResponseError, match="mangadex"):
            search("mangadex", "Claymore", title_languages=["en"], client=client)
    client, _seen = _client({"result": "error", "data": {}})
    with client:
        with pytest.raises(ProviderResponseError, match="mangadex"):
            load(
                "mangadex",
                MD_ID,
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
            )


def test_anilist_english_credits_and_summary() -> None:
    body = {
        "data": {
            "Media": {
                "id": 42,
                "title": {
                    "romaji": "Claymore",
                    "english": "Claymore EN",
                    "native": "クレイモア",
                },
                "description": "<p>Hello&nbsp;there</p>",
                "genres": ["Action", "Drama"],
                "siteUrl": "https://anilist.co/manga/42",
                "volumes": 27,
                "countryOfOrigin": "JP",
                "startDate": {"year": 2001, "month": 6, "day": 5},
                "staff": {
                    "edges": [
                        {"role": "Story & Art", "node": {"name": {"full": "Yagi"}}},
                        {
                            "role": "Partial coloring",
                            "node": {"name": {"full": "Colorist"}},
                        },
                        {"role": "starting", "node": {"name": {"full": "Starter"}}},
                        {"role": "Artist", "node": {"name": {"full": "Obata"}}},
                    ]
                },
            }
        }
    }
    client, seen = _client(body)
    with client:
        patch = load(
            "anilist",
            "42",
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    _assert_patch(patch)
    assert patch["Series"] == "Claymore EN"
    assert patch["Title"] == "Claymore EN"
    assert patch["LanguageISO"] == "en"
    assert patch["Summary"] == "Hello there"
    assert patch["Genre"] == "Action, Drama"
    assert patch["Year"] == "2001"
    assert patch["Month"] == "6"
    assert patch["Day"] == "5"
    assert patch["Writer"] == "Yagi"
    assert patch["Penciller"] == "Yagi, Obata"
    assert patch["CoverArtist"] == "Yagi, Obata"
    assert "Colorist" not in patch["Writer"]
    assert "Colorist" not in patch["Penciller"]
    assert "Starter" not in patch["Penciller"]
    assert patch["Web"] == "https://anilist.co/manga/42"
    assert "Publisher" not in patch
    assert patch["Manga"] == "YesAndRightToLeft"
    assert "Number" not in patch
    assert patch["Count"] == "27"
    request = seen[0]
    assert request.method == "POST"
    assert _bare(request) == "https://graphql.anilist.co"
    assert request.headers["user-agent"] == "manga-tagger"
    assert request.headers["accept"] == "application/json"
    assert request.headers["content-type"].startswith("application/json")
    payload = json.loads(request.content)
    assert "perPage: 25" in payload["query"]
    assert "type: MANGA" in payload["query"]
    assert "volumes" in payload["query"]
    assert payload["variables"] == {"id": 42}


def test_anilist_native_romaji_and_search() -> None:
    native = _anilist_media(
        title={"romaji": "Roma", "english": None, "native": "ネイティブ"},
        countryOfOrigin="JP",
    )
    client, _seen = _client(native)
    with client:
        patch = load(
            "anilist",
            "42",
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert patch["Series"] == "ネイティブ"
    assert patch["LanguageISO"] == "ja"

    other = _anilist_media(
        title={"romaji": "Roma", "english": None, "native": "Autre"},
        countryOfOrigin="FR",
    )
    client, _seen = _client(other)
    with client:
        patch = load(
            "anilist",
            "42",
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert patch["Series"] == "Autre"
    assert "LanguageISO" not in patch

    romaji = _anilist_media(
        title={"romaji": "Roma", "english": "  ", "native": ""},
        countryOfOrigin="JP",
    )
    client, _seen = _client(romaji)
    with client:
        patch = load(
            "anilist",
            "42",
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert patch["Series"] == "Roma"
    assert "LanguageISO" not in patch

    search_body = {
        "data": {
            "Page": {
                "media": [
                    {
                        "id": 42,
                        "title": {
                            "romaji": "Roma",
                            "english": "Claymore EN",
                            "native": "ネイティブ",
                        },
                        "coverImage": {
                            "large": "https://example.com/anilist-cover.jpg"
                        },
                        "startDate": {"year": 2004},
                        "volumes": 27,
                        "chapters": 155,
                        "description": "<p>Claymore summary</p>",
                        "staff": {"edges": [{"node": {"name": {"full": "Staff One"}}}]},
                    }
                ]
            }
        }
    }
    client, seen = _client(search_body)
    with client:
        found = search(
            "anilist",
            "Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert found == [
        Candidate(
            id="42",
            title="Claymore EN",
            year="2004",
            credit="Staff One",
            count="27",
            summary="Claymore summary",
            cover="https://example.com/anilist-cover.jpg",
        )
    ]
    payload = json.loads(seen[0].content)
    assert "perPage: 10" in payload["query"]
    assert "SEARCH_MATCH" in payload["query"]
    assert "coverImage { large }" in payload["query"]
    assert "volumes" in payload["query"]
    assert "chapters" in payload["query"]
    assert "description" in payload["query"]
    assert payload["variables"] == {"search": "Claymore"}
    assert seen[0].headers["user-agent"] == "manga-tagger"


def test_anilist_errors_and_empty_media() -> None:
    client, seen = _client({"data": {"Page": {"media": None}}})
    with client:
        assert (
            search("anilist", "Claymore", title_languages=["en"], client=client) == []
        )
    assert len(seen) == 1
    client, _seen = _client({"data": {"Page": {"media": []}}})
    with client:
        assert (
            search("anilist", "Claymore", title_languages=["en"], client=client) == []
        )
    bad = {
        "errors": [{"message": "nope"}],
        "data": {"Page": {"media": [{"id": 1, "title": {"english": "X"}}]}},
    }
    client, _seen = _client(bad)
    with client:
        with pytest.raises(ProviderResponseError, match="anilist"):
            search("anilist", "Claymore", title_languages=["en"], client=client)
    client, _seen = _client({"data": {"Media": None}})
    with client:
        with pytest.raises(ProviderResponseError, match="anilist"):
            load(
                "anilist",
                "42",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
            )


def test_jikan_french_title_dates_and_credits() -> None:
    body = {
        "data": {
            "mal_id": 26,
            "titles": [
                {"type": "French", "title": "Titre FR"},
                {"type": "English", "title": "Title EN"},
            ],
            "serializations": [{"name": "Shueisha"}],
            "genres": [{"name": "Action"}, {"name": "Drama"}],
            "themes": [{"name": "School"}],
            "demographics": [{"name": "Seinen"}],
            "explicit_genres": [{"name": "Erotica"}],
            "synopsis": "<p>Hello&nbsp;there</p>",
            "url": "https://myanimelist.net/manga/26",
            "volumes": 18,
            "published": {"prop": {"from": {"year": 2001, "month": 6, "day": None}}},
            "authors": [
                {"name": "Tsugumi Ohba", "type": "Story & Art"},
                {"name": "Nobody", "type": "Partial"},
            ],
        }
    }
    client, seen = _client(body)
    with client:
        patch = load(
            "jikan",
            "26",
            filename_stem="Monster 01",
            title_languages=["fr", "en"],
            client=client,
        )
    _assert_patch(patch)
    assert patch["Series"] == "Titre FR"
    assert patch["Title"] == "Titre FR"
    assert patch["LanguageISO"] == "fr"
    assert patch["Publisher"] == "Shueisha"
    assert patch["Genre"] == "Action, Drama"
    assert "School" not in patch["Genre"]
    assert "Seinen" not in patch["Genre"]
    assert patch["Summary"] == "Hello there"
    assert patch["Year"] == "2001"
    assert patch["Month"] == "6"
    assert "Day" not in patch
    assert patch["Writer"] == "Tsugumi Ohba"
    assert patch["Penciller"] == "Tsugumi Ohba"
    assert patch["CoverArtist"] == "Tsugumi Ohba"
    assert patch["Web"] == "https://myanimelist.net/manga/26"
    assert patch["Manga"] == "YesAndRightToLeft"
    assert patch["Number"] == "1"
    assert patch["Count"] == "18"
    request = seen[0]
    assert request.method == "GET"
    assert _bare(request) == "https://api.tenrai.org/v1/manga/26/full"
    assert request.headers["user-agent"] == "manga-tagger"


def test_jikan_search_original_title_and_unique_names() -> None:
    search_body = {
        "data": [
            {
                "mal_id": 26,
                "titles": [
                    {"type": "French", "title": "Titre FR"},
                    {"type": "English", "title": "Title EN"},
                ],
                "published": {
                    "prop": {"from": {"year": 2001, "month": 6, "day": None}}
                },
                "authors": [{"name": "Tsugumi Ohba", "type": "Story"}],
                "volumes": 12,
                "chapters": 108,
                "synopsis": "<p>Death Note synopsis</p>",
                "images": {
                    "jpg": {
                        "image_url": "https://example.com/large.jpg",
                        "small_image_url": "https://example.com/small.jpg",
                    }
                },
            }
        ]
    }
    client, seen = _client(search_body)
    with client:
        found = search(
            "jikan", "Death Note", title_languages=["fr", "en"], client=client
        )
    assert found == [
        Candidate(
            id="26",
            title="Titre FR",
            year="2001",
            credit="Tsugumi Ohba",
            count="12",
            summary="Death Note synopsis",
            cover="https://example.com/large.jpg",
        )
    ]
    assert seen[0].url.params.get("q") == "Death Note"
    assert seen[0].url.params.get("limit") == "10"
    assert seen[0].url.params.get("sfw") == "false"
    assert _bare(seen[0]) == "https://api.tenrai.org/v1/manga"

    japanese = {
        "data": {
            "titles": [{"type": "Japanese", "title": "日本語"}],
            "published": {},
        }
    }
    client, _seen = _client(japanese)
    with client:
        patch = load(
            "jikan",
            "26",
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert patch["Series"] == "日本語"
    assert patch["LanguageISO"] == "ja"
    assert "Year" not in patch

    default = {
        "data": {
            "titles": [{"type": "Default", "title": "Fallback"}],
            "authors": [
                {"name": "A", "type": "Story"},
                {"name": "A", "type": "Story"},
                {"name": "B", "type": "Story"},
            ],
        }
    }
    client, _seen = _client(default)
    with client:
        patch = load(
            "jikan",
            "26",
            filename_stem="Claymore",
            title_languages=["fr", "en"],
            client=client,
        )
    assert patch["Series"] == "Fallback"
    assert "LanguageISO" not in patch
    assert patch["Writer"] == "A, B"
    assert "Penciller" not in patch

    client, seen = _client({"data": []})
    with client:
        assert search("jikan", "None", title_languages=["en"], client=client) == []
    assert len(seen) == 1
    client, _seen = _client({"data": []})
    with client:
        with pytest.raises(ProviderResponseError, match="jikan"):
            load(
                "jikan",
                "26",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
            )


def test_comicvine_load_roles_and_summary() -> None:
    issue = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "id": 99,
            "issue_number": "1",
            "name": "The Sleep of the Just",
            "description": "<b>Plot</b>",
            "cover_date": "1989-01-01",
            "site_detail_url": "https://comicvine.gamespot.com/sandman/4000-99/",
            "volume": {"id": 12345, "name": "Sandman"},
            "person_credits": [
                {"name": "Alan Moore", "role": "writer, artist"},
                {"name": "Dave Gibbons", "role": "cover"},
                {"name": "Joe", "role": "inker"},
                {"name": "Kim", "role": "Cover Artist"},
            ],
        },
    }
    volume = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "name": "Sandman",
            "count_of_issues": 75,
            "site_detail_url": "https://comicvine.gamespot.com/sandman/4050-12345/",
            "person_credits": [],
        },
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/api/volume/" in str(request.url):
            return httpx.Response(200, json=volume)
        return httpx.Response(200, json=issue)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        patch = load(
            "comicvine",
            "12345",
            filename_stem="Sandman",
            title_languages=["fr", "en"],
            client=client,
            api_key="secret",
            issue_id="99",
        )
    assert all(isinstance(value, str) and value for value in patch.values())
    for key in _FORBIDDEN:
        assert key not in patch
    assert patch["Series"] == "Sandman"
    assert patch["Title"] == "The Sleep of the Just"
    assert patch["Number"] == "1"
    assert patch["Count"] == "75"
    assert patch["Manga"] == "No"
    assert "LanguageISO" not in patch
    assert "Publisher" not in patch
    assert patch["Summary"] == "Plot"
    assert patch["Year"] == "1989"
    assert patch["Month"] == "1"
    assert patch["Day"] == "1"
    assert patch["Writer"] == "Alan Moore"
    assert patch["Penciller"] == "Alan Moore"
    assert patch["CoverArtist"] == "Dave Gibbons, Kim"
    assert "Alan Moore" not in patch["CoverArtist"]
    assert patch["Inker"] == "Joe"
    assert patch["Web"] == "https://comicvine.gamespot.com/sandman/4000-99/"
    assert _bare(seen[0]) == "https://comicvine.gamespot.com/api/issue/4000-99/"
    assert seen[0].url.params.get("api_key") == "secret"
    assert seen[0].url.params.get("format") == "json"
    assert seen[0].headers["user-agent"] == "manga-tagger"
    assert _bare(seen[1]) == "https://comicvine.gamespot.com/api/volume/4050-12345/"
    assert "count_of_issues" in (seen[1].url.params.get("field_list") or "")


def test_comicvine_search_deck_and_year_string() -> None:
    body = {
        "error": "OK",
        "status_code": "1",
        "results": [
            {
                "id": 12345,
                "name": "Sandman",
                "start_year": "1989",
                "publisher": {"name": "DC Comics"},
                "count_of_issues": 75,
                "deck": "Dream of the Endless.",
                "description": "<p>Longer</p>",
                "image": {
                    "thumb_url": "https://example.com/thumb.jpg",
                    "small_url": "https://example.com/small.jpg",
                    "medium_url": "https://example.com/medium.jpg",
                    "super_url": "https://example.com/super.jpg",
                },
            },
            {"id": 8, "name": "  "},
        ],
    }
    client, seen = _client(body)
    with client:
        found = search(
            "comicvine",
            "Sandman",
            title_languages=["en"],
            client=client,
            api_key="secret",
        )
    assert found == [
        Candidate(
            id="12345",
            title="Sandman",
            year="1989",
            credit="DC Comics",
            count="75",
            summary="Dream of the Endless.",
            cover="https://example.com/super.jpg",
        )
    ]
    request = seen[0]
    assert _bare(request) == "https://comicvine.gamespot.com/api/search/"
    assert request.url.params.get("resources") == "volume"
    assert request.url.params.get("query") == "Sandman"
    assert request.url.params.get("limit") == "10"
    assert request.url.params.get("field_list") == (
        "id,name,start_year,publisher,image,count_of_issues,deck,description"
    )
    assert "4050-" not in found[0].id

    deck = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "id": 99,
            "issue_number": "1",
            "name": "Sandman",
            "description": "<p></p>",
            "volume": {"name": "Sandman"},
            "cover_date": "2001-06",
        },
    }
    client, _seen = _client(deck)
    with client:
        patch = load(
            "comicvine",
            "12345",
            filename_stem="Sandman",
            title_languages=["en"],
            client=client,
            api_key="secret",
            issue_id="99",
        )
    assert "Summary" not in patch
    assert patch["Year"] == "2001"
    assert patch["Month"] == "6"

    blank_year = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "id": 99,
            "issue_number": "1",
            "name": "Sandman",
            "volume": {"name": "Sandman"},
            "cover_date": "  ",
        },
    }
    client, _seen = _client(blank_year)
    with client:
        patch = load(
            "comicvine",
            "12345",
            filename_stem="Sandman",
            title_languages=["en"],
            client=client,
            api_key="secret",
            issue_id="99",
        )
    assert "Year" not in patch


def test_comicvine_blank_key_and_api_error() -> None:
    with _forbid_client() as client:
        for api_key in ("", "   "):
            with pytest.raises(
                ProviderUnavailableError, match="Comic Vine API key is not set"
            ):
                search(
                    "comicvine",
                    "Sandman",
                    title_languages=["en"],
                    client=client,
                    api_key=api_key,
                )
            with pytest.raises(
                ProviderUnavailableError, match="Comic Vine API key is not set"
            ):
                load(
                    "comicvine",
                    "12345",
                    filename_stem="Sandman",
                    title_languages=["en"],
                    client=client,
                    api_key=api_key,
                    issue_id="99",
                )


def test_disabled_provider_raises_without_http() -> None:
    with _forbid_client() as client:
        with pytest.raises(ProviderUnavailableError, match="provider is disabled"):
            search(
                "mangadex",
                "Claymore",
                title_languages=["en"],
                client=client,
                enabled_providers=["anilist"],
            )
        with pytest.raises(ProviderUnavailableError, match="provider is disabled"):
            load(
                "mangadex",
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
                enabled_providers=[],
            )
        with pytest.raises(ProviderUnavailableError, match="provider is disabled"):
            list_issues(
                "comicvine",
                "12345",
                title_languages=["en"],
                client=client,
                api_key="secret",
                enabled_providers=["mangadex"],
            )


def test_disabled_provider_before_blank_query() -> None:
    with _forbid_client() as client:
        with pytest.raises(ProviderUnavailableError, match="provider is disabled"):
            search(
                "mangadex",
                "",
                title_languages=["en"],
                client=client,
                enabled_providers=["anilist"],
            )
    client, _seen = _client({"data": []})
    assert (
        search(
            "mangadex",
            "",
            title_languages=["en"],
            client=client,
            enabled_providers=["mangadex"],
        )
        == []
    )
    client.close()


def test_comicvine_api_error_status() -> None:
    client, seen = _client(
        {
            "error": "OK",
            "status_code": 2,
            "results": {
                "id": 99,
                "issue_number": "1",
                "name": "Sandman",
                "volume": {"name": "Sandman"},
            },
        }
    )
    with client:
        with pytest.raises(ProviderResponseError, match="comicvine"):
            load(
                "comicvine",
                "12345",
                filename_stem="Sandman",
                title_languages=["en"],
                client=client,
                api_key="secret",
                issue_id="99",
            )
    assert len(seen) == 1
    client, _seen = _client(
        {"error": "Invalid API Key", "status_code": 1, "results": []}
    )
    with client:
        with pytest.raises(ProviderResponseError, match="comicvine"):
            search(
                "comicvine",
                "Sandman",
                title_languages=["en"],
                client=client,
                api_key="secret",
            )
    client, seen = _client({"error": "OK", "status_code": 1, "results": None})
    with client:
        assert (
            search(
                "comicvine",
                "Sandman",
                title_languages=["en"],
                client=client,
                api_key="secret",
            )
            == []
        )
    assert len(seen) == 1


def test_illegal_match_id_sends_nothing() -> None:
    with _forbid_client() as client:
        for provider, match_id in (
            ("anilist", "01"),
            ("jikan", "1.5"),
            ("comicvine", "12/3"),
            ("comicvine", "bad id"),
            ("mangadex", "abc def"),
            ("nautiljon", "slug with space"),
            ("nautiljon", "slug/path"),
            ("anilist", ""),
            ("jikan", " 12"),
        ):
            with pytest.raises(ProviderResponseError, match=provider):
                load(
                    provider,
                    match_id,
                    filename_stem="Claymore",
                    title_languages=["en"],
                    client=client,
                    api_key="",
                    nautiljon_base_url="https://nj.example",
                    nautiljon_api_key="secret",
                )


def test_anilist_zero_id_is_sent() -> None:
    client, seen = _client({"data": {"Media": None}})
    with client:
        with pytest.raises(ProviderResponseError):
            load(
                "anilist",
                "0",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
            )
    assert len(seen) == 1
    assert json.loads(seen[0].content)["variables"] == {"id": 0}


def test_rate_limit_timeout_and_bad_http() -> None:
    client, seen = _client(httpx.Response(429, content=b"not-json"))
    with client:
        with pytest.raises(ProviderRateLimitError, match="mangadex"):
            search("mangadex", "Claymore", title_languages=["en"], client=client)
    assert len(seen) == 1

    client, seen = _raising(httpx.ConnectError)
    with client:
        with pytest.raises(ProviderTimeoutError, match="jikan"):
            search("jikan", "Claymore", title_languages=["en"], client=client)
    assert len(seen) == 1

    client, seen = _raising(httpx.ReadTimeout)
    with client:
        with pytest.raises(ProviderTimeoutError, match="anilist"):
            search("anilist", "Claymore", title_languages=["en"], client=client)
    assert len(seen) == 1

    client, seen = _client(httpx.Response(500, json={"error": "down"}))
    with client:
        with pytest.raises(ProviderResponseError, match="mangadex"):
            search("mangadex", "Claymore", title_languages=["en"], client=client)
    assert len(seen) == 1

    client, _seen = _client(httpx.Response(200, content=b"not-json"))
    with client:
        with pytest.raises(ProviderResponseError, match="comicvine"):
            search(
                "comicvine",
                "Sandman",
                title_languages=["en"],
                client=client,
                api_key="secret",
            )


def test_cancel_sends_nothing() -> None:
    def cancel() -> bool:
        return True

    with _forbid_client() as client:
        with pytest.raises(ProviderCancelledError):
            search(
                "mangadex",
                "Claymore",
                title_languages=["en"],
                client=client,
                cancel=cancel,
            )
        with pytest.raises(ProviderCancelledError):
            load(
                "anilist",
                "42",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
                cancel=cancel,
            )


def test_search_and_load_write_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    hit = {
        "id": MD_ID,
        "attributes": {"title": {"en": "Claymore"}, "originalLanguage": "en"},
        "relationships": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/manga":
            return httpx.Response(200, json={"data": [hit]})
        return httpx.Response(200, json={"result": "ok", "data": hit})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = search("mangadex", "Claymore", title_languages=["en"], client=client)
        patch = load(
            "mangadex",
            MD_ID,
            filename_stem="Claymore v02",
            title_languages=["en"],
            client=client,
        )
    assert found[0].title == "Claymore"
    assert patch["Number"] == "2"
    assert patch["Title"] == patch["Series"] == "Claymore"
    assert list(tmp_path.iterdir()) == []


def test_nautiljon_search_request_and_candidate() -> None:
    payload = {
        "sourceUrl": "https://www.nautiljon.com/mangas/?q=town",
        "results": [
            {
                "cover": "https://www.nautiljon.com/images/manga/00/cover.jpg",
                "title": "A town where you live",
                "url": "https://www.nautiljon.com/mangas/a+town+where+you+live.html",
                "description": "Haruto <b>Kirishima</b>",
                "issues": 27,
                "dateVo": "2008",
            },
            {
                "title": "",
                "url": "https://www.nautiljon.com/mangas/empty.html",
            },
        ],
    }
    client, seen = _client(payload)
    with client:
        found = search(
            "nautiljon",
            "town",
            title_languages=["fr", "en"],
            client=client,
            nautiljon_base_url="https://nj.example/",
            nautiljon_api_key="secret",
        )
    assert len(seen) == 1
    assert _bare(seen[0]) == "https://nj.example/v1/search"
    assert seen[0].url.params["q"] == "town"
    assert seen[0].headers["x-api-key"] == "secret"
    assert seen[0].headers["user-agent"] == "manga-tagger"
    assert found == [
        Candidate(
            id="a+town+where+you+live",
            title="A town where you live",
            year="2008",
            credit="",
            count="27",
            summary="Haruto Kirishima",
            cover="https://www.nautiljon.com/images/manga/00/cover.jpg",
        )
    ]


def test_nautiljon_load_french_credits_and_volume() -> None:
    series = {
        "sourceUrl": "https://www.nautiljon.com/mangas/berserk.html",
        "title": "Berserk",
        "issues": 41,
        "volumeUrls": [
            "https://www.nautiljon.com/mangas/berserk/volume-1,3278.html",
        ],
        "infos": {
            "titreOriginal": "ベルセルク",
            "origine": "Japon - 1989",
            "anneeVf": "2004",
            "genres": ["Action", "Horreur"],
            "themes": ["Vengeance"],
            "auteurs": ["Miura Kentaro (auteur)"],
            "editeurVo": "Hakusensha",
            "editeurVf": "Glénat ( Seinen )",
            "ageConseille": "18 ans et +",
        },
        "extra": {"Dessinateur": "Studio Gaga"},
        "synopsis": "Series <i>synopsis</i>",
    }
    volume = {
        "number": 1,
        "cover": "https://www.nautiljon.com/images/manga_volumes/00/87/3278.webp",
        "rating": 8.45,
        "releaseDateVf": "06/10/2004",
        "description": "Volume <b>one</b> résumé",
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/volumes/" in request.url.path:
            return httpx.Response(200, json=volume)
        return httpx.Response(200, json=series)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        patch = load(
            "nautiljon",
            "berserk",
            filename_stem="Berserk v01",
            title_languages=["fr", "en"],
            client=client,
            nautiljon_base_url="https://nj.example",
            nautiljon_api_key="secret",
        )
    assert [request.url.path for request in seen] == [
        "/v1/series/berserk",
        "/v1/series/berserk/volumes/1",
    ]
    assert seen[0].headers["x-api-key"] == "secret"
    assert patch["Series"] == patch["Title"] == "Berserk"
    assert patch["LanguageISO"] == "fr"
    assert patch["Manga"] == "YesAndRightToLeft"
    assert patch["Publisher"] == "Glénat ( Seinen )"
    assert patch["Writer"] == "Miura Kentaro"
    assert patch["Penciller"] == patch["CoverArtist"] == "Studio Gaga"
    assert patch["Genre"] == "Action, Horreur, Vengeance"
    assert patch["AgeRating"] == "18 ans et +"
    assert patch["Web"] == "https://www.nautiljon.com/mangas/berserk/volume-1,3278.html"
    assert patch["Summary"] == "Volume one résumé"
    assert patch["Year"] == "2004"
    assert patch["Month"] == "10"
    assert patch["Day"] == "6"
    assert patch["Number"] == "1"
    assert patch["Count"] == "41"
    assert patch["CommunityRating"] == "8.45"
    _assert_patch(patch)


def test_nautiljon_volume_404_raises_on_resolve() -> None:
    series = {
        "sourceUrl": "https://www.nautiljon.com/mangas/berserk.html",
        "title": "Berserk",
        "infos": {},
        "synopsis": "Series only",
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/volumes/" in request.url.path:
            return httpx.Response(404, json={"detail": "missing"})
        return httpx.Response(200, json=series)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        with pytest.raises(ProviderResponseError, match="could not find an issue"):
            load(
                "nautiljon",
                "berserk",
                filename_stem="Berserk v01",
                title_languages=["fr"],
                client=client,
                nautiljon_base_url="https://nj.example",
                nautiljon_api_key="secret",
            )
    assert len(seen) == 2


def test_nautiljon_missing_number_raises() -> None:
    with _forbid_client() as client:
        with pytest.raises(ProviderResponseError, match="could not find an issue"):
            load(
                "nautiljon",
                "berserk",
                filename_stem="Berserk",
                title_languages=["ja", "fr"],
                client=client,
                nautiljon_base_url="https://nj.example",
                nautiljon_api_key="secret",
            )


def test_nautiljon_load_many_mode_series_only() -> None:
    series = {
        "sourceUrl": "https://www.nautiljon.com/mangas/berserk.html",
        "title": "Berserk",
        "issues": 41,
        "infos": {
            "titreOriginal": "ベルセルク",
            "origine": "Japon - 1989",
            "editeurVf": "Glénat",
            "auteurs": ["Miura Kentaro (auteur)"],
        },
        "synopsis": "Series only",
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/volumes/" in request.url.path:
            raise AssertionError(f"unexpected volume request {request.url.path}")
        return httpx.Response(200, json=series)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        patch = load(
            "nautiljon",
            "berserk",
            filename_stem="Berserk v02",
            title_languages=["ja", "fr"],
            client=client,
            nautiljon_base_url="https://nj.example",
            nautiljon_api_key="secret",
            mode="many",
        )
    assert [request.url.path for request in seen] == ["/v1/series/berserk"]
    assert patch["Series"] == "ベルセルク"
    assert patch["Publisher"] == "Glénat"
    assert patch["Count"] == "41"
    assert patch["Summary"] == "Series only"
    assert "Number" not in patch


def test_nautiljon_blank_settings_send_nothing() -> None:
    with _forbid_client() as client:
        with pytest.raises(
            ProviderUnavailableError, match="Nautiljon base URL is not set"
        ):
            search(
                "nautiljon",
                "Berserk",
                title_languages=["fr"],
                client=client,
                nautiljon_base_url="",
                nautiljon_api_key="secret",
            )
        with pytest.raises(
            ProviderUnavailableError, match="Nautiljon API key is not set"
        ):
            load(
                "nautiljon",
                "berserk",
                filename_stem="Berserk",
                title_languages=["fr"],
                client=client,
                nautiljon_base_url="https://nj.example",
                nautiljon_api_key="   ",
            )


def test_list_issues_unsupported_providers_send_nothing() -> None:
    with _forbid_client() as client:
        for provider in ("mangadex", "anilist", "jikan"):
            assert (
                list_issues(
                    provider,
                    MD_ID if provider == "mangadex" else "42",
                    title_languages=["fr"],
                    client=client,
                )
                == []
            )


def test_comicvine_list_issues_and_load_by_number() -> None:
    page = {
        "error": "OK",
        "status_code": 1,
        "number_of_total_results": 2,
        "results": [
            {
                "id": 10,
                "issue_number": "01",
                "name": "First",
                "cover_date": "2001-03-15",
                "description": "<p>One</p>",
                "image": {"super_url": "https://example.com/1.jpg"},
            },
            {
                "id": 11,
                "issue_number": "2",
                "name": "Second",
                "cover_date": "2001",
                "description": "",
                "image": {},
            },
        ],
    }
    issue = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "id": 10,
            "issue_number": "1",
            "name": "First",
            "description": "<p>One</p>",
            "cover_date": "2001-03-15",
            "site_detail_url": "https://comicvine.gamespot.com/i/4000-10/",
            "volume": {"name": "Claymore"},
            "person_credits": [],
        },
    }
    volume = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "name": "Claymore",
            "count_of_issues": 27,
            "person_credits": [],
        },
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if "/api/issues/" in url:
            return httpx.Response(200, json=page)
        if "/api/volume/" in url:
            return httpx.Response(200, json=volume)
        return httpx.Response(200, json=issue)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        found = list_issues(
            "comicvine",
            "12345",
            title_languages=["en"],
            client=client,
            api_key="secret",
        )
        patch = load(
            "comicvine",
            "12345",
            filename_stem="Claymore v99",
            title_languages=["en"],
            client=client,
            api_key="secret",
            number="1",
        )
    assert found == [
        IssueCandidate(
            id="10",
            number="01",
            title="First",
            date="2001-03",
            cover="https://example.com/1.jpg",
            summary="One",
        ),
        IssueCandidate(
            id="11",
            number="2",
            title="Second",
            date="2001",
            cover="",
            summary="",
        ),
    ]
    assert seen[0].url.params.get("filter") == "volume:12345"
    assert any(
        _bare(request) == "https://comicvine.gamespot.com/api/issue/4000-10/"
        for request in seen
    )
    assert patch["Number"] == "1"
    assert patch["Series"] == "Claymore"
    assert patch["Title"] == "First"
    assert patch["Count"] == "27"
    assert patch["Web"] == "https://comicvine.gamespot.com/i/4000-10/"


def test_comicvine_load_by_number_misses() -> None:
    page = {
        "error": "OK",
        "status_code": 1,
        "number_of_total_results": 0,
        "results": [],
    }
    client, _seen = _client(page)
    with client:
        with pytest.raises(ProviderResponseError, match="could not find an issue"):
            load(
                "comicvine",
                "12345",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
                api_key="secret",
                number="9",
            )
        with pytest.raises(ProviderResponseError, match="could not find an issue"):
            load(
                "comicvine",
                "12345",
                filename_stem="Claymore",
                title_languages=["en"],
                client=client,
                api_key="secret",
            )


def test_comicvine_load_many_mode_series_only() -> None:
    volume = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "name": "Claymore",
            "start_year": "2001",
            "count_of_issues": 27,
            "publisher": {"name": "Viz"},
            "description": "<p>Series</p>",
            "site_detail_url": "https://comicvine.gamespot.com/claymore/4050-12345/",
            "person_credits": [{"name": "Norihiro Yagi", "role": "writer"}],
        },
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/api/volume/" in str(request.url):
            return httpx.Response(200, json=volume)
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        patch = load(
            "comicvine",
            "12345",
            filename_stem="Claymore v02",
            title_languages=["en"],
            client=client,
            api_key="secret",
            mode="many",
        )
    assert len(seen) == 1
    assert _bare(seen[0]) == "https://comicvine.gamespot.com/api/volume/4050-12345/"
    assert patch["Series"] == "Claymore"
    assert patch["Publisher"] == "Viz"
    assert patch["Count"] == "27"
    assert patch["Manga"] == "No"
    assert "Number" not in patch


def test_nautiljon_list_issues_and_load_issue_id() -> None:
    series = {
        "title": "Berserk",
        "infos": {"titreOriginal": "ベルセルク", "origine": "Japon - 1989"},
        "synopsis": "Series",
        "sourceUrl": "https://www.nautiljon.com/mangas/berserk.html",
        "volumeUrls": [
            "https://www.nautiljon.com/mangas/berserk/volume-1,3278.html",
            "https://www.nautiljon.com/mangas/berserk/volume-2,3279.html",
            "https://www.nautiljon.com/mangas/volumes/berserk,2.html",
        ],
        "issues": 41,
    }
    volumes = {
        "1": {
            "number": 1,
            "cover": "https://www.nautiljon.com/images/manga_volumes/00/87/3278.webp",
            "rating": 8.0,
            "releaseDateVf": "06/10/2004",
            "description": "Volume <b>one</b>",
        },
        "2": {
            "number": 2,
            "cover": "https://www.nautiljon.com/images/manga_volumes/00/88/3279.webp",
            "rating": 7.5,
            "releaseDateVf": "15/01/2005",
            "description": "Volume <b>two</b>",
        },
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.endswith("/volumes/1"):
            return httpx.Response(200, json=volumes["1"])
        if path.endswith("/volumes/2"):
            return httpx.Response(200, json=volumes["2"])
        return httpx.Response(200, json=series)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        found = list_issues(
            "nautiljon",
            "berserk",
            title_languages=["fr"],
            client=client,
            nautiljon_base_url="https://nj.example",
            nautiljon_api_key="secret",
        )
        patch = load(
            "nautiljon",
            "berserk",
            filename_stem="Berserk",
            title_languages=["ja", "fr"],
            client=client,
            nautiljon_base_url="https://nj.example",
            nautiljon_api_key="secret",
            issue_id="2",
        )
    assert found == [
        IssueCandidate(
            id="1",
            number="1",
            title="Tome 1",
            date="2004-10",
            cover="https://www.nautiljon.com/images/manga_volumes/00/87/3278.webp",
            summary="Volume one",
        ),
        IssueCandidate(
            id="2",
            number="2",
            title="Tome 2",
            date="2005-01",
            cover="https://www.nautiljon.com/images/manga_volumes/00/88/3279.webp",
            summary="Volume two",
        ),
    ]
    assert [request.url.path for request in seen[:3]] == [
        "/v1/series/berserk",
        "/v1/series/berserk/volumes/1",
        "/v1/series/berserk/volumes/2",
    ]
    assert patch["Series"] == "ベルセルク"
    assert patch["LanguageISO"] == "ja"
    assert patch["Number"] == "2"
    assert patch["Summary"] == "Volume two"
    assert patch["CommunityRating"] == "7.5"
    assert patch["Count"] == "41"
    assert patch["Web"] == "https://www.nautiljon.com/mangas/berserk/volume-2,3279.html"
    assert any(request.url.path.endswith("/volumes/2") for request in seen)

def _assert_patch(patch: dict[str, str]) -> None:
    assert patch["Title"] == patch["Series"]
    assert all(isinstance(value, str) and value for value in patch.values())
    for key in _FORBIDDEN:
        assert key not in patch


def _anilist_media(**overrides: object) -> dict[str, object]:
    media: dict[str, object] = {
        "id": 42,
        "title": {"romaji": "Roma", "english": "English", "native": "Native"},
        "countryOfOrigin": "JP",
    }
    media.update(overrides)
    return {"data": {"Media": media}}


def _client(
    payload: dict[str, object] | httpx.Response,
) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if isinstance(payload, httpx.Response):
            return payload
        return httpx.Response(200, json=payload)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "other-agent"},
    )
    return client, seen


def _raising(
    exc_type: type[Exception],
) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        raise exc_type("down")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return client, seen


def _forbid_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def _bare(request: httpx.Request) -> str:
    return str(request.url.copy_with(query=None))
