---
description: One desktop process serves a localhost API and a pywebview window, and wires places, selection, scrape, save, rename, and convert to the archive, index, and provider modules.
status: active
---

# Application shell

This specification owns the desktop process, the TOML config file, the local API, background jobs, and what selection, scrape, save, rename, and convert do. It implements performance rules 1, 5, 7, and 8 from [00-project-overview.md](00-project-overview.md): a page read is one archive member, the first paint is the index, scrape and save and convert and rescan are cancellable background work, and a network result never writes an archive.

The Svelte client that performs these actions lives in `ui/` and uses the layout and components from [05-ui-design.md](05-ui-design.md). This specification places actions in that header, places sidebar, volume pane, and inspector. It does not define color, type, or component styling.

Archive bytes and ComicInfo stay in [01-archives-and-comicinfo.md](01-archives-and-comicinfo.md). The SQLite index, scan, and thumbnails stay in [02-library-index.md](02-library-index.md). Catalog HTTP, the query, and the form patch stay in [03-metadata-providers.md](03-metadata-providers.md).

## Modules

| Module | Role |
| --- | --- |
| `src/manga_tagger/config.py` | Resolve paths and read or write the TOML file. The only module that touches that file |
| `src/manga_tagger/shell.py` | Pure place, selection, and form functions, plus the job bodies. No FastAPI and no pywebview |
| `src/manga_tagger/jobs.py` | One worker, first in first out. No FastAPI and no pywebview |
| `src/manga_tagger/api/` | FastAPI app, Pydantic models, and HTTP errors. Routers validate input, call `shell` or `jobs`, and return models. They do not open archives, query SQLite, or call catalogs |
| `src/manga_tagger/window.py` | The only module that imports pywebview |
| `src/manga_tagger/__main__.py` | Load config, bind the server, enqueue the startup scan, open the window, then shut down |
| `ui/` | The client. `fetch` on the API origin. It does not call a pywebview JavaScript API |

`config.py`, `shell.py`, `jobs.py`, and `api/` do not import pywebview. Tests do not import `window.py` or `__main__.py`.

When this specification is implemented, `pyproject.toml` gains `fastapi`, `uvicorn`, `pywebview`, and `tomli-w`. `httpx` is the client library named by the provider specification. The server is uvicorn. There is no Flask, no Electron, and no second HTTP framework.

On Linux the dependency is the GTK extra of the pinned pywebview release,
`pywebview[gtk]==6.2.1`; other platforms install `pywebview==6.2.1` without
that extra. The GTK extra installs PyGObject into the same isolated Python
environment as the application. A distribution `python-gobject` package tied
to a different system-Python minor is not treated as satisfying this runtime
dependency. The operating system must still provide GTK 3, WebKitGTK 4.1, the
GObject-introspection and Cairo development files used to build the binding,
and their typelibs. Qt is not a fallback dependency for the Linux build.

`pyproject.toml` declares the supported interpreter range `>=3.12,<3.14`.
`uv.lock` is committed and development and CI install it with
`uv sync --locked --group dev`. CI runs the entire Python suite on CPython 3.12
and 3.13; adding another minor version requires first validating the FastAPI,
Starlette, HTTPX, and AnyIO `TestClient` combination on it and then expanding
both the declared range and the matrix.

The compatible ASGI test stack is pinned as one unit: FastAPI `0.116.1`,
Starlette `0.47.2`, HTTPX `0.28.1`, and AnyIO `4.10.0`. Starlette and AnyIO are
direct dependencies here to prevent the resolver from silently selecting a
new transitive combination that satisfies metadata constraints but hangs on
`TestClient` startup. Updating any member requires updating the lockfile and
passing the smoke test plus the full 3.12/3.13 matrix.

## Contract ownership

The application has one intentional implementation boundary: Python owns the
archive, index, provider, and HTTP contracts, while the TypeScript client owns
its local interaction state. The following inventory defines which repeated
values are authoritative and why a mirror exists:

| Contract | Authoritative definition | Browser mirror |
| --- | --- | --- |
| Owned and inspector ComicInfo fields | `archives/comicinfo.py` `OWNED_ELEMENTS`; `shell.py` derives `FORM_FIELDS` by omitting `Volume` | `ui/src/lib/library.ts` `FORM_FIELDS`, needed to render controls without a round trip |
| Shared batch fields | `archives/comicinfo.py` `BATCH_FIELDS`; `shell.py` keeps ordered `SHARED_FIELDS` and checks that the sets match at import | Ordered `SHARED_FIELDS`, needed for inspector order |
| Index-column mapping | `shell.py` `FIELD_COLUMNS` | `FIELD_COLUMNS`, because API rows arrive as JSON objects |
| Lockable fields | `FORM_FIELDS`; there is no separate lockable list | The same browser `FORM_FIELDS` drives lock controls |
| Provider ids | `providers/constants.py` `PROVIDER_IDS`; config defaults and provider dispatch import it | `PROVIDERS` adds display labels to those ids |
| Job and result keys | Pydantic `JobModel` plus shell result builders | TypeScript `Job`, `ScanResult`, candidate, issue, and work-entry shapes consume the JSON |
| Selection transitions and form construction | `shell.py` is the behavioral contract | Intentional pure TypeScript implementations keep clicks and typing synchronous |
| ComicInfo `Web` parsing for cover actions | `providers/web_id.py` performs authoritative validation before a write | The client mirrors supported URL shapes only to enable or disable controls early; the server always validates again |

`tests/contracts/app-contracts.json` is the cross-layer drift fixture. Python
tests compare it with the authoritative field lists, column mapping, provider
ids, lockable fields, constructed forms, and API result models. UI tests compare
the same fixture with their browser mirrors. A contract change therefore
requires an explicit fixture and test update on both sides. The duplicated
selection, form, and cover-URL algorithms also retain behavior tests in both
test suites; sharing their runtime code across the Python/browser boundary is
not practical.

The thumbnail route returns the cached path through `thumbnail_path`; there is
no shell helper that reads the whole thumbnail into bytes. FastAPI streams the
file response.

## Paths and config

