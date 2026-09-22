---
description: One desktop process serves a localhost API and a pywebview window, and wires places, selection, scrape, save, rename, and convert to the archive, index, and provider modules.
status: active
---

# Application shell

This specification owns the desktop process, the TOML config file, the local API, background jobs, and what selection, filtering, scrape, save, rename, and convert do. It implements performance rules 1, 5, 7, and 8 from [00-project-overview.md](00-project-overview.md): a page read is one archive member, the first paint is the index, scrape and save and convert and rescan are cancellable background work, and a network result never writes an archive.

The Svelte client that performs these actions lives in `ui/` and uses the layout and components from [05-ui-design.md](05-ui-design.md). This specification places actions in that header, places sidebar, volume pane, and inspector. It does not define color, type, or component styling.

Archive bytes and ComicInfo stay in [01-archives-and-comicinfo.md](01-archives-and-comicinfo.md). The SQLite index, scan, and thumbnails stay in [02-library-index.md](02-library-index.md). Catalog HTTP, the query, and the form patch stay in [03-metadata-providers.md](03-metadata-providers.md).

## Modules

| Module | Role |
| --- | --- |
| `src/manga_tagger/config.py` | Resolve paths and read or write the TOML file. The only module that touches that file |
| `src/manga_tagger/shell.py` | Pure place, filter, selection, and form functions, plus the job bodies. No FastAPI and no pywebview |
| `src/manga_tagger/jobs.py` | One worker, first in first out. No FastAPI and no pywebview |
| `src/manga_tagger/api/` | FastAPI app, Pydantic models, and HTTP errors. Routers validate input, call `shell` or `jobs`, and return models. They do not open archives, query SQLite, or call catalogs |
| `src/manga_tagger/window.py` | The only module that imports pywebview |
| `src/manga_tagger/__main__.py` | Load config, bind the server, enqueue the startup scan, open the window, then shut down |
| `ui/` | The client. `fetch` on the API origin. It does not call a pywebview JavaScript API |

`config.py`, `shell.py`, `jobs.py`, and `api/` do not import pywebview. Tests do not import `window.py` or `__main__.py`.

When this specification is implemented, `pyproject.toml` gains `fastapi`, `uvicorn`, `pywebview`, and `tomli-w`. `httpx` is the client library named by the provider specification. The server is uvicorn. There is no Flask, no Electron, and no second HTTP framework.

## Paths and config

