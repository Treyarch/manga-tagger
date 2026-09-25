---
description: After a series match, list issues or volumes and load one by picker or by form Number, ComicTagger-style.
status: active
---

# Select Issue

This specification owns listing issues or tankōbon volumes for a selected series candidate, the Matches **Select Issue** action, the Issues dialog, and how `load` resolves an issue by id or by number. It extends [03-metadata-providers.md](03-metadata-providers.md), [04-application-shell.md](04-application-shell.md), and [05-ui-design.md](05-ui-design.md). Archive writes stay in [01-archives-and-comicinfo.md](01-archives-and-comicinfo.md).

## Providers that list issues

| Provider | Lists | Load by issue |
| --- | --- | --- |
| Comic Vine | Yes — issues of the selected volume | Yes — `GET /issue/4000-{id}/` |
| Nautiljon | Yes — tankōbon from series `volumeUrls` | Yes — series load + `GET …/volumes/{number}` |
| MangaDex | No | Series load only (unchanged) |
| AniList | No | Series load only (unchanged) |
| Jikan | No | Series load only (unchanged) |

Unsupported catalogs return an empty issue list and send no request. That is success, not an error.

## IssueCandidate

An `IssueCandidate` has `id`, `number`, `title`, `date`, `cover`, and `summary`, all strings.

| Field | Meaning |
| --- | --- |
| `id` | Comic Vine issue id (decimal digits, no `4000-` prefix), or Nautiljon volume number as a decimal string |
| `number` | Display and match key (`issue_number` or tankōbon number) |
| `title` | Issue or volume title when known, otherwise `""` |
| `date` | `YYYY-MM` when a cover or release month is known, else a four-digit year, else `""` |
| `cover` | Absolute HTTPS cover URL, or `""` |
| `summary` | Plain synopsis (HTML-stripped), or `""` |

A hit with a blank `id` or blank `number` is dropped. Order is API order for Comic Vine and `volumeUrls` order for Nautiljon. An empty list is not an error.

## list_issues

```text
list_issues(provider, series_id, *, title_languages, api_key="", nautiljon_base_url="", nautiljon_api_key="", client, cancel=None) -> list[IssueCandidate]
```

Call order matches `load` for provider name, blank/illegal `series_id`, Comic Vine key, Nautiljon settings, and `cancel`. MangaDex, AniList, and Jikan return `[]` after those checks and before any HTTP.

### Comic Vine

Paginated `GET https://comicvine.gamespot.com/api/issues/` with `api_key`, `format` `json`, `filter` `volume:{series_id}`, `field_list` `id,issue_number,name,image,cover_date,description`, `limit` `100`, and `offset` starting at `0`. After each page, if more results remain (`number_of_total_results` and page size), raise `offset` by the page size and request again. `cancel` is checked before every request.

Each result becomes an `IssueCandidate`: `id` from `id`, `number` from `issue_number` (trimmed string; integers become decimal text), `title` from `name`, `date` from `cover_date` as `YYYY-MM` when that prefix is present otherwise the four-digit year when present, `cover` from `image` with the same URL preference as search (`super_url`, `medium_url`, `small_url`, `thumb_url`), `summary` from `description` HTML-stripped. HTTP and Comic Vine status rules match search/load.

### Nautiljon

`GET {base}/v1/series/{slug}` (same as series load). Parse each string in `volumeUrls`:

- Path matching `/volume-{n},{digits}.html` → number `n`
- Else legacy path `/mangas/volumes/…,{n}.html` (no `/volume-` in the path) → number `n`

`id` and `number` are the decimal string of `n` with leading zeros dropped on the integer part (`01` → `1`). Duplicate numbers keep the first. A URL that does not match is skipped. Missing or non-list `volumeUrls` yields `[]`.

