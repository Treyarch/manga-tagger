---
description: Nautilus-like light and dark window, with a three-zone header bar (brand, centered actions, trailing utilities), places sidebar, volume list or cover grid, inspector, Lucide icons, and a small set of local Tailwind components.
status: active
---

# UI design

This specification owns how the window looks: layout, color, type, icons, light and dark theme, and the shared controls. It implements none of the archive, index, or provider behavior.

[04-application-shell.md](04-application-shell.md) owns the process, the local API, pywebview, and what selection, search, scrape, and save do. That document places those actions into the header, sidebar, list, and inspector described here. This document does not decide their behavior.

The UI is Svelte 5, as locked in [00-project-overview.md](00-project-overview.md). The package lives in `ui/` and is created when this specification is implemented.

## Reference

The visual reference is GNOME Files (Nautilus).

- One header bar across the top of the window.
- A places sidebar on the left.
- A main pane that is either a file list or a cover grid.
- Hairline separators, neutral surfaces, and a single blue accent.
- Symbolic icons in the chrome, tinted with the current text color.
- The same arrangement in light and in dark. Dark mode changes color only.

The cover and the metadata form sit in a trailing inspector, the way a file manager keeps properties beside the files. Regions are panes separated by a hairline. They are not cards, and they do not stack on other cards.

## Layout

The window fills the webview. It does not sit in a centered page column. The chrome sits inset from the window edge by 8px (`p-2`) on the window background, with 8px (`gap-2`) between the header and the pane strip below it. That inset is the only breathing room around the regions. A hairline outlines the header and another outlines the pane strip so the inset stays visible where the sidebar matches the window background. The header stays put. The sidebar, the main pane, and the inspector stay flush with each other, separated by hairlines, and each scrolls on its own. They are not cards: no radius, no shadow, no gap between those three panes.

```text
+------------------------------------------------------------------+
| (window background, 8px inset)                                   |
|  +--------------------------------------------------------------+ |
|  | Brand |          action cluster          | Settings X  | |
|  +------------------+---------------------------+---------------+ |
|  | My library      | Volume list or cover grid | Inspector     | |
|  |                  |                           | cover         | |
|  |                  |                           | form          | |
|  +------------------+---------------------------+---------------+ |
+------------------------------------------------------------------+
```

The header bar is three zones in one 48px row: a leading product brand, a centered action cluster, and trailing settings/close. It is a CSS grid `grid-cols-[1fr_auto_1fr]`. The brand sits `justify-self-start` in the first column. The action cluster (provider select, scrape and write actions, view switch, and—for Rename, Convert, and Scan only—the job label with Cancel when that job is busy) sits in the middle column. Search, Load, and Save do not add header job chrome. Settings and Close sit `justify-self-end` in the third column. Equal `1fr` side columns keep the action cluster optically centered on wide windows. The bar does not wrap to a second row. The provider select only lists providers from `enabled_providers` in config.

The product brand is a mini SVG logo (closed tankōbon with a tag notch, about 20px, `currentColor` with the accent on the spine) beside the wordmark `Manga Tagger`. It is not a button.

| Region | Size | Surface |
| --- | --- | --- |
| Window inset | 8px (`p-2`) around the chrome, 8px (`gap-2`) under the header | Window background |
| Header bar | 48px tall (`h-12`), three zones as above | Same fill as the main pane, hairline around the header |
| My library sidebar | 240px (`w-60`) | Window background |
| Main pane | Remaining width | View background |
| Inspector | 384px (`w-96`) | View background, hairline along its left edge |
| Pane strip | Sidebar, main, and inspector as one row | Hairline around the strip |

The sidebar lists library places. The first row is 36px: muted caption text `My library` on the leading edge, and a quiet icon button at the trailing edge, Lucide `FolderPlus`, accessible name `Add folder`. A place row is an icon and a label, 36px tall. The selected place uses the selection wash. When no place is selected, no place row is washed and the main pane shows the whole library. Dragging a folder over the sidebar uses that same wash on the sidebar. When there are no places, one muted line under the button reads `Drop a folder here.` A failed add shows one line under the button. The main pane still says `No volumes yet.`

The main pane lists volumes. List is the default. Grid shows covers only. The switch is session state. It is not a configuration key. Switching back to list restores the list, and switching to grid restores the grid, for as long as the window is open.

