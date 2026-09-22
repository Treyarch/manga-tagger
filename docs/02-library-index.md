---
description: SQLite library index, recursive scan of cbz and cbr roots, on-demand cover thumbnails, and a shelf that paints from the index.
status: proposed
---

# Library index

This specification owns the SQLite index, the recursive library scan, the thumbnail cache, and first paint from that index. It implements performance rules 5 and 6, and the rescan clause of performance rule 7, from [00-project-overview.md](00-project-overview.md).

The core lives in `src/manga_tagger/index.py` and imports without FastAPI and without pywebview. It uses the standard-library `sqlite3` module. Callers pass the database path, the thumbnail cache directory, and the library roots. This module does not read the TOML config file and does not start a thread.

Archive reads, cover choice, ComicInfo edit, and the sibling `{stem}-poster.jpg` stay in [01-archives-and-comicinfo.md](01-archives-and-comicinfo.md). When the application starts a scan, and how the window paints the rows, belong to the application-shell specification.

## Volume record

One row is one resolved archive path. The row stores file facts, scan status, and every owned ComicInfo text field from the archives specification. `Pages` is not stored.

| Column | Meaning |
| --- | --- |
| `path` | Resolved absolute path. Primary key |
| `root` | Resolved absolute path of the library root that owns the row |
| `name` | Filename, including the extension |
| `extension` | `cbz` or `cbr`, lowercased |
| `size` | File size in bytes |
| `mtime_ns` | Modification time in nanoseconds |
| `status` | `ok` or `failed` |
| `error_type` | Exception class name when `status` is `failed`, otherwise `""` |
| `error_message` | Exception message when `status` is `failed`, otherwise `""` |
| `cover_index` | Reading-order cover index. NULL when `status` is `failed` |
| `archive_page_count` | Number of page images. NULL when `status` is `failed` |
| ComicInfo columns | One text column per owned element except `Pages`. A missing element is `""` |

The ComicInfo columns are `title`, `series`, `number`, `volume`, `publisher`, `page_count`, `language_iso`, `age_rating`, `manga`, `genre`, `summary`, `web`, `community_rating`, `notes`, `year`, `month`, `day`, `writer`, `penciller`, `inker`, and `cover_artist`. `page_count` is the `PageCount` element text. `archive_page_count` is the number of page images. They are stored as read and are not required to match.

`list_volumes` returns these fields, including failed rows. The form, and a search over series, title, or filename, can use the row without opening the archive.

## Database

Each public call opens its own connection, ensures the schema, does its work, and closes the connection. Connections are not shared across calls. This module does not keep a pool. The connection uses WAL journal mode.

A missing parent directory and a missing database file are created. `PRAGMA user_version` is the schema version.

- Version 0 gets the table below, then `user_version` is set to 1.
- Version 1 is opened unchanged.
- Any other version raises `IndexVersionError` and does not modify the file.

```sql
CREATE TABLE volumes (
  path TEXT PRIMARY KEY,
  root TEXT NOT NULL,
  name TEXT NOT NULL,
  extension TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  status TEXT NOT NULL,
  error_type TEXT NOT NULL,
  error_message TEXT NOT NULL,
  cover_index INTEGER,
  archive_page_count INTEGER,
  title TEXT NOT NULL,
  series TEXT NOT NULL,
  number TEXT NOT NULL,
  volume TEXT NOT NULL,
  publisher TEXT NOT NULL,
  page_count TEXT NOT NULL,
  language_iso TEXT NOT NULL,
  age_rating TEXT NOT NULL,
  manga TEXT NOT NULL,
  genre TEXT NOT NULL,
  summary TEXT NOT NULL,
  web TEXT NOT NULL,
  community_rating TEXT NOT NULL,
  notes TEXT NOT NULL,
  year TEXT NOT NULL,
  month TEXT NOT NULL,
  day TEXT NOT NULL,
  writer TEXT NOT NULL,
  penciller TEXT NOT NULL,
  inker TEXT NOT NULL,
  cover_artist TEXT NOT NULL
);
```

