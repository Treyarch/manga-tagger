"""FastAPI app and the localhost server."""

import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.requests import Request

from manga_tagger.api.models import (
    ConfigModel,
    ConfigPut,
    ConvertRequest,
    FolderDialogModel,
    IssuesRequest,
    JobModel,
    LibraryResponse,
    LoadRequest,
    PlaceModel,
    RenamePreviewEntry,
    RenamePreviewResponse,
    RenameRequest,
    RootsRequest,
    RootsResponse,
    SaveRequest,
    SearchRequest,
    VolumeModel,
)
from manga_tagger.archives.errors import ArchiveError
from manga_tagger.archives.poster import write_poster
from manga_tagger.archives.read import list_pages, read_page
from manga_tagger.archives.rename import plan_rename, rename_in_directory
from manga_tagger.archives.save import convert_cbr, save_comic_info
from manga_tagger.config import AppConfig, ConfigError, apply_put, save_config
from manga_tagger.index import (
    forget_volume,
    list_volumes,
    refresh_volume,
    scan,
    thumbnail_for,
)
from manga_tagger.jobs import (
    JobBusyError,
    JobNotFoundError,
    JobRunner,
)
from manga_tagger.providers import build_query, list_issues, load, parse_number, search
from manga_tagger.providers.remote_cover import RemoteCoverError, remote_cover_bytes
from manga_tagger.shell import (
    NoThumbnailError,
    ShellError,
    accept_root_paths,
    default_client,
    ensure_inside,
    load_library,
    parse_page_index,
    preview_rename,
    read_page_bytes,
    run_convert,
    run_list_issues,
    run_load,
    run_rename,
    run_save,
    run_scan,
    run_search,
    thumbnail_bytes,
    validate_save,
)


class DialogUnavailableError(Exception):
    """This process has no folder dialog."""


class WindowUnavailableError(Exception):
    """This process cannot close the desktop window."""


@dataclass
class Services:
    """Archive, index, and provider callables. Tests replace these."""

    list_volumes: Callable[..., object]
    scan: Callable[..., object]
    thumbnail_for: Callable[..., object]
    refresh_volume: Callable[..., object]
    forget_volume: Callable[..., object]
    list_pages: Callable[..., object]
    read_page: Callable[..., object]
    save_comic_info: Callable[..., object]
    write_poster: Callable[..., object]
    plan_rename: Callable[..., object]
    rename_in_directory: Callable[..., object]
    convert_cbr: Callable[..., object]
    search: Callable[..., object]
    list_issues: Callable[..., object]
    load: Callable[..., object]
    build_query: Callable[..., object]
    parse_number: Callable[..., object]
    client_factory: Callable[[], httpx.Client]


@dataclass
class AppState:
    """Process state for one desktop session."""

    config: AppConfig
    index_path: Path
    thumbnail_dir: Path
    ui_dir: Path | None
    runner: JobRunner
    services: Services
    pick_folder: Callable[[], str | None] | None = None
    destroy_window: Callable[[], None] | None = None


def default_services() -> Services:
    """Return the real archive, index, and provider operations."""
    return Services(
        list_volumes=list_volumes,
        scan=scan,
        thumbnail_for=thumbnail_for,
        refresh_volume=refresh_volume,
        forget_volume=forget_volume,
        list_pages=list_pages,
        read_page=read_page,
        save_comic_info=save_comic_info,
        write_poster=write_poster,
        plan_rename=plan_rename,
        rename_in_directory=rename_in_directory,
        convert_cbr=convert_cbr,
        search=search,
        list_issues=list_issues,
        load=load,
        build_query=build_query,
        parse_number=parse_number,
        client_factory=default_client,
    )


