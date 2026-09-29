import { describe, expect, it } from "vitest";

import type { Config } from "./api";
import { appendFolderPath, removeFolderPath, SETTINGS_TABS } from "./settings";

describe("Settings sections", () => {
  it("keeps the Library section between General and Archives", () => {
    expect(SETTINGS_TABS.map(({ id, label }) => ({ id, label }))).toEqual([
      { id: "general", label: "General" },
      { id: "library", label: "Library" },
      { id: "archives", label: "Archives" },
      { id: "scrapers", label: "Scrapers" },
      { id: "cache", label: "Cache" },
    ]);
  });

  it("assigns every library discovery setting only to Library", () => {
    const ownership = Object.fromEntries(
      SETTINGS_TABS.flatMap((tab) =>
        tab.configKeys.map((key) => [key, tab.id] as const),
      ),
    ) as Record<keyof Config, string>;

    expect(ownership.library_roots).toBe("library");
    expect(ownership.scan_subfolders).toBe("library");
    expect(ownership.excluded_folders).toBe("library");
    expect(Object.keys(ownership)).toHaveLength(13);
  });

  it("appends folder choices in order without duplicates", () => {
    expect(appendFolderPath(["/books"], "/manga")).toEqual([
      "/books",
      "/manga",
    ]);
    expect(appendFolderPath(["/books", "/manga"], "/books")).toEqual([
      "/books",
      "/manga",
    ]);
  });

  it("removes only the selected folder", () => {
    expect(removeFolderPath(["/books", "/manga", "/comics"], "/manga")).toEqual([
      "/books",
      "/comics",
    ]);
    expect(removeFolderPath(["/books"], "/missing")).toEqual(["/books"]);
  });
});
