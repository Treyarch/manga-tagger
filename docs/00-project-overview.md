# Project overview

Manga Tagger is a Linux-first desktop app for tagging a personal manga library in place. It edits `ComicInfo.xml` inside each archive, fills that metadata from public catalog sites, and previews pages without unpacking the book. Other readers and servers pick the files up from disk afterward.

This file is the project guideline. It has no YAML frontmatter, as required by [docs/README.md](README.md). It does not by itself authorize implementation. Feature work starts from the planned specifications listed below, and those specifications must follow this document.

## Purpose

The app replaces the day-to-day tagging flow of ComicTagger for a library of a few hundred volumes. ComicTagger is built around a blocking identify dialog and around Comic Vine, and it spends too much time opening archives for what should be a metadata edit. Manga Tagger is manga-first, writes only what changed, and keeps the window responsive.

The library lives as `.cbz` and `.cbr` files in folders the user chooses. The app does not become the reader, and it does not talk to Komga, Kavita, or any other server.

## Product bar

A session feels fast when cheap work stays cheap:

- The shelf is on screen as soon as the window opens, from data already indexed.
- Choosing a volume shows its cover and `ComicInfo.xml` without extracting the archive.
- Saving tags copies the page images through and replaces the XML. It does not recompress the book.
- A scrape, a save, or a rescan never freezes the window. The user can cancel a scrape.
- Nothing is written into an archive until the user saves. Accepting a match only loads the form.

Later specifications turn these into concrete behavior. They must not trade them away for a simpler implementation.

## Locked decisions

