---
description: Search one catalog, pick a series title, and return a ComicInfo form patch without writing the archive.
status: proposed
---

# Metadata providers

This specification owns the scrape query, the volume number parsed from a filename, and the four catalogs: MangaDex, AniList, MyAnimeList through Jikan, and Comic Vine. An accepted match is a form patch. It implements performance rule 8 from [00-project-overview.md](00-project-overview.md), and the cancel check the application shell uses for the scrape clause of performance rule 7.

The core lives in `src/manga_tagger/providers/` and imports without FastAPI and without pywebview. Callers pass `title_languages`, the Comic Vine key, an `httpx.Client`, and an optional `cancel` callable. This module does not read the TOML config file, does not open an archive, and does not start a thread.

Archive writes stay in [01-archives-and-comicinfo.md](01-archives-and-comicinfo.md). The window, the provider picker, and which patch keys a multi-volume save keeps belong to the application-shell specification.

## Query and number

`build_query(series, filename_stem)` returns the search string. `parse_number(filename_stem)` returns the tankōbon number or `None`. Both are pure. Neither takes a path.

`filename_stem` is the filename with its extension already removed. This module does not strip `.cbz` or `.cbr`. A non-blank `series` is the query after trimming whitespace. Characters inside that name stay, including digits. `20th Century Boys` stays `20th Century Boys`. A blank or whitespace-only `series` uses the filename stem after the tag and marker removal below.

`parse_number` always reads the filename stem, including when `series` is the query. No marker means `None`, and `load` then omits `Number`.

### Release tags

Tag removal is applied to a working copy of the stem.

1. Trim whitespace.
2. Repeatedly remove a `[`…`]` span whose interior contains neither `[` nor `]`. An empty interior is removed. A `[` with no closing `]` stops this step.
3. Repeatedly remove a `(`…`)` span whose interior contains neither `(` nor `)`, when that interior with whitespace trimmed is a 4-digit year or, case-insensitively, one of `digital`, `digital-hd`, `web`, `c2c`, `raw`, `fixed`, `fr`, `en`, `jp`, `jap`, `vf`, `vo`. Any other parenthetical stays. A `(` with no closing `)` stops this step.
4. Collapse ASCII whitespace to a single space and trim.

Brackets are removed before parentheses, so a parenthetical inside brackets is removed with the brackets.

### Volume marker

On the tag-stripped stem, the first matching suffix wins. Matching is case-insensitive. The pattern must end at the end of the stem. Separators are space, `.`, `_`, and `-`.

| Order | Suffix |
| --- | --- |
| 1 | separator or start, then `volume` or `vol`, optional `.`, optional separators, then the number |
| 2 | separator or start, then `tome`, optional `.`, optional separators, then the number |
| 3 | separator or start, then `v`, optional separators, then the number |
| 4 | separator or start, then `t`, optional `.`, optional separators, then the number |
| 5 | separator or start, then `#`, optional separators, then the number |
| 6 | a separator, then the number |

The number token is digits with an optional fractional part: `\d+(?:\.\d+)?`. Order 6 requires a separator. A stem that is only digits does not match it.

`vol` is tried before bare `v`, and `tome` before bare `t`, so `vol.2` and `tome 3` are not read as `v` or `t`. A chapter marker such as `c01` is not a volume marker. It matches none of these suffixes.

The stored number drops leading zeros on the integer part. `01` becomes `1`. `1.5` stays `1.5`. `1.50` stays `1.50`. `0` and `00` stay `0`. `0.5` stays `0.5`.

The query remainder is the tag-stripped stem without that matched suffix, including the separator that belonged to the match. Trailing spaces, `.`, `_`, and `-` are then removed, and ASCII whitespace is collapsed. An empty remainder is the query `""`.

| Stem | Query when `series` is blank | Number |
| --- | --- | --- |
| `[Group] Claymore v02 (Digital)` | `Claymore` | `2` |
| `Claymore Tome 03` | `Claymore` | `3` |
| `Claymore T.01` | `Claymore` | `1` |
| `Foo (Bar) v01` | `Foo (Bar)` | `1` |
| `Monster 01` | `Monster` | `1` |
| `Claymore_Vol_02` | `Claymore` | `2` |
| `20th Century Boys v01` | `20th Century Boys` | `1` |
| `v01` | `""` | `1` |
| `Claymore` | `Claymore` | `None` |