`app_paths(platform, env, home)` returns the config file, the index file, and the thumbnail directory. `platform` is `linux`, `darwin`, or `win32`. `__main__` passes `sys.platform`. The function does not read the process environment itself. A blank environment value is unset. A relative `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `APPDATA`, or `LOCALAPPDATA` is ignored.

| Platform | Config | Index | Thumbnail cache |
| --- | --- | --- | --- |
| `linux`, and any other value | `$XDG_CONFIG_HOME/manga-tagger/config.toml`, or `home/.config/manga-tagger/config.toml` | `$XDG_DATA_HOME/manga-tagger/index.db`, or `home/.local/share/manga-tagger/index.db` | `$XDG_CACHE_HOME/manga-tagger/covers`, or `home/.cache/manga-tagger/covers` |
| `darwin` | `home/Library/Application Support/manga-tagger/config.toml` | `home/Library/Application Support/manga-tagger/index.db` | `home/Library/Caches/manga-tagger/covers` |
| `win32` | `%APPDATA%/manga-tagger/config.toml`, or `home/AppData/Roaming/manga-tagger/config.toml` | the same directory's `index.db` | `%LOCALAPPDATA%/manga-tagger/covers`, or `home/AppData/Local/manga-tagger/covers` |

`load_config(path)` reads UTF-8 TOML with the standard-library `tomllib`. A missing file returns the defaults below and does not create the file. Invalid TOML raises `ConfigError`. The message includes the path and says the TOML could not be parsed. Startup then exits with status 1 and does not open the window.

`save_config(path, config)` creates the parent directory and writes UTF-8 TOML with `tomli-w`. Unknown keys from the last successful load are written back. Comments are not preserved. A missing file's first save writes every known key.

The process keeps the loaded config in memory. `GET /api/config` returns that memory. `PUT /api/config` writes the file and, only after the write succeeds, replaces memory. A failed write leaves memory and the previous file unchanged and does not enqueue a scan.

A TOML value of the wrong type falls back on load. The file is not rewritten just because it was loaded.

| Key | Load fallback | PUT |
| --- | --- | --- |
| `library_roots` | Not a list becomes `[]`. Non-strings are dropped. Relative paths are dropped. Duplicates keep the first. Stored paths are `resolve(strict=False)` | Same dropping rules. A provided non-list is `400` `ConfigError` and writes nothing |
| `excluded_folders` | Not a list becomes `[]`. Non-strings and relative paths are dropped. Duplicates keep the first. Stored paths are `resolve(strict=False)` | Same dropping rules. A provided non-list is `400` `ConfigError` and writes nothing |
| `scan_subfolders` | Not a boolean becomes `true` | Not a boolean is `400` `ConfigError` |
| `keep_cbr_original` | Not a boolean becomes `true` | Not a boolean is `400` `ConfigError` |
| `write_poster_on_save` | Not a boolean becomes `true` | Not a boolean is `400` `ConfigError` |
| `auto_save_metadata_on_switch` | Not a boolean becomes `false` | Not a boolean is `400` `ConfigError` |
| `comicvine_api_key` | Not a string becomes `""` | Not a string is `400` `ConfigError` |
| `nautiljon_base_url` | Not a string becomes `""` | Not a string is `400` `ConfigError` |
| `nautiljon_api_key` | Not a string becomes `""` | Not a string is `400` `ConfigError` |
| `title_languages` | Not a list becomes `["fr", "en"]`. Non-strings are dropped. An empty list stays `[]` | Not a list is `400` `ConfigError`. Non-strings are dropped |
| `enabled_providers` | Not a list becomes the five known provider ids. Non-strings and unknown ids are dropped. Duplicates keep the first. An empty list stays `[]` | Not a list is `400` `ConfigError`. Same dropping rules as load. An empty list stays `[]` |
| `theme` | Not a string becomes `system`. Any string is kept, including one the UI treats as `system` | `system`, `light`, or `dark` are stored. Any other value is stored as `system` |

`PUT` replaces `library_roots`, `excluded_folders`, and `enabled_providers` wholesale. Omitted keys stay. The API normalizes the three library discovery settings and enqueues a scan only when `library_roots`, `excluded_folders`, or `scan_subfolders` changed, including a list changing to empty. An unchanged discovery value is treated like an omitted one: it does not enqueue a scan and does not make the request subject to the job-busy check. If a discovery setting changed while a job is already `queued` or `running`, that `PUT` returns 409 `JobBusyError`, writes none of the requested settings, and does not enqueue. Other keys do not enqueue a scan and are accepted during a job.

`PUT /api/config` returns `{ "config": <full config>, "job": <scan job or null> }`. `job` is the exact scan started by a root change, including when an inline or very fast scan is already terminal by the time the response is serialized. The client watches that id directly and never discovers a Settings scan through `/api/jobs/current`.

A provider id not listed in `enabled_providers` is unavailable for search, load, and list_issues. The provider module raises `ProviderUnavailableError` before HTTP. The header provider select only offers enabled ids.

## Places

A place is the parent directory of an indexed volume: the folder that directly contains that archive. Places come from the volume rows. There is no places table.

`volumes_for_roots(rows, roots, excluded_folders=(), scan_subfolders=True)` keeps a row when its resolved `path` is inside a root, is outside every excluded folder, and either subfolder scanning is enabled or its parent is one of the explicit roots. The check uses path components, so `/books` does not match `/books-extra`. An empty `roots` list keeps nothing. This filter does not delete rows and does not scan. It applies the current discovery settings to first paint, so stale index rows do not briefly reveal an excluded or now-disabled subfolder while the startup scan prunes them.

`places_from_volumes(rows)` builds one place per parent directory.

- The place path is that parent, with trailing separators removed.
- Order is the place path, ascending, compared by Unicode code point.
- The label is the directory name. When two or more places share a directory name, each of those labels is `parent / name`, where `parent` is the parent directory's name. When those labels still collide, the label is the full place path.
- A library root is a place only when a volume's parent is the root. A volume in a child folder belongs to that child, not to the root.

`volumes_in_place(rows, place_path)` keeps rows whose parent equals `place_path`. A nested volume is not included. Order is the `name` column, ascending, by Unicode code point. `failed` rows are included.

The selected place is session state. It is not a config key. `null` means no folder is selected: the shelf shows every volume for the current roots. When the library response arrives and nothing is selected, the client keeps `null`. When the selected place is absent from a later response, the client clears the selection to `null`. Choosing a place clears the volume selection. Choosing the already-selected place again clears the place to `null` and clears the volume selection. Clicking the sidebar outside a place row also clears the selected place and volume selection; it does nothing when no place is selected. A sidebar-background clear uses the same dirty-form navigation guard as choosing a place.

`volumes_for_shelf(rows, place_path)` returns `volumes_in_place(rows, place_path)` when `place_path` is a string. When `place_path` is `null`, it returns every row ordered by the `name` column, ascending, by Unicode code point. `failed` rows are included.

The main pane lists `volumes_for_shelf` for the current place selection. An empty library, a selected place with no rows, or no volumes under the roots shows the sentence `No volumes yet.`

List and grid views group those rows by `series` after trim. Blank-series volumes come first with no header. Named series follow in case-folded alphabetical order, each with a muted series header above its volumes. A volume under a named series in list view shows a tree marker before the thumbnail. Grid view uses the same headers and has no tree marker. A volume row's only text label is `name`. A grid cell's label is `name`. Visible list order for selection is that grouped order, flattened.

`GET /api/library` calls `list_volumes`, then `volumes_for_roots` and `places_from_volumes`. The response `volumes` are every row kept for the current roots, not only the selected place. The client applies `volumes_for_shelf` locally. The request does not call `scan`, does not open an archive, and does not build a thumbnail.

There is no library filter field in the header. The shelf shows every volume for the current place (or the whole library when no place is selected).

## Selection

The selection is session state on the client. `shell.py` is the contract. The client uses the same transitions. Paths are stored in the current visible list order.

`select_plain(visible, path)` selects only `path` and makes it the anchor.

`select_range(visible, selection, path)` selects the inclusive range from the anchor to `path` in `visible` order. The anchor does not move. If there is no anchor, or the anchor is not in `visible`, it behaves as `select_plain`.

`select_toggle(visible, selection, path)` adds `path` when it was not selected and removes it when it was. Adding the first selected path makes it the anchor. Adding another path leaves the anchor. Removing the anchor makes the anchor the first remaining selected path in `visible` order, or nothing when the selection is empty.

A plain click calls `select_plain`. Shift-click calls `select_range`. Ctrl-click calls `select_toggle`. On macOS, Command-click is the same toggle. The preview is always the anchor.

`selection_after_filter(visible, selection)` drops selected paths that are no longer in `visible` (for example after a library refresh). If the anchor was dropped, the anchor becomes the first remaining selected path in list order, or nothing.

## Form

`FORM_FIELDS` is every owned ComicInfo text element except `Pages` and `Volume`, in this order: `Title`, `Series`, `Number`, `Count`, `Publisher`, `PageCount`, `LanguageISO`, `AgeRating`, `Manga`, `Genre`, `Summary`, `Web`, `CommunityRating`, `Notes`, `Year`, `Month`, `Day`, `Writer`, `Penciller`, `Inker`, `CoverArtist`. `Volume` is owned and saved when `Number` is written, but it is not an inspector field.

`SHARED_FIELDS` is `Series`, `Count`, `Publisher`, `LanguageISO`, `AgeRating`, `Genre`, `Manga`, `Writer`, `Penciller`, `Inker`, `CoverArtist`.

Index columns map to those elements: `title`, `series`, `number`, `volume`, `count`, `publisher`, `page_count`, `language_iso`, `age_rating`, `manga`, `genre`, `summary`, `web`, `community_rating`, `notes`, `year`, `month`, `day`, `writer`, `penciller`, `inker`, `cover_artist`. A missing element is `""`.

`form_from_volumes(rows)` returns no form when `rows` is empty. One row returns `mode` `one` and a `values` object with every `FORM_FIELDS` key. Each field is `{ "value", "dirty", "locked" }`. `dirty` starts false. `locked` is true when that ComicInfo name is in the row's `locked_fields` list (see [07-field-locks.md](07-field-locks.md)). When the row's ComicInfo `page_count` is blank after trim and `archive_page_count` is a positive integer, `PageCount`'s `value` is that count as decimal text and `dirty` stays false. When `page_count` is non-blank, or `archive_page_count` is null or not positive, `PageCount` keeps the stored text. Several rows return `mode` `many` and only `SHARED_FIELDS`. Each shared field is `{ "value", "mixed", "dirty", "locked" }`. `dirty` starts false. `locked` is true only when every selected row includes that name in `locked_fields`; otherwise `locked` is false. When every selected row has the same text, `value` is that text and `mixed` is false. When they differ, `value` is `""` and `mixed` is true. Editing a field sets `dirty` to true and, on a shared field, `mixed` to false, when the new text differs from the current value or the field is mixed. When the field is `locked`, an edit is a no-op. When the typed text equals the current value and the field is not mixed, the form is unchanged. Until Save rebuilds the form from the index, `dirty` is also the UI signal that the field has not been written to ComicInfo yet; [05-ui-design.md](05-ui-design.md) paints those controls amber.

No selection: the inspector has no form and no image. Save and scrape do nothing.

One volume: each field is a caption label and a control. The caption is a readable name for the ComicInfo element, not the element name itself: `Title`, `Series`, `Issue`, `Volumes`, `Publisher`, `Page count`, `Language`, `Age rating`, `Manga`, `Genre`, `Summary`, `Web`, `Community rating`, `Notes`, `Year`, `Month`, `Day`, `Writer`, `Penciller`, `Inker`, `Cover artist`. `Issue` is the caption for `Number`. `Volumes` is the caption for `Count`. There is no inspector control for `Volume`. The control still reads and writes the element key (`Number`, `Count`, `PageCount`, `LanguageISO`, and the rest). `Summary` and `Notes` are a textarea with the text input's border, radius, background, and `text-sm`, at least four rows. `Manga` is a select whose option values are the ComicInfo tokens `YesAndRightToLeft`, `Yes`, `No`, `YesAndLeftToRight`, a blank option, and the current token when it is not already in that list. Option captions are `Yes (right to left)`, `Yes`, `No`, `Yes (left to right)`, a blank caption, and the raw token for an unknown current value. Every other field is a text input.

Several volumes: the inspector shows only the shared fields, including `AgeRating` and `Manga`. A mixed field's placeholder is `Mixed`. A field that is not `dirty` is omitted from the save patch, whether it is mixed or the same on every row. An empty uniform value is not sent as `""`, so Save does not remove an element the user did not edit.

One volume uses the same dirty rule. The save patch is the fields whose `dirty` is true. A field the user did not edit is absent, not `""`.

The form is rebuilt from the index rows when the selection or place actually changes and when a save, rename, or convert refetch completes, except for a save whose archive writes failed or were cancelled. After such a save, the client overlays the pre-save dirty field values and dirty flags onto the refetched form. In a multi-volume form the dirty patch is shared, so any required archive-write failure preserves the whole dirty patch for retry; it is not possible to mark that shared value clean for only the files that succeeded. A finished scan refetches the library and rebuilds the form only when no field is dirty. Dirty fields stay as the user left them.

Leaving a dirty form by choosing another volume or another place is gated by `auto_save_metadata_on_switch`. When no field is dirty, the client applies the new selection or place and rebuilds immediately. When any field is dirty and the setting is `false` (the default), the client shows an Unsaved metadata dialog and holds the pending navigation: **Save** runs the save job for the current selection and applies the pending navigation only after that job reaches `succeeded` and every required archive write succeeded; **Don't save** discards the form and applies the pending navigation; **Cancel** (or Close) keeps the current selection, place, and form. When any field is dirty and the setting is `true`, the client starts that same save without the dialog and uses the same rule. A top-level failed or cancelled save, or a succeeded save with any per-file archive-write failure, clears the pending navigation and leaves the current selection and dirty form in place. A succeeded save with no entries is an unchanged save: no archive write was required, so it applies the pending navigation. Poster and index-refresh errors happen after the archive metadata write, retain that entry's `output_path`, and do not block pending navigation or keep the metadata draft dirty; their inspector errors still report that the follow-up work failed. While the dialog is open or a switch-triggered save is in flight, further volume and place clicks are ignored.

## Preview

The inspector image is one page of the anchor. The client starts at `cover_index`, or at `0` when `cover_index` is null or outside the page list. Previous and next stay inside `0 .. archive_page_count - 1`. They are quiet icon buttons, Lucide `ChevronLeft` and `ChevronRight`, with accessible names `Previous page` and `Next page`. At the ends, the matching button is disabled. Changing the anchor resets the index to the new cover. Page index lives in the preview control alone: paging does not rebuild the metadata form, and the previous image stays until the next page bytes arrive. The preview frame is a fixed 320px height so paging does not shift the fields below; the image is centered inside that frame.

`GET /api/page` calls the archive's combined page read once. That operation resolves the index and returns the requested member's uncompressed bytes plus its member name from one CBZ central-directory listing or one CBR `lsar` invocation; the route does not list the archive separately. Index bounds checking stays in the archive layer. The route selects `Content-Type` from the returned member name: `image/jpeg` for `jpg` and `jpeg`, `image/png` for `png`, `image/webp` for `webp`, and `image/gif` for `gif`, compared case-insensitively, otherwise `application/octet-stream`. A `failed` anchor, or a null or zero `archive_page_count`, shows an accessible preview-unavailable state when the row has an `error_message`, and requests no page. The state keeps the backend message as its detailed reason rather than replacing or hiding diagnostic information.

List and grid thumbnails use `GET /api/thumbnail`, which calls `thumbnail_for` and returns that JPEG as `image/jpeg`. The response is the cached file (not bytes read into the handler), with `Cache-Control: private, max-age=3600` and an `ETag` equal to the JPEG filename stem (`{digest}-{mtime_ns}-{size}`). The client sets that URL as the `img` `src` (lazy, async decode) and does not fetch into a blob URL. The list row uses the image when it loads, and Lucide `Book` when the volume is failed or the image errors. A grid cell uses the thumbnail the same way; a failed grid cell has no image and still shows its label. Thumbnail reads are not the preview page, and the preview does not write the thumbnail cache.

## Jobs

`JobRunner` runs one job at a time, in start order. It does not use a process pool. A job has `id`, `name`, `state`, `error_type`, `error_message`, `result`, `completed`, and `total`. Ids are decimal strings starting at `1`. States are `queued`, `running`, `succeeded`, `failed`, and `cancelled`. `error_type` and `error_message` are `""` unless the state is `failed`. `result` is null unless the job succeeded or was cancelled with a partial result. `completed` and `total` are integers. A queued job has `completed` 0.

`start(name, fn)` queues `fn` when no job is `queued` or `running`. Otherwise it raises `JobBusyError` and does not enqueue. The function receives `cancel`, a callable that returns true after a cancel request, and `progress(completed, total)`. `inline=True` runs the job to a terminal state on the caller thread before `start` returns. Tests use the inline runner. They do not call `time.sleep`.

Search and load set `total` to 1 and `completed` to 0 until the request finishes, then `completed` is 1. Issues uses the same 0/1 then 1/1 progress. Save and convert set `total` to the path count and increment `completed` after each path, including a failure or a skip. Rename sets `total` to the number of targeted archives and increments `completed` after each planned file. Scan calls `progress(0, 0)` before the index scan and `progress(committed, committed)` when it returns. `committed` is the number of written, unchanged, and failed paths. The index scan has no per-candidate callback, so this job does not report candidates found so far.

`cancel(id)` on a queued job sets `cancelled` and does not call `fn`. On a running job it sets the flag and does not abort the thread. A provider request that has already started is not aborted. `get` of an unknown id raises `JobNotFoundError`. `current` is the running job, or the queued job when none is running, or null when none has been started. The busy rule means there is at most one of those.

`fn` returns a result for `succeeded`. `JobCancelled` and `ProviderCancelledError` become `cancelled`. `JobCancelled` may carry the partial result. Any other exception becomes `failed`, with `error_type` the exception class name and `error_message` the exception message.

`shutdown` cancels every queued job without running it, sets the cancel flag on the running job, and joins the worker. It does not kill the thread. Closing the window calls `shutdown`, then stops the server. The process exits 0.

The header contains only its persistent controls. No job adds a contextual name, progress count, or Cancel button beside the icons. Search and Issues progress live in the Matches or Issues dialog, whose dismiss action can cancel that request. Job outcomes use the existing completion toasts, including Scan, Rename, and Cover; no in-progress toast is added. Scrape, Save, Rename file(s), Convert CBR, and Scan library are disabled while `current` is `queued` or `running`.

## HTTP API

`serve(app)` binds `127.0.0.1` and port `0`, so the port is chosen by the operating system. The host is not configurable. `serve` returns the chosen port and a `close()` that stops the server. The UI origin is `http://127.0.0.1:{port}/`.

