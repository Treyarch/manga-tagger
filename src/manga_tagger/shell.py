"""Places, selection, forms, and the job bodies. No FastAPI and no pywebview."""

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from manga_tagger.archives.comicinfo import BATCH_FIELDS, OWNED_ELEMENTS
from manga_tagger.archives.errors import BatchFieldError
from manga_tagger.index import ScanResult
from manga_tagger.jobs import Cancel, JobCancelled, Progress

FORM_FIELDS: tuple[str, ...] = OWNED_ELEMENTS
SHARED_FIELDS: tuple[str, ...] = (
    "Series",
    "Publisher",
    "LanguageISO",
    "AgeRating",
    "Genre",
    "Manga",
    "Writer",
    "Penciller",
    "Inker",
    "CoverArtist",
)
if set(SHARED_FIELDS) != BATCH_FIELDS:
    raise RuntimeError("SHARED_FIELDS does not match the archive batch fields")

FIELD_COLUMNS: dict[str, str] = {
    "Title": "title",
    "Series": "series",
    "Number": "number",
    "Volume": "volume",
    "Publisher": "publisher",
    "PageCount": "page_count",
    "LanguageISO": "language_iso",
    "AgeRating": "age_rating",
    "Manga": "manga",
    "Genre": "genre",
    "Summary": "summary",
    "Web": "web",
    "CommunityRating": "community_rating",
    "Notes": "notes",
    "Year": "year",
    "Month": "month",
    "Day": "day",
    "Writer": "writer",
    "Penciller": "penciller",
    "Inker": "inker",
    "CoverArtist": "cover_artist",
}

HTTP_TIMEOUT = 15.0

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class ShellError(Exception):
    """A relative archive path, a bad page index, or a one-save path count."""


class OutsideLibraryError(ShellError):
    """A resolved path is outside every current library root."""


class NoThumbnailError(Exception):
    """``thumbnail_for`` returns no path."""


@dataclass(frozen=True)
class Place:
    """One folder that directly contains indexed volumes."""

    path: str
    label: str


@dataclass(frozen=True)
class Selection:
    """Selected paths in visible-list order, plus the anchor."""

    paths: tuple[str, ...]
    anchor: str | None


def accept_root_paths(
    current: Sequence[str], candidates: Sequence[object]
) -> tuple[list[str], list[str]]:
    """Append existing directories that are not already roots.

    Relative paths, files, non-strings, and duplicates are dropped. Current
    roots stay, including a root that is not a directory. Added paths are
    ``resolve`` results, the same form config stores.

    Args:
        current: Roots already saved.
        candidates: Paths from the folder dialog or a drop.

    Returns:
        The full root list, then the paths that were added.
    """
    kept: list[str] = []
    seen: set[str] = set()
    for item in current:
        path = Path(item)
        if not path.is_absolute():
            continue
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        kept.append(resolved)
    added: list[str] = []
    for item in candidates:
        if not isinstance(item, str):
            continue
        path = Path(item)
        if not path.is_absolute():
            continue
        resolved = path.resolve()
        key = str(resolved)
        if key in seen or not resolved.is_dir():
            continue
        seen.add(key)
        kept.append(key)
        added.append(key)
    return kept, added


def volumes_for_roots(rows: Sequence[object], roots: Sequence[str]) -> list[object]:
    """Keep rows whose path is a root or a file inside a root.

    An empty ``roots`` list keeps nothing. Rows are not deleted or scanned.

    Args:
        rows: Indexed volumes. Each row has a ``path`` attribute.
        roots: Current library roots.

    Returns:
        The kept rows, in the order given.
    """
    if not roots:
        return []
    bases = [Path(root).resolve() for root in roots]
    kept: list[object] = []
    for row in rows:
        path = Path(str(row.path)).resolve()
        if any(path == base or path.is_relative_to(base) for base in bases):
            kept.append(row)
    return kept