`build_query("20th Century Boys", "20th Century Boys v01")` returns `20th Century Boys`. `parse_number("20th Century Boys v01")` returns `1`.

## Search and load

The caller chooses one provider: `mangadex`, `anilist`, `jikan`, or `comicvine`. Any other name raises `ProviderResponseError` and sends no request.

```text
search(provider, query, *, title_languages, api_key="", client, cancel=None) -> list[Candidate]
load(provider, match_id, *, filename_stem, title_languages, api_key="", client, cancel=None) -> dict[str, str]
```

A `Candidate` has `id`, `title`, and `detail`, all strings. `id` is the catalog id in decimal digits for AniList, Jikan, and Comic Vine, and the MangaDex UUID for MangaDex. `title` is the preferred series title. `detail` joins, with `, `, the year and the first credit the search payload actually has. The credit is the first author for MangaDex and Jikan, the first staff name for AniList, and the publisher name for Comic Vine. A missing part is left out. When both are missing, `detail` is `""`.

At most 10 hits are requested. That limit is a constant. A hit with no usable title is dropped. The module then keeps at most the first 10 remaining hits, in API order. An empty list is not an error.

`search` does not call `load`. `load` fetches one series record and returns the form patch. Patch keys are ComicInfo element names. A value is a string. A field the catalog does not have is absent, not `""`.

`load` adds `Number` when `parse_number(filename_stem)` returns a string. It never adds `Volume`, `Pages`, `PageCount`, `AgeRating`, `CommunityRating`, or `Notes`. `Series` and `Title` are the same preferred title. A record with no usable title raises `ProviderResponseError` and does not return a partial patch.

The patch is what one accepted match loads into the form. It may include `Title`, `Number`, `Summary`, `Manga`, `Web`, `Year`, `Month`, and `Day`. Those are not batch-save fields. This module does not call `save_comic_info` or `save_many`. The application shell decides which keys a later save writes.

`match_id` must be non-blank and must not contain `/`, `?`, `#`, or whitespace. AniList, Jikan, and Comic Vine ids must also be decimal digits with no sign and no leading zero unless the id is `0`. A bad id raises `ProviderResponseError` before any request. The Comic Vine URL adds the `4050-` prefix. The stored id does not include it.

### Call order

`search` does this, and stops at the first step that applies:

1. Unknown provider: `ProviderResponseError`.
2. `query` blank after trim: return `[]`.
3. Comic Vine with `api_key` blank after trim: `ProviderUnavailableError`.
4. `cancel` is not `None` and returns true: `ProviderCancelledError`.
5. Send one request.

`load` uses the same order, except step 2 is a blank or illegal `match_id`, which raises `ProviderResponseError`. An empty search query does not check the key and does not call `cancel`.

`cancel` is checked once, immediately before the request. A request already started is not aborted.

## Titles

`title_languages` is walked in order, then the original title. Comparison is exact. `fr` does not match `FR`. An empty list skips straight to the original title. The first non-blank title wins. `LanguageISO` is set only when the rule below names a code.

| Provider | `title_languages` slots | Original title | `LanguageISO` |
| --- | --- | --- | --- |
| MangaDex | Exact key in `attributes.title`, then the same key in `altTitles` in list order | The `originalLanguage` key, looked up the same way. If that is missing, the first non-blank value in `attributes.title` | The code of the chosen entry |
| AniList | `en` is `title.english`. Every other code, including `fr`, has no slot and is skipped | `title.native`, else `title.romaji` | `en` when the English title was chosen. For native, `JP` is `ja`, `KR` is `ko`, `CN` is `zh`, and `TW` is `zh`. Any other country, and a romaji fallback, omit `LanguageISO` |
| Jikan | `fr` is a title whose `type` is `French`. `en` is `English`. Every other code is skipped | `type` `Japanese`, else `type` `Default` | `fr`, `en`, or `ja` for those three types. `Default` omits `LanguageISO` |
| Comic Vine | No language slots. `name` is the title | `name` | Omitted |

MangaDex, AniList, and Jikan set `Manga` to `YesAndRightToLeft`. Comic Vine sets `Manga` to `No`.

## Shared field rules

Several names are joined with `, ` in API order. A blank name is skipped. The same name is not repeated in one field.