For each remaining number, `cancel` is checked and then `GET {base}/v1/series/{slug}/volumes/{n}` runs to enrich the row. `title` is `Tome {n}`. When the volume response is OK, `date` is `releaseDateVf` as `YYYY-MM` when that string matches `DD/MM/YYYY`, otherwise `""`; `summary` is `description` HTML-stripped; and `cover` is `cover` when that string is a non-blank absolute HTTPS URL, otherwise `""`. A volume HTTP 404 leaves `date`, `summary`, and `cover` as `""` and is not an error for the list. Any other volume HTTP error raises `ProviderResponseError` and stops the list. The Issues dialog falls back to the series candidate cover when the row `cover` is blank.
## load with issue_id and number

```text
load(provider, match_id, *, filename_stem, title_languages, api_key="", nautiljon_base_url="", nautiljon_api_key="", client, cancel=None, issue_id="", number=None) -> dict[str, str]
```

`issue_id` defaults to `""`. `number` defaults to `None` (caller omitted a preferred number).

### Unsupported providers (MangaDex, AniList, Jikan)

Behavior is unchanged from [03-metadata-providers.md](03-metadata-providers.md): series `load`, then `Number` from `parse_number(filename_stem)` when that returns a string. `issue_id` and `number` are ignored.

### Comic Vine

1. When `issue_id` is non-blank after trim: validate it like a Comic Vine numeric id. Fetch `GET …/api/issue/4000-{issue_id}/` with `field_list` `id,issue_number,name,description,cover_date,site_detail_url,person_credits,volume,image`. Build the patch from the issue: `Series` from `volume.name` when that object has a non-blank name, else the issue `name`; `Title` equals `Series` when the issue has no usable `name`, otherwise the issue `name`; `Number` from `issue_number`; `Summary` from description; dates from `cover_date` (`YYYY-MM-DD` or `YYYY-MM` or year); `Web` from `site_detail_url`; credits from `person_credits` with the same role rules as volume load; `Manga` `No`. Publisher is omitted from the issue payload unless a follow-up is unnecessary — when `volume` includes no publisher, omit `Publisher`. A missing usable series title (neither volume name nor issue name) raises `ProviderResponseError`.
2. When `issue_id` is blank: take the preferred number as trimmed `number` when that argument is a non-blank string, else `parse_number(filename_stem)`. When that preferred number is missing, raise `ProviderResponseError` with message `comicvine: could not find an issue`. Call `list_issues` for `match_id`, find the first issue whose `number` equals the preferred number after normalizing leading zeros on the integer part (same rule as `parse_number` storage). When none match, raise `ProviderResponseError` with message `comicvine: could not find an issue`. Then load that issue as in step 1 (`issue_id` = matched `id`).

### Nautiljon

