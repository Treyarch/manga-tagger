"""HTTP API, with archive and catalog calls replaced."""

import socket
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from manga_tagger.api import create_app, enqueue_startup_scan, serve
from manga_tagger.api.app import default_services
from manga_tagger.archives.results import FileResult
from manga_tagger.config import load_config, save_config
from manga_tagger.index import LibraryIndexError, Volume
from manga_tagger.jobs import JobRunner
from manga_tagger.providers import search as provider_search
from manga_tagger.shell import form_from_volumes
from manga_tagger.theme import SystemTheme


def test_library_does_not_scan(tmp_path: Path) -> None:
    rows = [_volume("/books/Claymore/a.cbz", series="Claymore", cover_index=None)]
    calls: list[str] = []

    def list_volumes(_db_path: str):
        calls.append("list")
        return rows

    def scan(*_args, **_kwargs):
        raise AssertionError("scan")

    app = _app(tmp_path, list_volumes=list_volumes, scan=scan, roots=["/books"])
    with TestClient(app) as client:
        response = client.get("/api/library")
    assert response.status_code == 200
    body = response.json()
    assert body["volumes"][0]["name"] == "a.cbz"
    assert body["volumes"][0]["series"] == "Claymore"
    assert body["volumes"][0]["cover_index"] is None
    assert body["places"][0]["path"] == "/books/Claymore"
    assert calls == ["list"]

    empty = _app(tmp_path, list_volumes=list_volumes, scan=scan, roots=[])
    with TestClient(empty) as client:
        response = client.get("/api/library")
    assert response.json()["volumes"] == []
    assert rows[0].path == "/books/Claymore/a.cbz"


def test_page_reads_one_index_and_rejects_paths_outside(tmp_path: Path) -> None:
    reads: list[int] = []

    def list_pages(_path: str) -> list[str]:
        return ["Cover.JPG", "b.png"]

    def read_page(_path: str, index: int) -> bytes:
        reads.append(index)
        return b"page-bytes"

    def save_comic_info(*_args, **_kwargs):
        raise AssertionError("save")

    app = _app(
        tmp_path,
        list_pages=list_pages,
        read_page=read_page,
        save_comic_info=save_comic_info,
        roots=["/books"],
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/page", params={"path": "/books/a.cbz", "index": "1"}
        )
        assert response.status_code == 200
        assert response.content == b"page-bytes"
        assert response.headers["content-type"] == "image/png"
        jpeg = client.get("/api/page", params={"path": "/books/a.cbz", "index": "0"})
        assert jpeg.headers["content-type"] == "image/jpeg"
        outside = client.get("/api/page", params={"path": "/etc/passwd", "index": "0"})
        relative = client.get("/api/page", params={"path": "a.cbz", "index": "0"})
        missing = client.get("/api/page", params={"path": "/books/a.cbz"})
        saved = client.post(
            "/api/jobs/save",
            json={"paths": ["/etc/passwd"], "patch": {"Series": "X"}, "mode": "one"},
        )
    assert reads == [1, 0]
    assert outside.status_code == 400
    assert outside.json()["error_type"] == "OutsideLibraryError"
    assert relative.status_code == 400
    assert relative.json()["error_type"] == "ShellError"
    assert missing.status_code == 400
    assert saved.status_code == 400
    assert saved.json()["error_type"] == "OutsideLibraryError"


def test_thumbnail_miss_is_404(tmp_path: Path) -> None:
    def thumbnail_for(*_args, **_kwargs):
        return None

    app = _app(tmp_path, thumbnail_for=thumbnail_for, roots=["/books"])
    with TestClient(app) as client:
        response = client.get("/api/thumbnail", params={"path": "/books/a.cbz"})
    assert response.status_code == 404
    assert response.json()["error_type"] == "NoThumbnailError"


def test_thumbnail_hit_is_cacheable_jpeg(tmp_path: Path) -> None:
    jpeg = tmp_path / "covers" / "abc-1-2.jpg"
    jpeg.parent.mkdir(parents=True)
    jpeg.write_bytes(b"\xff\xd8\xff\xd9")

    def thumbnail_for(*_args, **_kwargs):
        return jpeg

    app = _app(tmp_path, thumbnail_for=thumbnail_for, roots=["/books"])
    with TestClient(app) as client:
        response = client.get("/api/thumbnail", params={"path": "/books/a.cbz"})
    assert response.status_code == 200
    assert response.content == b"\xff\xd8\xff\xd9"
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert response.headers["etag"] == '"abc-1-2"'


