---
description: Replace or insert an archive cover page by re-fetching the full-size catalog cover from ComicInfo Web and writing it as reading-order page 0.
status: active
---

# Cover from provider

This specification owns replacing or inserting the archive cover page from a catalog cover image. It extends [01-archives-and-comicinfo.md](01-archives-and-comicinfo.md), [03-metadata-providers.md](03-metadata-providers.md), [04-application-shell.md](04-application-shell.md), and [05-ui-design.md](05-ui-design.md).

Accepting a scrape match still only loads the form. These actions are explicit write jobs, like Convert: they download a cover and rewrite the archive immediately.

## Purpose

The archive's first page is often the right cover, but sometimes it is wrong or missing. When ComicInfo `Web` points at a known catalog series or issue, the user can:

- **Replace cover** — remove the current cover page member and write the provider's full-size cover as the new reading-order index `0`.
- **Insert cover** — keep every existing page and write the provider's full-size cover as the new reading-order index `0`.

## Identity

No cover URL is stored after a scrape accept. The job parses the volume's ComicInfo **`Web`** value (the form field when dirty, otherwise the indexed `web`):

| `Web` host / path | Provider | Match id |
| --- | --- | --- |
| `mangadex.org/title/{uuid}` | `mangadex` | MangaDex UUID |
| `anilist.co/manga/{id}` | `anilist` | Decimal digits |
| `myanimelist.net/manga/{id}` | `jikan` | Decimal digits |
| `comicvine.gamespot.com/.../4050-{id}/` | `comicvine` | Digits without the `4050-` prefix |
| `comicvine.gamespot.com/.../4000-{id}/` | `comicvine` | Digits without the `4000-` prefix (issue) |
| `nautiljon.com/mangas/{slug}.html` | `nautiljon` | Series slug |
| Nautiljon volume URL under that series | `nautiljon` | Series slug; volume number from the path |

An unparseable, blank, or unknown `Web` raises `ProviderResponseError` before any download. Provider enablement and Comic Vine / Nautiljon keys follow the same rules as `load` in [03-metadata-providers.md](03-metadata-providers.md).

When the form (or index) `Number` is non-blank, it is passed to cover resolve so providers that have per-volume covers can prefer that image (MangaDex `cover_art.volume`, Nautiljon volume cover, Comic Vine issue image when `Web` is an issue URL or number resolves). AniList and Jikan always use the series cover.

## Resolve and download

```text
parse_web(web) -> { provider, match_id, issue_id? }
resolve_cover(provider, match_id, *, number="", issue_id="", …) -> CoverRef
```

`CoverRef` has `url` (absolute HTTPS full-size image URL) and `filename` (basename for the archive member leaf).

| Provider | Full-size URL | Filename |
| --- | --- | --- |
| MangaDex | `https://uploads.mangadex.org/covers/{id}/{fileName}` without `.256.jpg` | `fileName` |
| AniList | `coverImage.extraLarge`, else `large` | URL basename |
| Jikan | `images.jpg.image_url`, else `small_image_url` | URL basename |
| Comic Vine | `super_url` then `medium_url` / `small_url` / `thumb_url` | URL basename |
| Nautiljon | Volume `cover` when a volume is resolved, else series cover | URL basename |

A missing cover URL raises `ProviderResponseError`. Download uses the same allow-listed HTTPS GET as remote covers, with hosts extended for AniList, MyAnimeList, and Comic Vine CDNs. Redirect destinations are checked before requesting them. Before writing, Pillow must decode the downloaded image; an empty, corrupt, or unsupported image fails the job and leaves the archive unchanged. The filename must have a supported page-image extension.

Downloaded covers written by Replace or Insert are always JPEG, with a `.jpg` filename. Detect the format from the decoded bytes, not the URL extension or HTTP media type. Keep valid JPEG bytes unchanged to avoid recompression. Convert supported non-JPEG images (WebP, PNG, GIF) to RGB JPEG at quality 95 with no chroma subsampling, without resizing. Apply EXIF orientation during conversion, flatten transparency onto white, and use the first frame of animated images. Preserve the provider filename stem, changing its extension to `.jpg` before choosing the reading-order prefix. Conversion failures leave the original archive unchanged. This applies equally to CBZ writes and CBR conversion; existing retained pages are not converted.

When MangaDex's expanded manga relationship does not contain the requested volume, query the paginated `/cover` list with `manga[]`, `limit`, and `offset` before falling back to its series cover ([official API schema](https://api.mangadex.org/docs/static/api.yaml)).

## Archive write

```text
replace_cover_page(path, image_bytes, filename, *, keep_cbr_original) -> Path
insert_cover_page(path, image_bytes, filename, *, keep_cbr_original) -> Path
```

Both return the archive path that holds the pages (the `.cbz` after a CBR convert).

### Member name (reading-order index 0)

Reading order is still sorted member names ([01-archives-and-comicinfo.md](01-archives-and-comicinfo.md)).