List view groups volumes by ComicInfo `Series`. A non-blank series is a group header above its volumes: muted caption text (`text-xs`), not selectable, truncated on one line. Volumes that share that series sit directly under it. A volume row is 36px tall (`h-9`): a small tree marker, a 16px icon or thumbnail, and the filename as the only label. The tree marker is a muted hairline L (└) for the last volume in the group and a muted hairline tee (├) for every earlier volume, drawn with the hairline colors, so the row reads as a child of the series header. The series is not repeated on the row. The whole row takes the selection wash. Volumes with a blank series have no group header and no tree marker; they keep their place among the groups: blank-series volumes come first, then named series in case-folded alphabetical order. Within a group, volume order is the same name sort the shelf already uses.

Grid view uses the same series groups and the same muted series headers. Covers for one series sit in one cover grid under that header. There is no tree marker in the grid: covers sit side by side, so the header alone marks the group.

A grid cell is a cover at a 2:3 aspect ratio with the filename as one truncated label under it. Selection is a 2px accent ring around the cover and the selection wash behind the label. A wash behind the cover image would be hidden by the image, so the ring is the selection on the cover itself.

List and grid covers share `Thumb.svelte`: the `img` `src` is `GET /api/thumbnail?path=` for the volume path, with `loading="lazy"` and `decoding="async"`. The client does not `fetch` the JPEG into a blob URL. A failed volume, or an image that errors, shows Lucide `Book` in list view when `fallback` is on, and leaves the grid cell empty of an image while the label stays.

The inspector stacks, from the top: the cover, then the metadata fields. The cover sits in a fixed 320px-tall (`h-80`) frame the full inspector width; the image is centered with `object-contain` and does not change that frame's height when the page changes. Each field is a label above its control. Labels use the muted text color and the readable captions from [04-application-shell.md](04-application-shell.md) (`Page count`, `Language`, `Cover artist`, and the rest), not the raw ComicInfo element names. When a field's form `dirty` flag is true (the user edited it or a load overwrote it with a different value), the control's value text and border use the dirty field colors from the color table; the caption stays muted. A load or edit that leaves the value unchanged does not set `dirty`, so those controls stay primary. After a successful Save rebuilds the form from the index, those controls return to primary text and the hairline border. A 20px circular lock toggle sits on the control's top-right border corner (centered on that edge, view-background fill so the field border appears broken behind it)—not inside the value area, so selects keep a full clickable face. Circle and padlock are one custom SVG in a shared 20×20 viewBox (not Lucide) so the glyph stays centered. Locked uses a closed shackle; unlocked uses an open shackle. Accessible name `Unlock {caption}` or `Lock {caption}`. Hover uses `cursor-pointer` (disabled uses `cursor-not-allowed`). Unlocked: muted zinc. Locked: primary text. The control is disabled when the form is busy for Load/Save or the field is locked. The lock button is disabled only while Load/Save busy. Clicking the lock toggles via `POST /api/field-locks` (see [07-field-locks.md](07-field-locks.md)). Fields stack with `gap-3`. The pane has no shadow and no inner card.

An empty library, or an empty place, shows one sentence in the main pane, centered, in the muted color: `No volumes yet.` There is no illustration.

## Color

Use Tailwind's built-in `zinc` and `blue` scales for chrome so a control can keep the classes from the official Tailwind CSS examples. Dirty inspector fields use `amber` the same way danger buttons use `red`. Do not add a custom palette, and do not add an accent picker.

| Role | Light | Dark |
| --- | --- | --- |
| Window and sidebar | `zinc-100` | `zinc-950` |
| Header, main pane, inspector | `white` | `zinc-900` |
| Hairline | `zinc-200` | `zinc-800` |
| Primary text | `zinc-900` | `zinc-100` |
| Muted text | `zinc-500` | `zinc-400` |
| Accent | `blue-600` | `blue-500` |
| Selection wash | `blue-600/10` | `blue-500/15` |
| Cover ring when selected | `blue-600` | `blue-500` |
| Dirty field text | `amber-700` | `amber-400` |
| Dirty field border | `amber-600` | `amber-500` |

Text on a filled accent or danger button is `white` in both themes. A selected row keeps the primary text color. The wash shows the selection.

## Type

Use Tailwind's default `font-sans` stack for chrome, rows, and fields. On Linux that resolves to the desktop UI font. Do not bundle a webfont for those uses.

