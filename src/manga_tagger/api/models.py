"""Pydantic models for the local API. Not the ComicInfo or index types."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from manga_tagger.jobs import Job
from manga_tagger.shell import Place


class ErrorBody(BaseModel):
    """JSON body for an expected HTTP error."""

    error_type: str
    error_message: str


class PlaceModel(BaseModel):
    """One sidebar place."""

    path: str
    label: str

    @classmethod
    def from_place(cls, place: Place) -> "PlaceModel":
        return cls(path=place.path, label=place.label)


class VolumeModel(BaseModel):
    """One indexed volume. SQL NULL stays JSON null."""

    path: str
    root: str
    name: str
    extension: str
    size: int
    mtime_ns: int
    status: str
    error_type: str
    error_message: str
    cover_index: int | None
    archive_page_count: int | None
    title: str
    series: str
    number: str
    volume: str
    publisher: str
    page_count: str
    language_iso: str
    age_rating: str
    manga: str
    genre: str
    summary: str
    web: str
    community_rating: str
    notes: str
    year: str
    month: str
    day: str
    writer: str
    penciller: str
    inker: str
    cover_artist: str

    @classmethod
    def from_row(cls, row: object) -> "VolumeModel":
        values = {name: getattr(row, name) for name in cls.model_fields}
        return cls(**values)


class LibraryResponse(BaseModel):
    """Places and every volume kept for the current roots."""

    places: list[PlaceModel]
    volumes: list[VolumeModel]


class ConfigModel(BaseModel):
    """The eight known config keys."""

    library_roots: list[str]
    keep_cbr_original: bool
    comicvine_api_key: str
    nautiljon_base_url: str
    nautiljon_api_key: str
    title_languages: list[str]
    enabled_providers: list[str]
    theme: str


class ConfigPut(BaseModel):
    """A partial config update. Omitted keys stay."""

    model_config = ConfigDict(extra="ignore")

    library_roots: Any = None
    keep_cbr_original: Any = None
    comicvine_api_key: Any = None
    nautiljon_base_url: Any = None
    nautiljon_api_key: Any = None
    title_languages: Any = None
    enabled_providers: Any = None
    theme: Any = None


class SearchRequest(BaseModel):
    """Body for ``POST /api/jobs/search``."""

    provider: str
    series: str
    filename_stem: str


class IssuesRequest(BaseModel):
    """Body for ``POST /api/jobs/issues``."""

    provider: str
    match_id: str


class LoadRequest(BaseModel):
    """Body for ``POST /api/jobs/load``."""

    provider: str
    match_id: str
    filename_stem: str
    mode: str
    form: dict[str, Any]
    issue_id: str = ""


class SaveRequest(BaseModel):
    """Body for ``POST /api/jobs/save``."""

    paths: list[str]
    patch: dict[str, str]
    mode: str


class RenameRequest(BaseModel):
    """Body for ``POST /api/jobs/rename`` and ``POST /api/rename/preview``."""

    directory: str
    template: str


class RenamePreviewEntry(BaseModel):
    """One planned rename. ``output_path`` is null when the plan failed."""

    path: str
    output_path: str | None = None
    error_type: str = ""
    error_message: str = ""


class RenamePreviewResponse(BaseModel):
    """The plan from ``plan_rename``. Nothing has been renamed."""

    entries: list[RenamePreviewEntry]


class ConvertRequest(BaseModel):
    """Body for ``POST /api/jobs/convert``."""

    paths: list[str]


class FolderDialogModel(BaseModel):
    """The directory from the native folder dialog. ``path`` is null on cancel."""

    path: str | None


class RootsRequest(BaseModel):
    """Body for ``POST /api/library/roots``. ``paths`` is checked in the route."""

    model_config = ConfigDict(extra="ignore")

    paths: Any = None


class JobModel(BaseModel):
    """One background job."""

    id: str
    name: str
    state: str
    error_type: str
    error_message: str
    result: Any = None
    completed: int
    total: int

    @classmethod
    def from_job(cls, job: Job) -> "JobModel":
        return cls(
            id=job.id,
            name=job.name,
            state=job.state,
            error_type=job.error_type,
            error_message=job.error_message,
            result=job.result,
            completed=job.completed,
            total=job.total,
        )


class RootsResponse(BaseModel):
    """The config after an append, plus the directories that were new.

    ``job`` is the enqueued scan when ``added`` is non-empty, otherwise null.
    """

    config: ConfigModel
    added: list[str]
    job: JobModel | None = None
