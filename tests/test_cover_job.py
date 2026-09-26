"""Cover job boundaries, cancellation, refresh, and HTTP integration."""

import io
import zipfile
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from manga_tagger.api import create_app
from manga_tagger.api.app import default_services
from manga_tagger.archives import ArchiveError, list_pages, read_comic_info, read_page
from manga_tagger.config import load_config
from manga_tagger.index import list_volumes, refresh_volume
from manga_tagger.jobs import JobCancelled, JobRunner
from manga_tagger.providers.cover import CoverRef
from manga_tagger.providers.remote_cover import RemoteCoverError
from manga_tagger.shell import run_cover


@pytest.fixture
def fixture_book(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (8, 12), "red").save(buf, "JPEG")
    new = buf.getvalue()
    buf = io.BytesIO()
    Image.new("RGB", (8, 12), "blue").save(buf, "JPEG")
    old = buf.getvalue()
    path = tmp_path / "book.cbz"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("01.jpg", old)
        archive.writestr(
            "ComicInfo.xml",
            "<ComicInfo><Series>Original</Series><Web>https://anilist.co/manga/1</Web><Number>1</Number></ComicInfo>",
        )
    return path, new


def job_args(tmp_path, path, payload):
    services = default_services()
    return dict(
        path=str(path),
        action="insert",
        web="https://anilist.co/manga/2",
        number="3",
        roots=[str(tmp_path)],
        keep_cbr_original=True,
        write_poster_on_save=False,
        api_key="",
        nautiljon_base_url="",
        nautiljon_api_key="",
        enabled_providers=["anilist"],
        db_path=str(tmp_path / "index.db"),
        cache_dir=str(tmp_path / "covers"),
        resolve_cover_from_web=lambda *a, **kw: CoverRef(
            "https://s4.anilist.co/cover.jpg", "cover.jpg"
        ),
        remote_cover_bytes=lambda *a, **kw: (payload, "image/jpeg"),
        replace_cover_page=services.replace_cover_page,
        insert_cover_page=services.insert_cover_page,
        write_poster=services.write_poster,
        refresh_volume=services.refresh_volume,
        forget_volume=services.forget_volume,
        copy_locked_fields=services.copy_locked_fields,
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("unexpected network"))
        ),
        cancel=lambda: False,
        progress=lambda *a: None,
    )


@pytest.mark.parametrize("stage", ["start", "resolve", "download"])
def test_cancel_before_write_leaves_archive_unchanged(tmp_path, fixture_book, stage):
    path, payload = fixture_book
    before = path.read_bytes()
    args = job_args(tmp_path, path, payload)
    cancelled = stage == "start"
    calls = []

    def resolve(*a, **kw):
        nonlocal cancelled
        calls.append("resolve")
        cancelled = stage == "resolve"
        return CoverRef("https://s4.anilist.co/cover.jpg", "cover.jpg")

    def download(*a, **kw):
        nonlocal cancelled
        calls.append("download")
        cancelled = True
        return payload, "image/jpeg"

    args.update(
        resolve_cover_from_web=resolve,
        remote_cover_bytes=download,
        cancel=lambda: cancelled,
    )
    with pytest.raises(JobCancelled):
        run_cover(**args)
    assert path.read_bytes() == before
    assert (
        calls
        == {"start": [], "resolve": ["resolve"], "download": ["resolve", "download"]}[
            stage
        ]
    )


def test_download_failure_leaves_archive_unchanged_and_closes_client(
    tmp_path, fixture_book
):
    path, payload = fixture_book
    before = path.read_bytes()
    args = job_args(tmp_path, path, payload)
    client = args["client_factory"]()

    def fail(*a, **kw):
        raise RemoteCoverError("failed")

    args.update(remote_cover_bytes=fail, client_factory=lambda: client)
    with pytest.raises(RemoteCoverError):
        run_cover(**args)
    assert client.is_closed
    assert path.read_bytes() == before


@pytest.mark.parametrize("poster", [True, False])
def test_job_refreshes_index_poster_and_preserves_unsaved_metadata(
    tmp_path, fixture_book, poster
):
    path, payload = fixture_book
    args = job_args(tmp_path, path, payload)
    progress = []
    args.update(write_poster_on_save=poster, progress=lambda *a: progress.append(a))
    result = run_cover(**args)
    assert result == {"entries": [{"path": str(path), "output_path": str(path)}]}
    assert progress == [(0, 1), (1, 1)]
    assert read_page(path, 0) == payload
    assert len(list_pages(path)) == 2
    assert (tmp_path / "book-poster.jpg").exists() == poster
    model = read_comic_info(path)
    assert model.field_text("Web") == "https://anilist.co/manga/1"
    assert model.field_text("Number") == "1"
    row = list_volumes(tmp_path / "index.db")[0]
    assert row.archive_page_count == 2 and row.cover_index == 0


def test_job_cbr_refresh_copies_locks_and_forgets_old_path(tmp_path, fixture_book):
    path, payload = fixture_book
    source = tmp_path / "book.cbr"
    source.write_bytes(b"rar")
    args = job_args(tmp_path, source, payload)
    calls = []
    args.update(
        keep_cbr_original=False,
        insert_cover_page=lambda *a, **kw: calls.append(("write", kw)) or path,
        refresh_volume=lambda *a: calls.append(("refresh", a)),
        copy_locked_fields=lambda *a: calls.append(("locks", a)),
        forget_volume=lambda *a: calls.append(("forget", a)),
    )
    result = run_cover(**args)
    assert result["entries"][0]["output_path"] == str(path)
    assert [c[0] for c in calls] == ["write", "refresh", "locks", "forget"]
    assert calls[0][1] == {"keep_cbr_original": False}
    assert calls[2][1][1:] == (str(source), str(path))


