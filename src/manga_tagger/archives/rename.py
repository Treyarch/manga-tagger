"""In-place rename from a ComicInfo filename template."""

import os
import re
from collections.abc import Callable
from pathlib import Path

from manga_tagger.archives.comicinfo import OWNED_ELEMENTS, ComicInfo
from manga_tagger.archives.errors import (
    RenameConflictError,
    RenameFieldError,
    RenameTemplateError,
    UnreadableArchiveError,
)
from manga_tagger.archives.read import read_comic_info
from manga_tagger.archives.results import FileResult, failure

OFFERED_RENAME_TEMPLATE = "{Series} v{Number:02}"

_Tag = tuple[str, int | None]
_Part = str | _Tag


def plan_rename(directory: os.PathLike[str] | str, template: str) -> list[FileResult]:
    """Plan renames for archives directly in ``directory``.

    Nothing is renamed and posters are not moved. Page bytes are not read.

    Args:
        directory: Folder whose direct ``.cbz`` and ``.cbr`` children are planned.
        template: Filename stem, such as ``{Series} v{Number:02}``.

    Returns:
        One result per archive, in filename order. A success carries the new path.

    Raises:
        UnreadableArchiveError: ``directory`` is not a directory.
        RenameTemplateError: ``template`` is empty, includes an extension, or
            contains an unknown or unclosed tag. Nothing is renamed.
    """
    folder = Path(directory)
    if not folder.is_dir():
        raise UnreadableArchiveError(f"{folder} is not a directory")
    parts = _parse_template(template)
    drafts: list[_Draft] = []
    for path in _archives(folder):
        try:
            info = read_comic_info(path)
            stem = _render(parts, info, path.name)
        except Exception as exc:
            drafts.append(_Draft(path=path, dest=None, error=exc))
            continue
        drafts.append(
            _Draft(path=path, dest=folder / f"{stem}{path.suffix}", error=None)
        )
    _apply_conflicts(drafts)
    return [_draft_result(draft) for draft in drafts]


def rename_in_directory(
    directory: os.PathLike[str] | str, template: str
) -> list[FileResult]:
    """Rename archives directly in ``directory`` from their own ComicInfo.

    Archive bytes stay as they are. An existing ``{stem}-poster.jpg`` moves
    with a renamed file. One failure does not undo renames that succeeded.

    Args:
        directory: Folder whose direct children are renamed.
        template: Filename stem. The offered template is
            ``{Series} v{Number:02}``.

    Returns:
        The same shape as ``plan_rename``, after the successful renames.

    Raises:
        UnreadableArchiveError: ``directory`` is not a directory.
        RenameTemplateError: ``template`` is invalid. Nothing is renamed.
    """
    planned = plan_rename(directory, template)
    results: list[FileResult] = []
    for item in planned:
        if not item.ok or item.output_path is None:
            results.append(item)
            continue
        try:
            _rename_one(item.path, item.output_path)
        except Exception as exc:
            results.append(failure(item.path, exc))
        else:
            results.append(item)
    return results


class _Draft:
    def __init__(
        self, path: Path, dest: Path | None, error: BaseException | None
    ) -> None:
        self.path = path
        self.dest = dest
        self.error = error


def _parse_template(template: str) -> list[_Part]:
    if template.strip() == "":
        raise RenameTemplateError("template is empty")
    lowered = template.lower()
    if lowered.endswith(".cbz") or lowered.endswith(".cbr"):
        raise RenameTemplateError("template must not include a .cbz or .cbr extension")
    parts: list[_Part] = []
    literal: list[str] = []
    index = 0
    while index < len(template):
        if template[index] != "{":
            literal.append(template[index])
            index += 1
            continue
        if literal:
            parts.append("".join(literal))
            literal = []
        end = template.find("}", index + 1)
        if end == -1:
            raise RenameTemplateError("template has an unclosed {")
        parts.append(_parse_tag(template[index + 1 : end]))
        index = end + 1
    if literal:
        parts.append("".join(literal))
    if not parts:
        raise RenameTemplateError("template is empty")
    return parts