`app_paths(platform, env, home)` returns the config file, the index file, and the thumbnail directory. `platform` is `linux`, `darwin`, or `win32`. `__main__` passes `sys.platform`. The function does not read the process environment itself. A blank environment value is unset. A relative `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `APPDATA`, or `LOCALAPPDATA` is ignored.

| Platform | Config | Index | Thumbnail cache |
| --- | --- | --- | --- |
| `linux`, and any other value | `$XDG_CONFIG_HOME/manga-tagger/config.toml`, or `home/.config/manga-tagger/config.toml` | `$XDG_DATA_HOME/manga-tagger/index.db`, or `home/.local/share/manga-tagger/index.db` | `$XDG_CACHE_HOME/manga-tagger/covers`, or `home/.cache/manga-tagger/covers` |
| `darwin` | `home/Library/Application Support/manga-tagger/config.toml` | `home/Library/Application Support/manga-tagger/index.db` | `home/Library/Caches/manga-tagger/covers` |
| `win32` | `%APPDATA%/manga-tagger/config.toml`, or `home/AppData/Roaming/manga-tagger/config.toml` | the same directory's `index.db` | `%LOCALAPPDATA%/manga-tagger/covers`, or `home/AppData/Local/manga-tagger/covers` |

`load_config(path)` reads UTF-8 TOML with the standard-library `tomllib`. A missing file returns the defaults below and does not create the file. Invalid TOML raises `ConfigError`. The message includes the path and says the TOML could not be parsed. Startup then exits with status 1 and does not open the window.

`save_config(path, config)` creates the parent directory and writes UTF-8 TOML with `tomli-w`. Unknown keys from the last successful load are written back. Comments are not preserved. A missing file's first save writes the five known keys.

The process keeps the loaded config in memory. `GET /api/config` returns that memory. `PUT /api/config` writes the file and, only after the write succeeds, replaces memory. A failed write leaves memory and the previous file unchanged and does not enqueue a scan.

A TOML value of the wrong type falls back on load. The file is not rewritten just because it was loaded.

| Key | Load fallback | PUT |
| --- | --- | --- |
| `library_roots` | Not a list becomes `[]`. Non-strings are dropped. Relative paths are dropped. Duplicates keep the first. Stored paths are `resolve(strict=False)` | Same dropping rules. A provided non-list is `400` `ConfigError` and writes nothing |
| `keep_cbr_original` | Not a boolean becomes `false` | Not a boolean is `400` `ConfigError` |
| `comicvine_api_key` | Not a string becomes `""` | Not a string is `400` `ConfigError` |
| `title_languages` | Not a list becomes `["fr", "en"]`. Non-strings are dropped. An empty list stays `[]` | Not a list is `400` `ConfigError`. Non-strings are dropped |
| `theme` | Not a string becomes `system`. Any string is kept, including one the UI treats as `system` | `system`, `light`, or `dark` are stored. Any other value is stored as `system` |

`PUT` replaces `library_roots` wholesale. Omitted keys stay. When the body includes `library_roots`, a scan is enqueued after the successful write, including when the stored list is empty. If a job is already `queued` or `running`, that `PUT` returns 409 `JobBusyError` and does not write. Other keys do not enqueue a scan and are accepted during a job.

## Places

A place is the parent directory of an indexed volume: the folder that directly contains that archive. Places come from the volume rows. There is no places table.

`volumes_for_roots(rows, roots)` keeps a row when its resolved `path` equals a root or is inside a root. The check uses a path separator, so `/books` does not match `/books-extra`. An empty `roots` list keeps nothing. This filter does not delete rows and does not scan. A missing config therefore paints an empty shelf even when an older index file still has rows.

`places_from_volumes(rows)` builds one place per parent directory.

- The place path is that parent, with trailing separators removed.
- Order is the place path, ascending, compared by Unicode code point.
- The label is the directory name. When two or more places share a directory name, each of those labels is `parent / name`, where `parent` is the parent directory's name. When those labels still collide, the label is the full place path.
- A library root is a place only when a volume's parent is the root. A volume in a child folder belongs to that child, not to the root.

`volumes_in_place(rows, place_path)` keeps rows whose parent equals `place_path`. A nested volume is not included. Order is the `name` column, ascending, by Unicode code point. `failed` rows are included.

The selected place is session state. It is not a config key. When the library response arrives and nothing is selected, the client selects the first place. When the selected place is absent from a later response, the client selects the first remaining place, or nothing if there are no places. Changing place clears the selection.

The main pane lists `volumes_in_place` for the selected place. An empty library, a selected place with no rows, or a filter with no hits shows the sentence `No volumes yet.`

A list row's primary label is `name`. Its secondary text is `series` when that value is non-blank after trim, and is omitted otherwise. A grid cell's label is `name`.

`GET /api/library` calls `list_volumes`, then `volumes_for_roots` and `places_from_volumes`. The response `volumes` are every row kept for the current roots, not only the selected place. The client applies `volumes_in_place` locally. The request does not call `scan`, does not open an archive, and does not build a thumbnail.

## Filter

`filter_volumes(rows, query)` returns `rows` when `query` is blank after trim. Otherwise it keeps a row when Unicode casefold of `series`, `title`, or `name` contains the casefold of the trimmed query. The header search field runs this filter on the selected place's rows. It does not call a provider, does not scan, and does not change the selection's place.

A selected path that the filter hides is removed from the selection. If the anchor was hidden, the anchor becomes the first remaining selected path in list order, or nothing.

## Selection

The selection is session state on the client. `shell.py` is the contract. The client uses the same transitions. Paths are stored in the current visible list order.

`select_plain(visible, path)` selects only `path` and makes it the anchor.

`select_range(visible, selection, path)` selects the inclusive range from the anchor to `path` in `visible` order. The anchor does not move. If there is no anchor, or the anchor is not in `visible`, it behaves as `select_plain`.

`select_toggle(visible, selection, path)` adds `path` when it was not selected and removes it when it was. Adding the first selected path makes it the anchor. Adding another path leaves the anchor. Removing the anchor makes the anchor the first remaining selected path in `visible` order, or nothing when the selection is empty.

A plain click calls `select_plain`. Shift-click calls `select_range`. Ctrl-click calls `select_toggle`. On macOS, Command-click is the same toggle. The preview is always the anchor.

## Form

`FORM_FIELDS` is every owned ComicInfo text element except `Pages`, in this order: `Title`, `Series`, `Number`, `Volume`, `Publisher`, `PageCount`, `LanguageISO`, `AgeRating`, `Manga`, `Genre`, `Summary`, `Web`, `CommunityRating`, `Notes`, `Year`, `Month`, `Day`, `Writer`, `Penciller`, `Inker`, `CoverArtist`.

`SHARED_FIELDS` is `Series`, `Publisher`, `LanguageISO`, `Genre`, `Manga`, `Writer`, `Penciller`, `Inker`, `CoverArtist`.

Index columns map to those elements: `title`, `series`, `number`, `volume`, `publisher`, `page_count`, `language_iso`, `age_rating`, `manga`, `genre`, `summary`, `web`, `community_rating`, `notes`, `year`, `month`, `day`, `writer`, `penciller`, `inker`, `cover_artist`. A missing element is `""`.

`form_from_volumes(rows)` returns no form when `rows` is empty. One row returns `mode` `one` and a `values` object with every `FORM_FIELDS` key. Each field is `{ "value", "dirty" }`. `dirty` starts false. Several rows return `mode` `many` and only `SHARED_FIELDS`. Each shared field is `{ "value", "mixed", "dirty" }`. `dirty` starts false. When every selected row has the same text, `value` is that text and `mixed` is false. When they differ, `value` is `""` and `mixed` is true. Editing a field sets `dirty` to true and, on a shared field, `mixed` to false. `value` becomes what the user typed, including `""` when the user clears it.

No selection: the inspector has no form and no image. Save and scrape do nothing.

One volume: each field is a label and a control. `Summary` and `Notes` are a textarea with the text input's border, radius, background, and `text-sm`, at least four rows. `Manga` is a select whose options are `YesAndRightToLeft`, `Yes`, `No`, `YesAndLeftToRight`, a blank option, and the current token when it is not already in that list. Every other field is a text input.

Several volumes: the inspector shows only the shared fields, including `Manga`. A mixed field's placeholder is `Mixed`. A field that is not `dirty` is omitted from the save patch, whether it is mixed or the same on every row. An empty uniform value is not sent as `""`, so Save does not remove an element the user did not edit.

One volume uses the same dirty rule. The save patch is the fields whose `dirty` is true. A field the user did not edit is absent, not `""`.

The form is rebuilt from the index rows when the selection changes and when a save, rename, or convert refetch completes. A finished scan refetches the library and rebuilds the form only when no field is dirty. Dirty fields stay as the user left them.

## Preview

The inspector image is one page of the anchor. The client starts at `cover_index`, or at `0` when `cover_index` is null or outside the page list. Previous and next stay inside `0 .. archive_page_count - 1`. They are quiet icon buttons, Lucide `ChevronLeft` and `ChevronRight`, with accessible names `Previous page` and `Next page`. At the ends, the matching button is disabled. Changing the anchor resets the index to the new cover.

`GET /api/page` lists page names from the central directory, then reads that one index. The list reads no member bodies. The response body is that member's uncompressed bytes. `Content-Type` is `image/jpeg` for `jpg` and `jpeg`, `image/png` for `png`, `image/webp` for `webp`, and `image/gif` for `gif`, compared case-insensitively, otherwise `application/octet-stream`. A `failed` anchor, or a null or zero `archive_page_count`, shows `error_message` when the row has one, and requests no page.

List and grid thumbnails use `GET /api/thumbnail`, which calls `thumbnail_for` and returns that JPEG as `image/jpeg`. The list row uses the image when the response is a JPEG, and Lucide `Book` when it is not. A grid cell uses the thumbnail. A failed grid cell has no image and still shows its label. Thumbnail reads are not the preview page, and the preview does not write the thumbnail cache.

## Jobs

`JobRunner` runs one job at a time, in start order. It does not use a process pool. A job has `id`, `name`, `state`, `error_type`, `error_message`, `result`, `completed`, and `total`. Ids are decimal strings starting at `1`. States are `queued`, `running`, `succeeded`, `failed`, and `cancelled`. `error_type` and `error_message` are `""` unless the state is `failed`. `result` is null unless the job succeeded or was cancelled with a partial result. `completed` and `total` are integers. A queued job has `completed` 0.

`start(name, fn)` queues `fn` when no job is `queued` or `running`. Otherwise it raises `JobBusyError` and does not enqueue. The function receives `cancel`, a callable that returns true after a cancel request, and `progress(completed, total)`. `inline=True` runs the job to a terminal state on the caller thread before `start` returns. Tests use the inline runner. They do not call `time.sleep`.

Search and load set `total` to 1 and `completed` to 0 until the request finishes, then `completed` is 1. Save and convert set `total` to the path count and increment `completed` after each path, including a failure or a skip. Rename sets `total` to the number of archives directly in the place and increments `completed` after each planned file. Scan calls `progress(0, 0)` before the index scan and `progress(committed, committed)` when it returns. `committed` is the number of written, unchanged, and failed paths. The index scan has no per-candidate callback, so this job does not report candidates found so far.

`cancel(id)` on a queued job sets `cancelled` and does not call `fn`. On a running job it sets the flag and does not abort the thread. A provider request that has already started is not aborted. `get` of an unknown id raises `JobNotFoundError`. `current` is the running job, or the queued job when none is running, or null when none has been started. The busy rule means there is at most one of those.

`fn` returns a result for `succeeded`. `JobCancelled` and `ProviderCancelledError` become `cancelled`. `JobCancelled` may carry the partial result. Any other exception becomes `failed`, with `error_type` the exception class name and `error_message` the exception message.

`shutdown` cancels every queued job without running it, sets the cancel flag on the running job, and joins the worker. It does not kill the thread. Closing the window calls `shutdown`, then stops the server. The process exits 0.

Header text for a `queued` or `running` job is `Scan`, `Search`, `Load`, `Save`, `Rename`, or `Convert`. When `total` is greater than 0 the text is that name, a space, then `{completed}/{total}`, such as `Save 3/40`. The Cancel control is shown only then. Its accessible name is `Cancel`. Scrape, Save, Rename, Convert, and Rescan are disabled while `current` is `queued` or `running`.

## HTTP API

`serve(app)` binds `127.0.0.1` and port `0`, so the port is chosen by the operating system. The host is not configurable. `serve` returns the chosen port and a `close()` that stops the server. The UI origin is `http://127.0.0.1:{port}/`.

