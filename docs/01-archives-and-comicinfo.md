---
description: Read, preview, and atomically save ComicInfo.xml, apply shared series fields in a batch, and rename archives in place from a filename template.
status: active
---

# Archives and ComicInfo

This specification owns partial reads, page preview bytes, ComicInfo edit, `Number` as the tankōbon volume, atomic CBZ save, batch save of shared series fields, in-place rename from a filename template, and CBR-to-CBZ convert. It implements performance rules 1, 2, 3, and 4 from [00-project-overview.md](00-project-overview.md).

The core lives in `src/manga_tagger/` and imports without FastAPI and without pywebview. Callers pass the `keep_cbr_original` boolean in. This module does not read the TOML config file.

Scraping, the SQLite index, and the window are out of scope. A later specification decides which fields a form shows. This document defines the archive operations that form calls.

## Reference archive

`src/Claymore/` is a local reference for the finished series folder. It is not a unit-test fixture and it is not committed. Tests use small synthetic files under `tests/fixtures/`.

The folder holds three volumes and a poster beside each one:

```text
Claymore/
  Claymore v01.cbz
  Claymore v01-poster.jpg
  Claymore v02.cbz
  Claymore v02-poster.jpg
  Claymore v03.cbz
  Claymore v03-poster.jpg
```

Each ComicInfo has `Series` `Claymore` and `Volume` `1`, `2`, or `3` (the filename is zero-padded; the XML is not). `Number` matches `Volume`. `Title` differs per volume. The posters are JPEGs 600 pixels wide. Volume 1 was tagged by ComicTagger 1.5.5.

Observed shape of `Claymore v01.cbz`:

- `ComicInfo.xml` is a member at the archive root. Page images live in a subdirectory (`01 - La tueuse aux yeux d’argent/`, U+2019 in the folder name). Image member names are UTF-8.
- Every page image is ZIP stored (`compress_type` 0).
- Central-directory order is not reading order. `<Page Image="N">` matches index `N` after sorting member names. A spread is one file (`Claymore-01-180-181.jpg` is a single image). `PageCount` counts image files, not the printed page numbers in those names.
- Page types on that file: index 0 `FrontCover`, index 1 `InnerCover`, index 182 `BackCover`. Other `Page` elements omit `Type`.
- Elements present: `Title`, `Series`, `Number`, `Volume`, `Publisher`, `PageCount`, `LanguageISO`, `AgeRating`, `Manga`, `Genre`, `Summary`, `Web`, `CommunityRating`, `Notes`, `Year`, `Month`, `Day`, `Writer`, `Penciller`, `Inker`, `CoverArtist`, and `Pages`. `Manga` is the token `Yes`. `Volume` is `1`.

## Archive members

A `.cbz` or `.cbr` is identified by its extension, in any letter case.

Page images are members whose extension is `jpg`, `jpeg`, `png`, `webp`, or `gif`, in any letter case, at any folder depth. Directory entries are not pages. `ComicInfo.xml` is not a page. Any other member (text sidecars, unknown files) is kept on save and ignored for preview.

Reading order is the member name after replacing backslashes with `/`, sorted by Unicode code point. The sort is not locale-dependent and does not parse digits out of the filename. `<Page Image>` is the zero-based index in that order.

`ComicInfo.xml` is the member whose name is exactly `ComicInfo.xml` at the archive root. A different spelling, or the same name only inside a folder, counts as missing. Missing XML is an empty model, not an error.

An archive that cannot be opened, or a CBZ that is not a zip file, raises `UnreadableArchiveError`. An archive with no page images raises `NoPageImagesError`. Both leave the file unchanged.

## ComicInfo model

XML is parsed and written with `lxml`. The model owns these child elements of `ComicInfo`:

| Element | Meaning |
| --- | --- |
| `Title` | Volume title |
| `Series` | Series title |
| `Number` | Tankōbon volume number |
| `Volume` | Stored as found. This module does not copy `Number` into `Volume` |
| `Publisher` | Publisher |
| `PageCount` | Stored page-file count. A save does not recalculate it from the image list |
| `LanguageISO` | Language code, such as `fr` |
| `AgeRating` | Stored token, such as `M` |
| `Manga` | Stored token. Known values include `Yes`, `No`, `YesAndRightToLeft`, and `YesAndLeftToRight`. Other tokens are kept as text |
| `Genre` | Stored text |
| `Summary` | Stored text |
| `Web` | Stored URL |
| `CommunityRating` | Stored text |
| `Notes` | Stored text |
| `Year`, `Month`, `Day` | Stored text |
| `Writer`, `Penciller`, `Inker`, `CoverArtist` | Stored credit text |