def test_clear_thumbnail_cache_is_synchronous_and_isolated(tmp_path: Path) -> None:
    calls: list[Path] = []

    def clear_thumbnail_cache(path: Path) -> int:
        calls.append(path)
        return 3

    app = _app(
        tmp_path,
        clear_thumbnail_cache=clear_thumbnail_cache,
        roots=["/books"],
    )
    config_before = app.state.box.config.to_dict()
    with TestClient(app) as client:
        response = client.post("/api/cache/thumbnails/clear")

    assert response.status_code == 200
    assert response.json() == {"removed": 3}
    assert calls == [tmp_path / "covers"]
    assert app.state.box.runner.current() is None
    assert app.state.box.config.to_dict() == config_before
    assert not (tmp_path / "index.db").exists()
    assert not (tmp_path / "config.toml").exists()


def test_clear_thumbnail_cache_returns_structured_error(tmp_path: Path) -> None:
    def clear_thumbnail_cache(_path: Path) -> int:
        raise LibraryIndexError("thumbnail cache could not be cleared")

    app = _app(
        tmp_path,
        clear_thumbnail_cache=clear_thumbnail_cache,
        roots=["/books"],
    )
    with TestClient(app) as client:
        response = client.post("/api/cache/thumbnails/clear")

    assert response.status_code == 400
    assert response.json() == {
        "error_type": "LibraryIndexError",
        "error_message": "thumbnail cache could not be cleared",
    }


def test_cover_rejects_hosts_outside_the_allow_list(tmp_path: Path) -> None:
    app = _app(tmp_path, roots=["/books"])
    with TestClient(app) as client:
        response = client.get(
            "/api/cover",
            params={"url": "https://example.com/cover.jpg"},
        )
    assert response.status_code == 400
    assert response.json()["error_type"] == "RemoteCoverError"


