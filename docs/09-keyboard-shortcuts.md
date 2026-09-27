---
description: Fixed desktop keyboard shortcuts activate common library actions, dismiss dialogs, and navigate preview pages without interfering with form editing.
status: active
---

# Keyboard shortcuts

This specification owns the application's fixed keyboard shortcuts and their discoverability. The matching actions, guards, and page boundaries remain owned by [04-application-shell.md](04-application-shell.md); button appearance and native tooltips remain owned by [05-ui-design.md](05-ui-design.md).

## Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+S` or `Cmd+S` | Save metadata |
| `F2` | Open Rename |
| `F5` | Scan library |
| `Ctrl+1` or `Cmd+1` | Switch to list view |
| `Ctrl+2` or `Cmd+2` | Switch to grid view |
| `Ctrl+,` or `Cmd+,` | Open Settings |
| `Escape` | Dismiss the active dialog through its existing Cancel or Close behavior |
| `Left Arrow` | Show the previous preview page |
| `Right Arrow` | Show the next preview page |

`Ctrl` and `Cmd` are equivalent primary modifiers. Chorded shortcuts require exactly the primary modifier: adding Shift or Alt does not activate them. `F2`, `F5`, Escape, and the arrows require no modifier.

The application prevents the browser or webview default for a recognized shortcut, including when the matching action is currently unavailable. Repeated keydown events do not repeat commands. Preview arrows may repeat while held.

## Context and guards

A command shortcut calls the same function as its matching header control and therefore uses the same selection, place, and busy guards. In particular, Save is unavailable with no selection or while busy; Rename keeps its selected-files-or-current-place behavior; and Scan is unavailable while busy. `Ctrl+S` and `Cmd+S` work while focus is in a metadata control.

While any modal dialog is open, every background shortcut is suppressed. Escape alone acts, dismissing the topmost dialog. Dismissing Matches or Issues while its request is active uses the existing cancellation path. Escape outside a dialog does nothing.

`F2` and preview arrows do not activate when the event target is an input, textarea, select, or content-editable element. Arrow handling remains inside the page preview so its page index is not promoted to application state. Arrows are handled only when a page preview exists, never move outside its bounds, and remain suppressed behind a dialog.

Header action tooltips show their shortcuts without changing their accessible names. The dialog Close button shows `Close (Esc)`, and preview page buttons show their arrow hints. The hints use `Ctrl` and `Cmd` together so they are accurate on every supported desktop platform.

## Configuration

This feature adds no configuration keys. The shortcut set cannot be customized.

## Testing

Unit tests cover every command and preview mapping, both primary modifiers, rejection of extra modifiers, repeat behavior, editable targets, modal suppression and topmost-dialog selection, and page bounds. The UI production build verifies the Svelte wiring and component prop changes.

## Acceptance criteria

- Every shortcut in the table invokes the same guarded behavior as its corresponding control.
- A recognized command prevents browser/webview behavior even when its application action is unavailable, and command repeats do not enqueue duplicate work.
- Background shortcuts do nothing while a dialog is open; Escape dismisses the topmost dialog and preserves Matches/Issues cancellation.
- Metadata fields retain normal arrow editing, while `Ctrl+S` and `Cmd+S` save from inside them.
- Preview arrows stay within the current archive's pages and may repeat while held.
- Accessible names remain unchanged, while native tooltips expose the available shortcut hints.