There is no pagination. A library of a few hundred volumes is returned in one list.

A database that cannot be opened or written raises `LibraryIndexError`. Files already committed stay committed.

## List

`list_volumes(db_path, *, under=None)` reads `volumes` and returns the rows. Order is `path` ascending, compared by Unicode code point.

`under` is `None` or an absolute path. `None` returns every row. Otherwise a row is kept when `path` equals `under`, or when `path` is a file inside `under`. The check uses a path separator, so `/books` does not match `/books-extra`. A relative `under` raises `LibraryIndexError`.

The call does not stat the library, walk directories, open archives, or build thumbnails. Creating a missing database is the only write. An empty database returns an empty list. Painting the shelf is this call. It does not scan.

## Scan

`scan(db_path, cache_dir, roots, *, cancel=None)` walks `roots` in list order. Each root is an absolute path. A relative root raises `LibraryIndexError` before any walk. `cancel` is `None` or a callable that returns true when the scan should stop. It is checked before each file and before pruning. The function runs on the caller's thread.

A root that is not an existing directory is skipped. Its rows stay. The result names that root as skipped. A missing or unmounted root does not empty the shelf.

A root that is a directory is walked recursively. Paths stored and compared are resolved absolute paths with trailing separators removed.

- A directory entry whose name ends in `.cbz` or `.cbr`, in any letter case, is a candidate. Every other file is ignored. A ComicInfo save writes its temporary file under a name that is not `.cbz` or `.cbr`, so the scan does not index it.
- A symlink is followed only when its resolved path stays inside that root. A symlink that leaves the root is skipped and creates no row.
- A symlink to a directory is entered only when that resolved directory has not already been visited in this walk. A cycle is skipped.
- A directory that cannot be listed is named in the result. That root is then treated as incomplete and is not pruned.
- The row `path` is the resolved file path. A symlink and its target inside the root are one row.

The first root in `roots` that reaches a resolved path owns it for this scan. A later root that reaches the same path does not write the row again. When this scan sees a path that already has a row, it keeps the ComicInfo rules below and sets `root` to the root that saw it first in this scan. A file that used to belong to a root no longer in the list moves to the earlier remaining root that still contains it.

For each candidate the scan records size and mtime. An existing row with `status` `ok`, the same `size`, and the same `mtime_ns` is not opened. Its ComicInfo columns stay as stored. When `root` is not the root that saw the path first in this scan, that column is updated, and the path is still reported as unchanged. A `failed` row is read again even when size and mtime match, so a repaired file can become `ok`.

Any other candidate is read through the archive operations in the archives specification. Listing pages and reading ComicInfo use the central directory and the `ComicInfo.xml` member only. Page-image bodies are not read. The cover index is that specification's cover: the `FrontCover` page when `Pages` names it, otherwise `0`. On the Claymore reference set that index is `0`, the first page, which is the image the sibling poster is made from. This scan does not read or write that poster.

An `ok` row copies the ComicInfo text fields, `cover_index`, and `archive_page_count`. A missing element is `""`. `error_type` and `error_message` are `""`.

`UnreadableArchiveError`, `NoPageImagesError`, and `MissingUnarError` write a `failed` row. `error_type` is the exception class name. `error_message` is the exception message. ComicInfo columns are `""`. `cover_index` and `archive_page_count` are NULL. `size` and `mtime_ns` come from the successful stat. The walk continues. A missing `unar` fails each `.cbr` and still indexes `.cbz` files.

Each file is one transaction, committed before the next file.

### Prune

Prune runs only when `cancel` has not returned true and every requested root was either fully listed or skipped because it is not a directory. An incomplete root, and a cancelled scan, prune nothing. Rows committed before the stop stay. A file that disappeared stays listed until a scan finishes.

On a finished scan:

