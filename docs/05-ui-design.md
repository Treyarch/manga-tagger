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
|  | Brand |          action cluster          | Theme Settings X  | |
|  +------------------+---------------------------+---------------+ |
|  | My library      | Volume list or cover grid | Inspector     | |
|  |                  |                           | cover         | |
|  |                  |                           | form          | |
|  +------------------+---------------------------+---------------+ |
+------------------------------------------------------------------+
```

The header bar is three zones in one 48px row: a leading product brand, a centered action cluster, and trailing theme/settings/close. It is a CSS grid `grid-cols-[1fr_auto_1fr]`. The brand sits `justify-self-start` in the first column. The action cluster (provider select, scrape and write actions, view switch, and the job label with Cancel when a job is busy) sits in the middle column. Theme, Settings, and Close sit `justify-self-end` in the third column. Equal `1fr` side columns keep the action cluster optically centered on wide windows. The bar does not wrap to a second row.

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

The inspector stacks, from the top: the cover, then the metadata fields. The cover sits in a fixed 320px-tall (`h-80`) frame the full inspector width; the image is centered with `object-contain` and does not change that frame's height when the page changes. Each field is a label above its control. Labels use the muted text color and the readable captions from [04-application-shell.md](04-application-shell.md) (`Page count`, `Language`, `Cover artist`, and the rest), not the raw ComicInfo element names. Fields stack with `gap-3`. The pane has no shadow and no inner card.

An empty library, or an empty place, shows one sentence in the main pane, centered, in the muted color: `No volumes yet.` There is no illustration.

## Color

Use Tailwind's built-in `zinc` and `blue` scales so a control can keep the classes from the official Tailwind CSS examples. Do not add a custom palette, and do not add an accent picker.

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

The header bar has a quiet icon button that opens the menu with three choices: System, Light, and Dark. The icons are Lucide `Monitor`, `Sun`, and `Moon`. The current choice shows a check. Choosing one updates `theme` and applies the class immediately.

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
| `quiet` | Transparent, primary text, hover is a zinc wash (`zinc-200/70` light, `zinc-800` dark) |
| `danger` | `red-600` fill, white text. Hover is `red-700` in both themes |

The header icon button is `quiet`, 32px square (`size-8`), with a 20px icon. The default button height is 36px (`h-9`) and `text-sm`.

When a button has an accessible name and no visible text (icon buttons), that name is also the native `title` attribute. Hovering shows the browser tooltip after the platform delay so the user can learn what Scrape, Save, Rename file(s), Convert CBR, Scan library, List view, Grid view, and the other chrome icons do. Do not add a custom tooltip component.

### Text input

`TextInput.svelte`. Height 36px, `text-sm`, `rounded-md`, hairline border, view background, muted placeholder. Settings, rename, and inspector fields use it.

### Textarea

`Textarea.svelte`. Same border, radius, background, and `text-sm` as the text input. At least four rows. `Summary` and `Notes` use it.

### Checkbox

`Checkbox.svelte`. A native checkbox with a `text-sm` label beside it. The settings row `Keep the original CBR` uses it.

### Select

`Select.svelte`. Same height, radius, border, and background as the text input. It is a native `<select>`. Its open list follows the document `color-scheme`, so it is dark when the window is dark.

### Menu

`Menu.svelte`. The panel uses the view background, a hairline, `rounded-md`, and a small shadow. Items are 36px tall. Hover uses the selection wash. The checked item shows a 16px Lucide `Check`.

### Dialog

`Dialog.svelte`. A centered modal over the window with a `zinc-900/40` backdrop at `z-30` (below toasts). The panel is `max-w-md`, `rounded-lg`, and `p-4`. The title is `text-sm font-medium`.

Light mode uses a white fill, a `zinc-200` hairline, and `shadow-md` so the panel lifts off the panes the same way a toast does. Dark mode does not reuse the pane fill: it uses a `zinc-800` fill, a `zinc-600` border, and `shadow-lg` with a dark black wash so the dialog reads clearly against `zinc-900` panes and `zinc-950` chrome.

Enter: fade in and fly upward about 20px over ~400ms with a slight overshoot (`backOut`). Exit: fade out and drift downward over ~220ms. Backdrop click does not dismiss.

Actions sit at the trailing edge: a `quiet` dismiss button labeled `Cancel`. When the dialog has a confirm action, a `primary` or `danger` confirm button follows. Picker dialogs (scrape Matches) omit the confirm button; only Cancel remains. `MatchesDialog.svelte` uses this dismiss-only footer and lists scrape candidate rows (`title`, optional muted `detail`) in the body. Match rows are not shown in the inspector.

### Toast

`ToastHost.svelte` plus `ui/src/lib/toast.ts`. The host is a fixed stack at the top-right of the window (`top-4 right-4`), `z-40` so it sits above dialogs. Each toast is one short sentence, `rounded-lg`, `text-sm`, `max-w-sm`, and `px-4 py-3`. Success uses primary text. Failure uses `text-red-600` in light and `text-red-400` in dark. No badges, icons, or progress bars.

Light mode uses a white fill, a `zinc-200` hairline, and `shadow-md` so the toast lifts off the pane. Dark mode does not reuse the pane fill: it uses a `zinc-800` fill, a `zinc-600` border, and `shadow-lg` with a dark black wash so the toast reads clearly against `zinc-900` panes and `zinc-950` chrome.

Enter: fade in and fly downward about 24px over ~400ms with a slight overshoot (`backOut`). Exit: fade out and drift upward over ~220ms. Each toast removes itself after 5 seconds. A click dismisses it early. Several toasts stack downward with a small gap. The live region uses `role="status"` and `aria-live="polite"`. Toasts are not keyboard-focusable chrome and do not take a focus ring.

`toast.ts` owns the queue (`pushToast`, `dismissToast`) and the pure `jobToastMessage` helper that turns a finished job into that sentence. [04-application-shell.md](04-application-shell.md) decides when the client pushes a toast.

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
- Inspector field captions use the readable names from the shell form section, not camel-cased ComicInfo keys.
- `jobToastMessage` returns null for `cancelled`, the scrape/load/save/rename/convert/scan sentences from the shell toast table for `succeeded` and `failed`, and uses entry counts without `error_message` for save, rename, and convert.
- `pushToast` adds an item that `dismissToast` removes, and a timer removes it after 5 seconds.

The product brand (SVG logo and wordmark) is presentational chrome. It is covered by the acceptance criteria below, not by a separate unit test.

## Acceptance criteria

- The window is a header bar, a 240px My library sidebar, a flexible main pane, and a 384px inspector, separated by hairlines. An 8px window-background inset surrounds that chrome, with 8px between the header and the pane strip. A hairline outlines the header and the pane strip. The three panes stay flush with each other. The header does not scroll away.
- List is the view when the window opens. Rows are 36px. List and grid both group by series: a muted series header above the volumes that share it, blank-series volumes first with no header, then named series in case-folded alphabetical order. List rows are filename-only with a muted tree marker (tee or L). Grid cells show a 2:3 cover, the filename as a truncated label, and a 2px accent ring when selected, with no tree marker. List selection is the accent wash on the row.
- An empty main pane shows the sentence `No volumes yet.` and no illustration. An empty sidebar shows `Drop a folder here.` under the Add folder button.
- The first sidebar row is the muted caption `My library`, then Add folder, Lucide `FolderPlus`, 16px, trailing in a 36px row. A drag over the sidebar uses the selection wash.
- Light and dark use the color table in this document. Dark mode is the `dark` class. The layout does not change between themes. With `dark`, native selects use a dark popup through `color-scheme: dark`.
- `theme` defaults to `system`. `light` and `dark` force that theme. Any other value follows the system. The header menu can set each of the three values, and the class updates immediately. `system` keeps following `prefers-color-scheme`.
- The resolved theme is applied before the first paint.
- Icons are Lucide, `currentColor`, 16px in rows and menu items and 20px in the header. The view switch is `List` / `List view` and `LayoutGrid` / `Grid view`. The theme menu is `Monitor`, `Sun`, and `Moon`. Add folder is `FolderPlus`. Close is `X` at the trailing edge of the header. Icon buttons expose their accessible name as a native `title` so a short hover shows that label.
- Buttons, text inputs, textareas, checkboxes, selects, menus, dialogs, and toasts are the local components in this document, styled with Tailwind utilities. The UI package does not depend on a third-party component kit.
- Dialogs are centered over the window with a dimmed backdrop. Their panels use the same raised surface as toasts (white / `zinc-800` in dark, hairline, shadow) and fade in with a short upward overshoot. Settings, Rename, Convert, and Matches share that chrome. Matches is dismiss-only; the other three keep Cancel plus a confirm action.
- Action toasts appear in a top-right stack, fade in downward with a short overshoot, and disappear after 5 seconds or on click. In dark mode they use a raised `zinc-800` surface and a stronger shadow so they stand apart from the panes. They summarize scrape, load, save, rename, convert, and scan outcomes. Scrape match count, no matches, and provider errors are toast-only. Detailed per-file save/rename/convert errors and scan-root lines stay in the inspector.
- Type is the default sans stack at `text-sm` for controls and rows, and `text-xs` for captions. The product wordmark alone uses the bundled Dela Gothic One face via `.font-brand`.
- The header is three zones: leading brand (mini SVG + `Manga Tagger`), centered action cluster, trailing Theme / Settings / Close. The brand is readable in light and dark.
- A keyboard focus ring is visible on the shared controls.
