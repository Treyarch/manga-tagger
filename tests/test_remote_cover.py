"""Allow-listed remote cover downloads."""

import httpx
import pytest

from manga_tagger.providers.remote_cover import RemoteCoverError, remote_cover_bytes


def test_remote_cover_bytes_allows_mangadex_host() -> None:
    jpeg = b"\xff\xd8\xff\xd9"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "uploads.mangadex.org"
        assert request.headers["user-agent"] == "manga-tagger"
        return httpx.Response(200, content=jpeg, headers={"content-type": "image/jpeg"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        payload, media = remote_cover_bytes(
            "https://uploads.mangadex.org/covers/a/b.jpg.256.jpg",
            client=client,
        )
    assert payload == jpeg
    assert media == "image/jpeg"


def test_remote_cover_bytes_rejects_other_hosts_and_non_images() -> None:
    with pytest.raises(RemoteCoverError, match="not allowed"):
        remote_cover_bytes("https://example.com/cover.jpg")
    with pytest.raises(RemoteCoverError, match="not allowed"):
        remote_cover_bytes("http://uploads.mangadex.org/covers/a/b.jpg")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"nope", headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        with pytest.raises(RemoteCoverError, match="not an image"):
            remote_cover_bytes(
                "https://uploads.mangadex.org/covers/a/b.jpg",
                client=client,
            )