`create_app` takes the in-memory config, the index path, the thumbnail directory, the UI directory or null, an optional runner, optional service callables, an optional `pick_folder`, an optional `destroy_window`, and an optional `system_theme` reader. Omitted services are the archive, index, and provider operations this document names. The default runner is one worker thread. An omitted `pick_folder` makes `POST /api/dialogs/folder` return 503. An omitted `destroy_window` makes `POST /api/window/close` return 503. The default system-theme reader checks Omarchy's generated current theme on Linux and returns null elsewhere; tests inject a reader and never inspect the developer's home directory.

JSON errors are `{ "error_type", "error_message" }`. Expected client errors are HTTP 400, including an archive exception raised by `GET /api/page` or `GET /api/thumbnail`, and a rejected or failed `GET /api/cover`. An unknown job id is HTTP 404. A thumbnail that `thumbnail_for` does not create is HTTP 404 with `error_type` `NoThumbnailError`.

Archive, page, thumbnail, save, rename, and convert paths must be absolute. A relative path is `ShellError` and does not touch the archive. After `resolve(strict=False)`, the path must be inside a current library root, using the same separator rule as places. Otherwise `OutsideLibraryError`, and nothing is read or written. `OutsideLibraryError` subclasses `ShellError`. Validation that fails this way does not enqueue a job.

