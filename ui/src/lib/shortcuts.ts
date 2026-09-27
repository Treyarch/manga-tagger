export type AppShortcut =
  | "save"
  | "rename"
  | "scan"
  | "list-view"
  | "grid-view"
  | "settings"
  | "dismiss-dialog";

export type PreviewShortcut = "previous-page" | "next-page";

export type DialogKind =
  | "matches"
  | "issues"
  | "settings"
  | "rename"
  | "convert"
  | "unsaved";

export type DialogDismissal =
  | "dismiss-unsaved"
  | "close-convert"
  | "close-rename"
  | "close-settings"
  | "cancel-issues"
  | "cancel-matches";

export type ShortcutEvent = Pick<
  KeyboardEvent,
  "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "repeat" | "target"
>;

export type DialogState = Record<`${DialogKind}Open`, boolean>;

export const SHORTCUT_HINTS = {
  save: "Ctrl+S / Cmd+S",
  rename: "F2",
  scan: "F5",
  listView: "Ctrl+1 / Cmd+1",
  gridView: "Ctrl+2 / Cmd+2",
  settings: "Ctrl+, / Cmd+,",
  dismiss: "Esc",
  previousPage: "←",
  nextPage: "→",
} as const;

type TargetLike = {
  tagName?: unknown;
  isContentEditable?: unknown;
  parentElement?: TargetLike | null;
};

export function shortcutTooltip(label: string, hint: string): string {
  return `${label} (${hint})`;
}

export function isEditableTarget(target: EventTarget | null): boolean {
  let current = target as TargetLike | null;
  while (current !== null && typeof current === "object") {
    const tag = typeof current.tagName === "string" ? current.tagName.toUpperCase() : "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
    if (current.isContentEditable === true) return true;
    current = current.parentElement ?? null;
  }
  return false;
}

function hasNoModifiers(event: ShortcutEvent): boolean {
  return !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey;
}

function hasPrimaryModifierOnly(event: ShortcutEvent): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey;
}

export function appShortcut(event: ShortcutEvent): AppShortcut | null {
  const key = event.key.toLowerCase();
  if (hasPrimaryModifierOnly(event)) {
    if (key === "s") return "save";
    if (key === "1") return "list-view";
    if (key === "2") return "grid-view";
    if (key === ",") return "settings";
    return null;
  }
  if (!hasNoModifiers(event)) return null;
  if (event.key === "Escape") return "dismiss-dialog";
  if (event.key === "F5") return "scan";
  if (event.key === "F2" && !isEditableTarget(event.target)) return "rename";
  return null;
}

export function previewShortcut(event: ShortcutEvent): PreviewShortcut | null {
  if (!hasNoModifiers(event) || isEditableTarget(event.target)) return null;
  if (event.key === "ArrowLeft") return "previous-page";
  if (event.key === "ArrowRight") return "next-page";
  return null;
}

export function activeDialog(state: DialogState): DialogKind | null {
  if (state.unsavedOpen) return "unsaved";
  if (state.convertOpen) return "convert";
  if (state.renameOpen) return "rename";
  if (state.settingsOpen) return "settings";
  if (state.issuesOpen) return "issues";
  if (state.matchesOpen) return "matches";
  return null;
}

export function shortcutDisposition(
  shortcut: AppShortcut,
  dialog: DialogKind | null,
): "run" | "dismiss" | "suppress" {
  if (dialog !== null) return shortcut === "dismiss-dialog" ? "dismiss" : "suppress";
  return shortcut === "dismiss-dialog" ? "suppress" : "run";
}

export function dialogDismissal(dialog: DialogKind): DialogDismissal {
  if (dialog === "unsaved") return "dismiss-unsaved";
  if (dialog === "convert") return "close-convert";
  if (dialog === "rename") return "close-rename";
  if (dialog === "settings") return "close-settings";
  if (dialog === "issues") return "cancel-issues";
  return "cancel-matches";
}

export function pageAfterShortcut(
  pageIndex: number,
  pageCount: number,
  shortcut: PreviewShortcut,
): number {
  const delta = shortcut === "previous-page" ? -1 : 1;
  return Math.max(0, Math.min(pageCount - 1, pageIndex + delta));
}