Summary text is plain. The module does not render Markdown. Given a string, it unescapes HTML entities, replaces U+00A0 with a normal space, removes tags matching `<[^>]*>`, collapses whitespace to a single space, and trims. An empty result omits `Summary`. A non-string omits it.

`Year`, `Month`, and `Day` are decimal strings with no zero padding. Each component is set only when that component is present. `6` stays `6`.

## MangaDex

Base URL `https://api.mangadex.org`. Search is `GET /manga`. Load is `GET /manga/{id}`.

Search query parameters:

- `title` is the query
- `limit` is `10`
- `order[relevance]` is `desc`
- `contentRating[]` is `safe`, `suggestive`, `erotica`, and `pornographic`, repeated
- `includes[]` is `author`

Load repeats `includes[]` as `author` and `artist`.

The search body is `data` as a list. The load body is one manga object in `data`, and `result` is `ok`. Anything else on load raises `ProviderResponseError`. A search whose `data` is `[]` returns no candidates. A missing `data` raises `ProviderResponseError`.

| Patch key | Source |
| --- | --- |
| `Series`, `Title` | Preferred title |
| `LanguageISO` | Code of the chosen title |
| `Genre` | Tags whose `attributes.group` is `genre`, in response order. The name is `attributes.name.en` when that string is non-blank, otherwise the first non-blank name. Tags in other groups are ignored |
| `Summary` | `attributes.description`, using `title_languages`, then `originalLanguage`, then `en`, then the first remaining non-blank value. HTML-stripped |
| `Year` | `attributes.year` when it is an integer. Month and day are omitted |
| `Writer` | Relationships of type `author`, `attributes.name` |
| `Penciller`, `CoverArtist` | Relationships of type `artist`, `attributes.name`. Both keys receive that same list. Authors are not copied into either key |
| `Web` | `https://mangadex.org/title/{id}` |
| `Manga` | `YesAndRightToLeft` |

`Publisher` is omitted. A relationship with no `attributes` is skipped. The candidate detail uses `attributes.year` and the first author name.

## AniList

Search and load are `POST https://graphql.anilist.co` with `Content-Type: application/json` and `Accept: application/json`. The body is `{"query": ..., "variables": ...}`.

Search:

```graphql
query ($search: String) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      startDate { year }
      staff(perPage: 1, sort: RELEVANCE) {
        edges { node { name { full } } }
      }
    }
  }
}
```

Load:

```graphql
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    id
    title { romaji english native }
    description
    genres
    siteUrl
    countryOfOrigin
    startDate { year month day }
    staff(perPage: 25, sort: RELEVANCE) {
      edges { role node { name { full } } }
    }
  }
}
```

HTTP 200 with a non-empty `errors` array raises `ProviderResponseError`. Search uses `data.Page.media`. `null` or `[]` returns no candidates. Load uses `data.Media`. `null` raises `ProviderResponseError`.

| Patch key | Source |
| --- | --- |
| `Series`, `Title` | Preferred title |
| `LanguageISO` | From the title rule |
| `Genre` | `genres` joined in list order |
| `Summary` | `description`, HTML-stripped. AniList has one description, not one per language |
| `Year`, `Month`, `Day` | `startDate` components that are integers |
| `Writer` | Staff whose `role`, compared case-insensitively, contains `story` or `creator` |
| `Penciller`, `CoverArtist` | Staff whose `role` contains `art` or `illustrat`. Both keys receive that same list |
| `Web` | `siteUrl` |
| `Manga` | `YesAndRightToLeft` |

`Publisher` is omitted. One role can fill both credit groups. `Story & Art` is `Writer`, `Penciller`, and `CoverArtist`. The candidate detail uses `startDate.year` and the first staff name.

## Jikan

Search is `GET https://api.jikan.moe/v4/manga` with `q`, `limit` `10`, and `sfw` `false`. Load is `GET https://api.jikan.moe/v4/manga/{id}/full`.

Search reads `data` as a list. Load reads `data` as one object. A missing load `data`, or load `data` that is not an object, raises `ProviderResponseError`. Search `data` of `[]` returns no candidates.

