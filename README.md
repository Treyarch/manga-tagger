# Manga Tagger

Linux-first desktop app to organize and tag a personal manga library. It edits `ComicInfo.xml` inside `.cbz` / `.cbr` archives, scrapes public catalogs, renames volumes from those tags, and writes sibling `{stem}-poster.jpg` covers for Jellyfin Bookshelf. It is not a reader.

One process starts a localhost FastAPI server and a [pywebview](https://pywebview.flowrl.com/) window that loads the built Svelte UI.

## What it does

- Indexes one or more library folders without blocking first paint, with optional subfolder scanning and excluded folder trees.
- Edits one volume or shared series fields across a selection while preserving ComicInfo elements the app does not own.
- Searches MangaDex, AniList, MyAnimeList through Jikan, Comic Vine, and Nautiljon; Comic Vine and Nautiljon can also select a specific issue or volume.
- Locks individual fields per volume so later scrape loads and manual edits cannot overwrite a value accidentally.
- Previews archive pages, and can replace or insert a full-size provider cover without turning the app into a reader.
- Renames archives in place from a previewed template and converts `.cbr` files to verified `.cbz` files.
- Keeps page data compressed as-is during metadata writes, uses atomic replacements, and updates only after explicit user actions.
- Offers list/grid views, light/dark/System themes, optional motion, and desktop keyboard shortcuts.

## Requirements

| Tool | Why |
| --- | --- |
| [CPython](https://www.python.org/) 3.12 or 3.13 | App runtime; other minors are not currently supported |
| [uv](https://docs.astral.sh/uv/) | Install Python deps and run the app |
| [Node.js](https://nodejs.org/) 20.19+ or 22.12+ (npm) | Build the UI in `ui/`; matches Vite's supported engines |
| WebKitGTK + GObject development libraries | Build and run pywebview's GTK binding on Linux |
| `unar` / `lsar` on `PATH` | Optional. Required only for `.cbr` read and convert (The Unarchiver CLI) |

### System packages (Linux)

**Arch / Omarchy**

```bash
sudo pacman -S --needed base-devel cairo gobject-introspection gtk3 webkit2gtk-4.1 unarchiver
```

`uv sync` installs PyGObject into Manga Tagger's own Python environment. Arch's
`python-gobject` package alone is not sufficient when its system Python version
differs from the supported Manga Tagger runtime. `unarchiver` provides `unar`
and `lsar`; skip it if you only use `.cbz`.

**Debian / Ubuntu**

```bash
sudo apt install build-essential pkg-config libcairo2-dev libgirepository-2.0-dev gir1.2-gtk-3.0 gir1.2-webkit2-4.1 unar
```

These packages provide native libraries and headers. The Python `gi` module is
installed from the locked project dependency so it is available to the same
Python 3.12 or 3.13 interpreter that runs Manga Tagger.

## Quick start

From the repository root:

```bash
# 1. Python environment and dependencies
uv sync --locked --group dev

# 2. UI dependencies and production build (writes ui/dist/)
cd ui && npm ci && npm run build && cd ..

# 3. Launch the desktop app
uv run manga-tagger
```

The window title is **Manga Tagger**. Closing it stops the local API and exits the process.
`uv run python -m manga_tagger` is equivalent.

If the UI was not built, the window shows `UI build is missing.` while `/api` still works. Rebuild with `npm run build` in `ui/`.

## First run

1. Open **Settings** (or use **Add folder** in the sidebar) and add absolute paths to folders that contain `.cbz` / `.cbr` files. Settings can disable subfolder scanning or exclude complete folder trees.
2. Wait for the background library scan to finish. Write actions are disabled while it runs, and a completion toast plus any root errors report the outcome. The current UI does not expose scan cancellation.
3. Select one or more volumes, scrape a catalog, review the form, then **Save**. Lock any value that should be protected from later scrape loads.

Accepting a scrape match only fills the form; **Save** writes metadata. To fix a wrong or missing cover, select one volume and use **Replace cover** or **Insert cover** over the cover preview. These actions immediately download the full-size cover from the catalog linked in the Web field and update the archive. Unsaved metadata edits stay in the form.

Optional providers:

- **Comic Vine** — set `comicvine_api_key` in Settings.
- **Nautiljon** — set both `nautiljon_base_url` and `nautiljon_api_key` (wrapper API).

MangaDex, AniList, and MyAnimeList (via Jikan) need no keys.

## Configuration

A missing config file uses defaults and opens an empty library. The first Settings save creates the file.

| Platform | Config | Index | Thumbnail cache |
| --- | --- | --- | --- |
| Linux | `~/.config/manga-tagger/config.toml` | `~/.local/share/manga-tagger/index.db` | `~/.cache/manga-tagger/covers/` |
| macOS | `~/Library/Application Support/manga-tagger/config.toml` | same directory `index.db` | `~/Library/Caches/manga-tagger/covers/` |
| Windows | `%APPDATA%\manga-tagger\config.toml` | same directory `index.db` | `%LOCALAPPDATA%\manga-tagger\covers\` |

Linux honors `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, and `$XDG_CACHE_HOME` when set.

| Key | Default | Meaning |
| --- | --- | --- |
| `library_roots` | `[]` | Absolute folders scanned for `.cbz` / `.cbr` files |
| `excluded_folders` | `[]` | Absolute folder trees omitted from library scans, including descendants |
| `scan_subfolders` | `true` | Scan descendants of each root; when false, scan only files directly inside each root |
| `keep_cbr_original` | `true` | Keep the `.cbr` after a successful convert to `.cbz` |
| `write_poster_on_save` | `true` | Write `{stem}-poster.jpg` after a successful save, rename, or cover update |
| `auto_save_metadata_on_switch` | `false` | When leaving a dirty form, save silently (`true`) or ask first (`false`) |
| `comicvine_api_key` | `""` | Empty disables Comic Vine |
| `nautiljon_base_url` | `""` | Absolute origin of the Nautiljon wrapper; empty disables it |
| `nautiljon_api_key` | `""` | Wrapper `X-Api-Key`; empty disables Nautiljon |
| `title_languages` | `["fr", "en"]` | Title preference order; original title is the fallback |
| `enabled_providers` | `["mangadex", "anilist", "jikan", "comicvine", "nautiljon"]` | Catalogs shown in the provider picker; unknown ids are dropped and an empty list disables scraping |
| `theme` | `system` | `system`, `light`, or `dark`; System live-follows the active Omarchy palette when available, then falls back to the desktop light/dark preference |
| `animate_interface` | `false` | Enable decorative panel, dialog, preview, and notification transitions unless reduced motion is requested |

On Omarchy, System reads the generated palette at `~/.local/state/omarchy/current/theme/colors.toml` and updates the open window after a theme switch. Manga Tagger only reads this file; it does not install hooks or modify Omarchy configuration. Forced Light and Dark always use Manga Tagger's built-in palette.

The HTTP API binds to `127.0.0.1` on an ephemeral port. The port is not configurable.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl/Cmd+S` | Save metadata |
| `F2` | Rename selected files, or the current folder when nothing is selected |
| `F5` | Scan the library |
| `Ctrl/Cmd+1` | List view |
| `Ctrl/Cmd+2` | Grid view |
| `Ctrl/Cmd+,` | Settings |
| `Escape` | Close the active dialog |
| `Left` / `Right` | Previous / next preview page when focus is not in a form control |

## Production build

Build the UI first, run both test suites, then create the distributable wheel:

```bash
cd ui
npm ci
npm test
npm run build
cd ..

uv run pytest
uv build --wheel
```

The production artifact is `dist/manga_tagger-0.1.0-py3-none-any.whl`. It
contains the compiled Svelte UI and installs the `manga-tagger` command; it does
not require the source checkout or Node.js at runtime. Linux still needs the
GTK/WebKitGTK system packages listed above.

For example, install the wheel as an isolated application with:

```bash
uv tool install --python 3.13 dist/manga_tagger-0.1.0-py3-none-any.whl
manga-tagger
```

## Development

### Python

```bash
uv sync --locked --group dev
uv run pytest
```

The committed `uv.lock` is the reproducible dependency contract. CI performs
that locked install and runs the complete suite on every supported Python
minor, currently CPython 3.12 and 3.13.

Tests are hermetic: no network, no real sleep, and no read of your personal config, index, or library. Tests that need `unar` skip when it is not on `PATH`.

### UI

```bash
cd ui
npm ci
npm run build    # production assets → ui/dist/
npm test         # vitest
```

There is no separate Vite-dev ↔ API wiring for the desktop window. Change the UI, rebuild `ui/dist`, then relaunch `uv run python -m manga_tagger`.

### Repository layout

```text
src/manga_tagger/      archives, index, providers, jobs, desktop entry point
src/manga_tagger/api/  FastAPI app (localhost only)
ui/                    Vite + Svelte 5 client (build → ui/dist)
tests/                 pytest fixtures and unit tests
docs/                  architecture specs (spec-driven workflow)
```

## Specs

This project is **spec-driven**. Feature behavior lives in [docs/](docs/README.md):

- [Project overview](docs/00-project-overview.md)
- [Archives and ComicInfo](docs/01-archives-and-comicinfo.md)
- [Library index](docs/02-library-index.md)
- [Metadata providers](docs/03-metadata-providers.md)
- [Application shell](docs/04-application-shell.md)
- [UI design](docs/05-ui-design.md)
- [Select issue](docs/06-select-issue.md)
- [Field locks](docs/07-field-locks.md)
- [Cover from provider](docs/08-cover-from-provider.md)
- [Keyboard shortcuts](docs/09-keyboard-shortcuts.md)

Read those before changing scope or behavior.