The product wordmark is the one exception: it uses a self-hosted **Dela Gothic One** face (OFL), filed under `ui/src/assets/fonts/`, declared with `@font-face` in `app.css`, and applied only through a `.font-brand` class on the brand title. Chrome and form text stay on `font-sans`.

| Use | Classes |
| --- | --- |
| Labels, rows, header controls, fields | `text-sm` |
| Product wordmark | `text-sm font-brand` (Dela Gothic One) |
| Field captions, grid captions, muted secondary text | `text-xs` plus the muted color |

## Theme

`ui/src/app.css` contains the Tailwind import, the `dark` custom variant, the Dela Gothic One `@font-face` and `.font-brand` class, and:

```css
@import "tailwindcss";
@custom-variant dark (&:where(.dark, .dark *));
```

Dark mode is the `dark` class on an ancestor. Components use `dark:` variants for every color in the table above. There is no second stylesheet.

`ui/src/lib/theme.ts` exports `resolveDark(theme: string, prefersDark: boolean): boolean`.

| `theme` | `prefersDark` | `resolveDark` |
| --- | --- | --- |
| `light` | either | `false` |
| `dark` | either | `true` |
| `system` | `true` | `true` |
| `system` | `false` | `false` |
| any other string | either | same as `system` |

The shell reads `theme` before the first paint and puts `dark` on `document.documentElement` when `resolveDark` is true. It removes that class when `resolveDark` is false. The first frame uses the resolved theme. When `dark` is present, the document sets `color-scheme: dark` so native controls such as the provider `<select>` popup use the dark system palette. Without `dark`, it sets `color-scheme: light`.

Theme is chosen in Settings on the General tab (`system`, `light`, or `dark` via `Select`). There is no theme control in the header. Saving Settings writes `theme` and applies the class. Cancel leaves the previous theme.

While `theme` is `system`, the class follows later changes to `prefers-color-scheme` for the life of the window. A forced `light` or `dark` ignores those changes until the user picks System again.

## Icons

