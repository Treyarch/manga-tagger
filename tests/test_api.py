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
from manga_tagger.index import Volume
from manga_tagger.jobs import JobRunner
from manga_tagger.providers import search as provider_search
from manga_tagger.shell import form_from_volumes


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


def test_cover_rejects_hosts_outside_the_allow_list(tmp_path: Path) -> None:
    app = _app(tmp_path, roots=["/books"])
    with TestClient(app) as client:
        response = client.get(
            "/api/cover",
            params={"url": "https://example.com/cover.jpg"},
        )
    assert response.status_code == 400
    assert response.json()["error_type"] == "RemoteCoverError"


def test_config_put_keeps_unknown_keys_and_rejects_a_busy_rescan(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('theme = "dark"\ncustom = "keep"\n', encoding="utf-8")
    config = load_config(path)
    runner = JobRunner(inline=True)
    app = create_app(
        config,
        tmp_path / "index.db",
        tmp_path / "covers",
        runner=runner,
        services=replace(default_services(), scan=_scan_recorder([])),
    )
    with TestClient(app) as client:
        put = client.put("/api/config", json={"theme": "light"})
        assert put.status_code == 200
        assert put.json()["theme"] == "light"
        assert app.state.box.config.theme == "light"
        saved = path.read_text(encoding="utf-8")
        assert "keep" in saved
        bad = client.put("/api/config", json={"library_roots": "/books"})
        assert bad.status_code == 400
        assert bad.json()["error_type"] == "ConfigError"
        assert app.state.box.config.library_roots == []

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
        refused = client.put("/api/config", json={"library_roots": ["/books"]})
        assert refused.status_code == 409
        assert refused.json()["error_type"] == "JobBusyError"
        assert "/books" not in path.read_text(encoding="utf-8")
        theme = client.put("/api/config", json={"theme": "dark"})
        assert theme.status_code == 200
        again = client.post("/api/jobs/scan")
        assert again.status_code == 409
    held.shutdown()
    assert scans == []


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
    enqueue_startup_scan(empty)
    assert empty.state.box.runner.current() is None
    filled = _app(tmp_path, scan=_scan_recorder(scans), roots=["/books"], hold=True)
    enqueue_startup_scan(filled)
    current = filled.state.box.runner.current()
    assert current is not None
    assert current.name == "Scan"
    assert current.state == "queued"
    filled.state.box.runner.shutdown()
    assert scans == []


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

    def plan_rename(directory: str, template: str):
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
    }
    values.update(overrides)
    return Volume(**values)