def places_from_volumes(rows: Sequence[object]) -> list[Place]:
    """Build one place per parent directory that directly contains a volume.

    Args:
        rows: Indexed volumes.

    Returns:
        Places ordered by path, ascending, by Unicode code point.
    """
    parents = sorted({_parent_path(str(row.path)) for row in rows})
    names = [Path(parent).name for parent in parents]
    counts = Counter(names)
    labels = []
    for parent, name in zip(parents, names, strict=True):
        if counts[name] == 1:
            labels.append(name)
        else:
            labels.append(f"{Path(parent).parent.name} / {name}")
    label_counts = Counter(labels)
    places: list[Place] = []
    for parent, label in zip(parents, labels, strict=True):
        if label_counts[label] > 1:
            label = parent
        places.append(Place(path=parent, label=label))
    return places


def volumes_in_place(rows: Sequence[object], place_path: str) -> list[object]:
    """Return volumes whose parent is ``place_path``, ordered by ``name``.

    Nested volumes belong to their own parent and are not included.
    """
    place = _directory_key(place_path)
    matched = [row for row in rows if _parent_path(str(row.path)) == place]
    return sorted(matched, key=lambda row: str(row.name))


def volumes_for_shelf(
    rows: Sequence[object], place_path: str | None
) -> list[object]:
    """Return the shelf for ``place_path``, or every row by ``name`` when None."""
    if place_path is None:
        return sorted(rows, key=lambda row: str(row.name))
    return volumes_in_place(rows, place_path)


def select_plain(visible: Sequence[str], path: str) -> Selection:
    """Select only ``path`` and make it the anchor."""
    return Selection(paths=(path,), anchor=path)


def select_range(visible: Sequence[str], selection: Selection, path: str) -> Selection:
    """Select the inclusive range from the anchor to ``path``.

    The anchor does not move. With no anchor, or an anchor that is not
    visible, this is ``select_plain``.
    """
    if (
        selection.anchor is None
        or selection.anchor not in visible
        or path not in visible
    ):
        return select_plain(visible, path)
    start = list(visible).index(selection.anchor)
    end = list(visible).index(path)
    low, high = sorted((start, end))
    return Selection(paths=tuple(visible[low : high + 1]), anchor=selection.anchor)


def select_toggle(visible: Sequence[str], selection: Selection, path: str) -> Selection:
    """Add ``path`` when it is absent and remove it when it is selected.

    The first selected path becomes the anchor. Adding another path leaves
    the anchor. Removing the anchor moves it to the first remaining path.
    """
    selected = set(selection.paths)
    if path in selected:
        selected.remove(path)
        paths = tuple(item for item in visible if item in selected)
        anchor = selection.anchor
        if anchor not in paths:
            anchor = paths[0] if paths else None
        return Selection(paths=paths, anchor=anchor)
    selected.add(path)
    paths = tuple(item for item in visible if item in selected)
    anchor = path if not selection.paths else selection.anchor
    return Selection(paths=paths, anchor=anchor)


def selection_after_filter(visible: Sequence[str], selection: Selection) -> Selection:
    """Drop hidden paths. A hidden anchor becomes the first path still selected."""
    selected = set(selection.paths)
    paths = tuple(item for item in visible if item in selected)
    anchor = selection.anchor if selection.anchor in paths else None
    if anchor is None and paths:
        anchor = paths[0]
    return Selection(paths=paths, anchor=anchor)