- Delete a row whose `path` was not seen and whose `root` was fully walked.
- Delete a row whose `root` is not in `roots`.
- Leave a row whose `root` was skipped because that path is not an existing directory.
- A finished scan whose `roots` list is empty deletes every row.

For each deleted path, delete thumbnail files in `cache_dir` whose name starts with that path's digest followed by `-`. The digest is defined in the thumbnail section.

### Result

The result reports:

- paths inserted or rewritten, in the order they were written
- paths left unchanged because size and mtime matched, in walk order
- paths written as `failed`, in walk order
- paths deleted by prune, in `path` order
- roots that were skipped or incomplete, in input order
- whether the scan was cancelled

## Single-file update

`refresh_volume(db_path, path, roots)` re-reads one resolved path with the same stat and archive rules as a scan. `roots` is the current library-root list, in order. The row's `root` is the first root in that list that contains the path. The call does not walk other files and does not prune other rows.

A path that is missing, is not a `.cbz` or `.cbr`, or sits outside every root loses its row, and the call returns no row. That deletion does not remove thumbnail files. A caller that drops a path uses `forget_volume` so the thumbnail goes with it.

`forget_volume(db_path, cache_dir, path)` deletes the row for that resolved path and deletes its thumbnail files. A path that is not indexed is a success.

A save, a rename, or a convert calls `refresh_volume` on the output path and `forget_volume` on a path that is gone. This module does not watch the filesystem. Neither call builds a thumbnail.

## Thumbnail cache

`thumbnail_for(db_path, cache_dir, path)` returns the path of a JPEG in `cache_dir` for an `ok` row. A missing row or a `failed` row returns no path and writes nothing. A missing `cache_dir` is created.

The image is the cover page at `cover_index`. The read is that one archive member. The width is 256 pixels. The height keeps the cover's aspect ratio, rounded to the nearest integer. A cover already narrower than 256 pixels is not enlarged. A cover with an alpha channel is composited onto white before encoding. A cover without alpha is encoded as it is. Pillow encodes JPEG at quality 80. These values are not TOML keys.

The filename is `{digest}-{mtime_ns}-{size}.jpg`. `digest` is the SHA-256 hex digest of the resolved path encoded as UTF-8. A new size or mtime names a different file. Thumbnail files in `cache_dir` that start with `{digest}-` and are not the current name are removed before the call returns.

The JPEG is written to a temporary file in `cache_dir` and renamed into place. The archive is not modified. The sibling poster is not read and is not written. When the current filename already exists, it is returned and the archive is not opened.

`list_volumes` and `scan` do not call `thumbnail_for`.

## Errors

| Exception | When |
| --- | --- |
| `LibraryIndexError` | The database cannot be opened or written, a path that must be absolute is relative, or thumbnail encoding fails. A failed encode removes its temporary file and leaves an older thumbnail in place |
| `IndexVersionError` | `user_version` is neither 0 nor 1. The schema is not rewritten and existing rows stay |

`IndexVersionError` is a subclass of `LibraryIndexError`. The base name is not the builtin `IndexError`.

Archive failures during `scan` and `refresh_volume` are stored on the row. They are not raised by those calls.

## Configuration

This specification adds no configuration keys.

The database file and the thumbnail directory are the index and thumbnail-cache paths in [00-project-overview.md](00-project-overview.md). The application shell passes those paths in. Tests pass temporary paths. Thumbnail width 256, JPEG quality 80, and the white matte are not TOML keys.

## Testing

Tests are hermetic. They do not use the network, do not sleep, and do not read the developer’s config, index, or library. They do not open `src/Claymore/`. Fixtures are small archives created under `tests/fixtures/` or in a temporary directory during the test. The database and the cache directory are temporary paths passed into the functions. Tests that need `unar` or `lsar` skip when that executable is not on `PATH`. Every other test passes without them. A unit test for a missing `unar` may stub the executable lookup.