| Method and path | Behavior |
| --- | --- |
| `GET /api/library` | `{ "places": [{ "path", "label" }], "volumes": [row] }`. Volume keys are the index columns. SQL NULL is JSON null. Does not scan |
| `GET /api/page?path=&index=` | One page. `index` is a non-negative integer. A missing or negative index is `ShellError` |
| `GET /api/thumbnail?path=` | The cached cover JPEG, building it on demand through `thumbnail_for`. `Cache-Control: private, max-age=3600`. `ETag` is the JPEG filename stem |
| `GET /api/cover?url=` | Bytes of one allow-listed remote catalog cover. Only `https` URLs whose host is `uploads.mangadex.org`, `www.nautiljon.com`, or `nautiljon.com` are accepted. Used by Matches so the WebView loads a same-origin image |
| `GET /api/config` | The known keys |
| `GET /api/system-theme` | The active Omarchy semantic palette, or JSON null when it is missing or invalid. The response is `Cache-Control: no-store` |
| `PUT /api/config` | A partial object of those keys. Returns `{ "config": <full config>, "job": <scan job or null> }`. A normalized root change enqueues the returned scan after a successful write; omitted or unchanged roots do not |
| `POST /api/dialogs/folder` | Calls the injected `pick_folder`. Returns `{ "path" }` or `{ "path": null }` when the dialog is cancelled. No picker is HTTP 503 |
| `POST /api/window/close` | Calls the injected `destroy_window`. Returns an empty 204. No closer is HTTP 503 |
| `POST /api/library/roots` | Body `{ "paths": [...] }`. Appends existing directories that are not already roots. Returns the full config, `added`, and the scan `job` when a root was added |
| `POST /api/jobs/scan` | Enqueues `scan` |
| `POST /api/jobs/search` | Body `{ "provider", "series", "filename_stem" }` |
| `POST /api/jobs/issues` | Body `{ "provider", "match_id" }` |
| `POST /api/jobs/load` | Body `{ "provider", "match_id", "filename_stem", "mode", "form", "issue_id"?, "count"? }` |
| `POST /api/jobs/save` | Body `{ "paths", "patch", "mode" }` |
| `POST /api/jobs/rename` | Body `{ "directory", "template", "paths"? }` |
| `POST /api/rename/preview` | Body `{ "directory", "template", "paths"? }`. Returns `{ "entries": [{ "path", "output_path", "error_type", "error_message" }] }` from `plan_rename`. Does not rename. The same absolute-path and library-root checks as rename apply before `plan_rename` is called |
| `POST /api/jobs/convert` | Body `{ "paths" }` |
| `POST /api/jobs/cover` | Body `{ "path", "action", "web", "number"? }` where `action` is `replace` or `insert`. See [08-cover-from-provider.md](08-cover-from-provider.md) |
| `POST /api/field-locks` | Body `{ "paths", "field", "locked" }`. Synchronous. Updates index `locked_fields` for each path that has a row. Returns `{ "volumes": [row, ...] }`. See [07-field-locks.md](07-field-locks.md). Does not enqueue a job and does not write an archive |
| `POST /api/cache/thumbnails/clear` | Synchronously calls `clear_thumbnail_cache` for the app thumbnail directory and returns `{ "removed": N }`. Does not enqueue a job or alter configuration, the index, archives, posters, or browser caches |
| `GET /api/jobs/current` | The running job, or the queued job, or JSON null |
| `GET /api/jobs/startup` | The startup scan job, including its terminal result, or JSON null when startup did not enqueue one |
| `GET /api/jobs/{id}` | That job |
| `POST /api/jobs/{id}/cancel` | Cancel that job. Returns the job |
| `GET /` | `ui/dist/index.html` when that directory was given and contains it. Otherwise HTTP 200, `text/plain; charset=utf-8`, body `UI build is missing.` |
| other non-API paths | A file inside `ui/dist` whose resolved path stays inside that directory. Anything else is 404, including a path that escapes the directory |

`/api` routes are matched before static files. A missing UI build does not disable `/api`.

`GET /api/system-theme` returns null, or `{ "mode", "background", "dark_background", "lighter_background", "foreground", "dark_foreground", "accent", "selection", "red", "yellow", "orange" }`. `mode` is `light` or `dark`; every color is normalized lowercase `#rrggbb`. The reader accepts only a complete palette and turns a missing file, malformed TOML, unsupported mode, missing role, or invalid color into null. On Linux its source is `~/.local/state/omarchy/current/theme/colors.toml`. It never writes that file or invokes an Omarchy command.

Job JSON is `{ "id", "name", "state", "error_type", "error_message", "result", "completed", "total" }`. Start endpoints return that object. A start while a job is `queued` or `running` is HTTP 409 `JobBusyError` and does not enqueue.

On mount the client requests `GET /api/jobs/startup` once and watches the returned id, even when that job is already terminal. This makes startup completion discoverable when the scan finishes before the first UI request. The client also polls `GET /api/jobs/current`, and polls `GET /api/jobs/{id}` for a job it started, while the state is `queued` or `running`. The same 500 millisecond timer also refreshes `GET /api/system-theme`; a theme failure is isolated from job polling. The interval is not a TOML key. Tests do not wait on it. When `scan`, `save`, `rename`, or `convert` reaches `succeeded`, `failed`, or `cancelled`, the client fetches the library once for that job id. A set of settled ids prevents the startup endpoint, current-job polling, and a direct start response from settling one job more than once. `search`, `issues`, and `load` do not refetch the library. A search, issues, or load result is applied only when its id is the newest search, issues, or load the client started. While that load is `queued` or `running`, the form controls are disabled. While that save is `queued` or `running`, the form controls are disabled.

When a watched job reaches `succeeded` or `failed`, the client also shows one toast summary from [05-ui-design.md](05-ui-design.md). A `cancelled` job does not toast. Stale search, issues, or load ids (not the newest the client started) do not toast. Rename preview errors and folder-drop validation stay in their dialogs and sidebar lines; they are not toasts. Search, issues, and load outcomes (match count, no matches, no issues, and provider errors) are toast-only; the inspector does not repeat them. Inspector lines for per-file save/rename/convert errors and scan-root detail stay as they are. For Save, client draft handling treats an error entry without `output_path` as an archive-write failure and an error entry with `output_path` as a post-write poster or index-maintenance failure. Cover jobs refetch the library and toast like Save; see [08-cover-from-provider.md](08-cover-from-provider.md).

| Job | Success toast | Failure toast |
| --- | --- | --- |
| Search (Scrape) | `Found 1 match.` when N is 1; `Found N matches.` when N is not 1; `No matches.` when N is 0 | `error_message`, or `Scrape failed.` when that string is blank |
| Issues | `No issues available.` when the list is empty; otherwise no toast (Issues dialog opens) | `error_message`, or `Issues failed.` when that string is blank |
| Load | `Metadata loaded.` | `error_message`, or `Load failed.` when that string is blank |
| Save | `Issue updated.` when exactly one counted entry succeeded with no `error_message`; `Saved N issues.` when every counted entry succeeded and N is not 1; `Saved N of M.` when some have `error_message` | `error_message`, or `Save failed.` when that string is blank |
| Rename | `Renamed 1 file.` when every counted entry succeeded and N is 1; `Renamed N files.` when every counted entry succeeded and N is not 1; `Renamed N of M.` when some have `error_message` | `error_message`, or `Rename failed.` when that string is blank |
| Convert | `Converted 1 file.` / `Converted N files.` / `Converted N of M.` with the same entry rule as Rename, counting only entries that are not `skipped` | `error_message`, or `Convert failed.` when that string is blank |
| Scan | `Library updated.` | `error_message`, or `Scan failed.` when that string is blank |

For save, rename, and convert, `N` is the number of counted entries with a blank or missing `error_message`, and `M` is the counted entry total. An empty entry list on success is `Saved 0 issues.`, `Renamed 0 files.`, or `Converted 0 files.` English count agreement uses the singular noun only when the count is 1; 0 and other values use the plural.

## Scrape

The provider select lists MangaDex (`mangadex`), AniList (`anilist`), MyAnimeList (`jikan`), Comic Vine (`comicvine`), and Nautiljon (`nautiljon`). The choice is session state and defaults to `mangadex`. It is not a config key.

Scrape uses the anchor. It does nothing when there is no anchor. The request `series` is the form's `Series` when that control is non-blank and not mixed. Otherwise `series` is `""`. `filename_stem` is the anchor `name` with its extension removed. The job calls `build_query(series, filename_stem)` and then `search`. It passes `title_languages`, `comicvine_api_key`, `nautiljon_base_url`, and `nautiljon_api_key` from config at the start of the job, the cancel callable, and an `httpx.Client` with a 15 second timeout. The client is closed when the job ends. The shell does not set `User-Agent` and does not retry.

The result is `{ "candidates": [{ "id", "title", "year", "credit", "count", "summary", "cover" }] }`. When Scrape starts, the client opens a centered Matches dialog in a searching state (see [05-ui-design.md](05-ui-design.md)). When the list is non-empty, the dialog replaces that body with a cover preview, a candidate table, and a summary pane. The first candidate is highlighted. A single click or arrow key changes the highlight (cover and summary follow) and does not start `load`. Footer actions are Cancel and OK; when the form mode is `one`, Select Issue precedes Cancel. OK or Enter starts `load` for the highlighted series id without `issue_id`. When mode is `one`, preferred `number` for that load is the form's `Number` when non-blank and not mixed, otherwise the provider falls back to `parse_number(filename_stem)`. When mode is `many`, Comic Vine and Nautiljon load series metadata only (no issue/volume resolve); other catalogs stay series-only. When mode is `one`, Select Issue or a double-click on a row starts the Issues job for that id (see [06-select-issue.md](06-select-issue.md)). When mode is `many`, Select Issue is hidden and double-click acts like OK. Dismiss while searching cancels the Search job and closes the dialog. Dismiss after results clears the candidate list without loading. An empty list is success, not an error. The toast shows `No matches.`, the dialog closes, and the form is unchanged. The inspector does not show match rows or a no-matches line.