`create_app` takes the in-memory config, the index path, the thumbnail directory, the UI directory or null, an optional runner, optional service callables, an optional `pick_folder`, and an optional `destroy_window`. Omitted services are the archive, index, and provider operations this document names. The default runner is one worker thread. An omitted `pick_folder` makes `POST /api/dialogs/folder` return 503. An omitted `destroy_window` makes `POST /api/window/close` return 503.

JSON errors are `{ "error_type", "error_message" }`. Expected client errors are HTTP 400, including an archive exception raised by `GET /api/page` or `GET /api/thumbnail`. An unknown job id is HTTP 404. A thumbnail that `thumbnail_for` does not create is HTTP 404 with `error_type` `NoThumbnailError`.

Archive, page, thumbnail, save, rename, and convert paths must be absolute. A relative path is `ShellError` and does not touch the archive. After `resolve(strict=False)`, the path must be inside a current library root, using the same separator rule as places. Otherwise `OutsideLibraryError`, and nothing is read or written. `OutsideLibraryError` subclasses `ShellError`. Validation that fails this way does not enqueue a job.

| Method and path | Behavior |
| --- | --- |
| `GET /api/library` | `{ "places": [{ "path", "label" }], "volumes": [row] }`. Volume keys are the index columns. SQL NULL is JSON null. Does not scan |
| `GET /api/page?path=&index=` | One page. `index` is a non-negative integer. A missing or negative index is `ShellError` |
| `GET /api/thumbnail?path=` | The cached cover JPEG, building it on demand through `thumbnail_for` |
| `GET /api/config` | The five known keys |
| `PUT /api/config` | A partial object of those keys. Returns the full config. Roots in the body enqueue a scan after a successful write |
| `POST /api/dialogs/folder` | Calls the injected `pick_folder`. Returns `{ "path" }` or `{ "path": null }` when the dialog is cancelled. No picker is HTTP 503 |
| `POST /api/window/close` | Calls the injected `destroy_window`. Returns an empty 204. No closer is HTTP 503 |
| `POST /api/library/roots` | Body `{ "paths": [...] }`. Appends existing directories that are not already roots. Returns the full config, `added`, and the scan `job` when a root was added |
| `POST /api/jobs/scan` | Enqueues `scan` |
| `POST /api/jobs/search` | Body `{ "provider", "series", "filename_stem" }` |
| `POST /api/jobs/load` | Body `{ "provider", "match_id", "filename_stem", "mode", "form" }` |
| `POST /api/jobs/save` | Body `{ "paths", "patch", "mode" }` |
| `POST /api/jobs/rename` | Body `{ "directory", "template" }` |
| `POST /api/rename/preview` | Body `{ "directory", "template" }`. Returns `{ "entries": [{ "path", "output_path", "error_type", "error_message" }] }` from `plan_rename`. Does not rename. The same absolute-path and library-root checks as rename apply before `plan_rename` is called |
| `POST /api/jobs/convert` | Body `{ "paths" }` |
| `GET /api/jobs/current` | The running job, or the queued job, or JSON null |
| `GET /api/jobs/{id}` | That job |
| `POST /api/jobs/{id}/cancel` | Cancel that job. Returns the job |
| `GET /` | `ui/dist/index.html` when that directory was given and contains it. Otherwise HTTP 200, `text/plain; charset=utf-8`, body `UI build is missing.` |
| other non-API paths | A file inside `ui/dist` whose resolved path stays inside that directory. Anything else is 404, including a path that escapes the directory |

