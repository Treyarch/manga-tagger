import { describe, expect, it } from "vitest";

import { applyDocumentClass, resolveDark } from "./theme";

describe("resolveDark", () => {
  it("forces light and dark and follows the system otherwise", () => {
    expect(resolveDark("light", true)).toBe(false);
    expect(resolveDark("light", false)).toBe(false);
    expect(resolveDark("dark", true)).toBe(true);
    expect(resolveDark("dark", false)).toBe(true);
    expect(resolveDark("system", true)).toBe(true);
    expect(resolveDark("system", false)).toBe(false);
    expect(resolveDark("nope", true)).toBe(true);
    expect(resolveDark("nope", false)).toBe(false);
  });
});

describe("applyDocumentClass", () => {
  it("adds dark for a resolved dark theme and removes it for light", () => {
    const names = new Set<string>();
    const root = {
      classList: {
        add(name: string) {
          names.add(name);
        },
        remove(name: string) {
          names.delete(name);
        },
        contains(name: string) {
          return names.has(name);
        },
      },
    };
    applyDocumentClass(root, resolveDark("dark", false));
    expect(root.classList.contains("dark")).toBe(true);
    applyDocumentClass(root, resolveDark("light", true));
    expect(root.classList.contains("dark")).toBe(false);
  });
});