| Patch key | Source |
| --- | --- |
| `Series`, `Title` | Preferred title from `titles` |
| `LanguageISO` | From the title rule |
| `Publisher` | `serializations[0].name` when that list is non-empty and the name is non-blank |
| `Genre` | `genres[].name` in list order. Themes, demographics, and explicit genres are not included |
| `Summary` | `synopsis`, HTML-stripped |
| `Year`, `Month`, `Day` | `published.prop.from` components that are not null. A missing `published`, `prop`, or `from` omits all three |
| `Writer` | `authors` whose `type`, compared case-insensitively, contains `story` |
| `Penciller`, `CoverArtist` | `authors` whose `type` contains `art`. Both keys receive that same list |
| `Web` | `url` |
| `Manga` | `YesAndRightToLeft` |

`Story & Art` fills `Writer`, `Penciller`, and `CoverArtist`. The candidate detail uses `published.prop.from.year` and `authors[0].name`.

## Comic Vine

Search is `GET https://comicvine.gamespot.com/api/search/` with `api_key`, `format` `json`, `resources` `volume`, `query`, `limit` `10`, and `field_list` `id,name,start_year,publisher`.

Load is `GET https://comicvine.gamespot.com/api/volume/4050-{id}/` with `api_key`, `format` `json`, and `field_list` `name,start_year,publisher,description,deck,site_detail_url,person_credits`.

No issue is requested. A blank key raises `ProviderUnavailableError` before this request. The message says the Comic Vine API key is not set.

HTTP 200 is still an error when `error` is not `OK` or `status_code` is not `1`. Search `results` of `null` or `[]` returns no candidates. Load `results` must be an object. `null` or a list raises `ProviderResponseError`.

| Patch key | Source |
| --- | --- |
| `Series`, `Title` | `name` |
| `Publisher` | `publisher.name` when `publisher` is an object and the name is non-blank |
| `Summary` | `description` after HTML stripping. When that is empty, `deck` after HTML stripping |
| `Year` | `start_year` when it is present. An integer becomes its decimal string. A string is trimmed, and a blank string is omitted. Month and day are omitted |
| `Web` | `site_detail_url` |
| `Writer` | `person_credits` whose role piece is `writer` |
| `Penciller` | Role piece `penciler`, `penciller`, or `artist` |
| `Inker` | Role piece `inker` |
| `CoverArtist` | Role piece `cover` or `cover artist` |
| `Manga` | `No` |

`LanguageISO` is omitted. A role is split on commas. Each piece is trimmed and compared case-insensitively, as a whole piece. `writer, artist` fills `Writer` and `Penciller`. It does not fill `CoverArtist`. `artist` is not copied into `CoverArtist`. The candidate detail uses `start_year` and `publisher.name`.

## HTTP

Every request sets `User-Agent` to `manga-tagger`, including when the client already has another default. The module does not build a client and does not set a timeout. The application shell builds the client with a 15 second timeout. Tests pass their own client.

There is no sleep and no retry. `httpx.TransportError`, including timeouts, raises `ProviderTimeoutError`. An HTTP response is not a transport error. Status 429 raises `ProviderRateLimitError` before the body is read as a success. Any other status of 400 or higher, a body that is not JSON, and a JSON body that fails the rules above raise `ProviderResponseError`.

## Errors

| Exception | When |
| --- | --- |
| `ProviderUnavailableError` | The provider is `comicvine` and `api_key` is blank. The message says the Comic Vine API key is not set. No request is sent |
| `ProviderCancelledError` | `cancel` returns true immediately before a request. That request is not sent |
| `ProviderTimeoutError` | The client raises `httpx.TransportError` |
| `ProviderRateLimitError` | The response status is 429 |
| `ProviderResponseError` | The provider name is unknown, `match_id` is illegal, the status is a different HTTP error, Comic Vine reports failure, or the body has no usable record |

All of these are subclasses of `ProviderError`. `ProviderRateLimitError`, `ProviderTimeoutError`, and `ProviderResponseError` name the provider in the message. None of them write a file.

An empty candidate list is not an exception.

## Configuration

This specification adds no configuration keys.

`title_languages` and `comicvine_api_key` are arguments. Their defaults remain those in [00-project-overview.md](00-project-overview.md): `["fr", "en"]` and `""`. The result limit of 10, the `User-Agent` `manga-tagger`, and the shell timeout of 15 seconds are not TOML keys.

`httpx` is the HTTP library. It is added to `pyproject.toml` when this specification is implemented.

## Testing

Tests are hermetic. They do not use the network, do not sleep, and do not read the developer’s config, index, or library. They do not open `src/Claymore/`. Provider bodies are JSON fixtures under `tests/fixtures/providers/` or responses built in the test. The HTTP client is an `httpx.Client` with `httpx.MockTransport`. Tests record the requests that transport saw.