`/api` routes are matched before static files. A missing UI build does not disable `/api`.

Job JSON is `{ "id", "name", "state", "error_type", "error_message", "result", "completed", "total" }`. Start endpoints return that object. A start while a job is `queued` or `running` is HTTP 409 `JobBusyError` and does not enqueue.

The client polls `GET /api/jobs/current` from startup, and polls `GET /api/jobs/{id}` for a job it started, while the state is `queued` or `running`. The poll interval is 500 milliseconds. It is not a TOML key. Tests do not wait on it. When `scan`, `save`, `rename`, or `convert` reaches `succeeded`, `failed`, or `cancelled`, the client fetches the library once for that job id. `search` and `load` do not refetch the library. A search or load result is applied only when its id is the newest search or load the client started. While that load is `queued` or `running`, the form controls are disabled. While that save is `queued` or `running`, the form controls are disabled.

## Scrape

The provider select lists MangaDex (`mangadex`), AniList (`anilist`), MyAnimeList (`jikan`), and Comic Vine (`comicvine`). The choice is session state and defaults to `mangadex`. It is not a config key.

Scrape uses the anchor. It does nothing when there is no anchor. The request `series` is the form's `Series` when that control is non-blank and not mixed. Otherwise `series` is `""`. `filename_stem` is the anchor `name` with its extension removed. The job calls `build_query(series, filename_stem)` and then `search`. It passes `title_languages` and `comicvine_api_key` from config at the start of the job, the cancel callable, and an `httpx.Client` with a 15 second timeout. The client is closed when the job ends. The shell does not set `User-Agent` and does not retry.

