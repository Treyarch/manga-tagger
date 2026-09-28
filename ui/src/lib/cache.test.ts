import { describe, expect, it } from "vitest";

import {
  cacheResultMessage,
  clearThumbnailCache,
  thumbnailRevision,
} from "./cache";

describe("cacheResultMessage", () => {
  it("describes empty, singular, and plural clears", () => {
    expect(cacheResultMessage(0)).toBe("Cache is already empty.");
    expect(cacheResultMessage(1)).toBe("Cleared 1 cached thumbnail.");
    expect(cacheResultMessage(3)).toBe("Cleared 3 cached thumbnails.");
  });
});

describe("thumbnailRevision", () => {
  it("changes every thumbnail URL generation without losing cover revisions", () => {
    expect(thumbnailRevision(0, "")).toBe("");
    expect(thumbnailRevision(0, "17")).toBe("cover-17");
    expect(thumbnailRevision(1, "17")).toBe("cache-1:cover-17");
    expect(thumbnailRevision(2, "17")).toBe("cache-2:cover-17");
  });
});

describe("clearThumbnailCache", () => {
  it("reports success without changing unrelated drafts", async () => {
    const draft = { roots: "/books/draft", theme: "dark" };
    let revisions = 0;

    await expect(
      clearThumbnailCache(async () => ({ removed: 2 }), () => (revisions += 1)),
    ).resolves.toBe("Cleared 2 cached thumbnails.");
    expect(revisions).toBe(1);
    expect(draft).toEqual({ roots: "/books/draft", theme: "dark" });
  });

  it("propagates failures without advancing the thumbnail revision", async () => {
    let revisions = 0;

    await expect(
      clearThumbnailCache(
        async () => {
          throw new Error("Cache is busy.");
        },
        () => (revisions += 1),
      ),
    ).rejects.toThrow("Cache is busy.");
    expect(revisions).toBe(0);
  });
});
