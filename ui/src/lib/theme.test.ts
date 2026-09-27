import { describe, expect, it } from "vitest";

import type { SystemTheme } from "./api";
import {
  THEME_PROPERTIES,
  applyDocumentClass,
  applyTheme,
  contrastRatio,
  resolveDark,
  tokensFromSystemTheme,
} from "./theme";

const palette: SystemTheme = {
  mode: "dark",
  background: "#05182e",
  dark_background: "#031222",
  lighter_background: "#0a2540",
  foreground: "#f6dcac",
  dark_foreground: "#3f8f8a",
  accent: "#faa968",
  selection: "#134e5a",
  red: "#f85525",
  yellow: "#e97b3c",
  orange: "#faa968",
};

const lightPalette: SystemTheme = {
  mode: "light",
  background: "#faf4ed",
  dark_background: "#ede7e1",
  lighter_background: "#f2e9e1",
  foreground: "#575279",
  dark_foreground: "#9893a5",
  accent: "#56949f",
  selection: "#dfdad9",
  red: "#b4637a",
  yellow: "#ea9d34",
  orange: "#cf8057",
};

describe("resolveDark", () => {
  it("forces light and dark and follows the system otherwise", () => {
    expect(resolveDark("light", true)).toBe(false);
    expect(resolveDark("light", false)).toBe(false);
    expect(resolveDark("dark", true)).toBe(true);
    expect(resolveDark("dark", false)).toBe(true);
    expect(resolveDark("system", true)).toBe(true);
    expect(resolveDark("system", false)).toBe(false);
    expect(resolveDark("system", false, palette)).toBe(true);
    expect(resolveDark("light", true, palette)).toBe(false);
    expect(resolveDark("nope", true)).toBe(true);
    expect(resolveDark("nope", false)).toBe(false);
    expect(resolveDark("nope", false, palette)).toBe(true);
  });
});

describe("Omarchy semantic tokens", () => {
  it("maps palette roles and adjusts readable text", () => {
    const tokens = tokensFromSystemTheme(palette);
    expect(tokens["--app-window"]).toBe("#031222");
    expect(tokens["--app-view"]).toBe("#05182e");
    expect(tokens["--app-accent"]).toBe("#faa968");
    expect(tokens["--app-selection"]).toBe("#134e5a");
    expect(contrastRatio(tokens["--app-muted"], palette.background)).toBeGreaterThanOrEqual(
      4.49,
    );
    expect(contrastRatio(tokens["--app-dirty"], palette.background)).toBeGreaterThanOrEqual(
      4.49,
    );
    expect(contrastRatio(tokens["--app-on-accent"], palette.accent)).toBeGreaterThanOrEqual(
      4.5,
    );
    const lightTokens = tokensFromSystemTheme(lightPalette);
    expect(lightTokens["--app-window"]).toBe("#ede7e1");
    expect(contrastRatio(lightTokens["--app-dirty"], lightPalette.background)).toBeGreaterThanOrEqual(
      4.49,
    );
  });

  it("applies live palettes and clears them for a forced theme", () => {
    const names = new Set<string>();
    const values = new Map<string, string>();
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
      style: {
        setProperty(name: string, value: string) {
          values.set(name, value);
        },
        removeProperty(name: string) {
          values.delete(name);
        },
      },
    };
    applyTheme(root, "system", false, palette);
    expect(root.classList.contains("dark")).toBe(true);
    expect(values.get("--app-accent")).toBe("#faa968");

    const changed = { ...palette, accent: "#89b4fa" };
    applyTheme(root, "system", false, changed);
    expect(values.get("--app-accent")).toBe("#89b4fa");

    applyTheme(root, "light", true, changed);
    expect(root.classList.contains("dark")).toBe(false);
    expect(values.size).toBe(0);
    expect(THEME_PROPERTIES.length).toBeGreaterThan(10);
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