The result is `{ "candidates": [{ "id", "title", "detail" }] }`. The inspector shows those rows above the form. A row shows `title`, and `detail` on a second muted line when `detail` is non-blank. Choosing a row starts `load` for that id. An empty list is success, not an error. The inspector shows `No matches.` and the form is unchanged.

`load` calls the provider `load` with the anchor `filename_stem` and the same config and client rules. The job then runs `merge_load_patch(form, patch, mode)`. For `one`, each patch key that is in `FORM_FIELDS` replaces that form value and sets `dirty` to true. Keys the patch omits stay, and their `dirty` flag stays as it was. For `many`, each patch key that is in `SHARED_FIELDS` sets that field's `value`, sets `mixed` to false, and sets `dirty` to true. `Manga` is one of those keys. Every other patch key is ignored, including `Title`, `Number`, `Summary`, `Web`, and dates. The result is `{ "form": { "mode", "values" } }`. The client replaces its form with that object when the selection is still the one it sent. No archive is written.

`ProviderUnavailableError`, `ProviderTimeoutError`, `ProviderRateLimitError`, and `ProviderResponseError` fail the job. `ProviderCancelledError` cancels it. The form is unchanged and the archive is unchanged. A new search clears the candidate list when it starts. A failed search clears candidates and shows `error_message` in the inspector. A failed load leaves the candidate list so another row can be chosen.

A blank Comic Vine key fails inside `search` or `load` with `ProviderUnavailableError` before a request. The shell does not replace that error.

## Save

Save does nothing when the selection is empty.

The patch for one volume is every `FORM_FIELDS` key whose `dirty` is true, excluding `Pages`. `""` removes that element. `mode` is `one` and `paths` has that one path. When `Number` is dirty, `write_number` is true and the patch uses the form value. When `Number` is not dirty, the shell parses that file's filename stem. If the parse returns a string and the form's `Number` value differs, the patch includes `Number` and `write_number` is true. If the parse returns `None`, or the form value already equals it, `Number` is omitted. An empty patch does not call `save_comic_info`. The job succeeds with `{ "entries": [] }`.

The shared patch for several volumes is the shared fields whose `dirty` is true, including a field the user cleared to `""` and a field a load just set. `Manga` follows that rule. Fields that are still not `dirty` are absent, not `""`. `mode` is `many`. For each path the shell copies that shared patch and, when `parse_number` of that file's stem returns a string different from the row's `number`, adds `Number`. `write_number` is true only when that file's patch includes `Number`. `Volume` is never added. The request body does not carry `Number`. The shell adds it. A file whose patch is empty is not passed to `save_comic_info` and is not an error. If every file is skipped, the job succeeds with `{ "entries": [] }`.

Before any write, a `one` save whose `paths` length is not 1, or whose patch contains a key outside `FORM_FIELDS`, raises `BatchFieldError` for a bad key and `ShellError` for the path count. A `many` save whose shared patch contains a key outside `SHARED_FIELDS` raises `BatchFieldError`. `Pages` is never a patch key. These failures write nothing and do not enqueue a job when the route can see them. The job repeats the key check so a direct call is just as strict. The per-file `Number` is added after that check.

The job then calls `save_comic_info` once per path that has a patch. It does not call `save_many`, because that function cannot check cancel between files. The shared keys are the `save_many` field set. `keep_cbr_original` is the config value copied when the job starts.

Cancel is checked before each file. A true flag raises `JobCancelled` with the entries so far. The current file is not interrupted. A file that raises records `{ "path", "error_type", "error_message" }` and the loop continues. A success records `{ "path", "output_path" }`. `output_path` is the `.cbz` path when a `.cbr` save converted it, otherwise the same path. After each success the job calls `write_poster` on `output_path`, then `refresh_volume` on `output_path` and, when `output_path` differs, `forget_volume` on the old path. A poster error does not undo the save. That entry keeps `output_path` and also has `error_type` and `error_message`.

The result is `{ "entries": [...] }` in request order. The job succeeds when the loop finishes, including when some entries have errors. Those errors are listed in the inspector as `{filename}: {error_message}`. The client updates a selected path to `output_path` when the entry succeeded, drops a path that failed and is no longer in the library, then rebuilds the form from the refetched rows.

## Rename