def form_from_volumes(rows: Sequence[object]) -> dict[str, object] | None:
    """Build the inspector form for the current selection.

    Args:
        rows: Selected volumes. Empty returns no form.

    Returns:
        ``mode`` ``one`` with every form field, or ``mode`` ``many`` with the
        shared fields. ``dirty`` starts false. ``Pages`` is omitted.
    """
    if not rows:
        return None
    if len(rows) == 1:
        values = {}
        for name in FORM_FIELDS:
            value = _field_text(rows[0], name)
            if name == "PageCount":
                filled = _page_count_fill(rows[0])
                if filled is not None:
                    value = filled
            values[name] = {"value": value, "dirty": False}
        return {"mode": "one", "values": values}
    values: dict[str, dict[str, object]] = {}
    for name in SHARED_FIELDS:
        texts = [_field_text(row, name) for row in rows]
        if all(text == texts[0] for text in texts):
            values[name] = {"value": texts[0], "mixed": False, "dirty": False}
        else:
            values[name] = {"value": "", "mixed": True, "dirty": False}
    return {"mode": "many", "values": values}


def edit_field(form: Mapping[str, object], key: str, value: str) -> dict[str, object]:
    """Set one field to ``value``, mark it dirty, and clear ``mixed``.

    When ``value`` equals the current text and the field is not mixed, the form
    is returned unchanged (values copied, dirty left as it was).
    """
    values = {
        name: dict(field)  # type: ignore[arg-type]
        for name, field in form["values"].items()  # type: ignore[union-attr]
    }
    current = values[key]
    if current.get("value") == value and not current.get("mixed"):
        return {"mode": form["mode"], "values": values}
    updated: dict[str, object] = {"value": value, "dirty": True}
    if "mixed" in values[key]:
        updated["mixed"] = False
    values[key] = updated
    return {"mode": form["mode"], "values": values}


def merge_load_patch(
    form: Mapping[str, object], patch: Mapping[str, str], mode: str
) -> dict[str, object]:
    """Apply a catalog patch onto a form. Does not write an archive.

    Args:
        form: Form from ``form_from_volumes`` or a later edit.
        patch: Provider load patch.
        mode: ``one`` or ``many``.

    Returns:
        A new form. Omitted keys keep their value and dirty flag. A patch value
        that equals the current text on a non-mixed field leaves that field
        unchanged. On ``many``, only shared fields change. ``Number`` and
        ``Title`` are ignored there.
    """
    values = {
        name: dict(field)  # type: ignore[arg-type]
        for name, field in form["values"].items()  # type: ignore[union-attr]
    }
    allowed = FORM_FIELDS if mode == "one" else SHARED_FIELDS
    for key, value in patch.items():
        if key not in allowed or key not in values:
            continue
        current = values[key]
        if current.get("value") == value and not current.get("mixed"):
            continue
        updated: dict[str, object] = {"value": value, "dirty": True}
        if mode == "many":
            updated["mixed"] = False
        values[key] = updated
    return {"mode": mode, "values": values}


def load_library(
    list_volumes: Callable[[str], Sequence[object]],
    db_path: str,
    roots: Sequence[str],
) -> tuple[list[object], list[Place]]:
    """Return volumes inside ``roots`` and their places. Does not scan."""
    rows = list(list_volumes(db_path))
    kept = volumes_for_roots(rows, roots)
    return kept, places_from_volumes(kept)


def thumbnail_bytes(
    path: str,
    roots: Sequence[str],
    *,
    thumbnail_for: Callable[..., object],
    db_path: str,
    cache_dir: str,
) -> bytes:
    """Return the cached cover JPEG, building it through ``thumbnail_for``.

    Raises:
        NoThumbnailError: ``thumbnail_for`` returns no path.
        OutsideLibraryError: ``path`` is outside the library.
    """
    ensure_inside(path, roots)
    found = thumbnail_for(db_path, cache_dir, path)
    if found is None:
        raise NoThumbnailError(f"{path} has no thumbnail")
    return Path(str(found)).read_bytes()


def media_type_for(name: str) -> str:
    """Return the response type for a page filename."""
    return _MEDIA_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


def parse_page_index(raw: str | None) -> int:
    """Return a non-negative page index.

    Raises:
        ShellError: The index is missing or not a non-negative integer.
    """
    if raw is None or not raw.isdigit():
        raise ShellError("page index must be a non-negative integer")
    return int(raw)


