"""Hermetic provider identity, full-size selection, and download tests."""

import httpx
import pytest

from manga_tagger.providers.cover import resolve_cover, resolve_cover_from_web
from manga_tagger.providers.errors import (
    ProviderCancelledError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from manga_tagger.providers.remote_cover import RemoteCoverError, remote_cover_bytes
from manga_tagger.providers.web_id import parse_web

UUID = "11111111-2222-3333-4444-555555555555"


@pytest.mark.parametrize(
    "url,provider,match,issue,number",
    [
        (f"https://mangadex.org/title/{UUID}/title", "mangadex", UUID, "", ""),
        ("https://anilist.co/manga/12/title", "anilist", "12", "", ""),
        ("https://www.myanimelist.net/manga/34/title?x=y", "jikan", "34", "", ""),
        ("https://comicvine.gamespot.com/title/4050-56/", "comicvine", "56", "", ""),
        ("https://comicvine.gamespot.com/title/4000-78/", "comicvine", "", "78", ""),
        ("https://www.nautiljon.com/mangas/a+b.html", "nautiljon", "a+b", "", ""),
        (
            "https://www.nautiljon.com/mangas/a+b/volume-03,42.html",
            "nautiljon",
            "a+b",
            "",
            "3",
        ),
        (
            "https://www.nautiljon.com/mangas/volumes/a+b,03.html",
            "nautiljon",
            "a+b",
            "",
            "3",
        ),
    ],
)
def test_parse_known_web(url, provider, match, issue, number):
    identity = parse_web(url)
    assert (
        identity.provider,
        identity.match_id,
        identity.issue_id,
        identity.volume_number,
    ) == (provider, match, issue, number)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "garbage",
        "http://anilist.co/manga/1",
        "https://example.org/manga/1",
        "https://anilist.co.evil/manga/1",
        "https://anilist.co/manga/1junk",
        "https://anilist.co/manga/١",
        "https://anilist.co/wrong/manga/1",
        "https://name@anilist.co/manga/1",
        "https://[bad",
        "https://nautiljon.com/volume-1,42.html",
        "https://mangadex.org/title/------------------------------------",
    ],
)
def test_reject_invalid_web(url):
    with pytest.raises(ProviderResponseError):
        parse_web(url)


def md_art(volume, name):
    return {"type": "cover_art", "attributes": {"volume": volume, "fileName": name}}


