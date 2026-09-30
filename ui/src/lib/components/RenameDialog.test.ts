import { render } from "svelte/server";
import { describe, expect, it } from "vitest";

import { RENAME_TAGS, renameToken } from "../rename";
import RenameDialog from "./RenameDialog.svelte";

describe("RenameDialog", () => {
  it("renders every rename tag as a draggable, activatable chip", () => {
    const { body } = render(RenameDialog, {
      props: {
        template: "{Series} v{Number:02}",
        lines: [],
        error: "",
        onTemplate: () => undefined,
        onDismiss: () => undefined,
        onConfirm: () => undefined,
      },
    });

    expect(body.match(/draggable="true"/g)).toHaveLength(RENAME_TAGS.length);
    for (const tag of RENAME_TAGS) {
      const token = renameToken(tag);
      expect(body).toContain(`aria-label="Insert ${token}"`);
      expect(body).toContain(`title="Drag or click to insert ${token}"`);
    }
  });

  it("keeps a long rename preview in its own bounded scroll region", () => {
    const { body } = render(RenameDialog, {
      props: {
        template: "{Series}",
        lines: ["old.cbz → new.cbz"],
        error: "",
        onTemplate: () => undefined,
        onDismiss: () => undefined,
        onConfirm: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Rename preview"');
    expect(body).toContain("max-h-64");
    expect(body).toContain("overflow-y-auto");
  });
});