def ensure_inside(path: str, roots: Sequence[str]) -> str:
    """Reject a relative path or a path outside the current roots.

    Nothing is read or written.

    Args:
        path: Archive, page, thumbnail, rename directory, or convert path.
        roots: Library roots copied for this request.

    Returns:
        ``path`` when it is inside a root.

    Raises:
        ShellError: ``path`` is relative.
        OutsideLibraryError: The resolved path is outside every root.
    """
    raw = Path(path)
    if not raw.is_absolute():
        raise ShellError(f"{path} is not absolute")
    resolved = raw.resolve()
    for root in roots:
        base = Path(root).resolve()
        if resolved == base or resolved.is_relative_to(base):
            return path
    raise OutsideLibraryError(f"{resolved} is outside the library")


def validate_save(
    mode: str, paths: Sequence[str], patch: Mapping[str, str], roots: Sequence[str]
) -> None:
    """Reject a save the route can see before a job is queued.

    The job calls this again so a direct call is just as strict.

    Raises:
        ShellError: ``mode`` is ``one`` and ``paths`` does not contain one path.
        BatchFieldError: ``patch`` contains a key that mode does not allow.
        OutsideLibraryError: A path is outside the library.
    """
    if mode == "one":
        if len(paths) != 1:
            raise ShellError("a one save needs one path")
        allowed = FORM_FIELDS
    elif mode == "many":
        allowed = SHARED_FIELDS
    else:
        raise ShellError(f"{mode} is not a save mode")
    extra = sorted(set(patch) - set(allowed))
    if extra:
        raise BatchFieldError(f"batch save cannot write {', '.join(extra)}")
    for path in paths:
        ensure_inside(path, roots)


def read_page_bytes(
    path: str,
    index: int,
    roots: Sequence[str],
    *,
    list_pages: Callable[[str], list[str]],
    read_page: Callable[[str, int], bytes],
) -> tuple[bytes, str]:
    """List page names, then read one index.

    Args:
        path: Absolute archive path inside a library root.
        index: Zero-based page index.
        roots: Current library roots.
        list_pages: Central-directory listing. It is not given another index.
        read_page: Reads that one index and no other.

    Returns:
        Uncompressed page bytes and the content type.
    """
    ensure_inside(path, roots)
    names = list_pages(path)
    payload = read_page(path, index)
    name = names[index] if 0 <= index < len(names) else ""
    return payload, media_type_for(name)


def run_search(
    *,
    provider: str,
    series: str,
    filename_stem: str,
    title_languages: Sequence[str],
    api_key: str,
    nautiljon_base_url: str,
    nautiljon_api_key: str,
    enabled_providers: Sequence[str],
    build_query: Callable[[str, str], str],
    search: Callable[..., list[object]],
    client_factory: Callable[[], httpx.Client],
    cancel: Cancel,
    progress: Progress,
) -> dict[str, object]:
    """Search one catalog and return candidates. Does not write an archive."""
    progress(0, 1)
    query = build_query(series, filename_stem)
    client = client_factory()
    try:
        found = search(
            provider,
            query,
            title_languages=list(title_languages),
            client=client,
            api_key=api_key,
            nautiljon_base_url=nautiljon_base_url,
            nautiljon_api_key=nautiljon_api_key,
            enabled_providers=list(enabled_providers),
            cancel=cancel,
        )
    finally:
        client.close()
    progress(1, 1)
    return {
        "candidates": [
            {
                "id": item.id,
                "title": item.title,
                "year": item.year,
                "credit": item.credit,
                "count": item.count,
                "summary": item.summary,
                "cover": item.cover,
            }
            for item in found
        ]
    }