Instrument archive opens so a test can see which member bodies were read, and instrument directory walks so a test can see that a list did not scan.

Cover at least:

- `list_volumes` on a missing database creates it, returns an empty list, and does not walk a library directory beside it.
- `list_volumes` returns `ok` and `failed` rows ordered by `path`. `under` returns that directory and the files inside it, and does not return a sibling whose path only shares a prefix.
- A scan indexes a nested `.CBZ` and a `.cbr`, and ignores a `.txt`, a `.pdf`, and a temporary file that is not a `.cbz` or `.cbr`.
- A symlink whose target leaves the root creates no row. A symlink to a file inside the root is one row at the resolved path. A directory symlink cycle ends. The same resolved path under two roots is one row, owned by the first root. A second scan that adds an earlier root moves `root` to that root and does not open the archive when size and mtime match.
- An unreadable archive becomes `failed`, and a later archive in the walk is still indexed. ComicInfo text, `cover_index`, and `archive_page_count` on an `ok` row match a partial read. A re-read opens `ComicInfo.xml` and no page-image body.
- An `ok` row with the same size and mtime does not open the archive. A changed mtime re-reads ComicInfo. A `failed` row with the same mtime is opened again.
- Cancel after the first committed file keeps that row, leaves a deleted file's previous row in place, and does not drop rows for a root removed from the list.
- A finished scan deletes a removed file and its thumbnail, deletes rows whose root is no longer in the list, and keeps rows for a root that is not an existing directory. A finished scan with an empty root list deletes every row. A directory that cannot be listed does not prune that root.
- `refresh_volume` updates one file after its ComicInfo changes and does not walk a sibling. `forget_volume` removes the row and the thumbnail. A missing path returns no row.
- `thumbnail_for` reads only the cover page, writes a JPEG 256 pixels wide, and leaves the archive bytes unchanged. It does not write `{stem}-poster.jpg`. A cover narrower than 256 pixels is not enlarged. A cover with an alpha channel encodes on white. The test may decode that JPEG. A second call for the same size and mtime does not open the archive. A `failed` row returns no path. `list_volumes` creates no thumbnail.
- When `unar` is absent, a `.cbr` row is `failed` with `error_type` `MissingUnarError` and a message that names `unar`, and a `.cbz` row is `ok`.
- `user_version` 2 raises `IndexVersionError`. The version stays 2 and a sentinel row is still present.

## Acceptance criteria

- The shelf is a read of the SQLite index. Opening that list does not walk the library, open an archive, or build a thumbnail. A missing database becomes an empty index.
- A scan visits `.cbz` and `.cbr` recursively, in any letter case, and ignores every other file. A symlink is followed only when its target stays inside that root. One resolved path is one row, owned by the first root that contains it.
- An unchanged `ok` file is not opened. A changed file, and a `failed` file, are read from the central directory and `ComicInfo.xml` only. The row stores every owned ComicInfo text field except `Pages`, plus the cover index and the archive page count.
- An unreadable archive, an archive with no page images, or a `.cbr` read without `unar` is a `failed` row. The scan continues. A `.cbz` still indexes when `unar` is missing. The `unar` error message names `unar`.
- Each file is committed on its own. Cancel keeps those rows and prunes nothing.
- A finished scan drops files that disappeared and drops roots that are no longer in the list, including a finished scan of an empty root list. A root that is not an existing directory keeps its rows. A root whose directory cannot be listed is not pruned.
- `refresh_volume` updates one archive. `forget_volume` drops one path and its thumbnail. The module does not watch the filesystem and does not start a thread.
- A thumbnail is built when asked, from the cover page only, as a 256-pixel-wide JPEG at quality 80 on a white matte when the cover has an alpha channel, by rename inside the cache directory. The sibling poster is left alone. A scan does not build thumbnails.
- A database whose `user_version` is neither 0 nor 1 is refused. The schema is not rewritten and existing rows stay.