def test_config_put_scans_only_changed_roots_and_keeps_unknown_keys(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('theme = "dark"\ncustom = "keep"\n', encoding="utf-8")
    config = load_config(path)
    runner = JobRunner(inline=True)
    scans: list[object] = []
    app = create_app(
        config,
        tmp_path / "index.db",
        tmp_path / "covers",
        runner=runner,
        services=replace(default_services(), scan=_scan_recorder(scans)),
    )
    with TestClient(app) as client:
        put = client.put("/api/config", json={"theme": "light"})
        assert put.status_code == 200
        assert put.json()["config"]["theme"] == "light"
        assert put.json()["job"] is None
        assert app.state.box.config.theme == "light"
        saved = path.read_text(encoding="utf-8")
        assert "keep" in saved
        bad = client.put("/api/config", json={"library_roots": "/books"})
        assert bad.status_code == 400
        assert bad.json()["error_type"] == "ConfigError"
        assert app.state.box.config.library_roots == []

        unchanged = client.put(
            "/api/config", json={"library_roots": [], "theme": "dark"}
        )
        assert unchanged.status_code == 200
        assert unchanged.json()["config"]["theme"] == "dark"
        assert unchanged.json()["job"] is None
        assert scans == []

        changed = client.put("/api/config", json={"library_roots": ["/books"]})
        assert changed.status_code == 200
        assert changed.json()["config"]["library_roots"] == ["/books"]
        assert changed.json()["job"]["name"] == "Scan"
        assert changed.json()["job"]["state"] == "succeeded"
        assert scans == ["scan"]

        emptied = client.put("/api/config", json={"library_roots": []})
        assert emptied.status_code == 200
        assert emptied.json()["config"]["library_roots"] == []
        assert emptied.json()["job"]["state"] == "succeeded"
        assert scans == ["scan", "scan"]


def test_config_put_allows_unrelated_settings_during_another_job(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    config = load_config(path)
    config.library_roots = ["/books"]
    save_config(path, config)

    held = JobRunner(hold=True)
    scans: list[str] = []
    busy = create_app(
        load_config(path),
        tmp_path / "index.db",
        tmp_path / "covers",
        runner=held,
        services=replace(default_services(), scan=_scan_recorder(scans)),
    )
    with TestClient(busy) as client:
        started = client.post("/api/jobs/scan")
        assert started.status_code == 200
        assert started.json()["state"] == "queued"
        allowed = client.put(
            "/api/config",
            json={"library_roots": ["/books"], "theme": "dark"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["config"]["theme"] == "dark"
        assert allowed.json()["job"] is None
        refused = client.put(
            "/api/config",
            json={"library_roots": ["/other"], "theme": "light"},
        )
        assert refused.status_code == 409
        assert refused.json()["error_type"] == "JobBusyError"
        stored = load_config(path)
        assert stored.library_roots == ["/books"]
        assert stored.theme == "dark"
        again = client.post("/api/jobs/scan")
        assert again.status_code == 409
    held.shutdown()
    assert scans == []


def test_config_put_returns_the_queued_scan_job_for_changed_roots(
    tmp_path: Path,
) -> None:
    scans: list[object] = []
    app = _app(tmp_path, roots=[], hold=True, scan=_scan_recorder(scans))

    with TestClient(app) as client:
        response = client.put("/api/config", json={"library_roots": ["/books"]})
        assert response.status_code == 200
        returned = response.json()["job"]
        current = client.get("/api/jobs/current").json()
        assert returned["id"] == current["id"]
        assert returned["state"] == current["state"] == "queued"

    app.state.box.runner.shutdown()
    assert scans == []


def test_system_theme_endpoint_is_injected_and_never_cached(tmp_path: Path) -> None:
    palette = SystemTheme(
        mode="light",
        background="#faf4ed",
        dark_background="#ede7e1",
        lighter_background="#f2e9e1",
        foreground="#575279",
        dark_foreground="#9893a5",
        accent="#56949f",
        selection="#dfdad9",
        red="#b4637a",
        yellow="#ea9d34",
        orange="#cf8057",
    )
    app = create_app(
        load_config(tmp_path / "config.toml"),
        tmp_path / "index.db",
        tmp_path / "covers",
        system_theme=lambda: palette,
    )
    with TestClient(app) as client:
        response = client.get("/api/system-theme")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["mode"] == "light"
    assert response.json()["accent"] == "#56949f"

    missing = create_app(
        load_config(tmp_path / "missing-config.toml"),
        tmp_path / "missing.db",
        tmp_path / "missing-covers",
        system_theme=lambda: None,
    )
    with TestClient(missing) as client:
        unavailable = client.get("/api/system-theme")
    assert unavailable.status_code == 200
    assert unavailable.headers["cache-control"] == "no-store"
    assert unavailable.json() is None


def test_folder_dialog_and_root_append(tmp_path: Path) -> None:
    folder = tmp_path / "Claymore"
    folder.mkdir()
    note = tmp_path / "note.txt"
    note.write_text("x", encoding="utf-8")
    scans: list[object] = []
    chosen: dict[str, str | None] = {"path": str(folder)}

    def pick() -> str | None:
        return chosen["path"]

    path = tmp_path / "config.toml"
    app = create_app(
        load_config(path),
        tmp_path / "index.db",
        tmp_path / "covers",
        runner=JobRunner(inline=True),
        services=replace(default_services(), scan=_scan_recorder(scans)),
        pick_folder=pick,
    )
    with TestClient(app) as client:
        picked = client.post("/api/dialogs/folder")
        assert picked.status_code == 200
        assert picked.json()["path"] == str(folder)
        chosen["path"] = None
        cancelled = client.post("/api/dialogs/folder")
        assert cancelled.json()["path"] is None
        bad = client.post("/api/library/roots", json={"paths": str(folder)})
        assert bad.status_code == 400
        assert bad.json()["error_type"] == "ConfigError"
        added = client.post(
            "/api/library/roots",
            json={"paths": [str(folder), str(note), "relative", str(folder)]},
        )
        assert added.status_code == 200
        body = added.json()
        resolved = str(folder.resolve())
        assert body["added"] == [resolved]
        assert body["config"]["library_roots"] == [resolved]
        assert body["job"] is not None
        assert body["job"]["name"] == "Scan"
        skipped = client.post("/api/library/roots", json={"paths": [str(note)]})
        assert skipped.json()["added"] == []
        assert skipped.json()["job"] is None
    assert scans == ["scan"]
    assert resolved in path.read_text(encoding="utf-8")

    bare = create_app(
        load_config(tmp_path / "bare.toml"),
        tmp_path / "bare.db",
        tmp_path / "bare-covers",
        runner=JobRunner(inline=True),
        services=replace(default_services(), scan=_scan_recorder([])),
    )
    with TestClient(bare) as client:
        unavailable = client.post("/api/dialogs/folder")
        assert unavailable.status_code == 503
        assert unavailable.json()["error_type"] == "DialogUnavailableError"
        closed = client.post("/api/window/close")
        assert closed.status_code == 503
        assert closed.json()["error_type"] == "WindowUnavailableError"

    closed_calls: list[str] = []
    with_close = create_app(
        load_config(tmp_path / "close.toml"),
        tmp_path / "close.db",
        tmp_path / "close-covers",
        runner=JobRunner(inline=True),
        services=replace(default_services(), scan=_scan_recorder([])),
        destroy_window=lambda: closed_calls.append("close"),
    )
    with TestClient(with_close) as client:
        done = client.post("/api/window/close")
        assert done.status_code == 204
        assert done.content == b""
    assert closed_calls == ["close"]

    other = tmp_path / "Other"
    other.mkdir()
    busy_path = tmp_path / "busy.toml"
    held = JobRunner(hold=True)
    busy = create_app(
        load_config(busy_path),
        tmp_path / "busy.db",
        tmp_path / "busy-covers",
        runner=held,
        services=replace(default_services(), scan=_scan_recorder([])),
        pick_folder=pick,
    )
    with TestClient(busy) as client:
        started = client.post("/api/jobs/scan")
        assert started.status_code == 200
        refused = client.post("/api/library/roots", json={"paths": [str(other)]})
        assert refused.status_code == 409
        assert refused.json()["error_type"] == "JobBusyError"
    held.shutdown()
    assert not busy_path.exists() or str(other.resolve()) not in busy_path.read_text(
        encoding="utf-8"
    )


def test_save_title_on_many_is_rejected(tmp_path: Path) -> None:
    calls: list[str] = []

    def save_comic_info(*_args, **_kwargs):
        calls.append("save")

    app = _app(tmp_path, save_comic_info=save_comic_info, roots=["/books"])
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/save",
            json={
                "paths": ["/books/a.cbz", "/books/b.cbz"],
                "patch": {"Title": "Nope"},
                "mode": "many",
            },
        )
    assert response.status_code == 400
    assert response.json()["error_type"] == "BatchFieldError"
    assert calls == []


def test_search_and_load_jobs(tmp_path: Path) -> None:
    writes: list[str] = []

    def search(*_args, **_kwargs):
        class Hit:
            id = "9"
            title = "Claymore"
            year = ""
            credit = ""
            count = ""
            summary = ""
            cover = ""

        return [Hit()]

    def load(*_args, **_kwargs):
        return {
            "Series": "Claymore",
            "Manga": "YesAndRightToLeft",
            "Number": "2",
            "Title": "Claymore",
        }

    def save_comic_info(*_args, **_kwargs):
        writes.append("save")

    def scan(*_args, **_kwargs):
        writes.append("scan")

    app = _app(
        tmp_path,
        search=search,
        load=load,
        save_comic_info=save_comic_info,
        scan=scan,
        roots=["/books"],
    )
    form = form_from_volumes(
        [_volume("/books/a.cbz", series="A"), _volume("/books/b.cbz", series="B")]
    )
    with TestClient(app) as client:
        found = client.post(
            "/api/jobs/search",
            json={
                "provider": "mangadex",
                "series": "Claymore",
                "filename_stem": "Claymore v02",
            },
        )
        loaded = client.post(
            "/api/jobs/load",
            json={
                "provider": "mangadex",
                "match_id": "9",
                "filename_stem": "Claymore v02",
                "mode": "many",
                "form": form,
            },
        )
    assert found.status_code == 200
    assert found.json()["state"] == "succeeded"
    assert found.json()["result"]["candidates"][0]["title"] == "Claymore"
    assert "Number" not in loaded.json()["result"]["form"]["values"]
    assert loaded.json()["result"]["form"]["values"]["Manga"]["dirty"] is True
    assert writes == []


def test_issues_job(tmp_path: Path) -> None:
    def list_issues(*_args, **_kwargs):
        class Hit:
            id = "10"
            number = "1"
            title = "First"
            date = "2001-03"
            cover = ""
            summary = "One"

        return [Hit()]

    app = _app(tmp_path, list_issues=list_issues, roots=["/books"])
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/issues",
            json={"provider": "comicvine", "match_id": "12345"},
        )
    assert response.status_code == 200
    assert response.json()["state"] == "succeeded"
    assert response.json()["name"] == "Issues"
    assert response.json()["result"]["issues"][0]["id"] == "10"


def test_load_job_passes_issue_id(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def load(*_args, **kwargs):
        captured.update(kwargs)
        return {"Series": "Claymore", "Number": "1"}

    app = _app(tmp_path, load=load, roots=["/books"])
    form = form_from_volumes([_volume("/books/a.cbz", series="A", number="7")])
    with TestClient(app) as client:
        loaded = client.post(
            "/api/jobs/load",
            json={
                "provider": "comicvine",
                "match_id": "12345",
                "filename_stem": "Claymore v02",
                "mode": "one",
                "form": form,
                "issue_id": "99",
                "count": "27",
            },
        )
    assert loaded.status_code == 200
    assert loaded.json()["state"] == "succeeded"
    assert captured["issue_id"] == "99"
    assert captured["number"] == "7"
    assert loaded.json()["result"]["form"]["values"]["Count"] == {
        "value": "27",
        "dirty": True,
        "locked": False,
    }


def test_blank_comicvine_key_sends_no_request(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        raise AssertionError(request.url)

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), timeout=15.0)

    app = _app(
        tmp_path,
        search=provider_search,
        client_factory=factory,
        roots=["/books"],
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/search",
            json={
                "provider": "comicvine",
                "series": "Sandman",
                "filename_stem": "Sandman",
            },
        )
    body = response.json()
    assert body["state"] == "failed"
    assert body["error_type"] == "ProviderUnavailableError"
    assert "Comic Vine API key is not set" in body["error_message"]
    assert seen == []


def test_startup_scan_only_when_roots_are_set(tmp_path: Path) -> None:
    scans: list[object] = []
    empty = _app(tmp_path, scan=_scan_recorder(scans), roots=[], hold=True)
    assert enqueue_startup_scan(empty) is None
    assert empty.state.box.runner.current() is None
    with TestClient(empty) as client:
        assert client.get("/api/jobs/startup").json() is None
    filled = _app(tmp_path, scan=_scan_recorder(scans), roots=["/books"], hold=True)
    started = enqueue_startup_scan(filled)
    assert started is not None
    current = filled.state.box.runner.current()
    assert current is not None
    assert current.name == "Scan"
    assert current.state == "queued"
    with TestClient(filled) as client:
        startup = client.get("/api/jobs/startup").json()
        assert startup["id"] == current.id
        assert startup["state"] == "queued"
    filled.state.box.runner.shutdown()
    assert scans == []


def test_finished_startup_scan_remains_discoverable(tmp_path: Path) -> None:
    scans: list[object] = []
    app = _app(tmp_path, scan=_scan_recorder(scans), roots=["/books"])
    started = enqueue_startup_scan(app)
    assert started is not None
    assert started.state == "succeeded"

    with TestClient(app) as client:
        first = client.get("/api/jobs/startup").json()
        second = client.get("/api/jobs/startup").json()

    assert first == second
    assert first["id"] == started.id
    assert first["state"] == "succeeded"
    assert first["name"] == "Scan"
    assert scans == ["scan"]


def test_missing_ui_and_serve(tmp_path: Path) -> None:
    app = _app(tmp_path, list_volumes=lambda _db: [], roots=[])
    with TestClient(app) as client:
        missing = client.get("/")
        library = client.get("/api/library")
    assert missing.status_code == 200
    assert missing.text == "UI build is missing."
    assert missing.headers["content-type"].startswith("text/plain")
    assert library.status_code == 200

    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("hello", encoding="utf-8")
    (ui / "app.js").write_text("ok", encoding="utf-8")
    built = _app(tmp_path, list_volumes=lambda _db: [], roots=[], ui_dir=ui)
    with TestClient(built) as client:
        assert client.get("/").text == "hello"
        assert client.get("/app.js").text == "ok"
        assert client.get("/../config.toml").status_code == 404

    served = _app(tmp_path, list_volumes=lambda _db: [], roots=[])
    port, close = serve(served)
    try:
        assert port != 0
        with httpx.Client(timeout=2.0) as http:
            root = http.get(f"http://127.0.0.1:{port}/")
            shelf = http.get(f"http://127.0.0.1:{port}/api/library")
        assert root.text == "UI build is missing."
        assert shelf.status_code == 200
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        close()
    with pytest.raises(httpx.HTTPError):
        httpx.get(f"http://127.0.0.1:{port}/", timeout=1.0)


def test_rename_preview_does_not_rename(tmp_path: Path) -> None:
    planned: list[tuple[str, str]] = []

    def plan_rename(directory: str, template: str, *, paths=None):
        planned.append((directory, template))
        return [
            FileResult(
                path=Path("/books/Claymore/old.cbz"),
                output_path=Path("/books/Claymore/Claymore v01.cbz"),
            )
        ]

    def rename_in_directory(*_args, **_kwargs):
        raise AssertionError("rename_in_directory")

    app = _app(
        tmp_path,
        plan_rename=plan_rename,
        rename_in_directory=rename_in_directory,
        roots=["/books"],
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/rename/preview",
            json={"directory": "/books/Claymore", "template": "{Series} v{Number:02}"},
        )
        outside = client.post(
            "/api/rename/preview",
            json={"directory": "/etc", "template": "{Series} v{Number:02}"},
        )
    assert response.status_code == 200
    entry = response.json()["entries"][0]
    assert entry["path"] == "/books/Claymore/old.cbz"
    assert entry["output_path"] == "/books/Claymore/Claymore v01.cbz"
    assert entry["error_type"] == ""
    assert planned == [("/books/Claymore", "{Series} v{Number:02}")]
    assert outside.status_code == 400
    assert outside.json()["error_type"] == "OutsideLibraryError"


def test_unknown_job_is_404(tmp_path: Path) -> None:
    app = _app(tmp_path, roots=[])
    with TestClient(app) as client:
        response = client.get("/api/jobs/99")
        assert response.status_code == 404
        assert response.json()["error_type"] == "JobNotFoundError"
        assert client.get("/api/jobs/current").json() is None


def test_field_locks_endpoint(tmp_path: Path) -> None:
    from manga_tagger.index import list_volumes, scan

    library = tmp_path / "books"
    archive = library / "a.cbz"
    archive.parent.mkdir()
    with __import__("zipfile").ZipFile(archive, "w") as zf:
        zf.writestr(
            "ComicInfo.xml",
            b'<?xml version="1.0"?><ComicInfo><Series>Claymore</Series></ComicInfo>',
        )
        zf.writestr("0.jpg", b"page")
    root = str(library.resolve())
    scan(tmp_path / "index.db", tmp_path / "covers", [library])
    path = str(archive.resolve())
    app = _app(tmp_path, roots=[root])
    with TestClient(app) as client:
        bad = client.post(
            "/api/field-locks",
            json={"paths": [path], "field": "Volume", "locked": True},
        )
        assert bad.status_code == 400
        assert bad.json()["error_type"] == "ShellError"
        ok = client.post(
            "/api/field-locks",
            json={"paths": [path], "field": "Series", "locked": True},
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["volumes"][0]["locked_fields"] == '["Series"]'
        assert list_volumes(tmp_path / "index.db")[0].locked_fields == '["Series"]'
        outside = client.post(
            "/api/field-locks",
            json={"paths": ["/etc/passwd"], "field": "Series", "locked": True},
        )
        assert outside.status_code == 400
        assert outside.json()["error_type"] == "OutsideLibraryError"


def _app(
    tmp_path: Path, *, roots: list[str], hold: bool = False, ui_dir=None, **services
):
    config = load_config(tmp_path / "config.toml")
    config.library_roots = list(roots)
    if config.path.exists():
        save_config(config.path, config)
    runner = JobRunner(hold=True) if hold else JobRunner(inline=True)
    base = default_services()
    wired = replace(base, **services) if services else base
    return create_app(
        config,
        tmp_path / "index.db",
        tmp_path / "covers",
        ui_dir=ui_dir,
        runner=runner,
        services=wired,
    )


def _scan_recorder(calls: list[object]):
    def scan(*_args, **_kwargs):
        calls.append("scan")
        from manga_tagger.index import ScanResult

        return ScanResult((), (), (), (), (), False)

    return scan


def _volume(path: str, **overrides: object) -> Volume:
    name = Path(path).name
    values: dict[str, object] = {
        "path": path,
        "root": str(Path(path).parent),
        "name": name,
        "extension": Path(name).suffix,
        "size": 1,
        "mtime_ns": 1,
        "status": "ok",
        "error_type": "",
        "error_message": "",
        "cover_index": 0,
        "archive_page_count": 1,
        "title": "",
        "series": "",
        "number": "",
        "volume": "",
        "count": "",
        "publisher": "",
        "page_count": "",
        "language_iso": "",
        "age_rating": "",
        "manga": "",
        "genre": "",
        "summary": "",
        "web": "",
        "community_rating": "",
        "notes": "",
        "year": "",
        "month": "",
        "day": "",
        "writer": "",
        "penciller": "",
        "inker": "",
        "cover_artist": "",
        "locked_fields": "[]",
    }
    values.update(overrides)
    return Volume(**values)


@pytest.mark.parametrize("scope", ["one", "many", "empty", "omitted", "null"])
def test_rename_preview_and_job_share_selection_scope(tmp_path: Path, scope: str) -> None:
    import zipfile

    folder = tmp_path / "books"
    folder.mkdir()
    sources = [folder / f"old-{number}.cbz" for number in range(1, 4)]
    for number, path in enumerate(sources, 1):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "ComicInfo.xml",
                f"<ComicInfo><Series>Claymore</Series><Number>{number}</Number></ComicInfo>",
            )
    selected = sources[:1] if scope == "one" else sources[:2]
    expected = selected if scope in {"one", "many"} else sources
    body: dict[str, object] = {
        "directory": str(folder), "template": "{Series} v{Number:02}"
    }
    if scope != "omitted":
        body["paths"] = (
            None if scope == "null"
            else [] if scope == "empty"
            else [str(path) for path in selected]
        )
    posters: list[str] = []
    refreshed: list[str] = []
    forgotten: list[str] = []
    app = _app(
        tmp_path,
        roots=[str(folder)],
        write_poster=lambda path: posters.append(str(path)),
        refresh_volume=lambda _db, path, _roots: refreshed.append(str(path)),
        forget_volume=lambda _db, _cache, path: forgotten.append(str(path)),
        copy_locked_fields=lambda *_args, **_kwargs: None,
    )
    with TestClient(app) as client:
        preview = client.post("/api/rename/preview", json=body)
        assert preview.status_code == 200
        assert [entry["path"] for entry in preview.json()["entries"]] == [
            str(path) for path in expected
        ]
        assert all(path.exists() for path in sources)
        response = client.post("/api/jobs/rename", json=body)
        assert response.status_code == 200
        job = response.json()
        assert job["state"] == "succeeded"
        assert job["total"] == job["completed"] == len(expected)
        assert job["result"]["entries"] == [
            {"path": entry["path"], "output_path": entry["output_path"]}
            for entry in preview.json()["entries"]
        ]
    for number, source in enumerate(sources, 1):
        assert source.exists() == (source not in expected)
        assert (folder / f"Claymore v{number:02}.cbz").exists() == (source in expected)
    assert len(posters) == len(refreshed) == len(forgotten) == len(expected)


@pytest.mark.parametrize("route", ["/api/rename/preview", "/api/jobs/rename"])
@pytest.mark.parametrize(
    "path",
    [
        "relative.cbz",
        "/outside/a.cbz",
        "/books/other/a.cbz",
        "/books/series/nested/a.cbz",
        "/books/series/a.jpg",
    ],
)
def test_rename_rejects_invalid_selection_before_work(
    tmp_path: Path, route: str, path: str
) -> None:
    def unexpected(*_args, **_kwargs):
        raise AssertionError("invalid scope must be rejected before archive work")

    app = _app(
        tmp_path, roots=["/books"], plan_rename=unexpected, rename_in_directory=unexpected
    )
    with TestClient(app) as client:
        response = client.post(
            route,
            json={"directory": "/books/series", "template": "{Series}", "paths": [path]},
        )
        assert response.status_code == 400
        assert client.get("/api/jobs/current").json() is None


def test_interface_motion_config_api(tmp_path: Path) -> None:
    app = _app(tmp_path, roots=[])
    with TestClient(app) as client:
        assert client.get("/api/config").json()["animate_interface"] is False
        for value in (True, False, True):
            response = client.put("/api/config", json={"animate_interface": value})
            assert response.status_code == 200
            assert response.json()["config"]["animate_interface"] is value
            assert response.json()["job"] is None
        themed = client.put("/api/config", json={"theme": "dark"}).json()
        assert themed["config"]["animate_interface"] is True
        for invalid in (None, 1, "true", [], {}):
            assert client.put("/api/config", json={"animate_interface": invalid}).status_code == 400
            assert client.get("/api/config").json()["animate_interface"] is True
        assert load_config(app.state.box.config.path).animate_interface is True
        assert client.get("/api/jobs/current").json() is None