Rename is enabled when a place is selected, including when the volume selection is empty, and no job is `queued` or `running`. It renames every archive directly in that place, not only the selection. The dialog's text input starts as `{Series} v{Number:02}`. That string is not written to config. The dialog lists `plan_rename` before confirm by calling `POST /api/rename/preview`. Each success is `{old name} → {new name}`. Each failure is `{old name}: {error_message}`. Dismiss writes nothing. Confirm enqueues the job with that template.

The job checks cancel, then calls `rename_in_directory(directory, template)`. The directory is the selected place and must sit inside a library root. `rename_in_directory` has no cancel argument, so a call that has started runs until it returns. For each success the job calls `write_poster` on the new path, then `refresh_volume` on the new path and `forget_volume` on the old path when they differ. Cancel is checked between poster writes. A poster error does not undo the rename. That entry keeps `output_path` and also has `error_type` and `error_message`. A rename failure has `path`, `error_type`, and `error_message` and no `output_path`.

The place stays selected. The volume selection is cleared. The result entries follow the archives rename order.

## Convert

Convert is enabled when at least one selected file has extension `cbr`, compared case-insensitively, and no job is `queued` or `running`. When `keep_cbr_original` is false, confirm shows `Convert N CBR files to CBZ and delete the originals?`, where N is the number of selected `.cbr` files. Dismiss writes nothing. When `keep_cbr_original` is true, convert starts without that dialog. Selected `.cbz` files are entries `{ "path", "skipped": true }`. They are not errors and are not passed to `convert_cbr`. Each `.cbr` is `convert_cbr(path, keep_cbr_original=...)`. Cancel, per-file failure, `refresh_volume`, and `forget_volume` follow the save loop. Convert does not call `write_poster`.

## Rescan and startup

`POST /api/jobs/scan` and the startup scan call `scan(db_path, cache_dir, roots, cancel=...)`. `roots` is the in-memory `library_roots` copied when the job starts. The job result is the index scan result, unchanged. When that result says the scan was cancelled, the job raises `JobCancelled` with that result. Otherwise it returns the result. A raised `LibraryIndexError` fails the job. Rows committed before a cancel stay, as the index specification already requires.

When the result names a skipped root, the inspector shows `{path} was skipped.` When it names an incomplete root, the inspector shows `{path} was not fully scanned.` These lines sit with the other inspector errors.

`__main__` does this in order:

1. Resolve paths.
2. Load config. A missing file stays missing.
3. Create the app and bind `127.0.0.1` on an ephemeral port.
4. If `library_roots` is non-empty, enqueue `scan` and do not wait for it. An empty list does not enqueue a scan.
5. Open the window at the API origin. The window title is `Manga Tagger`. The default size is 1280 by 800.
6. When the window closes, shut the runner down and close the server.

`GET /api/library` remains callable as soon as the server is bound. The startup scan is not part of that request.

## Header and settings

Leading to trailing, the header contains: the filter field, the provider select, Scrape (`ScanSearch`), Save (`Save`), Rename (`Pencil`), Convert (`FileArchive`), Rescan (`RefreshCw`), the list and grid switch, the job name and Cancel (`X`) while a job is queued or running, the theme menu, Settings (`Settings`), and Close (`X`). The filter field, view switch, and theme menu are the controls in the UI specification. The controls this specification adds are quiet header icon buttons with those accessible names, except the provider select, which is the select component. Close sits at the trailing edge. It calls `POST /api/window/close`, which destroys the pywebview window. That ends the process the same way the window chrome close does. No closer returns 503.

Choosing a theme calls `PUT /api/config` with that `theme` value. On success the class updates from the UI specification's `resolveDark`. That change does not rescan. A failed write leaves the previous theme in memory and does not change the class.

A place row uses Lucide `Folder`.

The first sidebar row is Add folder. It calls `POST /api/dialogs/folder`. A cancelled dialog does nothing. A returned path is sent to `POST /api/library/roots`. That route calls `accept_root_paths`. Relative paths, files, and paths that are not directories are dropped. A directory already in `library_roots` is not added again. The current roots stay. When `added` is non-empty, the route writes `library_roots` and enqueues one scan. When `added` is empty, it does not write and does not enqueue. A job that is queued or running makes a request that would add a root return 409 `JobBusyError` and write nothing. The client stores the returned config. When `added` is non-empty, the response includes the scan job and the client watches it the same way a Rescan does, so the shelf refreshes when the scan finishes. When `added` is empty, `job` is null. A path that was not a directory shows `Drop a folder.` A 409 or 503 shows `error_message` under the button.

Dropping a folder on the sidebar does not call into Python from the client. `window.py` reads the native drop on `#places` and dispatches a `folders-dropped` window event whose `detail.paths` are absolute paths. The client posts those paths to `POST /api/library/roots`.

Settings is a dialog. It edits library roots, one absolute path per line, the Comic Vine key, `keep_cbr_original` as a checkbox labeled `Keep the original CBR`, and `title_languages` as comma-separated codes in order. It does not edit `theme`. Dismiss writes nothing. Save drops blank root lines. If a non-blank root line is not absolute, the dialog does not send the request and shows `Paths must be absolute.` A successful save calls `PUT /api/config`.