def create_app(
    config: AppConfig,
    index_path: Path,
    thumbnail_dir: Path,
    ui_dir: Path | None = None,
    runner: JobRunner | None = None,
    services: Services | None = None,
    pick_folder: Callable[[], str | None] | None = None,
    destroy_window: Callable[[], None] | None = None,
) -> FastAPI:
    """Build the local API.

    Args:
        config: In-memory config. ``PUT /api/config`` writes ``config.path``.
        index_path: SQLite index.
        thumbnail_dir: Cover thumbnail cache.
        ui_dir: ``ui/dist``, or ``None`` when there is no build.
        runner: Background jobs. The default is one worker thread.
        services: Callables the routes hand to the shell. Omitted services are
            the real archive, index, and provider operations.
        pick_folder: Native folder dialog. Omitted, the dialog route is 503.
        destroy_window: Closes the desktop window. Omitted, close is 503.

    Returns:
        The FastAPI app. Routes do not open archives, query SQLite, or call
        catalogs themselves.
    """
    app = FastAPI()
    state = AppState(
        config=config,
        index_path=Path(index_path),
        thumbnail_dir=Path(thumbnail_dir),
        ui_dir=None if ui_dir is None else Path(ui_dir),
        runner=runner if runner is not None else JobRunner(),
        services=services if services is not None else default_services(),
        pick_folder=pick_folder,
        destroy_window=destroy_window,
    )
    app.state.box = state
    _register_errors(app)
    _register_routes(app)
    return app


def enqueue_startup_scan(app: FastAPI) -> None:
    """Enqueue a scan when ``library_roots`` is non-empty.

    Call this only after the server is bound. An empty root list does nothing.
    """
    state: AppState = app.state.box
    if not state.config.library_roots:
        return
    _start_scan(state)