Cover at least:

- The query and number table above, including `Foo (Bar) v01` keeping `(Bar)`, and `build_query("20th Century Boys", "20th Century Boys v01")` leaving the series text intact while `parse_number` returns `1`.
- `search` with query `""` or `"   "` returns `[]` and the transport sees no request, including for `comicvine` with a blank key.
- A MangaDex fixture whose `title` has `fr` and `en` yields `Series` and `Title` `fr` when `title_languages` is `["fr", "en"]`, and `LanguageISO` `fr`. With only `ja` under `originalLanguage`, the title is that Japanese title and `LanguageISO` is `ja`. `Manga` is `YesAndRightToLeft`. A genre tag is included and a theme tag is not. An author is `Writer`. An artist is both `Penciller` and `CoverArtist`. No artist omits both, and the author is not copied. `Publisher` is absent. `Volume` is absent.
- An AniList fixture with `english` and `native`, and `title_languages` `["fr", "en"]`, uses the English title and `LanguageISO` `en`. A fixture with only `native` and `countryOfOrigin` `JP` uses the native title and `LanguageISO` `ja`. A romaji-only fixture omits `LanguageISO`. A staff role `Story & Art` fills `Writer`, `Penciller`, and `CoverArtist`. `Publisher` is absent. `Manga` is `YesAndRightToLeft`.
- A Jikan fixture with title types `French` and `English` uses the French title and `LanguageISO` `fr`. `serializations[0].name` is `Publisher`. `genres` are joined in order and a theme is not included. `published.prop.from` of year `2001`, month `6`, day `null` sets `Year` `2001` and `Month` `6` and omits `Day`. An author type `Story & Art` fills `Writer`, `Penciller`, and `CoverArtist`.
- A Comic Vine load sets `Manga` to `No`, omits `LanguageISO`, uses `description` over `deck`, and maps `writer, artist` to `Writer` and `Penciller` but not `CoverArtist`. A role `cover` sets `CoverArtist`. A blank `api_key` raises `ProviderUnavailableError`, the message says the Comic Vine API key is not set, and the transport sees no request. A JSON `status_code` other than `1` raises `ProviderResponseError`.
- `load` with filename stem `Claymore v02` includes `Number` `2` and does not include `Volume`. `load` with stem `Claymore` omits `Number`. `Title` equals `Series`.
- Summary `<p>Hello&nbsp;there</p>` becomes `Hello there`.
- Status 429 raises `ProviderRateLimitError`. A transport that raises `httpx.ConnectError` raises `ProviderTimeoutError`.
- `load` whose `cancel` returns true raises `ProviderCancelledError` and the transport sees no request.
- Provider name `other` raises `ProviderResponseError` and the transport sees no request.
- `search` and `load` have no archive path argument. A test that calls them writes nothing in a temporary directory.

## Acceptance criteria

- The caller selects one of MangaDex, AniList, Jikan, or Comic Vine. Search returns at most 10 candidates. An empty query returns no candidates and sends no request.
- The query is the trimmed `Series` when that value is non-blank, without removing numbers from it. Otherwise it is the filename stem after release tags and one volume suffix. The locked stem table produces those queries and numbers.
- `load` returns a form patch and does not write an archive. `Title` and `Series` are the same preferred series title. `Number` is present only when the filename stem has a volume marker. `Volume` is never present.
- French, then English, then the original title, following `title_languages`. AniList has no French title slot, so `fr` is skipped there. Comic Vine uses its single name and omits `LanguageISO`.
- MangaDex, AniList, and Jikan set `Manga` to `YesAndRightToLeft`. Comic Vine sets `Manga` to `No`.
- A blank Comic Vine key fails before any request, and the message says the Comic Vine API key is not set. A timeout, a connection failure, or HTTP 429 raises the matching provider error. No call sleeps or retries.
- `cancel` returning true before a request sends no request. A network result is not an archive write.

## Open questions

All resolved. Recorded here so they are not re-opened.

- **What does a match fill?** Series-level fields. `Title` is the same preferred series title. There is no per-volume or per-issue lookup. `Number` comes from the filename. `Volume` is not set.
- **How many catalogs are searched at once?** One. The caller passes the provider id.
