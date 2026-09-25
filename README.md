# Manga Tagger

Linux-first desktop app to organize and tag a personal manga library. It edits `ComicInfo.xml` inside `.cbz` / `.cbr` archives, scrapes public catalogs, renames volumes from those tags, and writes sibling `{stem}-poster.jpg` covers for Jellyfin Bookshelf. It is not a reader.

One process starts a localhost FastAPI server and a [pywebview](https://pywebview.flowrl.com/) window that loads the built Svelte UI.

## Requirements

| Tool | Why |
| --- | --- |
| [Python](https://www.python.org/) 3.12+ | App runtime |
| [uv](https://docs.astral.sh/uv/) | Install Python deps and run the app |
| [Node.js](https://nodejs.org/) 20+ (npm) | Build the UI in `ui/` |
| WebKitGTK + GObject bindings | pywebview on Linux |
| `unar` / `lsar` on `PATH` | Optional. Required only for `.cbr` read and convert (The Unarchiver CLI) |

### System packages (Linux)

**Arch / Omarchy**

```bash
sudo pacman -S webkit2gtk-4.1 python-gobject unarchiver
```

`unarchiver` provides `unar` and `lsar`. Skip it if you only use `.cbz`.

**Debian / Ubuntu**

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 unar
```

## Quick start

From the repository root:

```bash
# 1. Python environment and dependencies
uv sync --group dev

# 2. UI dependencies and production build (writes ui/dist/)
cd ui && npm ci && npm run build && cd ..

# 3. Launch the desktop app
uv run python -m manga_tagger
```

The window title is **Manga Tagger**. Closing it stops the local API and exits the process.

If the UI was not built, the window shows `UI build is missing.` while `/api` still works. Rebuild with `npm run build` in `ui/`.

## First run

1. Open **Settings** (or use **Add folder** in the sidebar) and add absolute paths to folders that contain `.cbz` / `.cbr` files.
2. Wait for the library scan to finish (header shows progress; cancel is available).
3. Select one or more volumes, scrape a catalog, review the form, then **Save**.

Nothing is written into an archive until you save. Accepting a scrape match only fills the form.

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
| `library_roots` | `[]` | Absolute folders scanned recursively for `.cbz` / `.cbr` |
| `keep_cbr_original` | `false` | Keep the `.cbr` after a successful convert to `.cbz` |
| `comicvine_api_key` | `""` | Empty disables Comic Vine |
| `nautiljon_base_url` | `""` | Absolute origin of the Nautiljon wrapper; empty disables it |
| `nautiljon_api_key` | `""` | Wrapper `X-Api-Key`; empty disables Nautiljon |
| `title_languages` | `["fr", "en"]` | Title preference order; original title is the fallback |
| `theme` | `system` | `system`, `light`, or `dark` |

The HTTP API binds to `127.0.0.1` on an ephemeral port. The port is not configurable.

## Development

### Python

```bash
uv sync --group dev
uv run pytest
```

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
src/manga_tagger/      archives, index, providers, jobs
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

Read those before changing scope or behavior.