def _parse_tag(body: str) -> _Tag:
    if ":" in body:
        name, width_text = body.split(":", 1)
    else:
        name, width_text = body, None
    if name not in OWNED_ELEMENTS:
        raise RenameTemplateError(f"unknown tag {{{name}}}")
    if width_text is None:
        return name, None
    if not re.fullmatch(r"[0-9]+", width_text):
        raise RenameTemplateError("tag width must be a positive integer")
    width = int(width_text)
    if width <= 0:
        raise RenameTemplateError("tag width must be a positive integer")
    return name, width


def _render(parts: list[_Part], info: ComicInfo, filename: str) -> str:
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
            continue
        name, width = part
        raw = info.field_text(name)
        if raw is None or raw.strip() == "":
            raise RenameFieldError(f"{filename} has no {name} value")
        chunks.append(_format_value(filename, name, raw, width))
    stem = "".join(chunks)
    stem = stem.replace("/", "-").replace("\\", "-").replace("\0", "-")
    stem = stem.strip(" .")
    if stem in {"", ".", ".."}:
        raise RenameFieldError(f"{filename} rendered an empty filename")
    return stem


def _format_value(filename: str, name: str, raw: str, width: int | None) -> str:
    if width is None:
        return raw
    if re.fullmatch(r"\d+", raw):
        return f"{int(raw):0{width}d}"
    if re.fullmatch(r"\d+\.\d+", raw):
        return raw
    raise RenameFieldError(f"{filename} has a {name} value that is not a number")


def _archives(directory: Path) -> list[Path]:
    found = [
        entry
        for entry in directory.iterdir()
        if entry.is_file() and entry.suffix.lower() in {".cbz", ".cbr"}
    ]
    found.sort(key=lambda entry: entry.name)
    return found


def _apply_conflicts(drafts: list[_Draft]) -> None:
    _fail_duplicate_targets(drafts, key=_archive_target, label="archive")
    for draft in drafts:
        if draft.dest is None:
            continue
        if draft.dest.name != draft.path.name and draft.dest.exists():
            draft.error = RenameConflictError(
                f"{draft.path.name} would overwrite {draft.dest.name}"
            )
            draft.dest = None
    _fail_duplicate_targets(drafts, key=_poster_target, label="poster")
    for draft in drafts:
        if draft.dest is None:
            continue
        poster_dest = _poster_for(draft.dest)
        poster_src = _poster_for(draft.path)
        if poster_dest != poster_src and poster_dest.exists():
            draft.error = RenameConflictError(
                f"{draft.path.name} poster would overwrite {poster_dest.name}"
            )
            draft.dest = None


def _fail_duplicate_targets(
    drafts: list[_Draft],
    *,
    key: Callable[[_Draft], Path],
    label: str,
) -> None:
    groups: dict[Path, list[_Draft]] = {}
    for draft in drafts:
        if draft.dest is None:
            continue
        target = key(draft)
        groups.setdefault(target, []).append(draft)
    for target, group in groups.items():
        if len(group) < 2:
            continue
        for draft in group:
            draft.error = RenameConflictError(
                f"{draft.path.name} shares a {label} target {target.name}"
            )
            draft.dest = None


def _archive_target(draft: _Draft) -> Path:
    assert draft.dest is not None
    return draft.dest


def _poster_target(draft: _Draft) -> Path:
    assert draft.dest is not None
    return _poster_for(draft.dest)


def _poster_for(archive: Path) -> Path:
    return archive.with_name(f"{archive.stem}-poster.jpg")


def _draft_result(draft: _Draft) -> FileResult:
    if draft.error is not None or draft.dest is None:
        error = draft.error or RenameFieldError(f"{draft.path.name} was not renamed")
        return failure(draft.path, error)
    return FileResult(path=draft.path, output_path=draft.dest)


def _rename_one(source: Path, dest: Path) -> None:
    poster_src = _poster_for(source)
    poster_dest = _poster_for(dest)
    if dest != source:
        os.replace(source, dest)
    if poster_src != poster_dest and poster_src.is_file():
        os.replace(poster_src, poster_dest)