Per-file errors and provider errors are listed at the top of the inspector, above candidates, above the form.

## Errors

| Exception | When |
| --- | --- |
| `ConfigError` | The TOML file cannot be parsed, or a `PUT` value has the wrong JSON type. A failed save does not replace memory |
| `ShellError` | A relative archive path, a bad page index, or a `one` save whose path count is not 1. Nothing is read or written |
| `OutsideLibraryError` | A resolved path is outside every current library root. Nothing is read or written |
| `JobNotFoundError` | `GET` or cancel names an id this process did not start |
| `JobBusyError` | `start` while a job is `queued` or `running`, including a `PUT` that would enqueue a scan and a `POST /api/library/roots` that would add a root. Nothing is enqueued |
| `JobCancelled` | The job saw cancel before the next file, poster, or provider request. Partial entries stay on the job |
| `NoThumbnailError` | `thumbnail_for` returns no path |
| `BatchFieldError` | A save patch contains a key the mode does not allow. Nothing is written |

`OutsideLibraryError` subclasses `ShellError`. `JobNotFoundError` and `ConfigError` do not. Archive and provider exceptions pass through the job as `failed`, except `ProviderCancelledError`, which is `cancelled`.

## Configuration

This specification adds no configuration keys.

It is the only reader and writer of `library_roots`, `keep_cbr_original`, `comicvine_api_key`, and `title_languages` from [00-project-overview.md](00-project-overview.md), and of `theme` from [05-ui-design.md](05-ui-design.md). Defaults stay those documents' defaults. View mode, the selected place, the provider choice, and the rename template are not keys. The HTTP port is not a key. The `httpx` timeout of 15 seconds is not a key. The job poll interval of 500 milliseconds is not a key.

## Testing

Tests are hermetic. They use temporary config, index, library, and UI paths. They do not open pywebview, do not use the network, do not call `time.sleep`, and do not read the developer's config, index, or library. They do not open `src/Claymore/`. Provider calls are the real `search` and `load` with `httpx.MockTransport`, or fakes passed into `create_app`. Archive and index behavior is covered by their own specifications. Shell tests replace those services and assert which ones ran.

Importing `manga_tagger.config`, `manga_tagger.shell`, `manga_tagger.jobs`, or `manga_tagger.api` does not import pywebview.

Cover at least:

- `load_config` on a missing path returns the five defaults and does not create the file. A relative `library_roots` entry is absent from the result and the file bytes are unchanged. An unknown key is still present after a `PUT` that changes `theme`. Invalid TOML raises `ConfigError` and the message includes the path.
- `app_paths("linux", {}, home)` uses `home/.config`, `home/.local/share`, and `home/.cache`. A set absolute `XDG_CONFIG_HOME` replaces only the config root. A relative `XDG_DATA_HOME` is ignored. `darwin` and `win32` use their table, including the `APPDATA` fallback under `home`.
- Two volumes in `/books/Claymore` and one in `/books/Other/Claymore` produce two places. The colliding labels are `books / Claymore` and `Other / Claymore`. `/books/Claymore/extra/v01.cbz` is a place `/books/Claymore/extra` and is not listed for `/books/Claymore`. A volume directly in `/books` makes `/books` a place. Empty roots return no volumes and do not delete a row that is already in the index.
- `filter_volumes` with `clay` keeps a row whose `series` is `Claymore` and drops an unrelated row. A blank query returns every row. Hiding the anchor assigns the anchor to the first remaining selected path.
- `select_plain`, `select_range`, and `select_toggle` follow the selection section, including a range that keeps the anchor and a toggle that removes it.
- `form_from_volumes` on one row includes `Number` as `{ "value", "dirty" }` with `dirty` false, and omits `Pages`. On two rows it includes only `SHARED_FIELDS`, including `Manga`, marks a differing `Series` mixed, shows a shared `Publisher`, and sets every `dirty` flag false.
- `merge_load_patch` for `one` applies `Number`, sets that field `dirty`, and leaves a form field the patch omits. For `many` it applies `Series` and `Manga`, sets those fields `dirty`, and ignores `Number` and `Title`.
- `GET /api/library` calls `list_volumes` and does not call `scan`.
- A `one` save with a dirty `Number` calls `save_comic_info` with `write_number` true and that value. A `one` save with no dirty fields and a filename stem `Claymore v02` whose stored `Number` is `""` calls `save_comic_info` with `Number` `2`. A `one` save with no dirty fields and a stored `Number` that already matches the filename does not call `save_comic_info`. A `many` save calls `save_comic_info` once per path that needs a write, with the dirty shared fields and that file's `Number` from its filename, and does not call `save_many`. A shared `Series` the user did not edit is absent. A file whose shared patch is empty and whose `Number` already matches the filename is not passed to `save_comic_info`. A `many` patch that contains `Title` raises `BatchFieldError` and does not call `save_comic_info`. A successful save calls `write_poster` on the output path.
- A save cancel flag that becomes true after the first file leaves the second file's service uncalled. The first file's `refresh_volume` has run. The job state is `cancelled`.
- `search` and `load` jobs call no archive write and no `scan`. A load job for `many` returns a form without `Number`.
- Comic Vine with `comicvine_api_key` `""` fails the search job as `ProviderUnavailableError`. The mock transport sees no request. The message says the Comic Vine API key is not set.
- `GET /api/page` calls the page read once for the requested index and does not read another index. A path outside the roots calls neither the page read nor `save_comic_info`.
- A rename preview calls `plan_rename` and does not call `rename_in_directory`. A rename job calls `rename_in_directory` on the place and calls `write_poster` on each success path. A convert job skips a `.cbz` and calls `convert_cbr` for a `.cbr`. It does not call `write_poster`.
- `serve` binds `127.0.0.1`, returns a non-zero port, and `close()` stops it. A missing UI directory makes `GET /` return the plain sentence `UI build is missing.` and leaves `GET /api/library` working.
- Cancel of a queued job does not call its function. `start` while a job is `queued` or `running` raises `JobBusyError` and does not call the new function. The inline runner does not sleep. A running save reports `completed` and `total`.
- `accept_root_paths` keeps a directory, ignores a file and a relative path, and does not duplicate a root. `POST /api/dialogs/folder` returns the injected path, and null when the picker cancels. With no picker the route is 503. `POST /api/library/roots` writes a new directory and enqueues one scan. The same route while a job is queued returns 409 and does not write. `POST /api/window/close` calls the injected destroyer and returns 204. With no destroyer the route is 503.

