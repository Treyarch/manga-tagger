"""Hermetic catalog search and form-patch tests."""

import json

import httpx
import pytest

from manga_tagger.providers import (
    Candidate,
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    build_query,
    load,
    parse_number,
    search,
)

MD_ID = "6b1eb93e-473a-4ab3-9922-1a66d2a29a4b"
_FORBIDDEN = (
    "Volume",
    "Pages",
    "PageCount",
    "AgeRating",
    "CommunityRating",
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
        for provider in ("mangadex", "anilist", "jikan", "comicvine"):
            for query in ("", "   "):
                assert (
                    search(
                        provider,
                        query,
                        title_languages=["fr", "en"],
                        client=client,
                        api_key="",
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
    assert "Volume" not in patch
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
    request = seen[0]
    assert request.method == "POST"
    assert _bare(request) == "https://graphql.anilist.co"
    assert request.headers["user-agent"] == "manga-tagger"
    assert request.headers["accept"] == "application/json"
    assert request.headers["content-type"].startswith("application/json")
    payload = json.loads(request.content)
    assert "perPage: 25" in payload["query"]
    assert "type: MANGA" in payload["query"]
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
    assert "Volume" not in patch
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
    body = {
        "error": "OK",
        "status_code": 1,
        "results": {
            "name": "Sandman",
            "start_year": 1989,
            "publisher": {"name": "DC Comics"},
            "description": "<b>Plot</b>",
            "deck": "Deck text",
            "site_detail_url": "https://comicvine.gamespot.com/sandman/4050-12345/",
            "person_credits": [
                {"name": "Alan Moore", "role": "writer, artist"},
                {"name": "Dave Gibbons", "role": "cover"},
                {"name": "Joe", "role": "inker"},
                {"name": "Kim", "role": "Cover Artist"},
            ],
        },
    }
    client, seen = _client(body)
    with client:
        patch = load(
            "comicvine",
            "12345",
            filename_stem="Sandman",
            title_languages=["fr", "en"],
            client=client,
            api_key="secret",
        )
    _assert_patch(patch)
    assert patch["Series"] == "Sandman"
    assert patch["Title"] == "Sandman"
    assert patch["Manga"] == "No"
    assert "LanguageISO" not in patch
    assert patch["Publisher"] == "DC Comics"
    assert patch["Summary"] == "Plot"
    assert "Deck" not in patch["Summary"]
    assert patch["Year"] == "1989"
    assert "Month" not in patch
    assert "Day" not in patch
    assert patch["Writer"] == "Alan Moore"
    assert patch["Penciller"] == "Alan Moore"
    assert patch["CoverArtist"] == "Dave Gibbons, Kim"
    assert "Alan Moore" not in patch["CoverArtist"]
    assert patch["Inker"] == "Joe"
    assert patch["Web"] == "https://comicvine.gamespot.com/sandman/4050-12345/"
    assert "Number" not in patch
    assert "Volume" not in patch
    request = seen[0]
    assert _bare(request) == "https://comicvine.gamespot.com/api/volume/4050-12345/"
    assert request.url.params.get("api_key") == "secret"
    assert request.url.params.get("format") == "json"
    assert request.url.params.get("field_list") == (
        "name,start_year,publisher,description,deck,site_detail_url,person_credits"
    )
    assert request.headers["user-agent"] == "manga-tagger"


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
            "name": "Sandman",
            "description": "<p></p>",
            "deck": "Deck text",
            "start_year": " 2001 ",
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
        )
    assert patch["Summary"] == "Deck text"
    assert patch["Year"] == "2001"

    blank_year = {
        "error": "OK",
        "status_code": 1,
        "results": {"name": "Sandman", "start_year": "  "},
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
                )
    client, seen = _client(
        {"error": "OK", "status_code": 2, "results": {"name": "Sandman"}}
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