def preferred_load_number(form: Mapping[str, object]) -> str | None:
    """Return form ``Number`` when non-blank and not mixed, else ``None``."""
    values = form.get("values")
    if not isinstance(values, Mapping):
        return None
    field = values.get("Number")
    if not isinstance(field, Mapping):
        return None
    if field.get("mixed") is True:
        return None
    value = field.get("value")
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def run_list_issues(
    *,
    provider: str,
    match_id: str,
    title_languages: Sequence[str],
    api_key: str,
    nautiljon_base_url: str,
    nautiljon_api_key: str,
    enabled_providers: Sequence[str],
    list_issues: Callable[..., list[object]],
    client_factory: Callable[[], httpx.Client],
    cancel: Cancel,
    progress: Progress,
) -> dict[str, object]:
    """List issues or volumes for one series. Does not write an archive."""
    progress(0, 1)
    client = client_factory()
    try:
        found = list_issues(
            provider,
            match_id,
            title_languages=list(title_languages),
            client=client,
            api_key=api_key,
            nautiljon_base_url=nautiljon_base_url,
            nautiljon_api_key=nautiljon_api_key,
            enabled_providers=list(enabled_providers),
            cancel=cancel,
        )
    finally:
        client.close()
    progress(1, 1)
    return {
        "issues": [
            {
                "id": item.id,
                "number": item.number,
                "title": item.title,
                "date": item.date,
                "cover": item.cover,
                "summary": item.summary,
            }
            for item in found
        ]
    }


def run_load(
    *,
    provider: str,
    match_id: str,
    filename_stem: str,
    mode: str,
    form: Mapping[str, object],
    title_languages: Sequence[str],
    api_key: str,
    nautiljon_base_url: str,
    nautiljon_api_key: str,
    enabled_providers: Sequence[str],
    load: Callable[..., Mapping[str, str]],
    client_factory: Callable[[], httpx.Client],
    cancel: Cancel,
    progress: Progress,
    issue_id: str = "",
) -> dict[str, object]:
    """Load one series or issue and merge the patch into the form. Writes nothing."""
    progress(0, 1)
    client = client_factory()
    try:
        patch = load(
            provider,
            match_id,
            filename_stem=filename_stem,
            title_languages=list(title_languages),
            client=client,
            api_key=api_key,
            nautiljon_base_url=nautiljon_base_url,
            nautiljon_api_key=nautiljon_api_key,
            enabled_providers=list(enabled_providers),
            cancel=cancel,
            issue_id=issue_id,
            number=preferred_load_number(form),
        )
    finally:
        client.close()
    merged = merge_load_patch(form, patch, mode)
    progress(1, 1)
    return {"form": merged}


def run_save(
    *,
    paths: Sequence[str],
    patch: Mapping[str, str],
    mode: str,
    volumes: Sequence[object],
    roots: Sequence[str],
    keep_cbr_original: bool,
    db_path: str,
    cache_dir: str,
    save_comic_info: Callable[..., Path],
    write_poster: Callable[[str], object],
    refresh_volume: Callable[..., object],
    forget_volume: Callable[..., object],
    parse_number: Callable[[str], str | None],
    cancel: Cancel,
    progress: Progress,
) -> dict[str, object]:
    """Save each path through ``save_comic_info``. Does not call ``save_many``."""
    validate_save(mode, paths, patch, roots)
    by_path = _volumes_by_path(volumes)
    total = len(paths)
    progress(0, total)
    entries: list[dict[str, object]] = []
    for index, path in enumerate(paths):
        if cancel():
            raise JobCancelled({"entries": entries})
        file_patch, write_number = _file_patch(
            mode, path, patch, by_path.get(_resolved(path)), parse_number
        )
        if not file_patch:
            progress(index + 1, total)
            continue
        try:
            output = save_comic_info(
                path,
                file_patch,
                write_number=write_number,
                keep_cbr_original=keep_cbr_original,
            )
        except Exception as exc:
            entries.append(_error_entry(path, exc))
            progress(index + 1, total)
            continue
        entries.append(
            _after_success(
                path,
                output,
                db_path=db_path,
                cache_dir=cache_dir,
                roots=roots,
                write_poster=write_poster,
                refresh_volume=refresh_volume,
                forget_volume=forget_volume,
                with_poster=True,
            )
        )
        progress(index + 1, total)
    return {"entries": entries}