1. List pages. Replace removes the member at `resolve_cover_index`. Insert removes nothing.
2. Directory = the parent path of the current cover member (or of page `0`), including a trailing `/`, or empty when that page is at the archive root. Insert uses the current cover's directory too.
3. Leaf = sanitized scraper `filename` with its extension normalized to `.jpg` (no `/`, `\`, or `..`; empty after sanitize fails).
4. Candidate = `{directory}{leaf}`. Prepend `!` as needed to make it strictly less than every remaining page name under Unicode code-point order (backslashes normalized to `/`). If the directory itself sorts after another page, use the archive root instead. For names starting with characters before `!`, a space prefix is allowed at the root. Name selection is bounded and fails without writing if no safe name can sort first. Avoid collisions with all retained members, including directories. The scraper's filename stem with `.jpg` stays the suffix.

### Zip write

Atomic temp sibling → verify → rename, as in metadata save. Existing members that are kept are copied with the same compressed bytes, compression method, CRC, and sizes (performance rule 2). The new cover is added as ZIP stored. Root `ComicInfo.xml` is rewritten:

- `PageCount` = new page-image count.
- `Pages`: set `Type="FrontCover"` on `Image="0"`; clear `FrontCover` from other `Page` entries.
  - **Insert**: bump every existing numeric `Image` by 1, then add the FrontCover at `0`.
  - **Replace**: drop the `Page` whose `Image` equals the removed index; remap remaining indices so that old index `i < removed` becomes `i + 1`, and old `i > removed` stays `i`; then ensure FrontCover at `0`.

Preserve unrelated XML, including unknown attributes and children on retained `Page` entries and on `Pages`. Unsafe member paths must not escape the extraction directory during CBR conversion.

CBR inputs follow the same convert-then-write path as `save_comic_info`, including `keep_cbr_original` and `ConvertTargetExistsError`.

Replace requires at least one page image. Insert may run on an archive that already has pages; an archive with no pages still raises `NoPageImagesError` (the app is not a blank-archive builder).

## Shell and API

One-volume mode only. `POST /api/jobs/cover` body:

```json
{ "path": "<absolute archive>", "action": "replace" | "insert", "web": "<url>", "number": "<optional>" }
```

`web` and `number` come from the current form when present so an unsaved `Web` / `Number` still works. The path must be absolute and inside a library root.

The job name is `Cover`. Progress is `0/1` then `1/1`. Cancel is checked before resolve and before the archive write. On success the job calls `write_poster` when `write_poster_on_save` is true, then `refresh_volume` (and lock copy / `forget_volume` when the path changes after CBR convert). The client refetches the library on terminal Cover like Save/Convert.

Toast: success `Cover updated.` / failure uses `error_message` or `Cover failed.`

## UI

On the inspector page preview, when the shown page is the cover index (or `0` when cover is null) and the form mode is `one`, two quiet overlay controls sit over the image frame: **Replace cover** and **Insert cover**. They are disabled when `Web` does not parse, its provider is disabled or lacks required configuration, a job is busy, or there are no pages. They do not appear in multi-select mode.

After the job, refresh the preview at the cover index and invalidate the affected thumbnail URL. Retain unsaved form edits, including `Web` and `Number`, while refreshing unedited fields such as `PageCount`; the cover job does not save those edits. This also applies when a CBR becomes a CBZ. Show Cover progress and Cancel in the header.

## Configuration

This specification adds no TOML keys. It uses `keep_cbr_original`, `write_poster_on_save`, `enabled_providers`, `comicvine_api_key`, `nautiljon_base_url`, and `nautiljon_api_key` from [00-project-overview.md](00-project-overview.md).

## Open questions

All resolved.

- **Where does the cover URL come from?** Re-fetch from the provider using identity parsed from ComicInfo `Web` (and `Number` when useful). Not from a URL kept after accept.
- **Filename vs reading order?** Use the scraper's basename as the leaf, in the current cover directory when possible, with the bounded root/prefix fallback described above so the member sorts as reading-order index `0`.

## Testing

Hermetic tests. No network; `httpx.MockTransport` for resolve and download. Archive fixtures under `tests/`.

Cover at least:

- `parse_web` for each provider URL shape; blank and unknown hosts fail.
- MangaDex `resolve_cover` omits `.256.jpg` and prefers a `cover_art` whose `volume` matches `Number` when present.
- AniList prefers `extraLarge` over `large`.
- Insert: new member is reading-order `0` with the scraper basename, or `!` + basename when needed; page count increases by 1; other members' compressed bytes unchanged; `FrontCover` is Image `0`; `PageCount` matches.
- Replace: old cover member is gone; page count unchanged; new cover is index `0`.
- JPEG payloads are preserved byte-for-byte; WebP, PNG, and GIF become real JPEG bytes with `.jpg` names, full resolution, white transparency, and correct orientation, even when extensions are misleading.
- Failed download or image conversion leaves the archive bytes unchanged.
- Cancel before the write leaves the archive unchanged.
- Cover job refreshes the index path; CBR convert path respects `keep_cbr_original`.
- Folder-order edge cases terminate, corrupt images and verification failures leave originals untouched, and retained XML extensions survive.
- UI enablement respects provider configuration; terminal Cover jobs refresh the shelf and preserve dirty fields; errors and cancellation never show a success toast.

## Acceptance criteria

- Replace and Insert re-fetch a full-size cover from the provider identified by `Web`, download it, and atomically rewrite the CBZ (or convert a CBR) so that image is reading-order page `0`.
- The new cover is JPEG with a `.jpg` extension and retains the scraper's filename stem, using the current cover's directory when possible and the documented fallback when necessary for sort order.
- Existing kept page members are not recompressed. The write is atomic.
- ComicInfo `PageCount` and `Pages` / `FrontCover` match the new page list.
- The inspector shows Replace cover and Insert cover overlays on the cover preview in one-volume mode when `Web` parses.
- A Cover job success refreshes the shelf and optional poster; failure and cancel do not toast as success.