`Pages` is part of the model for reading. Each `Page` keeps `Image`, `ImageWidth`, `ImageHeight`, `ImageSize`, and `Type` when present. A metadata save does not rebuild `Pages` and does not open image pixels to refresh width, height, or size.

Any other element, and any attribute this table does not name, is preserved across a save. Editing the existing tree in place is what makes that true. Serialization does not have to match the original bytes, quotes, or indentation. Preserved element text and attribute values do have to match.

Provider rules that set `Manga` to `YesAndRightToLeft` or `No`, and the rule that `Volume` is not filled automatically, belong to the provider specification. This module writes the token it is given. It does not rewrite `Yes` into `YesAndRightToLeft`.

## Read and preview

These operations use the zip central directory and the requested members only. They do not extract the CBZ to a directory.

- Listing pages reads the central directory and no member bodies.
- Reading ComicInfo reads the `ComicInfo.xml` member only. When that member is absent, the result is an empty model and no page-image member is read.
- Reading one page reads that member only and returns its uncompressed bytes. The index is the reading-order index. An index outside the page list raises `UnreadableArchiveError` and does not write the archive.
- Resolving the cover does not read image bytes. The cover index is the lowest reading-order index whose `Page` has `Image` equal to that index and `Type` equal to `FrontCover`. If there is no such page, the cover index is `0`. `Page` entries whose `Image` does not match a current page are ignored. A missing or stale `Pages` list still yields a cover: the first page.

A CBR list runs `lsar -json` on the archive and does not extract it. `lsarContents` is a list. Each entry's `XADFileName` is the member name, as a string. An entry with `XADIsDirectory` true is a directory and is not a page. A non-zero exit, a body that is not JSON, a missing `lsarContents`, or an entry whose `XADFileName` is not a string raises `UnreadableArchiveError`.

A CBR single-member read creates a temporary directory in the same directory as the archive, so the extract stays on that filesystem. The directory's name does not end in `.cbz` or `.cbr`. The command is `unar -quiet -no-directory -output-directory <temp> <archive> <member>`, where `<member>` is that `XADFileName`. The call reads the extracted file, then deletes the temporary directory. On failure the temporary directory is still deleted and the archive is unchanged.

A full extract, used by convert and by saving metadata on a `.cbr`, uses the same temporary-directory rule and `unar -quiet -output-directory <temp> <archive>` with no member argument, so internal paths are kept. The new `.cbz` is built from that directory. The temporary directory is deleted after the `.cbz` has been renamed into place, or on failure.

`unar` and `lsar` both come from The Unarchiver and must be on `PATH`. If either is missing, every CBR read or convert raises `MissingUnarError`. The message names `unar`. CBZ operations do not need either tool.

## Save

`save_comic_info(path, patch, *, write_number, keep_cbr_original)` writes metadata for one archive.

`patch` maps owned element names to `str` or `None`, excluding `Pages`. A string value creates or replaces that element’s text. `None` or `""` removes that element. A name absent from the patch leaves the existing element as it was. `Pages` is never a patch key.

`write_number` controls `Number` only. When it is false, a `Number` entry in the patch is ignored and the element already in the file stays. When it is true, `Number` is applied like any other patched field. `Volume` follows the patch rules above and is never derived from `Number`. The application shell calls `save_comic_info` once per file. It does not call `save_many`. `save_many` below is the shared-field check those per-file calls follow.

### CBZ

The save builds a new zip in a temporary file in the same directory. The temporary name is not a `.cbz` or `.cbr`, so a library scan will not treat it as a book. Every existing member except root `ComicInfo.xml` is copied unchanged: same member name, compression method, CRC, and uncompressed bytes, including directory entries and non-image files. The new `ComicInfo.xml` is the only member whose contents may differ. Image bytes are copied from the zip data. They are not decoded and not recompressed.

Members are written in their original central-directory order. When root `ComicInfo.xml` already exists, the new member occupies that same position. When it does not, the new member is written first and every other member follows in its original order. Every member name is stored as UTF-8, with general-purpose bit 11 set.

The temporary file is opened and its `ComicInfo.xml` is read back before the original is replaced. On success the temporary file is renamed over the original. On failure the temporary file is removed and the original is left as it was. A crash or a cancel during the write must not leave the original truncated.

### CBR

Saving metadata for a `.cbr`, and `convert_cbr(path, *, keep_cbr_original)`, both produce `Foo.cbz` beside `Foo.cbr`.

