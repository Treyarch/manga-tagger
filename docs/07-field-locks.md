---
description: Per-volume ComicInfo field locks in the SQLite index that block scrape overwrite and manual edits until unlocked.
status: active
---

# Field locks

This specification owns per-volume field locks: storage in the library index, merge and save behavior that respects them, the lock API, and the inspector lock toggle. It extends [02-library-index.md](02-library-index.md), [04-application-shell.md](04-application-shell.md), and [05-ui-design.md](05-ui-design.md). It does not write locks into `ComicInfo.xml`.

## Purpose

A user who has fixed a field (for example `Series` or `Number`) can lock it so an accepted scrape match does not overwrite it, and so the control cannot be typed into until unlocked. Locks live with the indexed volume and survive selection change, save, scan, and restart.

## Storage

Each `volumes` row has `locked_fields TEXT NOT NULL DEFAULT '[]'`. The value is a JSON array of ComicInfo element names from the shell `FORM_FIELDS` list (for example `["Series","Number"]`). On read, non-strings and names outside `FORM_FIELDS` are dropped. Order of names is not significant; writers store a sorted unique list. Empty is `[]`.

Locks are app-owned index state. They are not ComicInfo elements. Jellyfin and other readers never see them.

Schema version **3** adds the column. Version 2 migrates with `ALTER TABLE volumes ADD COLUMN locked_fields TEXT NOT NULL DEFAULT '[]'`, then `PRAGMA user_version = 3`. A fresh database creates version 3 with the column present. Version 0 still creates the full table then jumps to the current version. Any version other than 0, 1, 2, or 3 raises `IndexVersionError`.

### Preserve on upsert

`INSERT OR REPLACE` for an existing path must copy the previous `locked_fields` into the new row. A new path starts as `[]`. An unchanged size/mtime `ok` row is not replaced, so its locks stay. A `failed` re-index of an existing path also keeps that path's locks.

### Rename and convert

When a save, rename, or convert moves a volume to a new path, the shell copies `locked_fields` from the old path onto the new row after `refresh_volume` and before `forget_volume` on the old path. A new path that had no prior row receives the old list. When old and new paths are the same, nothing is copied.

## Form

Each form field object gains `locked` (boolean).

`form_from_volumes(rows)`:

- One row: each `FORM_FIELDS` key has `locked` true when that name is in the row's `locked_fields` list.
- Several rows: each `SHARED_FIELDS` key has `locked` true when **every** selected row includes that name in `locked_fields`. When some but not all include it, `locked` is false (mixed shows unlocked).

Editing a locked field is a no-op in the shell helper (the UI disables the control). Unlocking does not clear `dirty`. Locking does not set `dirty`.

## Scrape merge

`merge_load_patch(form, patch, mode)` skips any patch key whose form field has `locked` true. That field's `value`, `dirty`, and `mixed` stay as they were. Unlocked keys behave as in [04-application-shell.md](04-application-shell.md).

## Save

When building a per-file patch:

- Filename `Number` fill is skipped when that volume's `locked_fields` includes `Number` (or, for a `one` form, when the form field `Number` is locked).
- Blank `PageCount` fill from `archive_page_count` is skipped when `PageCount` is locked the same way.

Locks are never keys in the ComicInfo save patch. Toggle lock does not write an archive.

## API

`POST /api/field-locks` is synchronous (not a job). Body: `{ "paths": string[], "field": string, "locked": boolean }`.

- Each path must be absolute and inside a current library root (same rules as other volume ops). Relative or outside paths are `ShellError` / `OutsideLibraryError` and write nothing.
- `field` must be a `FORM_FIELDS` name. Any other string is `ShellError` and writes nothing.
- An empty `paths` list succeeds and returns `{ "volumes": [] }`.
- For each path that has a volume row, add `field` to (or remove it from) that row's `locked_fields` JSON. A missing path is skipped (not an error).
- Returns `{ "volumes": [row, ...] }` for the updated rows in request order (paths that had no row are omitted).

`set_field_lock(db_path, paths, field, locked)` in the index module performs the writes. The shell validates paths and field name, then calls it.

The client patches its local volume list from the returned rows and sets `form.values[field].locked` from the multi-select rule (all selected paths locked) without rebuilding the whole form, so dirty edits stay.

## UI

Each inspector field row is the caption, then the control. A 20px circular lock toggle sits on the control's top-right border corner (centered on that edge, view-background fill). Circle and padlock are one custom SVG (shared 20×20 viewBox) so the glyph stays centered; unlocked shows an open shackle. It is not inside the value area and does not steal clicks from a native select.

- Accessible name `Unlock {caption}` when locked, `Lock {caption}` when unlocked (caption is the readable field label).
- Hover uses `cursor-pointer`; while Load/Save busy the button is disabled (`cursor-not-allowed`).
- The control is `disabled` when `formLocked` or `field.locked`.
- Unlocked: muted zinc. Locked: primary text.

Clicking the button calls `POST /api/field-locks` with the current selection paths, that field name, and the opposite of the displayed locked state (when mixed/unlocked, send `locked: true`).

## Configuration

This specification adds no configuration keys.

## Testing

Hermetic tests. Temporary database and archives. No network.

Cover at least:

- Schema: version 2 migrates to 3 with `locked_fields` default `[]`; fresh DB is version 3; version 4 raises `IndexVersionError`.
- Upsert of an existing path preserves `locked_fields`; a new path stores `[]`.
- `set_field_lock` adds and removes a field; unknown field names are rejected by the shell/API; locking twice is idempotent.
- `form_from_volumes` sets `locked` from one row; for many rows, `locked` is true only when every row locks that shared field.
- `merge_load_patch` leaves a locked field unchanged (value and dirty); unlocked fields still update.
- Save skips filename `Number` fill and blank `PageCount` fill when those fields are locked.
- Rename/convert path change copies `locked_fields` from old to new before forgetting the old row.
- API `POST /api/field-locks` returns updated volumes and persists across `list_volumes`.

## Acceptance criteria

- Locking a field and accepting a scrape match leaves that field's form value and dirty flag unchanged.
- A locked field's inspector control is disabled; unlocking restores editing.
- Locks survive selection change, successful save, scan upsert of the same path, and process restart (via the index).
- Rename or convert to a new path keeps the same locked field set on the new row.
- Toggle lock does not write `ComicInfo.xml` and does not mark the form dirty.
- No configuration key is required for this feature.

## Open questions

All resolved.

- **Where do locks live?** SQLite per volume (`locked_fields`), not ComicInfo and not session-only.
- **Can the user still type?** No. Fully locked until unlocked.
- **Multi-select display?** Locked only when every selected volume locks that field; mixed shows unlocked; click locks or unlocks all.