def preview_rename(
    directory: str,
    template: str,
    roots: Sequence[str],
    *,
    plan_rename: Callable[[str, str], list[object]],
) -> list[object]:
    """Plan renames in ``directory``. Does not call ``rename_in_directory``."""
    ensure_inside(directory, roots)
    return plan_rename(directory, template)


def run_rename(
    *,
    directory: str,
    template: str,
    roots: Sequence[str],
    db_path: str,
    cache_dir: str,
    rename_in_directory: Callable[[str, str], list[object]],
    write_poster: Callable[[str], object],
    refresh_volume: Callable[..., object],
    forget_volume: Callable[..., object],
    cancel: Cancel,
    progress: Progress,
) -> dict[str, object]:
    """Rename every archive directly in the place, then write posters."""
    ensure_inside(directory, roots)
    if cancel():
        raise JobCancelled({"entries": []})
    results = rename_in_directory(directory, template)
    total = len(results)
    progress(0, total)
    entries: list[dict[str, object]] = []
    for index, item in enumerate(results):
        if cancel():
            raise JobCancelled({"entries": entries})
        source = str(item.path)
        if not item.ok or item.output_path is None:
            entries.append(
                {
                    "path": source,
                    "error_type": item.error_type,
                    "error_message": item.error_message,
                }
            )
        else:
            entries.append(
                _after_success(
                    source,
                    item.output_path,
                    db_path=db_path,
                    cache_dir=cache_dir,
                    roots=roots,
                    write_poster=write_poster,
                    refresh_volume=refresh_volume,
                    forget_volume=forget_volume,
                    with_poster=True,
                )
            )
        progress(index + 1, total)
    return {"entries": entries}


def run_convert(
    *,
    paths: Sequence[str],
    roots: Sequence[str],
    keep_cbr_original: bool,
    db_path: str,
    cache_dir: str,
    convert_cbr: Callable[..., Path],
    refresh_volume: Callable[..., object],
    forget_volume: Callable[..., object],
    cancel: Cancel,
    progress: Progress,
) -> dict[str, object]:
    """Convert selected ``.cbr`` files. ``.cbz`` files are skipped, not errors."""
    for path in paths:
        ensure_inside(path, roots)
    total = len(paths)
    progress(0, total)
    entries: list[dict[str, object]] = []
    for index, path in enumerate(paths):
        if cancel():
            raise JobCancelled({"entries": entries})
        if Path(path).suffix.lower() == ".cbz":
            entries.append({"path": path, "skipped": True})
            progress(index + 1, total)
            continue
        try:
            output = convert_cbr(path, keep_cbr_original=keep_cbr_original)
        except Exception as exc:
            entries.append(_error_entry(path, exc))
            progress(index + 1, total)
            continue
        entries.append(
            _after_success(
                path,
                output,
                db_path=db_path,
                cache_dir=cache_dir,
                roots=roots,
                write_poster=lambda _path: None,
                refresh_volume=refresh_volume,
                forget_volume=forget_volume,
                with_poster=False,
            )
        )
        progress(index + 1, total)
    return {"entries": entries}


def run_scan(
    *,
    db_path: str,
    cache_dir: str,
    roots: Sequence[str],
    scan: Callable[..., ScanResult],
    cancel: Cancel,
    progress: Progress,
) -> dict[str, object]:
    """Scan ``roots``. A cancelled scan result becomes ``JobCancelled``."""
    progress(0, 0)
    result = scan(db_path, cache_dir, roots, cancel=cancel)
    payload = _scan_payload(result)
    committed = len(result.written) + len(result.unchanged) + len(result.failed)
    progress(committed, committed)
    if result.cancelled:
        raise JobCancelled(payload)
    return payload