If `Foo.cbz` already exists, the operation raises `ConvertTargetExistsError`, writes nothing, and leaves the `.cbr` untouched.

Otherwise:

1. Extract the `.cbr` with `unar` into a temporary directory.
2. Write a temporary `.cbz` in the same directory as the `.cbr`, using the same member rules as a CBZ save. A metadata save applies `patch`. A convert applies an empty patch and `write_number` false, so existing ComicInfo is copied and no field is changed.
3. Read `ComicInfo.xml` back from the temporary `.cbz`. For a metadata save, the patched fields must match. For a convert, the read must succeed (an archive that had no ComicInfo reads back as an empty model).
4. Rename the temporary `.cbz` onto `Foo.cbz`.
5. When `keep_cbr_original` is false, delete `Foo.cbr` only after step 4. When it is true, leave `Foo.cbr` in place.

If a step before the rename fails, the temporary files are removed, `Foo.cbz` does not appear, and `Foo.cbr` is unchanged. If the `.cbz` is in place and deleting the `.cbr` fails, the `.cbz` stays and the error reports that the original could not be removed.

## Batch save

A batch save exists to stamp the same series-level ComicInfo onto every selected archive. `save_many(paths, patch, *, keep_cbr_original)` writes only these elements:

- `Series`
- `Publisher`
- `LanguageISO`
- `Genre`
- `Writer`
- `Penciller`
- `Inker`
- `CoverArtist`
- `Manga`

`Title`, `Number`, `Volume`, `Summary`, `PageCount`, `Pages`, dates, `Web`, `Notes`, `AgeRating`, and `CommunityRating` are not batch fields. `Number` is written per file by the shell, from that file's filename, through `save_comic_info` with `write_number` true. It is not a `save_many` key. If `patch` contains any other key, `save_many` raises `BatchFieldError` before it writes any file.

Each path is saved with `write_number` false and with that patch. The call runs sequentially. One path that raises leaves that file unchanged, records the failure, and continues with the remaining paths. Files already written stay written. There is no rollback.

The result is one entry per path, in order, with either the output path (the `.cbz` path after a CBR save) or the error type and message.

## Rename

`rename_in_directory(directory, template)` renames the `.cbz` and `.cbr` files directly in `directory`. It does not recurse, and it does not move a file into another directory. Archive bytes, including `ComicInfo.xml`, stay as they are. The rename reads `ComicInfo.xml` only.

The template is a filename stem. `{Series} v{Number:02}` is the template the action offers. On a `.cbz` whose `Series` is `Claymore` and whose `Number` is `1`, the new name is `Claymore v01.cbz`. The existing extension is kept, including its letter case. A template that itself ends in `.cbz` or `.cbr` is rejected with `RenameTemplateError` before any file is renamed. The extension is not part of the pattern.

A tag is `{` + an owned element name + `}`, optionally followed by `:` and a positive decimal width. Names match the model (`Series`, `Volume`, `Number`, and the other owned elements except `Pages`). `{Volume}` reads the `Volume` element. `{Number}` reads `Number`. The module does not substitute one for the other. `{Number:02}` zero-pads an integer value to at least that many digits, so `1` becomes `01` and `100` stays `100`. A fractional value matching `\d+(?:\.\d+)?` is kept as stored and the width is ignored, so `1.5` stays `1.5` and `1.50` stays `1.50`. Any other non-integer fails that file with `RenameFieldError`. An unknown tag, a width that is not a positive integer, an unclosed `{`, or a template whose stem is empty raises `RenameTemplateError` and renames nothing.

When `{stem}-poster.jpg` already sits beside the archive, the rename moves that poster to the new stem in the same directory. A missing poster does not fail the rename.