Icons are [Lucide](https://lucide.dev), package `lucide-svelte`. They are outline strokes, colored with `currentColor`, at the library's default stroke width.

| Place | Size |
| --- | --- |
| Rows and menu items | 16px |
| Header bar | 20px |

The view switch uses Lucide `List` and `LayoutGrid`, with accessible names `List view` and `Grid view`. The active view uses the selection wash on its button.

Do not add a second icon set. Do not use filled or multicolor icons in the chrome.

## Components

Shared controls live in `ui/src/lib/components/`. Each one is a Svelte 5 component styled only with Tailwind utilities, in the shape of the simple official Tailwind CSS controls. Allowed UI dependencies for this specification are `svelte`, Vite, `tailwindcss`, `@tailwindcss/vite`, and `lucide-svelte`.

Do not add Flowbite, daisyUI, Skeleton, shadcn-svelte, `@tailwindcss/forms`, or any other component kit.

Every control shows a 2px accent focus ring on `:focus-visible` (`blue-600` in light, `blue-500` in dark).

### Button

`Button.svelte`. Variants:

| Variant | Look |
| --- | --- |
| `primary` | Accent fill, white text |
| `secondary` | Hairline border, zinc fill (`zinc-100` light, `zinc-700` dark), primary text. Hover darkens the fill (`zinc-200` light, `zinc-600` dark). Used for dialog alternate actions so they read as buttons beside a filled confirm |
| `quiet` | Transparent, primary text, hover is a zinc wash (`zinc-200/70` light, `zinc-800` dark). Header and inspector icon buttons stay quiet |
| `danger` | `red-600` fill, white text. Hover is `red-700` in both themes |

The header icon button is `quiet`, 32px square (`size-8`), with a 20px icon. The default button height is 36px (`h-9`) and `text-sm`. Enabled buttons use `cursor-pointer`; disabled buttons use `cursor-not-allowed`.

When a button has an accessible name and no visible text (icon buttons), that name is also the native `title` attribute. Hovering shows the browser tooltip after the platform delay so the user can learn what Scrape, Save, Rename file(s), Convert CBR, Scan library, List view, Grid view, and the other chrome icons do. Do not add a custom tooltip component.

### Text input

`TextInput.svelte`. Height 36px, `text-sm`, `rounded-md`, hairline border, view background, muted placeholder. Settings, rename, and inspector fields use it. An optional `extra` class string is appended for callers that need it. When `dirty` is true, value text and border use the dirty amber colors instead of primary text and the hairline border (not both; amber must replace zinc so it wins). When `disabled` is true (including a locked inspector field), the control uses `cursor-not-allowed` and `opacity-60`.

### Textarea

`Textarea.svelte`. Same border, radius, background, and `text-sm` as the text input. At least four rows. `Summary` and `Notes` use it. It accepts the same optional `extra`, `dirty`, and `disabled` styling as the text input.

### Checkbox

`Checkbox.svelte`. A custom-styled checkbox (`appearance-none`) with a `text-sm` label beside it: zinc hairline border, white / `zinc-900` fill, and blue fill with a white check when on. Focus uses the shared accent ring. Optional `hideLabel` keeps the accessible name and hides the visible caption — Settings Scrapers uses that so each row shows only the box. Settings Archives keeps the visible `Keep the original CBR` label.

### Select

`Select.svelte`. Same height, radius, border, and background as the text input. It is a native `<select>`. Its open list follows the document `color-scheme`, so it is dark when the window is dark. It accepts the same optional `extra`, `dirty`, and `disabled` styling as the text input.

### Menu

`Menu.svelte`. The panel uses the view background, a hairline, `rounded-md`, and a small shadow. Items are 36px tall. Hover uses the selection wash. The checked item shows a 16px Lucide `Check`.

### Dialog

`Dialog.svelte`. A centered modal over the window with a `zinc-900/40` backdrop at `z-30` (below toasts). The panel is `rounded-lg` and `p-4`. Size is a prop: `md` (default, `max-w-md`) for Rename, Convert, and Unsaved metadata; `lg` (`max-w-2xl`) for Settings; `xl` (`max-w-4xl`) for Matches and Issues. The title row is obvious: the Lucide icon of the control that opened the dialog (20px, `currentColor`, decorative) sits before a `text-base font-bold` title. Settings uses `Settings`, Rename uses `Pencil`, Convert uses `FileArchive`, Unsaved metadata uses `Save`, Matches uses `ScanSearch` (the Scrape control), and Issues uses `ListOrdered`. A quiet icon button with Lucide `X` sits at the trailing edge of that row; its accessible name is `Close`, and it dismisses the same way Cancel does.

`SettingsDialog.svelte` uses the `lg` panel. Under the title it has a left tab rail and a content pane. The tabs are **General**, **Archives**, and **Scrapers**. Selecting a tab only changes the visible pane; Save still writes every field from both tabs.

- **General** — theme (`Select` with System / Light / Dark), library roots (textarea), then title languages (text input).
- **Archives** — `keep_cbr_original` as a checkbox labeled `Keep the original CBR`, with a short muted description under it explaining that convert writes a sibling `.cbz` and, when this is on (the default), keeps the `.cbr` beside the new `.cbz`; when off, deletes the `.cbr` so each book stays one file. `write_poster_on_save` as a checkbox labeled `Write poster on save`, with a short muted description explaining that a successful save or rename writes `{stem}-poster.jpg` from the cover when this is on (the default), and that rename still moves an existing sibling poster when it is off. `auto_save_metadata_on_switch` as a checkbox labeled `Auto-save metadata on switch`, with a short muted description explaining that when this is off (the default), changing issue or place with a dirty form asks Save / Don't save / Cancel, and when it is on the app saves that form then switches.
- **Scrapers** — one block per known provider in a fixed order (MangaDex, AniList, MyAnimeList, Comic Vine, Nautiljon). Each block shows the provider label, a short muted capability line, and a checkbox (no visible caption; accessible name `Enable {label}`) to enable it. Comic Vine adds an API key field. Nautiljon adds base URL and API key fields. Credential fields stay editable when the provider is off so keys can be set before enabling. The header provider select only offers enabled providers after Save.

Light mode uses a white fill, a `zinc-200` hairline, and `shadow-md` so the panel lifts off the panes the same way a toast does. Dark mode does not reuse the pane fill: it uses a `zinc-800` fill, a `zinc-600` border, and `shadow-lg` with a dark black wash so the dialog reads clearly against `zinc-900` panes and `zinc-950` chrome.

Enter: fade in and fly upward about 20px over ~400ms with a slight overshoot (`backOut`). Exit: fade out and drift downward over ~220ms. Backdrop click does not dismiss.

Actions sit at the trailing edge by default: a `secondary` dismiss button labeled `Cancel`. When the dialog has a confirm action, a `primary` or `danger` confirm button follows. An optional leading action (label, handler, disabled) sits before Cancel and also uses `secondary`. The Unsaved metadata dialog uses leading secondary `Don't save`, secondary `Cancel`, and primary `Save`. `MatchesDialog.svelte` uses leading secondary `Select Issue` when a single volume is selected (`selectIssueEnabled`), secondary `Cancel`, and primary `OK`. While a Search is queued or running, the body shows muted `Searching…` with a spinning Lucide `LoaderCircle` (20px) and `aria-busy`. When candidates arrive, that body is replaced by a two-column picker: a large cover preview on the left (2:3 frame, `object-contain`, Lucide `Book` placeholder on miss or load failure) and a right stack with a Series / Year / Issues / (Publisher or Author) table above a muted summary pane. The credit column caption is `Publisher` when the selected provider is Comic Vine, and `Author` for MangaDex, AniList, Jikan, and Nautiljon. The first candidate is highlighted. A single click or arrow key changes the highlight and updates the cover and summary; it does not load. OK or Enter starts load for the highlighted series id (no `issue_id`). When Select Issue is shown, Select Issue or a double-click starts the Issues job for that id. When several volumes are selected, Select Issue is omitted and double-click starts load like OK. OK and Select Issue are disabled while searching, while a Load or Issues job is busy, or when nothing is highlighted. Row selection uses the existing accent wash (`blue-600/10` / dark `blue-500/15`), not a solid fill. MangaDex covers (`uploads.mangadex.org`) and Nautiljon covers load through `GET /api/cover?url=` so the image is same-origin; other hosts use the candidate URL directly. The preview `img` uses `referrerpolicy="no-referrer"`. Match rows are not shown in the inspector. In-progress scrape status is not a toast.

`IssuesDialog.svelte` reuses the same `xl` chrome. The title is `{Series} ({Year}) - Select matching issue` from the series candidate (omit ` ({Year})` when year is blank). While the Issues job runs, the body shows muted `Loading issues…` with a spinner. When issues arrive, the layout matches Matches: cover left, Issue / Date / Title table and summary on the right. When the highlighted issue has a blank `cover`, the left preview uses the series candidate cover. The row whose `number` matches the preferred form/stem number is highlighted when present; otherwise the first row. The issues table scrolls that highlighted row into view (`scrollIntoView` with `block: "nearest"`) when the list first loads and whenever the highlight moves with the arrow keys. OK, Enter, or double-click starts load with that `issue_id`. Cancel closes only the Issues dialog and returns to Matches.

### Thumb

`Thumb.svelte`. Shared by list rows and grid cells. Props: `path` (absolute archive path), `failed` (index status), and optional `fallback` (list rows set this so a miss shows Lucide `Book`). When `failed` is false, it renders an `img` whose `src` is `/api/thumbnail?path=` with the path URI-encoded (`thumbnailSrc` in `library.ts`), `loading="lazy"`, and `decoding="async"`. It does not use `fetch` or `URL.createObjectURL`. An `error` event hides the image and, when `fallback` is true, shows `Book`.

### Toast

`ToastHost.svelte` plus `ui/src/lib/toast.ts`. The host is a fixed stack at the top-center of the window (`top-16 left-1/2 -translate-x-1/2`), clear of the 8px window inset and 48px header, `z-40` so it sits above dialogs. The host stays mounted even when empty so the first toast still runs its enter transition. Each toast is a flex row: a leading 16px Lucide icon (`currentColor`, decorative, `aria-hidden`) and one short sentence. The row is `rounded-lg`, `text-sm`, `max-w-sm`, and `px-4 py-3`. Success uses primary text. Failure uses `text-red-600` in light and `text-red-400` in dark. No badges or progress bars.

The icon follows the job that produced the toast (same glyphs as the chrome that started it). Failures always use Lucide `CircleAlert`. A direct `pushToast` with no job defaults to `Check` on success and `CircleAlert` on failure.

| Context | Success icon | Failure icon |
| --- | --- | --- |
| Search | `ScanSearch` | `CircleAlert` |
| Issues | `ListOrdered` | `CircleAlert` |
| Load | `Check` | `CircleAlert` |
| Save | `Save` | `CircleAlert` |
| Rename | `Pencil` | `CircleAlert` |
| Convert | `FileArchive` | `CircleAlert` |
| Scan | `RefreshCw` | `CircleAlert` |

Light mode uses a white fill, a `zinc-200` hairline, and `shadow-md` so the toast lifts off the pane. Dark mode does not reuse the pane fill: it uses a `zinc-800` fill, a `zinc-600` border, and `shadow-lg` with a dark black wash so the toast reads clearly against `zinc-900` panes and `zinc-950` chrome.

Enter: fade in and fly downward about 24px over ~400ms with a slight overshoot (`backOut`). The leading icon pops once on mount (opacity 0→1 and scale 0.5→1 over ~400ms with a slight overshoot); it does not spin or pulse. Exit: fade out and drift upward over ~220ms. Each toast removes itself after 5 seconds. A click dismisses it early. Several toasts stack downward with a small gap. The live region uses `role="status"` and `aria-live="polite"`. Toasts are not keyboard-focusable chrome and do not take a focus ring.

`toast.ts` owns the queue (`pushToast`, `dismissToast`) and the pure `jobToastMessage` helper that turns a finished job into that sentence plus its `icon`. [04-application-shell.md](04-application-shell.md) decides when the client pushes a toast. Any new UI string that interpolates a count with a noun must use `pluralize` from `ui/src/lib/pluralize.ts` (or an equivalent `count === 1` branch). English uses the singular only for 1; 0 and every other count use the plural form.

## Configuration

This specification adds one key to the TOML file described in [00-project-overview.md](00-project-overview.md).

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `theme` | string | `system` | `system` follows `prefers-color-scheme`. `light` forces the light surfaces. `dark` forces the dark surfaces. Any other value is treated as `system`. |

The application shell reads and writes this key. This specification defines the values and the class they produce. A missing config file uses `system`, which is the project default for a missing file.

View mode is not a key.

## Testing

Tests are hermetic. They do not open pywebview, do not take screenshots, do not use the network, and do not read the developer’s config, index, or library. `prefers-color-scheme` is a value passed into `resolveDark`, not a live media query in the test.

Cover at least:

- `resolveDark("light", true)` and `resolveDark("light", false)` are both false.
- `resolveDark("dark", true)` and `resolveDark("dark", false)` are both true.
- `resolveDark("system", true)` is true, and `resolveDark("system", false)` is false.
- `resolveDark("nope", true)` is true, and `resolveDark("nope", false)` is false.
- With a resolved dark theme, the shell root that sets the document class carries `dark`. With a resolved light theme, that element does not carry `dark`.
- Grouping by series puts blank-series volumes first with an empty `series` key, then named series in case-folded alphabetical order, preserving name order within each group.
- `thumbnailSrc` returns `/api/thumbnail?path=` with the archive path URI-encoded.
- Inspector field captions use the readable names from the shell form section, not camel-cased ComicInfo keys.
- `dirtyFieldClass(true)` returns the amber dirty text and border utilities; `dirtyFieldClass(false)` returns `""`.
- `pluralize(1, "match")` is `match`; `pluralize(0, "match")` and `pluralize(2, "match")` are `matches`; an explicit plural argument overrides the default `s` suffix.
- `jobToastMessage` returns null for `cancelled`, the scrape/load/save/rename/convert/scan sentences and icons from the shell toast table for `succeeded` and `failed`, and uses entry counts without `error_message` for save, rename, and convert.
- `pushToast` adds an item that `dismissToast` removes, defaults `icon` from tone when omitted, and a timer removes it after 5 seconds.
- `candidatesOf` maps `id`, `title`, `year`, `credit`, `count`, `summary`, and `cover` from the search result, coercing missing fields to `""`.
- `issuesOf` maps `id`, `number`, `title`, `date`, `cover`, and `summary` from the issues result, coercing missing fields to `""`.
- `preferredIssueId` returns the id of the issue whose `number` matches the preferred number after normalizing leading zeros on the integer part, or the first issue when none match, or `null` when the list is empty.
- `jobToastMessage` for Issues returns `No issues available.` on success with an empty list, null on success with hits, and the failure toast on failure.

The product brand (SVG logo and wordmark) is presentational chrome. It is covered by the acceptance criteria below, not by a separate unit test.

## Acceptance criteria

- The window is a header bar, a 240px My library sidebar, a flexible main pane, and a 384px inspector, separated by hairlines. An 8px window-background inset surrounds that chrome, with 8px between the header and the pane strip. A hairline outlines the header and the pane strip. The three panes stay flush with each other. The header does not scroll away.
- List is the view when the window opens. Rows are 36px. List and grid both group by series: a muted series header above the volumes that share it, blank-series volumes first with no header, then named series in case-folded alphabetical order. List rows are filename-only with a muted tree marker (tee or L). Grid cells show a 2:3 cover, the filename as a truncated label, and a 2px accent ring when selected, with no tree marker. List selection is the accent wash on the row. List and grid thumbs use `Thumb` with a lazy `img` on `/api/thumbnail`, not blob URLs.
- An empty main pane shows the sentence `No volumes yet.` and no illustration. An empty sidebar shows `Drop a folder here.` under the Add folder button.
- The first sidebar row is the muted caption `My library`, then Add folder, Lucide `FolderPlus`, 16px, trailing in a 36px row. A drag over the sidebar uses the selection wash.
- Light and dark use the color table in this document. Dark mode is the `dark` class. The layout does not change between themes. With `dark`, native selects use a dark popup through `color-scheme: dark`.
- A dirty inspector field (edited or loaded, `dirty` true) shows amber value text and border on its text input, textarea, or select. A clean field keeps primary text and the hairline border. After Save rebuilds the form, dirty styling is gone.
- Each inspector field has a 20px circular lock toggle (custom SVG padlock) on the top-right border corner of the control. A locked field disables the control. The lock toggle does not mark the form dirty.
- `theme` defaults to `system`. `light` and `dark` force that theme. Any other value follows the system. Settings General can set each of the three values; the class updates when Settings is saved. `system` keeps following `prefers-color-scheme`.
- The resolved theme is applied before the first paint.
- Icons are Lucide, `currentColor`, 16px in rows and menu items and 20px in the header. The view switch is `List` / `List view` and `LayoutGrid` / `Grid view`. Add folder is `FolderPlus`. Close is `X` at the trailing edge of the header. Icon buttons expose their accessible name as a native `title` so a short hover shows that label.
- Buttons, text inputs, textareas, checkboxes, selects, menus, dialogs, and toasts are the local components in this document, styled with Tailwind utilities. The UI package does not depend on a third-party component kit.
- Dialogs are centered over the window with a dimmed backdrop. Their panels use the same raised surface as toasts (white / `zinc-800` in dark, hairline, shadow) and fade in with a short upward overshoot. The title is bold with the opening control's Lucide icon ahead of it, and a Close `X` at the trailing edge of the title row. Settings, Rename, Convert, Unsaved metadata, Matches, and Issues share that chrome. Settings uses the `lg` panel with a General / Archives / Scrapers tab rail. Matches and Issues use the `xl` panel width. Matches shows secondary Cancel and primary OK; when one volume is selected it also shows secondary Select Issue before Cancel; while searching it shows `Searching…` with a spinner, then a large cover beside a Series/Year/Issues/(Publisher or Author) table and a summary pane. Issues shows Loading issues… then Issue/Date/Title with the same cover and summary layout, preselects the preferred-number row (else the first), and scrolls that row into view in the issues table. Rename and Convert keep `md` width, secondary Cancel, and a confirm action. Unsaved metadata keeps `md` width, leading Don't save, secondary Cancel, and primary Save.
- Action toasts appear in a top-center stack below the header bar, fade in downward with a short overshoot (including the first toast), show a leading 16px Lucide icon that pops once on mount (job-matched on success, `CircleAlert` on failure), and disappear after 5 seconds or on click. In dark mode they use a raised `zinc-800` surface and a stronger shadow so they stand apart from the panes. They summarize scrape, load, save, rename, convert, and scan outcomes only—not in-progress search. Scrape match count, no matches, and provider errors are toast-only. Detailed per-file save/rename/convert errors and scan-root lines stay in the inspector.
- Type is the default sans stack at `text-sm` for controls and rows, and `text-xs` for captions. The product wordmark alone uses the bundled Dela Gothic One face via `.font-brand`.
- The header is three zones: leading brand (mini SVG + `Manga Tagger`), centered action cluster, trailing Settings / Close. The brand is readable in light and dark.
- A keyboard focus ring is visible on the shared controls.