@pytest.mark.parametrize("number", ["", "02"])
def test_mangadex_full_size_and_relationship_volume(number):
    def handler(request):
        assert request.url.path == f"/manga/{UUID}"
        assert request.url.params.get("includes[]") == "cover_art"
        return httpx.Response(
            200,
            json={
                "result": "ok",
                "data": {
                    "relationships": [
                        md_art(None, "series.jpg"),
                        md_art("2", "volume.jpg"),
                    ]
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ref = resolve_cover("mangadex", UUID, number=number, client=client)
    assert ref.filename == ("volume.jpg" if number else "series.jpg")
    assert ref.url == f"https://uploads.mangadex.org/covers/{UUID}/{ref.filename}"
    assert ".256" not in ref.url


@pytest.mark.parametrize("found", [True, False])
def test_mangadex_volume_paginates_and_falls_back(found):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.startswith("/manga/"):
            return httpx.Response(
                200,
                json={
                    "result": "ok",
                    "data": {"relationships": [md_art(None, "series.jpg")]},
                },
            )
        assert request.url.path == "/cover"
        assert request.url.params["manga[]"] == UUID
        offset = int(request.url.params["offset"])
        return httpx.Response(
            200,
            json={
                "result": "ok",
                "data": [md_art("2" if offset and found else "1", "volume.jpg")],
                "total": 2,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ref = resolve_cover("mangadex", UUID, number="02", client=client)
    assert ref.filename == ("volume.jpg" if found else "series.jpg")
    assert calls == [f"/manga/{UUID}", "/cover", "/cover"]


@pytest.mark.parametrize(
    "provider,body,url",
    [
        (
            "anilist",
            {
                "data": {
                    "Media": {
                        "coverImage": {
                            "extraLarge": "https://s4.anilist.co/full.jpg?x=1",
                            "large": "https://s4.anilist.co/small.jpg",
                        }
                    }
                }
            },
            "https://s4.anilist.co/full.jpg?x=1",
        ),
        (
            "anilist",
            {
                "data": {
                    "Media": {
                        "coverImage": {"large": "https://s4.anilist.co/fallback.jpg"}
                    }
                }
            },
            "https://s4.anilist.co/fallback.jpg",
        ),
        (
            "jikan",
            {
                "data": {
                    "images": {
                        "jpg": {
                            "image_url": "https://cdn.myanimelist.net/full.jpg",
                            "small_image_url": "https://cdn.myanimelist.net/small.jpg",
                        }
                    }
                }
            },
            "https://cdn.myanimelist.net/full.jpg",
        ),
        (
            "comicvine",
            {
                "status_code": 1,
                "error": "OK",
                "results": {
                    "image": {
                        "super_url": "https://comicvine.gamespot.com/full.jpg",
                        "medium_url": "https://comicvine.gamespot.com/small.jpg",
                    }
                },
            },
            "https://comicvine.gamespot.com/full.jpg",
        ),
        (
            "nautiljon",
            {"cover": "https://www.nautiljon.com/full.jpg"},
            "https://www.nautiljon.com/full.jpg",
        ),
    ],
)
def test_catalog_full_size(provider, body, url):
    def handler(request):
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ref = resolve_cover(
            provider,
            "12",
            client=client,
            api_key="key",
            nautiljon_base_url="https://wrapper.test",
            nautiljon_api_key="key",
        )
    assert ref.url == url
    assert ref.filename == url.split("/")[-1].split("?")[0]


def test_comicvine_issue_url_uses_issue_image():
    def handler(request):
        assert request.url.path == "/api/issue/4000-42/"
        return httpx.Response(
            200,
            json={
                "status_code": 1,
                "error": "OK",
                "results": {
                    "image": {"super_url": "https://comicvine.gamespot.com/issue.jpg"}
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ref = resolve_cover_from_web(
            "https://comicvine.gamespot.com/title/4000-42/",
            client=client,
            api_key="key",
            number="99",
        )
    assert ref.filename == "issue.jpg"


def test_nautiljon_volume_from_web_and_form_override():
    def handler(request):
        assert request.headers["X-Api-Key"] == "key"
        if "/volumes/" in request.url.path:
            number = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200, json={"cover": f"https://www.nautiljon.com/{number}.jpg"}
            )
        return httpx.Response(
            200, json={"cover": "https://www.nautiljon.com/series.jpg"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for number, expected in [("", "3.jpg"), ("4", "4.jpg")]:
            ref = resolve_cover_from_web(
                "https://www.nautiljon.com/mangas/title/volume-3,42.html",
                client=client,
                number=number,
                nautiljon_base_url="https://wrapper.test",
                nautiljon_api_key="key",
            )
            assert ref.filename == expected


def test_provider_guards_do_not_request():
    def handler(request):
        pytest.fail("guard should reject before HTTP")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for provider, kwargs in [
            ("comicvine", {}),
            ("nautiljon", {}),
            ("anilist", {"enabled_providers": []}),
        ]:
            with pytest.raises(ProviderUnavailableError):
                resolve_cover(provider, "12", client=client, **kwargs)
        with pytest.raises(ProviderCancelledError):
            resolve_cover("anilist", "12", client=client, cancel=lambda: True)
        with pytest.raises(ProviderResponseError):
            resolve_cover_from_web("bad", client=client)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": {"Media": {"coverImage": {}}}},
        {"data": {"Media": {"coverImage": {"large": "http://s4.anilist.co/a.jpg"}}}},
    ],
)
def test_missing_cover_fails(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(ProviderResponseError):
            resolve_cover("anilist", "12", client=client)


@pytest.mark.parametrize(
    "host",
    [
        "s4.anilist.co",
        "cdn.myanimelist.net",
        "comicvine.gamespot.com",
        "static.comicvine.com",
    ],
)
def test_full_cover_download_hosts(host):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=b"image", headers={"content-type": "image/jpeg"}
            )
        )
    ) as client:
        assert remote_cover_bytes(f"https://{host}/a.jpg", client=client) == (
            b"image",
            "image/jpeg",
        )


def test_redirect_checks_destination_before_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://example.org/private"})

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(RemoteCoverError, match="not allowed"):
            remote_cover_bytes("https://s4.anilist.co/a.jpg", client=client)
    assert calls == ["https://s4.anilist.co/a.jpg"]


def test_relative_redirect_is_supported_and_empty_image_fails():
    def handler(request):
        if request.url.path == "/old.jpg":
            return httpx.Response(302, headers={"location": "/new.jpg"})
        return httpx.Response(200, content=b"", headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RemoteCoverError, match="empty"):
            remote_cover_bytes("https://s4.anilist.co/old.jpg", client=client)


def test_comicvine_series_number_resolves_issue_cover():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/issues/":
            assert request.url.params["filter"] == "volume:12"
            body = {
                "error": "OK",
                "status_code": 1,
                "number_of_total_results": 1,
                "results": [{"id": 42, "issue_number": "3", "name": "Issue three"}],
            }
        else:
            assert request.url.path == "/api/issue/4000-42/"
            body = {
                "error": "OK",
                "status_code": 1,
                "results": {
                    "image": {"super_url": "https://comicvine.gamespot.com/issue.jpg"}
                },
            }
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ref = resolve_cover(
            "comicvine", "12", number="03", client=client, api_key="key"
        )
    assert ref.filename == "issue.jpg"
    assert calls == ["/api/issues/", "/api/issue/4000-42/"]