| Decision | Choice |
| --- | --- |
| Language | Python 3.12 or newer |
| Packaging of the core | `src/` layout, dependencies in `pyproject.toml`, installs via [uv](https://docs.astral.sh/uv/) |
| HTTP API | FastAPI, Pydantic models, bound to `127.0.0.1` on an ephemeral port |
| UI | Vite and Svelte 5 |
| Window | [pywebview](https://pywebview.flowrl.com/), loading the local UI. WebKitGTK on Linux |
| Index | SQLite, via the standard-library `sqlite3` module |
| XML | `lxml` |
| RAR read | The `unar` executable on `PATH` |
| Process | One desktop process. It starts the API and the window. The user does not start a server |

The API is FastAPI. Do not add Flask. Do not add Electron, a bundled Chromium, or a Go or Rust component in v1. The archive, index, and provider code must import and run without FastAPI and without pywebview, so unit tests never open a window.

## Version 1

Version 1 does three jobs:

1. **ComicInfo.** Read and edit `ComicInfo.xml` inside an archive. Preserve XML elements the app does not edit.
2. **Scrape.** Search MangaDex, AniList, MyAnimeList (through Jikan), and Comic Vine. An accepted match loads the form. Save is what writes the archive.
3. **Preview.** Show the cover and individual pages by reading those entries from the archive.

Each archive is one tankōbon. The volume number is stored in ComicInfo `Number`. `Volume` is not filled automatically.

The user can select one volume or several. Accepting a match loads one shared form and does not change any archive. Save writes the fields that form shows into every selected file and keeps every other XML element in each file. With one volume selected, the match may fill `Number` on the form, and save writes it. With several volumes selected, save does not change `Number` on any of them. One file failing during that save does not stop the other selected files, and files already written stay written.

Title text uses the first language the catalog actually has, in this order: French, then English, then the original title.

A match from MangaDex, AniList, or MyAnimeList sets reading direction to right to left (`Manga` = `YesAndRightToLeft`). A Comic Vine match sets it to left to right (`Manga` = `No`). The form shows that value. Save writes the value still on the form.

Saving metadata for a `.cbr`, or an explicit convert action, produces a `.cbz` beside it. The original `.cbr` is removed only after the `.cbz` is complete and its `ComicInfo.xml` can be read back. `Foo.cbr` becomes `Foo.cbz` in the same directory. If `Foo.cbz` already exists, the convert fails for that file and leaves the `.cbr` untouched. The default is to delete the `.cbr` so one book stays one file. `keep_cbr_original` keeps it.

## Out of scope

- A reading mode. Preview exists to check tags and page order.
- Clients for Komga, Kavita, or similar servers.
- Writing RAR, or any workflow that keeps the canonical file as `.cbr` after a successful convert.
- Renaming files from metadata, and moving volumes into a series/volume folder layout.
- Loose page-image folders, PDF, and archives other than `.cbz` and `.cbr`.
- Unattended auto-tagging. A scrape proposes a match. A person accepts it, reviews the form, and saves.
- Accounts, sync, or multi-user access.

## Performance rules

These rules are mandatory for every feature specification. Tests should assert the mechanism, not a wall-clock budget.

1. **Partial reads.** Listing a CBZ, reading `ComicInfo.xml`, and reading one page use the zip central directory and the requested members only. They do not extract the archive to a directory.
2. **No recompression.** A metadata save writes a new CBZ by copying image members unchanged, including their original compression method. Only `ComicInfo.xml` is new or replaced. Page bytes stay the same.
3. **Atomic replace.** The new CBZ is written to a temporary file in the same directory and renamed into place only after it is complete. A crash or a cancel must not leave the previous file truncated.
4. **Convert once.** CBR extraction happens to create the CBZ. Later edits open the CBZ.
5. **Index first.** The shelf renders from the SQLite index. Opening the app does not rescan the library before the first paint. Rescans and per-file refreshes update the index off the UI thread.
6. **Thumbnail cache.** The cover grid uses cached thumbnails. Building a thumbnail reads the cover entry only.
7. **Background work.** Scrapes, saves, converts, and rescans run as cancellable background work. A scrape uses the current selection. Save writes each selected volume. One failed file does not stop the rest of a batch save or a rescan.
8. **Confirmed writes.** Network results never modify an archive on their own.

The design size is a few hundred volumes. V1 does not add process pools or native extensions. The rules above are the whole performance plan unless a later specification shows one of them cannot be met.

## Application shape

The window has one primary layout: the library, a page preview, and the metadata for the current selection. One selected volume shows that volume. Several selected volumes share one series form, and the preview follows the volume used to start the scrape. Match results appear on that same screen. Tagging is not a separate wizard.

Library roots are scanned recursively for `.cbz` and `.cbr`, in any letter case. Other files are ignored. A symlink is followed only when its target stays inside that root.

The scrape query is the existing `Series` value when that field is non-empty. Otherwise it is the filename without its extension. The provider specification defines how release tags and numbers are stripped from that filename.

The API listens on `127.0.0.1` only. The port is chosen at startup and is not a configuration setting. The UI loads from that origin.

Background failures are reported per file and leave that file unchanged. Expected cases:

- The archive is unreadable or has no page images. The file is marked failed in the index. The scan continues.
- `unar` is missing. CBZ features still work. Any CBR read or convert fails with an error that names `unar`.
- A provider times out, rate-limits, or returns no match. The form shows the failure. `ComicInfo.xml` is unchanged.
- Comic Vine is selected and `comicvine_api_key` is empty. The provider is unavailable until a key is set.

## Configuration

Configuration is a TOML file. If the file is missing, the app uses the defaults below and opens on an empty library.

| Platform | Config | Index | Thumbnail cache |
| --- | --- | --- | --- |
| Linux | `$XDG_CONFIG_HOME/manga-tagger/config.toml` | `$XDG_DATA_HOME/manga-tagger/index.db` | `$XDG_CACHE_HOME/manga-tagger/covers/` |
| macOS | `~/Library/Application Support/manga-tagger/config.toml` | `~/Library/Application Support/manga-tagger/index.db` | `~/Library/Caches/manga-tagger/covers/` |
| Windows | `%APPDATA%\manga-tagger\config.toml` | `%APPDATA%\manga-tagger\index.db` | `%LOCALAPPDATA%\manga-tagger\covers\` |

On Linux, unset XDG variables mean `~/.config`, `~/.local/share`, and `~/.cache`.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `library_roots` | list of absolute paths | `[]` | Folders scanned for `.cbz` and `.cbr` files. An empty list means an empty shelf. |
| `keep_cbr_original` | boolean | `false` | When `false`, delete the `.cbr` after its `.cbz` has been written and read back. When `true`, keep the `.cbr` next to the new `.cbz`. |
| `comicvine_api_key` | string | `""` | Comic Vine API key. Empty disables that provider. The other three providers need no key. |
| `title_languages` | list of strings | `["fr", "en"]` | Title preference order. Each entry is a language the catalog may have. The original title is used when none of them exist. |

Unknown keys are ignored. The feature specification that introduces a key must document it here or in its own Configuration section before that specification becomes `active`.

## Repository layout

```text
src/manga_tagger/     core: archives, index, providers
src/manga_tagger/api/ FastAPI app
ui/                   Vite + Svelte
tests/                hermetic unit tests and fixture archives
```

## Planned specifications

Write these before the code they describe. Each one is a normal spec: YAML frontmatter, Configuration, Testing, and Acceptance criteria.

| Document | Covers |
| --- | --- |
| `01-archives-and-comicinfo.md` | Partial read, preview, ComicInfo edit, `Number` as the volume, atomic CBZ save, batch save that leaves each `Number` alone, CBR convert |
| `02-library-index.md` | SQLite index, recursive scan, thumbnail cache, first paint |
| `03-metadata-providers.md` | MangaDex, AniList, Jikan, Comic Vine, title language order, reading direction, accept-before-write |
| `04-application-shell.md` | Single process, local FastAPI, pywebview, the one-screen layout, multi-volume selection |

## Testing

This guideline produces no runnable code and has no tests of its own.

Feature specifications follow these project rules:

- Tests are hermetic. They do not use the network, do not sleep for real time, and do not read the developer’s real config, index, or library.
- Archive tests use small fixture files under `tests/`.
- Tests that need `unar` skip when it is not on `PATH`. Every other test passes without it.
- Performance rules are checked by behavior: which zip members were opened, whether image bytes and compression methods survived a save, and whether a rejected scrape left the file untouched.

## Acceptance criteria

- A reader can name the stack, the three v1 jobs, and the out-of-scope list without opening another document.
- The performance rules are specific enough that a feature spec can cite one by number and test it.
- Every configuration key in this document has a type and a default, and a missing config file is defined as those defaults.
- No feature spec marked `proposed` or `active` contradicts the locked decisions, the v1 scope, or the performance rules.
- Implementation of a behavior waits for the planned specification that owns it.

## Open questions

All resolved. Recorded here so they are not re-opened in feature specs.

- **What is the UI?** A Svelte web UI inside a pywebview window. Chosen for a real web frontend and a single desktop window, without shipping Chromium.
- **Which language?** Python 3.12. The library is a few hundred volumes, so the speed goal is avoiding full extracts and recompression, not a native rewrite.
- **What must v1 do?** Edit ComicInfo, scrape the four catalogs, preview pages, and apply one accepted match to every volume in the current selection.
- **How does a batch save work?** One shared form is reviewed, then save writes those fields to each selected file. A single selected volume may take `Number` from the match. Several selected volumes keep the `Number` each file already has. This is still a confirmed save, not an unattended auto-tag.
- **What is one file?** One tankōbon. ComicInfo `Number` is the volume number. `Volume` is not auto-filled.
- **Which catalogs?** MangaDex, AniList, MyAnimeList via Jikan, and Comic Vine when an API key is set.
- **Which title?** French, then English, then the original. The order is `title_languages`, default `["fr", "en"]`, with the original title as the fallback.
- **Which reading direction?** Right to left for MangaDex, AniList, and MyAnimeList. Left to right for Comic Vine. The form can change it before save.
- **What happens when ComicInfo already exists?** The match loads the form. Disk changes only on save. Save writes the form fields and keeps every other XML element.
- **What happens to `.cbr`?** Convert to `.cbz` on save or explicit convert. Delete the `.cbr` after a verified write unless `keep_cbr_original` is true.
- **Which files are scanned?** `.cbz` and `.cbr` only, recursively inside each library root. Symlinks that leave the root are ignored.
- **Where does the search text come from?** Existing `Series`, or the filename without its extension when `Series` is empty.
- **How big is the library?** A few hundred volumes. The performance rules still forbid work that grows with the whole archive when only metadata or one page is needed.
- **Does the app own the library?** No. It updates files on disk. Readers and servers are out of scope.
