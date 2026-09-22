"""Archive reads, ComicInfo edits, rename, and cover posters."""

from manga_tagger.archives.comicinfo import (
    BATCH_FIELDS,
    OWNED_ELEMENTS,
    ComicInfo,
    ComicPage,
    resolve_cover_index,
)
from manga_tagger.archives.errors import (
    ArchiveError,
    BatchFieldError,
    ConvertTargetExistsError,
    MissingUnarError,
    NoPageImagesError,
    RenameConflictError,
    RenameFieldError,
    RenameTemplateError,
    UnreadableArchiveError,
)
from manga_tagger.archives.poster import write_poster
from manga_tagger.archives.read import (
    cover_index,
    list_pages,
    read_comic_info,
    read_page,
)
from manga_tagger.archives.rename import (
    OFFERED_RENAME_TEMPLATE,
    plan_rename,
    rename_in_directory,
)
from manga_tagger.archives.results import FileResult
from manga_tagger.archives.save import convert_cbr, save_comic_info, save_many

__all__ = [
    "BATCH_FIELDS",
    "OFFERED_RENAME_TEMPLATE",
    "OWNED_ELEMENTS",
    "ArchiveError",
    "BatchFieldError",
    "ComicInfo",
    "ComicPage",
    "ConvertTargetExistsError",
    "FileResult",
    "MissingUnarError",
    "NoPageImagesError",
    "RenameConflictError",
    "RenameFieldError",
    "RenameTemplateError",
    "UnreadableArchiveError",
    "convert_cbr",
    "cover_index",
    "list_pages",
    "plan_rename",
    "read_comic_info",
    "read_page",
    "rename_in_directory",
    "resolve_cover_index",
    "save_comic_info",
    "save_many",
    "write_poster",
]
