"""Errors raised by archive reads, saves, and renames."""


class ArchiveError(Exception):
    """Base class for archive operations that leave the source unchanged."""


class UnreadableArchiveError(ArchiveError):
    """The file is missing, not an archive, or a page index is out of range."""


class NoPageImagesError(ArchiveError):
    """The archive opens and contains no page images."""


class MissingUnarError(ArchiveError):
    """A CBR operation needs ``unar`` or ``lsar`` and either one is absent."""


class ConvertTargetExistsError(ArchiveError):
    """The ``.cbz`` beside a ``.cbr`` already exists."""


class BatchFieldError(ArchiveError):
    """A batch patch contains a field outside the shared series set."""


class RenameTemplateError(ArchiveError):
    """The rename template is empty, has an extension, or has a bad tag."""


class RenameFieldError(ArchiveError):
    """One archive cannot be rendered from the template and its ComicInfo."""


class RenameConflictError(ArchiveError):
    """A rendered archive name or poster path collides with another file."""
