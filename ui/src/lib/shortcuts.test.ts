import { describe, expect, it } from "vitest";

import {
  activeDialog,
  appShortcut,
  dialogDismissal,
  isEditableTarget,
  pageAfterShortcut,
  previewShortcut,
  shortcutDisposition,
  shortcutTooltip,
  type ShortcutEvent,
} from "./shortcuts";

function key(
  value: string,
  extra: Partial<ShortcutEvent> = {},
): ShortcutEvent {
  return {
    key: value,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    shiftKey: false,
    repeat: false,
    target: null,
    ...extra,
  };
}

describe("application shortcuts", () => {
  it.each([
    ["s", "save"],
    ["1", "list-view"],
    ["2", "grid-view"],
    [",", "settings"],
  ] as const)("maps Ctrl+%s and Cmd+%s", (pressed, action) => {
    expect(appShortcut(key(pressed, { ctrlKey: true }))).toBe(action);
    expect(appShortcut(key(pressed, { metaKey: true }))).toBe(action);
  });

  it("maps unmodified desktop commands", () => {
    expect(appShortcut(key("F2"))).toBe("rename");
    expect(appShortcut(key("F5"))).toBe("scan");
    expect(appShortcut(key("Escape"))).toBe("dismiss-dialog");
  });

  it("rejects added Alt or Shift modifiers", () => {
    expect(appShortcut(key("s", { ctrlKey: true, shiftKey: true }))).toBeNull();
    expect(appShortcut(key("1", { metaKey: true, altKey: true }))).toBeNull();
    expect(appShortcut(key("F5", { shiftKey: true }))).toBeNull();
    expect(appShortcut(key("Escape", { ctrlKey: true }))).toBeNull();
  });

  it("keeps repeated commands recognizable for default prevention", () => {
    expect(appShortcut(key("s", { ctrlKey: true, repeat: true }))).toBe("save");
    expect(appShortcut(key("F5", { repeat: true }))).toBe("scan");
  });
});

describe("shortcut context", () => {
  it("recognizes editable elements and their descendants", () => {
    const input = { tagName: "input", parentElement: null };
    const child = { tagName: "span", parentElement: input };
    expect(isEditableTarget(input as unknown as EventTarget)).toBe(true);
    expect(isEditableTarget(child as unknown as EventTarget)).toBe(true);
    expect(
      isEditableTarget({ isContentEditable: true } as unknown as EventTarget),
    ).toBe(true);
    expect(isEditableTarget({ tagName: "button" } as unknown as EventTarget)).toBe(false);
  });

  it("does not rename while an editable control has focus", () => {
    const target = { tagName: "textarea" } as unknown as EventTarget;
    expect(appShortcut(key("F2", { target }))).toBeNull();
    expect(appShortcut(key("s", { ctrlKey: true, target }))).toBe("save");
  });

  it("selects the topmost rendered dialog", () => {
    const closed = {
      matchesOpen: false,
      issuesOpen: false,
      settingsOpen: false,
      renameOpen: false,
      convertOpen: false,
      unsavedOpen: false,
    };
    expect(activeDialog(closed)).toBeNull();
    expect(activeDialog({ ...closed, matchesOpen: true, issuesOpen: true })).toBe("issues");
    expect(activeDialog({ ...closed, settingsOpen: true, unsavedOpen: true })).toBe(
      "unsaved",
    );
  });

  it("suppresses background commands and reserves Escape for dialogs", () => {
    expect(shortcutDisposition("save", "matches")).toBe("suppress");
    expect(shortcutDisposition("dismiss-dialog", "issues")).toBe("dismiss");
    expect(shortcutDisposition("save", null)).toBe("run");
    expect(shortcutDisposition("dismiss-dialog", null)).toBe("suppress");
  });

  it("routes search and issue dismissal through their cancellation paths", () => {
    expect(dialogDismissal("matches")).toBe("cancel-matches");
    expect(dialogDismissal("issues")).toBe("cancel-issues");
    expect(dialogDismissal("settings")).toBe("close-settings");
  });
});

describe("preview shortcuts", () => {
  it("maps unmodified arrows and permits repeats", () => {
    expect(previewShortcut(key("ArrowLeft"))).toBe("previous-page");
    expect(previewShortcut(key("ArrowRight", { repeat: true }))).toBe("next-page");
  });

  it("leaves arrows to editable controls and modified key combinations", () => {
    const target = { tagName: "select" } as unknown as EventTarget;
    expect(previewShortcut(key("ArrowLeft", { target }))).toBeNull();
    expect(previewShortcut(key("ArrowRight", { ctrlKey: true }))).toBeNull();
  });

  it("keeps page navigation within the archive", () => {
    expect(pageAfterShortcut(0, 3, "previous-page")).toBe(0);
    expect(pageAfterShortcut(1, 3, "previous-page")).toBe(0);
    expect(pageAfterShortcut(1, 3, "next-page")).toBe(2);
    expect(pageAfterShortcut(2, 3, "next-page")).toBe(2);
  });

  it("formats native tooltip hints", () => {
    expect(shortcutTooltip("Save", "Ctrl+S / Cmd+S")).toBe(
      "Save (Ctrl+S / Cmd+S)",
    );
  });
});