Each file is rendered from its own ComicInfo. A tag whose element is missing or blank fails that file with `RenameFieldError`. Characters that cannot appear in a filename (`/`, `\`, and NUL) are replaced with `-`. The stem is then stripped of leading and trailing spaces and dots. If the stem is empty, `.`, or `..`, that file fails with `RenameFieldError`.

`plan_rename(directory, template)` applies these rules and writes nothing. It does not move posters and does not read page bytes. Archive names and poster names are planned together before any rename. Two files that render to the same archive name both fail with `RenameConflictError`. A target archive that already exists and is not the source file fails that source with `RenameConflictError`. Two files whose posters would land on the same path, or a poster target that already exists and is not that file's current poster, fail those sources with `RenameConflictError`. A file whose rendered name is its current name is a success. The result has the same shape as `rename_in_directory`.

`rename_in_directory` uses that plan, then renames only the successes. A conflict leaves that archive and its poster in place. `os.replace` renames each remaining file inside `directory`, and moves its poster when one exists. One failed file does not stop the others and does not undo renames that already succeeded.

The result is one entry per archive, in filename order, with either the new path or the error type and message.

## Poster

`write_poster(path)` writes `{stem}-poster.jpg` in the same directory as the archive. The image is the cover page, encoded as JPEG with Pillow. The width is 600 pixels. The height keeps the cover’s aspect ratio, rounded to the nearest integer. A cover that is already narrower than 600 pixels is not enlarged. A cover with an alpha channel is composited onto white before encoding. A cover without alpha is encoded as it is. The quality is 85. The call reads that one page and does not modify the archive. An existing poster is replaced by writing a temporary file in the same directory and renaming it into place.

## Errors

| Exception | When |
| --- | --- |
| `UnreadableArchiveError` | The file is missing, not an archive, or a page index is outside the page list |
| `NoPageImagesError` | The archive opens and contains no page images |
| `MissingUnarError` | A CBR operation needs `unar` or `lsar` and either executable is absent. The message names `unar` |
| `ConvertTargetExistsError` | The `.cbz` beside a `.cbr` already exists |
| `BatchFieldError` | A batch patch contains an element outside the shared series set. Nothing is written |
| `RenameTemplateError` | The template is empty, includes an extension, or contains an unknown or unclosed tag. Nothing is renamed |
| `RenameFieldError` | A file’s ComicInfo has no text for a tag the template uses, a width is set and the value is neither an integer nor a decimal number, or the rendered stem is empty |
| `RenameConflictError` | The rendered name collides with another file in the directory |

All of these are subclasses of `ArchiveError`. None of them modify the source archive, except the CBR case where the new `.cbz` is already in place and only the delete of the `.cbr` failed. That failure is still an `ArchiveError`, and the message says the `.cbz` is complete and the `.cbr` is still present.

## Configuration

This specification adds no configuration keys.

Convert and CBR save take `keep_cbr_original` from the caller. The project default is `false`, as defined in [00-project-overview.md](00-project-overview.md): delete the `.cbr` after the `.cbz` has been written and read back. `true` keeps the `.cbr` next to the new `.cbz`.

The rename action takes the template from the caller. The template it offers is `{Series} v{Number:02}`. That string is not a TOML key.

Poster width is 600 pixels, JPEG quality is 85, and the matte is white. None of these is a TOML key. Pillow is the library that scales the cover.

## Testing

Tests are hermetic. They do not use the network, do not sleep, and do not read the developer’s config, index, or library. They do not open `src/Claymore/`. Archive fixtures are small files created under `tests/fixtures/` or in a temporary directory during the test. Tests that need `unar` or `lsar` skip when that executable is not on `PATH`. Every other test passes without them.

Instrument `zipfile.ZipFile` so each test can see which member bodies were read.

Cover at least:

- A CBZ whose central-directory order differs from filename order, with a nested folder, a non-ASCII character in that folder name, ZIP-stored page images, root `ComicInfo.xml`, a `Pages` list, and an unknown sibling element. Listing pages follows filename sort. `Page Image` indexes match that sort. Listing reads no member bodies. Reading ComicInfo reads only `ComicInfo.xml`. Reading one page reads only that page.
- The cover index is the `FrontCover` page when `Pages` says so, and `0` when `Pages` is missing or has no `FrontCover`.
- A metadata save copies image bytes, compression method, CRC, uncompressed size, and member names unchanged, including a deflated image and a stored image in the same archive. The output central-directory order matches the input, with `ComicInfo.xml` in its original position. A first save of a missing `ComicInfo.xml` writes that member first. A member name with a non-ASCII character has general-purpose bit 11 set. Unknown elements, unknown attributes, and `Pages` are still present and unchanged. The test does not decode image pixels.
- A patch that sets `Series` and omits `Volume` updates `Series` and leaves `Volume` in place. A patch that sets `Volume` to `None` removes `Volume`. `PageCount` changes only when the patch includes it.
- `write_number` false leaves `Number` unchanged even when the patch contains `Number`. `write_number` true writes `Number`.
- A missing `ComicInfo.xml` reads as an empty model. The first save creates the member with only the patched elements.
- Replacing the original happens by rename of a temporary file in the same directory. Forcing the write to fail before the rename leaves the original bytes intact and removes the temporary file.
- `save_many` with `Series`, `Writer`, and `Manga` updates those elements on each selected file and leaves `Title`, `Number`, and `Volume` as they were. A patch that also contains `Title` or `Number` raises `BatchFieldError` and writes neither file.
- `save_many` on two CBZs, with the second path unreadable, writes the first file and leaves the second path absent or unchanged. The first file’s new ComicInfo is still readable.
- `rename_in_directory` with `{Series} v{Number:02}` renames `old.cbz` to `Claymore v01.cbz` when `Series` is `Claymore` and `Number` is `1`, and the zip bytes are unchanged. `Number` `1.5` produces `Claymore v1.5.cbz`. An existing `old-poster.jpg` becomes `Claymore v01-poster.jpg`. A sibling with a blank `Number` stays at its old name. An archive in a subdirectory is not renamed. Two files that render to the same name both stay put. Two files whose posters would land on the same path both stay put. A template of `{Series} v{Number:02}.cbz` or `{NotAField}` raises `RenameTemplateError` and renames nothing.
- `plan_rename` with the same template returns the new path and does not rename the file or move the poster.
- `write_poster` reads only the cover page, writes a JPEG 600 pixels wide beside the archive, and leaves the archive bytes unchanged. A cover narrower than 600 pixels is not enlarged. A cover with an alpha channel encodes on white. The test may decode that JPEG.
- A `.cbr` whose `.cbz` sibling already exists is not extracted and is not deleted.
- When `unar` is on `PATH`, a convert writes a `.cbz`, reads `ComicInfo.xml` back, and deletes the `.cbr` when `keep_cbr_original` is false. With `keep_cbr_original` true, the `.cbr` remains. A CBR metadata save applies the patch in the new `.cbz`. When `unar` is absent, the CBR test is skipped and a CBZ save still passes. A unit test for `MissingUnarError` may stub the executable lookup so it does not depend on the developer machine.
- A unit test stubs the process runner. A list runs `lsar -json` and does not run `unar`. A one-member read runs `unar -quiet -no-directory -output-directory <temp> <archive> <member>`. `<temp>` is inside the archive's directory and is gone after the call, including when the stubbed command fails.

## Acceptance criteria

- Listing a CBZ, reading `ComicInfo.xml`, and reading one page use the central directory and the requested members only. They do not extract the CBZ to a directory.
- Reading order is sorted member names. It stays correct when the central directory is in a different order, when pages sit in a subdirectory, and when a spread is one file.
- The cover is the `FrontCover` page when that type is present, and the first page otherwise. Choosing it does not read every image.
- A metadata save replaces `ComicInfo.xml` and copies every other member unchanged, including compression method, page bytes, and central-directory order. Member names are marked UTF-8. `Pages` is not rebuilt. Unknown XML is still there after the save.
- The new CBZ is written to a temporary file in the same directory and renamed into place only after `ComicInfo.xml` reads back. A failed save does not truncate the previous file.
- `Number` is written only when `write_number` is true on a single-file save. `Volume` is written only when the patch includes it. A save never copies `Number` into `Volume` and never rewrites a stored `Manga` token on its own.
- `save_many` writes only `Series`, `Publisher`, `LanguageISO`, `Genre`, `Writer`, `Penciller`, `Inker`, `CoverArtist`, and `Manga`. Any other patch key, including `Number`, writes nothing. A failed file does not roll back files already written. The shell does not call `save_many`.
- Rename uses each file’s own ComicInfo, keeps the file in the same directory, keeps its extension, and does not change archive bytes. The offered template `{Series} v{Number:02}` produces `Claymore v01.cbz` from `Number` `1`, and `Claymore v1.5.cbz` from `Number` `1.5`. A blank tag or a name collision skips that file. Poster targets are part of the same plan. An invalid template renames nothing. An existing sibling poster moves with the archive. `plan_rename` writes nothing.
- `write_poster` writes `{stem}-poster.jpg` from the cover only, 600 pixels wide, on white when the cover has an alpha channel, without modifying the archive.
- Saving a `.cbr`, or converting one, produces a sibling `.cbz` and removes the `.cbr` only after that `.cbz` is complete and its `ComicInfo.xml` reads back. An existing sibling `.cbz` fails the convert and leaves the `.cbr` untouched. `keep_cbr_original` true keeps the `.cbr`.
- A CBR list is `lsar -json`. A one-member read is `unar -quiet -no-directory -output-directory` into a temporary directory beside the archive, and that directory is removed afterwards. A missing `unar` or `lsar` fails CBR operations with an error that names `unar`, and does not affect CBZ operations.