1. When `issue_id` is non-blank: it must be digits with integer value at least `1` (same rule as today's volume fetch). Series load runs as today, then the volume page for that number is requested. A volume HTTP 404 raises `ProviderResponseError` with message `nautiljon: could not find an issue` (unlike the silent 404 when enriching from filename alone on unsupported-style series OK paths — here an explicit issue id must resolve). Set patch `Number` to that volume number string.
2. When `issue_id` is blank: preferred number is trimmed `number` when non-blank, else `parse_number(filename_stem)`. When missing, or not a positive integer string, raise `ProviderResponseError` with message `nautiljon: could not find an issue`. Otherwise behave as step 1 with that number as `issue_id`. Fractional filename numbers still skip the volume GET only on the old series-only path; for Nautiljon issue resolve they fail with could not find an issue.

For Nautiljon Select Issue / OK-by-number, a volume 404 is an error. The legacy series scrape path that only had `filename_stem` without going through issue resolve is replaced for Nautiljon by this resolve path when the shell always passes preferred `number` or empty `issue_id` through the new rules above.

Clarification for Nautiljon OK: the shell always uses issue resolve (preferred number or stem). There is no separate “series-only OK” for Nautiljon once this specification is active. MangaDex/AniList/Jikan remain series-only on OK.

## Shell and jobs

`POST /api/jobs/issues` body `{ "provider", "match_id" }` runs `list_issues` with the same config and client rules as search/load. Progress is `0/1` then `1/1`. Result is `{ "issues": [{ "id", "number", "title", "date", "cover", "summary" }] }`. Job name is `Issues`.

`POST /api/jobs/load` body gains optional `issue_id` (default `""`). The job derives preferred `number` from the form: when form `Number` is non-blank and not mixed, that trimmed value; otherwise `None` so the provider falls back to `parse_number(filename_stem)`. It passes `issue_id` and that `number` into `load`.

Search and Issues progress live in the Matches / Issues dialogs, not the header. A failed Issues job leaves Matches open. An empty Issues result is success; the client toasts `No issues available.` and does not open the Issues dialog (or closes it if it was showing a loading state).

| Job | Success toast | Failure toast |
| --- | --- | --- |
| Issues | `No issues available.` when the list is empty; otherwise no toast (Issues dialog opens) | `error_message`, or `Issues failed.` when blank |

Load success still toasts `Metadata loaded.` and clears candidates (and issues) so both dialogs close. A failed load with Matches still open leaves candidates; if Issues was open it stays open until dismiss.

Preferred number for OK: form `Number` when non-blank and not mixed, else filename stem via provider `parse_number`.

## UI

Matches footer actions, leading to trailing: secondary **Select Issue**, secondary **Cancel**, primary **OK**.

- **OK** / Enter: start Load for the highlighted series id without `issue_id` (number from form/stem).
- **Select Issue** / double-click on a series row: start the Issues job for that id. While Issues is queued or running, Matches shows busy (Select Issue and OK disabled) or the client may show the Issues dialog in a loading state; either is acceptable if Cancel on Matches can still dismiss and cancel.
- Dismiss Matches clears candidates and issues and cancels a running Search or Issues job started from that flow.

Issues dialog (`IssuesDialog.svelte`), `xl` size, title `{Series} ({Year}) - Select Issue` using the highlighted candidate's title and year (omit ` (Year)` when year is blank). Lucide `ListOrdered` (or `ScanSearch`) as the title icon. Body: loading spinner `Loading issues…`, or the same two-column layout as Matches with table columns **Issue** / **Date** / **Title**, cover left, summary below the table. Preselect the row whose `number` matches the preferred number (form or stem); if none, the first row. OK / double-click / Enter starts Load with that `issue_id`. Cancel closes Issues only and returns to Matches with candidates kept.

Cover proxy rules for issue covers match Matches (MangaDex and Nautiljon hosts through `/api/cover`; Comic Vine uses the direct URL). When an issue row has a blank `cover`, the Issues dialog shows the series candidate cover instead.

## Configuration

This specification adds no configuration keys.

## Testing

Hermetic MockTransport tests. Cover at least:

- Comic Vine `list_issues` returns candidates from one or more pages; blank key raises `ProviderUnavailableError` with no request.
- Comic Vine `load` with `issue_id` hits `/issue/4000-…` and sets `Number` from `issue_number`.
- Comic Vine `load` without `issue_id` matches preferred `number` (and form-preferred number over stem when the shell passes it); missing or unmatched number raises `ProviderResponseError` (`could not find an issue`).
- Nautiljon `list_issues` parses `volumeUrls`, sets `title` to `Tome {n}`, and enriches `date`/`summary`/`cover` from each volume page (volume 404 leaves those blank); `load` with `issue_id` `"2"` requests volumes/2 and sets `Number` `2` and `CommunityRating` from `rating` when present; volume 404 raises could not find an issue when resolving by issue.
- MangaDex, AniList, and Jikan `list_issues` return `[]` with no HTTP.
- Issues job returns `{ "issues": [...] }`; empty list is success.
- Load job passes `issue_id` through; preferred number from non-blank form `Number`.

## Acceptance criteria

- Matches always shows **Select Issue**. Double-click opens the issue flow; OK loads by number (or series-only on unsupported catalogs).
- Comic Vine and Nautiljon can list issues/volumes and load one by id or by preferred number.
- MangaDex, AniList, and Jikan return an empty issue list; the client toasts `No issues available.`
- A successful issue or number load merges a form patch and does not write an archive. `Number` comes from the chosen issue/volume when that path ran.
- Cancel checks run before each new HTTP request. Multi-volume save still ignores patch `Number` per the shell shared-field rules.