The Issues job calls `list_issues` with the same config and client rules. The result is `{ "issues": [{ "id", "number", "title", "date", "cover", "summary" }] }`. When the list is non-empty, the client opens the Issues dialog. When it is empty, the toast shows `No issues available.` and Matches stays open. A failed Issues job leaves Matches open and toasts `error_message` (or `Issues failed.`).

`load` calls the provider `load` with the anchor `filename_stem`, optional `issue_id`, preferred `number` from the form as above, `mode` from the form, and the same config and client rules. When `mode` is `many` and `issue_id` is blank, Comic Vine and Nautiljon use series/volume catalog load only (see [06-select-issue.md](06-select-issue.md)). When the load body includes a non-blank `count` (the highlighted search candidate's `count` from the Matches step), that string is written into the patch as `Count` after the provider returns, so the inspector `Volumes` field fills from the series search even when the issue or volume load does not repeat that total. A blank or omitted `count` leaves whatever `Count` the provider set, or omits it. The job then runs `merge_load_patch(form, patch, mode)`. For `one`, each patch key that is in `FORM_FIELDS` replaces that form value and sets `dirty` to true when the patch text differs from the current value, except a key whose form field is `locked` is skipped entirely (value and dirty stay). When the patch text equals the current value, that key is left unchanged and its `dirty` flag stays as it was. Keys the patch omits stay, and their `dirty` flag stays as it was. For `many`, each patch key that is in `SHARED_FIELDS` sets that field's `value`, sets `mixed` to false, and sets `dirty` to true when the patch text differs from the current value or the field is mixed, except a locked shared field is skipped. When the patch text equals the current value and the field is not mixed, that key is left unchanged. `Manga` and `Count` are among those keys. Every other patch key is ignored, including `Title`, `Number`, `Summary`, `Web`, and dates. The result is `{ "form": { "mode", "values" } }`. The client replaces its form with that object when the selection is still the one it sent. No archive is written. A successful load clears the candidate list and any open issues list so the Matches and Issues dialogs close. OK and Select Issue both send the highlighted series candidate's `count` on the load body.

`ProviderUnavailableError`, `ProviderTimeoutError`, `ProviderRateLimitError`, and `ProviderResponseError` fail the job. `ProviderCancelledError` cancels it. The form is unchanged and the archive is unchanged. A new search clears the candidate list when it starts and shows the Matches searching body again. A failed or cancelled search closes the Matches dialog; a failed search also clears candidates and the toast shows `error_message` (or `Scrape failed.`). A failed load leaves the candidate list so the Matches dialog stays open and another row can be chosen; its toast shows `error_message` (or `Load failed.`). Search, issues, and load do not write those messages into the inspector.

A blank Comic Vine key, or a blank Nautiljon base URL or API key, fails inside `search`, `list_issues`, or `load` with `ProviderUnavailableError` before a request. The shell does not replace that error.

## Save

Save does nothing when the selection is empty.

The patch for one volume is every `FORM_FIELDS` key whose `dirty` is true, excluding `Pages`. `""` removes that element. `mode` is `one` and `paths` has that one path. When `Number` is dirty, `write_number` is true and the patch uses the form value. When `Number` is not dirty and `Number` is not locked on that volume, the shell parses that file's filename stem. If the parse returns a string and the form's `Number` value differs, the patch includes `Number` and `write_number` is true. If the parse returns `None`, or the form value already equals it, or `Number` is locked, `Number` is omitted. When `PageCount` is not in the patch, the row's ComicInfo `page_count` is blank after trim, `archive_page_count` is a positive integer, and `PageCount` is not locked on that volume, the patch includes `PageCount` with that count as decimal text. When `PageCount` is already in the patch (including `""`), or `page_count` is non-blank, or there is no positive `archive_page_count`, or `PageCount` is locked, `PageCount` is not added. An empty patch does not call `save_comic_info`. The job succeeds with `{ "entries": [] }`.

The shared patch for several volumes is the shared fields whose `dirty` is true, including a field the user cleared to `""` and a field a load just set. `Manga` follows that rule. Fields that are still not `dirty` are absent, not `""`. `mode` is `many`. For each path the shell copies that shared patch and, when that volume does not lock `Number` and `parse_number` of that file's stem returns a string different from the row's `number`, adds `Number`. `write_number` is true only when that file's patch includes `Number`. `Volume` is never added. The same per-file `PageCount` fill used for `one` applies: blank ComicInfo `page_count`, a positive `archive_page_count`, and an unlocked `PageCount` add `PageCount` unless the shared patch already carries `PageCount`. The request body does not carry `Number` or that filled `PageCount`. The shell adds them. A file whose patch is empty is not passed to `save_comic_info` and is not an error. If every file is skipped, the job succeeds with `{ "entries": [] }`.

Before any write, a `one` save whose `paths` length is not 1, or whose patch contains a key outside `FORM_FIELDS`, raises `BatchFieldError` for a bad key and `ShellError` for the path count. A `many` save whose shared patch contains a key outside `SHARED_FIELDS` raises `BatchFieldError`. `Pages` is never a patch key. These failures write nothing and do not enqueue a job when the route can see them. The job repeats the key check so a direct call is just as strict. The per-file `Number` and `PageCount` fills are added after that check.

The job then calls `save_comic_info` once per path that has a patch. It does not call `save_many`, because that function cannot check cancel between files. The shared keys are the `save_many` field set. `keep_cbr_original` and `write_poster_on_save` are the config values copied when the job starts.

Cancel is checked before each file. A true flag raises `JobCancelled` with the entries so far. The current file is not interrupted. A file that raises records `{ "path", "error_type", "error_message" }` and the loop continues. A success records `{ "path", "output_path" }`. `output_path` is the `.cbz` path when a `.cbr` save converted it, otherwise the same path. When `write_poster_on_save` is true, after each success the job calls `write_poster` on `output_path`. When it is false, the job does not call `write_poster`. Then it calls `refresh_volume` on `output_path`, copies `locked_fields` from the old path onto the new row when the paths differ (see [07-field-locks.md](07-field-locks.md)), and, when `output_path` differs, `forget_volume` on the old path. A poster error does not undo the save. That entry keeps `output_path` and also has `error_type` and `error_message`.

The result is `{ "entries": [...] }` in request order. The job succeeds when the loop finishes, including when some entries have errors. An archive-write failure has `path`, `error_type`, and `error_message`, and no `output_path`. Once `save_comic_info` succeeds, its entry always retains `output_path`; a later poster, index refresh, lock-copy, or old-row cleanup failure adds `error_type` and `error_message` without removing that path. Those errors are listed in the inspector as `{filename}: {error_message}`. The client updates a selected path to `output_path` when present and drops a path that failed and is no longer in the library. It rebuilds the form after every save refetch, then restores the pre-save dirty fields when the job failed, was cancelled, or has an archive-write failure. A successful empty result and results containing only successful writes or post-write errors leave the rebuilt form clean.

## Rename

Rename is enabled when a place is selected, including when the volume selection is empty, and no job is `queued` or `running`. It renames only the selected archives when the selection is non-empty. With no files selected, it targets every archive directly in that place. Opening the dialog captures the selected paths; preview and confirmation use that same scope. The optional request `paths` list carries that selection; omitted, null, or empty means all direct archives. Each supplied path must be absolute, inside a library root, and a direct archive child of the selected directory; invalid scope is rejected before preview reads or job enqueueing. The dialog's text input starts as `{Series} v{Number:02}`. That string is not written to config. The dialog lists `plan_rename` before confirm by calling `POST /api/rename/preview`. Each success is `{old name} → {new name}`. Each failure is `{old name}: {error_message}`. Dismiss writes nothing. Confirm enqueues the job with that template.

The job checks cancel, then calls `rename_in_directory(directory, template, paths=paths)`. The directory is the selected place and must sit inside a library root. `rename_in_directory` has no cancel argument, so a call that has started runs until it returns. That call moves an existing sibling poster with the archive when one is present. When `write_poster_on_save` is true, for each success the job then calls `write_poster` on the new path. When it is false, the job does not call `write_poster`. Then it calls `refresh_volume` on the new path, copies `locked_fields` from the old path when they differ, and `forget_volume` on the old path when they differ. Cancel is checked between poster writes. A poster error does not undo the rename. That entry keeps `output_path` and also has `error_type` and `error_message`. A rename failure has `path`, `error_type`, and `error_message` and no `output_path`.

The place stays selected. The volume selection is cleared. The result entries follow the archives rename order.

## Convert

The selection check uses the library API's `extension` value, which is `cbr` or `cbz` without a leading dot, as defined in [02-library-index.md](02-library-index.md). UI test fixtures must use this same representation. Tests cover a CBR selection, a mixed CBR/CBZ selection, and an empty or CBZ-only selection.

Convert is enabled when at least one selected file has extension `cbr`, compared case-insensitively, and no job is `queued` or `running`. When `keep_cbr_original` is false, confirm shows `Convert 1 CBR file to CBZ and delete the originals?` when N is 1, or `Convert N CBR files to CBZ and delete the originals?` when N is not 1, where N is the number of selected `.cbr` files. Dismiss writes nothing. When `keep_cbr_original` is true, convert starts without that dialog. Selected `.cbz` files are entries `{ "path", "skipped": true }`. They are not errors and are not passed to `convert_cbr`. Each `.cbr` is `convert_cbr(path, keep_cbr_original=...)`. Cancel, per-file failure, `refresh_volume`, lock copy when the path changes, and `forget_volume` follow the save loop. Convert does not call `write_poster`.

## Rescan and startup

`POST /api/jobs/scan` and the startup scan call `scan(db_path, cache_dir, roots, cancel=...)`. `roots` is the in-memory `library_roots` copied when the job starts. The shell serializes `ScanResult` to one stable job-result object with exactly `written`, `unchanged`, `failed`, `deleted`, `skipped`, `incomplete`, and `cancelled`. The six path collections are JSON arrays and `cancelled` is a boolean. `skipped` contains roots that were not existing directories; `incomplete` contains roots whose walk could not list every directory. Neither Python nor TypeScript uses a combined `skipped_or_incomplete` field. When that result says the scan was cancelled, the job raises `JobCancelled` with the same serialized result. Otherwise it returns the result. A raised `LibraryIndexError` fails the job. Rows committed before a cancel stay, as the index specification already requires.

When the result names a skipped root, the inspector shows `{path} was skipped.` When it names an incomplete root, the inspector shows `{path} was not fully scanned.` These lines sit with the other inspector errors.

`__main__` does this in order:

1. Resolve paths.
2. Load config. A missing file stays missing.
3. Create the app and bind `127.0.0.1` on an ephemeral port.
4. If `library_roots` is non-empty, enqueue `scan`, retain that job id as the startup job, and do not wait for it. An empty list does not enqueue a scan and leaves the startup job null.
5. Open the window at the API origin. The window title is `Manga Tagger`. The default size is 1280 by 800.
6. When the window closes, shut the runner down and close the server.

`GET /api/library` remains callable as soon as the server is bound. The startup scan is not part of that request.

## Header and settings

Keyboard activation of header actions and dialog dismissal is defined in [09-keyboard-shortcuts.md](09-keyboard-shortcuts.md). A shortcut calls the same client function as its matching control, so job, selection, and dialog guards stay identical.

Leading to trailing, the header contains: the product brand (mini SVG and the wordmark `Manga Tagger` at the leading edge), then the provider select, Scrape (`ScanSearch`), Save (`Save`), Rename file(s) (`Pencil`), Convert CBR (`FileArchive`), Scan library (`RefreshCw`), the list and grid switch, then Settings (`Settings`), and Close (`X`) at the trailing edge. The brand, the centered action cluster, and the trailing utilities are the three header zones in the UI specification. The view switch and theme menu are the controls in the UI specification. The controls this specification adds are quiet header icon buttons with those accessible names, except the provider select, which is the select component. Close sits at the trailing edge. It calls `POST /api/window/close`, which destroys the pywebview window. That ends the process the same way the window chrome close does. No closer returns 503.

Choosing a theme calls `PUT /api/config` with that `theme` value. On success the class updates from the UI specification's `resolveDark`. That change does not rescan. A failed write leaves the previous theme in memory and does not change the class.

A place row uses Lucide `Folder`.

The first sidebar row is Add folder. It calls `POST /api/dialogs/folder`. A cancelled dialog does nothing. A returned path is sent to `POST /api/library/roots`. That route calls `accept_root_paths`. Relative paths, files, and paths that are not directories are dropped. A directory already in `library_roots` is not added again. The current roots stay. When `added` is non-empty, the route writes `library_roots` and enqueues one scan. When `added` is empty, it does not write and does not enqueue. A job that is queued or running makes a request that would add a root return 409 `JobBusyError` and write nothing. The client stores the returned config. When `added` is non-empty, the response includes the scan job and the client watches it the same way a Rescan does, so the shelf refreshes when the scan finishes. When `added` is empty, `job` is null. A path that was not a directory shows `Drop a folder.` A 409 or 503 shows `error_message` under the button.

Right-clicking a place row opens a context menu at the pointer without changing the selected place. Its first action is **Remove folder**. Choosing it appends that place's absolute path to `excluded_folders` through `PUT /api/config`; the server normalizes and deduplicates the list, saves it, and returns the scan job caused by the exclusion change. The client stores the returned config and watches that exact job, so the place and every descendant place disappear when the library refreshes. The action is disabled while a job is active. An API failure leaves the menu closed and shows its message in the sidebar. Unsaved metadata uses the same Save / Don't save / Cancel or auto-save guard as place navigation before the exclusion is written.

Dropping a folder on the sidebar does not call into Python from the client. `window.py` reads the native drop on `#places` and dispatches a `folders-dropped` window event whose `detail.paths` are absolute paths. The client posts those paths to `POST /api/library/roots`.

Settings is a dialog with General, Library, Archives, Scrapers, and Cache tabs. It edits `theme`, `animate_interface` (General, with live preview and rollback on dismissal), library roots, excluded folders, and `scan_subfolders` (Library), `title_languages` as comma-separated codes in order (General), `keep_cbr_original` as a checkbox labeled `Keep the original CBR` on Archives, `write_poster_on_save` as a checkbox labeled `Write poster on save` on Archives, `auto_save_metadata_on_switch` as a checkbox labeled `Auto-save metadata on switch` on Archives, the Comic Vine key, the Nautiljon base URL, the Nautiljon API key, and `enabled_providers`. The Library tab puts `Include subfolders automatically` first. Roots and exclusions are separate ordered folder lists: each row shows its absolute path and a trailing Remove button, and each list has an icon-only add-folder button that calls `POST /api/dialogs/folder`. Cancelling the native picker does nothing; choosing a path appends it to that draft list unless it is already present. Removing a row only changes the draft. Add and Remove do not write config or start a scan. Dismiss writes nothing. A successful Save calls `PUT /api/config` with the complete draft lists. The client includes each library-discovery field only when its value differs from the config used to open the dialog. It stores `response.config` and watches `response.job` directly when non-null. Consequently a theme, animation, archive, language, or provider-credential change remains saveable while another job is active, and unchanged discovery settings never trigger a scan.

Settings also has a Cache tab. Its `Clear cache` action calls
`POST /api/cache/thumbnails/clear` immediately and independently of Save or
Cancel. It does not write draft settings, close the dialog, enqueue a job, or
require confirmation. While the request is pending the action is disabled and
reads `Clearing…`. Success reports `Cache is already empty.` when no files were
removed, or `Cleared N cached thumbnail(s).` with normal singular agreement.
Failure leaves the dialog open and shows the API error. After success, the
client increments a session-only thumbnail revision and combines it with the
existing per-cover revision in every list and grid thumbnail URL. This bypasses
an already cached HTTP response and regenerates visible thumbnails on demand.

Per-file save, rename, and convert errors, and scan-root lines, are listed at the top of the inspector, above the form. Search and load status (match count, no matches, provider errors) is toast-only and is not repeated in the inspector. Scrape opens the Matches dialog (searching, then rows when any); match rows are not listed in the inspector. The toast for every finished job is the short summary in the jobs client section.

## Errors

| Exception | When |
| --- | --- |
| `ConfigError` | The TOML file cannot be parsed, or a `PUT` value has the wrong JSON type. A failed save does not replace memory |
| `ShellError` | A relative archive path, a bad page index, or a `one` save whose path count is not 1. Nothing is read or written |
| `OutsideLibraryError` | A resolved path is outside every current library root. Nothing is read or written |
| `JobNotFoundError` | `GET` or cancel names an id this process did not start |
| `JobBusyError` | `start` while a job is `queued` or `running`, including a `PUT` whose normalized roots changed and would enqueue a scan and a `POST /api/library/roots` that would add a root. Nothing is enqueued |
| `JobCancelled` | The job saw cancel before the next file, poster, or provider request. Partial entries stay on the job |
| `NoThumbnailError` | `thumbnail_for` returns no path |
| `LibraryIndexError` | The thumbnail cache cannot be cleared. The API reports the filesystem error and does not report success |
| `BatchFieldError` | A save patch contains a key the mode does not allow. Nothing is written |

`OutsideLibraryError` subclasses `ShellError`. `JobNotFoundError` and `ConfigError` do not. Archive and provider exceptions pass through the job as `failed`, except `ProviderCancelledError`, which is `cancelled`.

## Configuration

This specification reads and writes `excluded_folders` and `scan_subfolders` from [00-project-overview.md](00-project-overview.md), in addition to the existing keys.

It is the only reader and writer of `library_roots`, `excluded_folders`, `scan_subfolders`, `keep_cbr_original`, `write_poster_on_save`, `auto_save_metadata_on_switch`, `comicvine_api_key`, `nautiljon_base_url`, `nautiljon_api_key`, and `title_languages` from [00-project-overview.md](00-project-overview.md), and of `theme` and `animate_interface` from [05-ui-design.md](05-ui-design.md). Defaults stay those documents' defaults. View mode, the selected place, the provider choice, and the rename template are not keys. The HTTP port is not a key. The `httpx` timeout of 15 seconds is not a key. The job poll interval of 500 milliseconds is not a key.

## Testing

Tests are hermetic. They use temporary config, index, library, and UI paths. They do not open pywebview, do not use the network, do not call `time.sleep`, and do not read the developer's config, index, or library. They do not open `src/Claymore/`. Provider calls are the real `search` and `load` with `httpx.MockTransport`, or fakes passed into `create_app`. Archive and index behavior is covered by their own specifications. Shell tests replace those services and assert which ones ran.

The first API compatibility check is a minimal `TestClient` smoke test that
creates the app, enters the client context, and reads `/api/config`. It runs as
part of the complete suite on every supported Python minor. This deliberately
exercises the dependency boundary that can otherwise hang before an endpoint
assertion is reached.

Omarchy palette tests read only temporary `colors.toml` fixtures. API tests inject the system-theme reader and cover a complete palette, null fallback, and the no-store response without reading desktop state.

Importing `manga_tagger.config`, `manga_tagger.shell`, `manga_tagger.jobs`, or `manga_tagger.api` does not import pywebview.

On Linux, a runtime dependency test imports `gi`, requires `Gtk` 3.0 and
`WebKit2` 4.1, and imports both repositories. It does not create a window or
connect to a display. CI installs the matching distribution development
packages before the locked Python environment.

Cover at least:

- `animate_interface` defaults to false; invalid stored types fall back to false. GET exposes it, PUT accepts only booleans, omitted keys stay unchanged, and TOML round trips preserve it and unknown keys. Preview alone never writes configuration.
- Clearing a missing or populated thumbnail cache returns the removal count through the injected cache service, does not create a job or change config/index data, and returns a structured `LibraryIndexError` response when clearing fails.

- `load_config` on a missing path returns the known-key defaults and does not create the file. Relative `library_roots` and `excluded_folders` entries are absent from the result and the file bytes are unchanged. An unknown key is still present after a `PUT` that changes `theme`. Invalid TOML raises `ConfigError` and the message includes the path. Non-boolean `scan_subfolders` and `auto_save_metadata_on_switch` values on load become `true` and `false` respectively. A `PUT` of a non-boolean for either key is `400`.
- `app_paths("linux", {}, home)` uses `home/.config`, `home/.local/share`, and `home/.cache`. A set absolute `XDG_CONFIG_HOME` replaces only the config root. A relative `XDG_DATA_HOME` is ignored. `darwin` and `win32` use their table, including the `APPDATA` fallback under `home`.
- Two volumes in `/books/Claymore` and one in `/books/Other/Claymore` produce two places. The colliding labels are `books / Claymore` and `Other / Claymore`. `/books/Claymore/extra/v01.cbz` is a place `/books/Claymore/extra` and is not listed for `/books/Claymore`. A volume directly in `/books` makes `/books` a place. Empty roots return no volumes and do not delete a row that is already in the index. `volumes_for_shelf` with `null` returns every row ordered by `name`. A missing place selection stays `null` after a library refresh; a place that left the list becomes `null`.
- Place-click transitions select a different place, toggle the selected place to `null` when clicked again, and return `null` for a sidebar-background click.
- Right-clicking a place opens its context menu without selecting it. Remove folder adds the place path once to `excluded_folders`, watches the returned scan, respects the unsaved-form guard, is disabled during another job, and reports a failed request in the sidebar.
- `selection_after_filter` drops a path that left `visible`. Hiding the anchor assigns the anchor to the first remaining selected path.
- `select_plain`, `select_range`, and `select_toggle` follow the selection section, including a range that keeps the anchor and a toggle that removes it.
- `switchGuard` returns `proceed` when the form is null or no field is dirty, `confirm` when dirty and `auto_save_metadata_on_switch` is false, and `autosave` when dirty and that setting is true.
- Save settlement tests cover a one-file archive-write failure, a partial multi-file archive-write failure, cancellation after an earlier success, a successful unchanged save with no entries, and a poster or index-refresh error after a successful metadata write. The first three preserve the dirty form and block pending navigation. The last two clear the draft and allow pending navigation.
- `form_from_volumes` on one row includes `Number` as `{ "value", "dirty", "locked" }` with `dirty` false, and omits `Pages`. When that row's `locked_fields` contains `Series`, that field's `locked` is true. When that row's `page_count` is blank and `archive_page_count` is `42`, `PageCount` is `{ "value": "42", "dirty": false, "locked": false }`. When `page_count` is `10`, `PageCount` stays `10`. On two rows it includes only `SHARED_FIELDS`, including `AgeRating` and `Manga`, marks a differing `Series` mixed, shows a shared `Publisher`, sets every `dirty` flag false, and sets a shared field `locked` true only when every row locks that field.
- `fieldLabel` maps each `FORM_FIELDS` key to its caption: `Number` to `Issue`, `Count` to `Volumes`, `PageCount` to `Page count`, `LanguageISO` to `Language`, `AgeRating` to `Age rating`, `CommunityRating` to `Community rating`, and `CoverArtist` to `Cover artist`.
- `mangaLabel` maps Manga tokens to captions: `YesAndRightToLeft` to `Yes (right to left)`, `YesAndLeftToRight` to `Yes (left to right)`, `Yes` and `No` unchanged, blank to blank, and an unknown token to itself.
- `merge_load_patch` for `one` applies `Number`, sets that field `dirty`, and leaves a form field the patch omits. A patch value that equals the current value leaves that field's `dirty` flag unchanged. A locked field is left unchanged even when the patch differs. For `many` it applies `Series` and `Manga`, sets those fields `dirty`, ignores `Number` and `Title`, and leaves a shared field unchanged when the patch equals its current non-mixed value or the field is locked.
- `POST /api/field-locks` persists `locked_fields` on each path and returns the updated rows. It does not enqueue a job and does not call `save_comic_info`.
- `GET /api/library` calls `list_volumes` and does not call `scan`.
- `PUT /api/config` with omitted or unchanged normalized discovery settings saves unrelated settings without scanning, including while another job is active. Changed roots, exclusions, or subfolder behavior each save and return the exact scan job when idle. A discovery change while busy returns 409 and writes none of its fields. A very fast inline scan is returned in its terminal state.
- `GET /api/jobs/startup` returns null when startup had no roots, and returns the retained startup scan after enqueue and after terminal completion. Client tests cover settling that scan exactly once whether the first observation is queued, running, or already terminal.
- A shared scan-result contract test runs a real scan with one missing root and one unreadable root through the job endpoint, then passes that same JSON shape to the TypeScript inspector formatter. It asserts the separate `skipped` and `incomplete` keys and their distinct sentences.
- The shared app-contract fixture is checked by Python and TypeScript for ordered form fields, ordered shared fields, field-to-column mappings, provider ids, API job/result keys, and lockable fields. Both sides also build one- and many-volume forms whose keys match the fixture.
- A locked install and the full Python suite pass on CPython 3.12 and 3.13;
  the minimal `TestClient` smoke test completes and returns the config payload
  on both.
- On Linux, the locked environment imports `gi.repository.Gtk` 3.0 and
  `gi.repository.WebKit2` 4.1 without using the system Python's site-packages.
- A `one` save with a dirty `Number` calls `save_comic_info` with `write_number` true and that value. A `one` save with no dirty fields and a filename stem `Claymore v02` whose stored `Number` is `""` calls `save_comic_info` with `Number` `2`. A `one` save with no dirty fields, a locked `Number`, and a filename that would otherwise fill `Number` does not add `Number`. A `one` save with no dirty fields, a stored `Number` that already matches the filename, a blank `page_count`, and `archive_page_count` `42` calls `save_comic_info` with `PageCount` `42`. A `one` save with a locked `PageCount` and a blank ComicInfo page count does not add `PageCount`. A `one` save with no dirty fields, a matching `Number`, and a non-blank `page_count` does not call `save_comic_info`. A dirty `PageCount` of `""` is written as `""` and does not get replaced by `archive_page_count`. A `many` save calls `save_comic_info` once per path that needs a write, with the dirty shared fields and that file's `Number` from its filename, and does not call `save_many`. A shared `Series` the user did not edit is absent. A file whose shared patch is empty and whose `Number` already matches the filename is not passed to `save_comic_info` when its `page_count` is also already set. A `many` patch that contains `Title` raises `BatchFieldError` and does not call `save_comic_info`. When `write_poster_on_save` is true, a successful save calls `write_poster` on the output path. When it is false, a successful save does not call `write_poster`.
- A save cancel flag that becomes true after the first file leaves the second file's service uncalled. The first file's `refresh_volume` has run. The job state is `cancelled`.
- `search` and `load` jobs call no archive write and no `scan`. A load job for `many` returns a form without `Number`.
- Comic Vine with `comicvine_api_key` `""` fails the search job as `ProviderUnavailableError`. The mock transport sees no request. The message says the Comic Vine API key is not set.
- Nautiljon with `nautiljon_base_url` `""` or `nautiljon_api_key` `""` fails the search job as `ProviderUnavailableError`. The mock transport sees no request. The message names the missing setting.
- `GET /api/page` calls the combined page read once for the requested index and does not list separately or read another index. Instrumented requests open one CBZ central directory or invoke CBR `lsar` once, and read or extract only the selected member. A path outside the roots calls neither the page read nor `save_comic_info`.
- `GET /api/thumbnail` returns `image/jpeg` with `Cache-Control: private, max-age=3600` and an `ETag` from the cached JPEG filename stem when `thumbnail_for` returns a path. A miss is 404 `NoThumbnailError`.
- A rename preview calls `plan_rename` and does not call `rename_in_directory`. Preview and rename pass the selected paths through; one selected file and several selected files exclude unselected siblings, while empty or omitted paths target all direct archives. Invalid selected paths are rejected before reads or enqueueing. A rename job calls `rename_in_directory` on the place and, when `write_poster_on_save` is true, calls `write_poster` on each success path. When it is false, the rename job does not call `write_poster`. A convert job skips a `.cbz` and calls `convert_cbr` for a `.cbr`. It does not call `write_poster`.
- `serve` binds `127.0.0.1`, returns a non-zero port, and `close()` stops it. A missing UI directory makes `GET /` return the plain sentence `UI build is missing.` and leaves `GET /api/library` working.
- Cancel of a queued job does not call its function. `start` while a job is `queued` or `running` raises `JobBusyError` and does not call the new function. The inline runner does not sleep. A running save reports `completed` and `total`.
- `accept_root_paths` keeps a directory, ignores a file and a relative path, and does not duplicate a root. `POST /api/dialogs/folder` returns the injected path, and null when the picker cancels. With no picker the route is 503. `POST /api/library/roots` writes a new directory and enqueues one scan. The same route while a job is queued returns 409 and does not write. `POST /api/window/close` calls the injected destroyer and returns 204. With no destroyer the route is 503.

## Acceptance criteria

- Saving Animate interface persists it across restarts. Cancel/Close restores the saved preference; a failed save leaves Settings open with its preview. The UI design specification owns motion behavior.
- One process loads config, binds `127.0.0.1` on an ephemeral port, and opens the pywebview window on that origin. The port is not config. Tests do not open the window.
- The shelf is `GET /api/library`. That response does not scan, open an archive, or build a thumbnail. A missing config file is the defaults, is not created, and paints no volumes.
- List and grid thumbs use `GET /api/thumbnail` as the `img` `src` with lazy/async decode; the client does not open a blob URL per row. A successful thumbnail response is cacheable (`Cache-Control` and `ETag` from the cached JPEG identity).
- A place is a directory that directly contains indexed volumes. With no place selected, the main pane lists every volume under the current roots, ordered by name and grouped by series alphabetically. With a place selected, it lists that place's volumes only. Clicking the selected place again or clicking the sidebar outside a place row clears the place filter and returns to the whole library; the latter does nothing when no place is selected. List and grid both group by series with a muted header above shared volumes; a list row shows the filename only with a tree marker, and a grid cell shows the cover and filename with no tree marker. Nested volumes are a different place. There is no library filter field in the header.
- One selected volume shows that volume's form and one preview page. Several selected volumes show one shared form for `Series`, `Count`, `Publisher`, `LanguageISO`, `AgeRating`, `Genre`, `Manga`, `Writer`, `Penciller`, `Inker`, and `CoverArtist`. Field captions are the readable names (`Issue`, `Volumes`, `Language`, `Cover artist`, and the rest), not the ComicInfo element names. A field is written only after the user edits it or a load sets it, except each file's `Number`, which a save takes from that file's filename when the stored number differs (and `Volume` mirrors that `Number`), and each file's `PageCount`, which a save takes from `archive_page_count` when ComicInfo `page_count` is blank. The form shows that archive count in `Page count` when ComicInfo left it blank. An override or a value already in ComicInfo is left alone. An unchanged save does not rewrite the archive. The preview follows the anchor. Leaving a dirty form by changing issue or place asks Save / Don't save / Cancel when `auto_save_metadata_on_switch` is false, and silently saves then navigates when it is true. A clean form navigates immediately.
- Search and load fill the form and do not write an archive. Scrape opens the centered Matches dialog in a searching state; results replace that body with a large cover, a Series/Year/Issues/(Publisher or Author) table, and a summary pane; the first row is highlighted; OK or Enter starts load (by preferred number when one volume is selected, or series-only batch fill when several are selected); Select Issue appears only for a single selection and then Select Issue or double-click starts the Issues job; with several selected, double-click acts like OK; dismiss while searching cancels the job; an empty or failed search closes the dialog; and a successful load clears the lists so the dialogs close. An empty Issues list toasts `No issues available.` A load marks the fields it sets dirty, including `Manga` on a shared form. A blank Comic Vine key, or a blank Nautiljon base URL or API key, fails before a request.
- Save writes through `save_comic_info` and does not call `save_many`. One volume writes dirty fields, `Number` from the filename when that field was not edited and the stored value differs (`Volume` mirrors `Number`), and `PageCount` from `archive_page_count` when that field was not in the patch and ComicInfo left it blank. Several volumes write the dirty shared fields, including `Manga` and `Count`, each file's `Number` from its filename, and each file's blank `PageCount` from its archive count. Cancel stops before the next file. A failed file does not stop the rest, and files already written stay written. An archive-write failure or cancellation preserves the dirty draft after the library refetch, including on an ordinary batch save, and a pending switch does not navigate. An unchanged save may navigate. Poster and index-refresh errors remain visible but may navigate because metadata is already safely written. When `write_poster_on_save` is true, a successful save writes the sibling poster.
- Rename shows and applies only selected files, or all direct archives in the selected place when none are selected, then runs with the offered template `{Series} v{Number:02}`, moves an existing sibling poster with the archive, and when `write_poster_on_save` is true calls `write_poster` on each success. Convert asks before deleting `.cbr` files when `keep_cbr_original` is false, turns selected `.cbr` files into `.cbz`, and skips `.cbz`. A path outside the library is rejected before any read or write.
- Scrapes, saves, converts, and rescans are jobs on one worker. A new job is refused while one is queued or running. No job adds a name, progress text, or Cancel button to the header. Search and Issues progress stay in their dialogs and can be cancelled by dismissing them. Save, Rename, Cover, Convert, and Scan outcomes are reported by toasts. A finished scrape, issues, load, save, rename, convert, or scan that succeeded or failed shows one toast summary when the toast table says so; cancelled jobs do not. A finished scan names a skipped or incomplete root in the inspector. Closing the window asks the worker to stop and does not leave a truncated archive from this process killing a write.
- Every scan job result uses `written`, `unchanged`, `failed`, `deleted`, `skipped`, `incomplete`, and `cancelled`. A missing root appears only in `skipped` and renders `{path} was skipped.`; a root that could not be fully walked appears only in `incomplete` and renders `{path} was not fully scanned.`
- The startup scan is enqueued only after the server is bound, and only when `library_roots` is non-empty. Its exact job remains available from `GET /api/jobs/startup` after completion, so the client refreshes the shelf even when the scan finishes before its first poll. The first library response does not wait for it.
- Add folder asks for one directory and appends it to `library_roots`, then scans. A drop on the sidebar does the same. Existing roots stay. Settings can still replace the list.
- Remove folder from a place's right-click menu appends that path to `excluded_folders` and scans; it does not delete the directory or its archives from disk.
- Settings omits unchanged library discovery fields and the API independently compares their normalized values. Unrelated settings save during another job. A roots, exclusions, or subfolder-policy change returns its exact scan job, including an empty-root or already-finished scan, and the client watches that id without consulting `/api/jobs/current`.
- Settings Cache clears generated thumbnails immediately without saving or discarding draft settings. A successful clear forces list and grid thumbnails onto a new revision URL; failures remain visible in the open dialog.
- Every duplicated Python/browser contract is either identified as intentional boundary code above or guarded by the shared app-contract fixture. Provider ids have one Python source of truth, and the shell has no unused thumbnail-bytes helper.
- The supported interpreter range is `>=3.12,<3.14`; `uv.lock` is committed,
  and CI verifies the complete Python suite on every supported minor from that
  lockfile.
- A normal locked Linux install includes pywebview's GTK binding in the
  application environment; with the documented system libraries installed,
  startup does not fall through to a missing Qt backend.

## Open questions

All resolved. Recorded here so they are not re-opened.

- **What is a place?** The directory that directly contains indexed volumes. The sidebar lists those folders under the caption My library. A library root is a place only when a volume sits directly in it. No place selected shows the whole library. Rename applies to the selected place.
- **How does the window call the API?** `fetch` on the API origin. The client does not call a pywebview JavaScript API. `window.py` may dispatch `folders-dropped` after a native drop. The client posts those paths with `fetch`.
- **How does the UI hear about background work?** It polls the job every 500 milliseconds. A second job is refused while one is queued or running. Tests use an inline runner and do not sleep.
- **Where is the page preview?** The inspector image is one page of the anchor volume. Thumbnails are a separate request.
- **Is there a library filter in the header?** No. Series count stays small enough that the shelf lists every volume for the current place. The provider select and Scrape search catalogs, not the local shelf.