## Acceptance criteria

- One process loads config, binds `127.0.0.1` on an ephemeral port, and opens the pywebview window on that origin. The port is not config. Tests do not open the window.
- The shelf is `GET /api/library`. That response does not scan, open an archive, or build a thumbnail. A missing config file is the defaults, is not created, and paints no volumes.
- A place is a directory that directly contains indexed volumes. The main pane lists those volumes only. A list row shows the filename, and the series underneath when it is set. A grid cell shows the filename. Nested volumes are a different place. The header field filters `series`, `title`, and filename, and does not scrape.
- One selected volume shows that volume's form and one preview page. Several selected volumes show one shared form for `Series`, `Publisher`, `LanguageISO`, `Genre`, `Manga`, `Writer`, `Penciller`, `Inker`, and `CoverArtist`. A field is written only after the user edits it or a load sets it, except each file's `Number`, which a save takes from that file's filename when the stored number differs. An unchanged save does not rewrite the archive. The preview follows the anchor.
- Search and load fill the form and do not write an archive. A load marks the fields it sets dirty, including `Manga` on a shared form. A blank Comic Vine key fails before a request.
- Save writes through `save_comic_info` and does not call `save_many`. One volume writes dirty fields, and `Number` from the filename when that field was not edited and the stored value differs. Several volumes write the dirty shared fields, including `Manga`, and each file's `Number` from its filename. `Volume` is not written. Cancel stops before the next file. A failed file does not stop the rest, and files already written stay written. A successful save writes the sibling poster.
- Rename shows the planned names, then runs on the selected place with the offered template `{Series} v{Number:02}`, then `write_poster` on each success. Convert asks before deleting `.cbr` files, turns selected `.cbr` files into `.cbz`, and skips `.cbz`. A path outside the library is rejected before any read or write.
- Scrapes, saves, converts, and rescans are jobs on one worker. A new job is refused while one is queued or running. The header shows `completed/total`. The user can cancel that job. A finished scan names a skipped or incomplete root in the inspector. Closing the window asks the worker to stop and does not leave a truncated archive from this process killing a write.
- The startup scan is enqueued only after the server is bound, and only when `library_roots` is non-empty. The first library response does not wait for it.
- Add folder asks for one directory and appends it to `library_roots`, then scans. A drop on the sidebar does the same. Existing roots stay. Settings can still replace the list.

## Open questions

All resolved. Recorded here so they are not re-opened.

- **What is a place?** The directory that directly contains indexed volumes. The sidebar lists those folders. A library root is a place only when a volume sits directly in it. Rename applies to the selected place.
- **How does the window call the API?** `fetch` on the API origin. The client does not call a pywebview JavaScript API. `window.py` may dispatch `folders-dropped` after a native drop. The client posts those paths with `fetch`.
- **How does the UI hear about background work?** It polls the job every 500 milliseconds. A second job is refused while one is queued or running. Tests use an inline runner and do not sleep.
- **Where is the page preview?** The inspector image is one page of the anchor volume. Thumbnails are a separate request.
- **What does the header search field do?** It filters the selected place by series, title, or filename. The provider select and Scrape are a different action.