def test_archive_and_poster_errors_return_error_entries(tmp_path, fixture_book):
    path, payload = fixture_book
    args = job_args(tmp_path, path, payload)
    before = path.read_bytes()

    def fail(*a, **kw):
        raise ArchiveError("write failed")

    args["insert_cover_page"] = fail
    result = run_cover(**args)
    assert result["entries"][0]["error_message"] == "write failed"
    assert path.read_bytes() == before
    args["insert_cover_page"] = default_services().insert_cover_page
    args.update(write_poster_on_save=True, write_poster=fail)
    result = run_cover(**args)
    assert result["entries"][0]["error_message"] == "write failed"
    assert result["entries"][0]["output_path"] == str(path)
    assert list_volumes(tmp_path / "index.db")[0].archive_page_count == 2


@pytest.mark.parametrize("action,count", [("insert", 2), ("replace", 1)])
def test_api_cover_download_write_and_refresh(tmp_path, fixture_book, action, count):
    path, payload = fixture_book
    config = load_config(tmp_path / "config.toml")
    config.library_roots = [str(tmp_path)]
    config.write_poster_on_save = False
    db = tmp_path / "index.db"
    cache = tmp_path / "covers"
    refresh_volume(db, path, config.library_roots)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.host == "graphql.anilist.co":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "Media": {
                            "coverImage": {
                                "extraLarge": "https://s4.anilist.co/cover.jpg"
                            }
                        }
                    }
                },
            )
        assert str(request.url) == "https://s4.anilist.co/cover.jpg"
        return httpx.Response(
            200, content=payload, headers={"content-type": "image/jpeg"}
        )

    app = create_app(
        config,
        db,
        cache,
        runner=JobRunner(inline=True),
        services=replace(
            default_services(),
            client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    with TestClient(app) as client:
        old_thumbnail = client.get("/api/thumbnail", params={"path": str(path)})
        response = client.post(
            "/api/jobs/cover",
            json={
                "path": str(path),
                "action": action,
                "web": "https://anilist.co/manga/2",
                "number": "3",
            },
        )
        assert response.status_code == 200
        job = response.json()
        assert job["name"] == "Cover" and job["state"] == "succeeded"
        assert job["completed"] == job["total"] == 1
        assert not job["result"]["entries"][0].get("error_type")
        rows = client.get("/api/library").json()["volumes"]
        assert rows[0]["archive_page_count"] == count
        assert rows[0]["web"] == "https://anilist.co/manga/1"
        assert (
            client.get("/api/page", params={"path": str(path), "index": 0}).content
            == payload
        )
        new_thumbnail = client.get(
            "/api/thumbnail", params={"path": str(path), "revision": job["id"]}
        )
        assert new_thumbnail.content != old_thumbnail.content
        assert new_thumbnail.headers["etag"] != old_thumbnail.headers["etag"]
    assert len(calls) == 2


def test_api_rejects_invalid_jobs_and_handles_provider_failure(tmp_path, fixture_book):
    path, payload = fixture_book
    config = load_config(tmp_path / "config.toml")
    config.library_roots = [str(tmp_path)]
    services = replace(
        default_services(),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("no request expected"))
        ),
    )
    app = create_app(
        config,
        tmp_path / "index.db",
        tmp_path / "covers",
        runner=JobRunner(inline=True),
        services=services,
    )
    body = {"path": str(path), "action": "insert", "web": "bad"}
    before = path.read_bytes()
    with TestClient(app) as client:
        for patch in [
            {"path": "/outside/book.cbz"},
            {"path": "relative.cbz"},
            {"action": "delete"},
        ]:
            response = client.post("/api/jobs/cover", json={**body, **patch})
            assert response.status_code == (422 if "action" in patch else 400)
        job = client.post("/api/jobs/cover", json=body).json()
        assert job["state"] == "failed" and job["error_type"] == "ProviderResponseError"
        config.enabled_providers = []
        job = client.post(
            "/api/jobs/cover", json={**body, "web": "https://anilist.co/manga/1"}
        ).json()
        assert (
            job["state"] == "failed" and job["error_type"] == "ProviderUnavailableError"
        )
    assert path.read_bytes() == before


@pytest.mark.parametrize("action", ["insert", "replace"])
def test_downloaded_webp_is_written_as_jpeg(tmp_path, fixture_book, action):
    path, _ = fixture_book
    source = io.BytesIO()
    Image.new("RGB", (80, 120), "red").save(source, format="WEBP")
    args = job_args(tmp_path, path, source.getvalue())
    args.update(
        action=action,
        resolve_cover_from_web=lambda *a, **kw: CoverRef(
            "https://s4.anilist.co/cover.webp", "cover.webp"
        ),
        remote_cover_bytes=lambda *a, **kw: (source.getvalue(), "image/webp"),
    )
    result = run_cover(**args)
    assert not result["entries"][0].get("error_type")
    assert list_pages(path)[0].endswith("cover.jpg")
    with Image.open(io.BytesIO(read_page(path, 0))) as cover:
        assert cover.format == "JPEG" and cover.size == (80, 120)