def serve(app: FastAPI) -> tuple[int, Callable[[], None]]:
    """Bind ``127.0.0.1`` on an ephemeral port.

    Args:
        app: App from ``create_app``.

    Returns:
        The chosen port and a ``close`` callable that stops the server.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(
        target=lambda: server.run(sockets=[sock]),
        name="manga-tagger-http",
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("server exited before it accepted connections")
        if time.monotonic() > deadline:
            raise RuntimeError("server did not bind")
        time.sleep(0.01)

    def close() -> None:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            server.force_exit = True
            thread.join(timeout=2)

    return port, close


def _register_errors(app: FastAPI) -> None:
    def error(status: int):
        def handler(_request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(
                status_code=status,
                content={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )

        return handler

    for exception_type, status in (
        (ConfigError, 400),
        (ShellError, 400),
        (ArchiveError, 400),
        (RemoteCoverError, 400),
        (NoThumbnailError, 404),
        (JobNotFoundError, 404),
        (JobBusyError, 409),
        (DialogUnavailableError, 503),
        (WindowUnavailableError, 503),
    ):
        app.add_exception_handler(exception_type, error(status))


def _register_routes(app: FastAPI) -> None:
    @app.get("/api/library", response_model=LibraryResponse)
    def library() -> LibraryResponse:
        state = _state(app)
        rows, places = load_library(
            state.services.list_volumes,
            str(state.index_path),
            state.config.library_roots,
        )
        return LibraryResponse(
            places=[PlaceModel.from_place(place) for place in places],
            volumes=[VolumeModel.from_row(row) for row in rows],
        )

    @app.get("/api/page")
    def page(
        path: str,
        index: str | None = Query(default=None),
    ) -> Response:
        state = _state(app)
        page_index = parse_page_index(index)
        payload, media = read_page_bytes(
            path,
            page_index,
            state.config.library_roots,
            list_pages=state.services.list_pages,
            read_page=state.services.read_page,
        )
        return Response(content=payload, media_type=media)

    @app.get("/api/thumbnail")
    def thumbnail(path: str) -> Response:
        state = _state(app)
        payload = thumbnail_bytes(
            path,
            state.config.library_roots,
            thumbnail_for=state.services.thumbnail_for,
            db_path=str(state.index_path),
            cache_dir=str(state.thumbnail_dir),
        )
        return Response(content=payload, media_type="image/jpeg")

    @app.get("/api/cover")
    def cover(url: str) -> Response:
        payload, media = remote_cover_bytes(url)
        return Response(content=payload, media_type=media)

    @app.get("/api/config", response_model=ConfigModel)
    def get_config() -> ConfigModel:
        return ConfigModel(**_state(app).config.to_dict())

    @app.put("/api/config", response_model=ConfigModel)
    def put_config(body: ConfigPut) -> ConfigModel:
        state = _state(app)
        updates = body.model_dump(exclude_unset=True)
        if "library_roots" in updates and state.runner.current() is not None:
            raise JobBusyError("a job is already queued or running")
        updated = apply_put(state.config, updates)
        save_config(state.config.path, updated)
        state.config = updated
        if "library_roots" in updates:
            _start_scan(state)
        return ConfigModel(**updated.to_dict())

    @app.post("/api/dialogs/folder", response_model=FolderDialogModel)
    def post_folder_dialog() -> FolderDialogModel:
        state = _state(app)
        if state.pick_folder is None:
            raise DialogUnavailableError("Folder dialog is unavailable.")
        chosen = state.pick_folder()
        if not chosen:
            return FolderDialogModel(path=None)
        return FolderDialogModel(path=chosen)

    @app.post("/api/window/close", status_code=204)
    def post_window_close() -> Response:
        state = _state(app)
        if state.destroy_window is None:
            raise WindowUnavailableError("Window close is unavailable.")
        state.destroy_window()
        return Response(status_code=204)

    @app.post("/api/library/roots", response_model=RootsResponse)
    def post_library_roots(body: RootsRequest) -> RootsResponse:
        state = _state(app)
        if not isinstance(body.paths, list):
            raise ConfigError("paths must be a list")
        roots, added = accept_root_paths(state.config.library_roots, body.paths)
        if added and state.runner.current() is not None:
            raise JobBusyError("a job is already queued or running")
        job = None
        if added:
            updated = apply_put(state.config, {"library_roots": roots})
            save_config(state.config.path, updated)
            state.config = updated
            job = JobModel.from_job(_start_scan(state))
        else:
            updated = state.config
        return RootsResponse(
            config=ConfigModel(**updated.to_dict()),
            added=added,
            job=job,
        )

    @app.post("/api/jobs/scan", response_model=JobModel)
    def post_scan() -> JobModel:
        return JobModel.from_job(_start_scan(_state(app)))

    @app.post("/api/jobs/search", response_model=JobModel)
    def post_search(body: SearchRequest) -> JobModel:
        state = _state(app)

        def fn(cancel, progress):
            config = state.config
            return run_search(
                provider=body.provider,
                series=body.series,
                filename_stem=body.filename_stem,
                title_languages=list(config.title_languages),
                api_key=config.comicvine_api_key,
                nautiljon_base_url=config.nautiljon_base_url,
                nautiljon_api_key=config.nautiljon_api_key,
                build_query=state.services.build_query,
                search=state.services.search,
                client_factory=state.services.client_factory,
                cancel=cancel,
                progress=progress,
            )

        return JobModel.from_job(state.runner.start("Search", fn))

    @app.post("/api/jobs/issues", response_model=JobModel)
    def post_issues(body: IssuesRequest) -> JobModel:
        state = _state(app)

        def fn(cancel, progress):
            config = state.config
            return run_list_issues(
                provider=body.provider,
                match_id=body.match_id,
                title_languages=list(config.title_languages),
                api_key=config.comicvine_api_key,
                nautiljon_base_url=config.nautiljon_base_url,
                nautiljon_api_key=config.nautiljon_api_key,
                list_issues=state.services.list_issues,
                client_factory=state.services.client_factory,
                cancel=cancel,
                progress=progress,
            )

        return JobModel.from_job(state.runner.start("Issues", fn))

    @app.post("/api/jobs/load", response_model=JobModel)
    def post_load(body: LoadRequest) -> JobModel:
        state = _state(app)

        def fn(cancel, progress):
            config = state.config
            return run_load(
                provider=body.provider,
                match_id=body.match_id,
                filename_stem=body.filename_stem,
                mode=body.mode,
                form=body.form,
                title_languages=list(config.title_languages),
                api_key=config.comicvine_api_key,
                nautiljon_base_url=config.nautiljon_base_url,
                nautiljon_api_key=config.nautiljon_api_key,
                load=state.services.load,
                client_factory=state.services.client_factory,
                cancel=cancel,
                progress=progress,
                issue_id=body.issue_id,
            )

        return JobModel.from_job(state.runner.start("Load", fn))

    @app.post("/api/jobs/save", response_model=JobModel)
    def post_save(body: SaveRequest) -> JobModel:
        state = _state(app)
        validate_save(body.mode, body.paths, body.patch, state.config.library_roots)

        def fn(cancel, progress):
            config = state.config
            volumes = state.services.list_volumes(str(state.index_path))
            return run_save(
                paths=body.paths,
                patch=body.patch,
                mode=body.mode,
                volumes=volumes,
                roots=list(config.library_roots),
                keep_cbr_original=config.keep_cbr_original,
                db_path=str(state.index_path),
                cache_dir=str(state.thumbnail_dir),
                save_comic_info=state.services.save_comic_info,
                write_poster=state.services.write_poster,
                refresh_volume=state.services.refresh_volume,
                forget_volume=state.services.forget_volume,
                parse_number=state.services.parse_number,
                cancel=cancel,
                progress=progress,
            )

        return JobModel.from_job(state.runner.start("Save", fn))

    @app.post("/api/jobs/rename", response_model=JobModel)
    def post_rename(body: RenameRequest) -> JobModel:
        state = _state(app)
        ensure_inside(body.directory, state.config.library_roots)

        def fn(cancel, progress):
            return run_rename(
                directory=body.directory,
                template=body.template,
                roots=list(state.config.library_roots),
                db_path=str(state.index_path),
                cache_dir=str(state.thumbnail_dir),
                rename_in_directory=state.services.rename_in_directory,
                write_poster=state.services.write_poster,
                refresh_volume=state.services.refresh_volume,
                forget_volume=state.services.forget_volume,
                cancel=cancel,
                progress=progress,
            )

        return JobModel.from_job(state.runner.start("Rename", fn))

    @app.post("/api/rename/preview", response_model=RenamePreviewResponse)
    def rename_preview(body: RenameRequest) -> RenamePreviewResponse:
        state = _state(app)
        ensure_inside(body.directory, state.config.library_roots)
        planned = preview_rename(
            body.directory,
            body.template,
            state.config.library_roots,
            plan_rename=state.services.plan_rename,
        )
        return RenamePreviewResponse(
            entries=[
                RenamePreviewEntry(
                    path=str(item.path),
                    output_path=(
                        None if item.output_path is None else str(item.output_path)
                    ),
                    error_type=item.error_type,
                    error_message=item.error_message,
                )
                for item in planned
            ]
        )

    @app.post("/api/jobs/convert", response_model=JobModel)
    def post_convert(body: ConvertRequest) -> JobModel:
        state = _state(app)
        for path in body.paths:
            ensure_inside(path, state.config.library_roots)

        def fn(cancel, progress):
            config = state.config
            return run_convert(
                paths=body.paths,
                roots=list(config.library_roots),
                keep_cbr_original=config.keep_cbr_original,
                db_path=str(state.index_path),
                cache_dir=str(state.thumbnail_dir),
                convert_cbr=state.services.convert_cbr,
                refresh_volume=state.services.refresh_volume,
                forget_volume=state.services.forget_volume,
                cancel=cancel,
                progress=progress,
            )

        return JobModel.from_job(state.runner.start("Convert", fn))

    @app.get("/api/jobs/current", response_model=JobModel | None)
    def current_job() -> JobModel | None:
        job = _state(app).runner.current()
        if job is None:
            return None
        return JobModel.from_job(job)

    @app.get("/api/jobs/{job_id}", response_model=JobModel)
    def get_job(job_id: str) -> JobModel:
        return JobModel.from_job(_state(app).runner.get(job_id))

    @app.post("/api/jobs/{job_id}/cancel", response_model=JobModel)
    def cancel_job(job_id: str) -> JobModel:
        return JobModel.from_job(_state(app).runner.cancel(job_id))

    @app.get("/")
    def ui_index() -> Response:
        return _ui_index(_state(app).ui_dir)

    @app.get("/{asset_path:path}")
    def ui_asset(asset_path: str) -> Response:
        return _ui_asset(_state(app).ui_dir, asset_path)


def _start_scan(state: AppState):
    services = state.services

    def fn(cancel, progress):
        return run_scan(
            db_path=str(state.index_path),
            cache_dir=str(state.thumbnail_dir),
            roots=list(state.config.library_roots),
            scan=services.scan,
            cancel=cancel,
            progress=progress,
        )

    return state.runner.start("Scan", fn)


def _state(app: FastAPI) -> AppState:
    return app.state.box


def _ui_index(ui_dir: Path | None) -> Response:
    if ui_dir is not None and (ui_dir / "index.html").is_file():
        return FileResponse(ui_dir / "index.html")
    return PlainTextResponse(
        "UI build is missing.",
        media_type="text/plain; charset=utf-8",
    )


def _ui_asset(ui_dir: Path | None, asset_path: str) -> Response:
    if ui_dir is None:
        return JSONResponse(
            status_code=404,
            content={"error_type": "NotFoundError", "error_message": "not found"},
        )
    root = ui_dir.resolve()
    candidate = (ui_dir / asset_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return JSONResponse(
            status_code=404,
            content={"error_type": "NotFoundError", "error_message": "not found"},
        )
    return FileResponse(candidate)