def default_client() -> httpx.Client:
    """Return the catalog client. The shell does not set ``User-Agent``."""
    return httpx.Client(timeout=HTTP_TIMEOUT)


def _file_patch(
    mode: str,
    path: str,
    patch: Mapping[str, str],
    volume: object | None,
    parse_number: Callable[[str], str | None],
) -> tuple[dict[str, str], bool]:
    stem = _stem(volume, path)
    stored = "" if volume is None else str(getattr(volume, "number", "") or "")
    file_patch = dict(patch)
    if mode == "one":
        if "Number" in file_patch:
            write_number = True
        else:
            parsed = parse_number(stem)
            if parsed is not None and parsed != stored:
                file_patch["Number"] = parsed
                write_number = True
            else:
                write_number = False
    else:
        file_patch.pop("Number", None)
        file_patch.pop("Volume", None)
        parsed = parse_number(stem)
        if parsed is not None and parsed != stored:
            file_patch["Number"] = parsed
        write_number = "Number" in file_patch
    if "PageCount" not in file_patch:
        filled = _page_count_fill(volume)
        if filled is not None:
            file_patch["PageCount"] = filled
    return file_patch, write_number


def _page_count_fill(volume: object | None) -> str | None:
    """Return archive page count text when ComicInfo left PageCount blank."""
    if volume is None:
        return None
    stored = str(getattr(volume, "page_count", "") or "").strip()
    if stored:
        return None
    count = getattr(volume, "archive_page_count", None)
    if not isinstance(count, int) or count <= 0:
        return None
    return str(count)


def _after_success(
    path: str,
    output: Path,
    *,
    db_path: str,
    cache_dir: str,
    roots: Sequence[str],
    write_poster: Callable[[str], object],
    refresh_volume: Callable[..., object],
    forget_volume: Callable[..., object],
    with_poster: bool,
) -> dict[str, object]:
    output_path = str(output)
    entry: dict[str, object] = {"path": path, "output_path": output_path}
    if with_poster:
        try:
            write_poster(output_path)
        except Exception as exc:
            entry["error_type"] = type(exc).__name__
            entry["error_message"] = str(exc)
    try:
        refresh_volume(db_path, output_path, roots)
    except Exception as exc:
        entry.setdefault("error_type", type(exc).__name__)
        entry.setdefault("error_message", str(exc))
    if Path(output_path).resolve() != Path(path).resolve():
        try:
            forget_volume(db_path, cache_dir, path)
        except Exception as exc:
            entry.setdefault("error_type", type(exc).__name__)
            entry.setdefault("error_message", str(exc))
    return entry


def _scan_payload(result: ScanResult) -> dict[str, object]:
    return {
        "written": list(result.written),
        "unchanged": list(result.unchanged),
        "failed": list(result.failed),
        "deleted": list(result.deleted),
        "skipped_or_incomplete": list(result.skipped_or_incomplete),
        "cancelled": result.cancelled,
    }


def _volumes_by_path(volumes: Sequence[object]) -> dict[str, object]:
    found: dict[str, object] = {}
    for volume in volumes:
        found[_resolved(str(volume.path))] = volume
    return found


def _resolved(path: str) -> str:
    return str(Path(path).resolve())


def _stem(volume: object | None, path: str) -> str:
    name = str(volume.name) if volume is not None else Path(path).name
    return Path(name).stem


def _field_text(row: object, name: str) -> str:
    value = getattr(row, FIELD_COLUMNS[name], "")
    if value is None:
        return ""
    return str(value)


def _parent_path(path: str) -> str:
    return _directory_key(str(Path(path).parent))


def _directory_key(path: str) -> str:
    text = str(Path(path))
    if len(text) > 1:
        text = text.rstrip("\\/")
    return text


def _error_entry(path: str, exc: BaseException) -> dict[str, object]:
    return {
        "path": path,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
