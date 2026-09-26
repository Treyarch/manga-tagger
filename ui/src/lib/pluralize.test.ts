import { describe, expect, it } from "vitest";
import { pluralize } from "./pluralize";

describe("pluralize", () => {
  it("uses singular only for count 1", () => {
    expect(pluralize(0, "file")).toBe("files");
    expect(pluralize(1, "file")).toBe("file");
    expect(pluralize(2, "file")).toBe("files");
  });

  it("accepts an explicit plural form", () => {
    expect(pluralize(1, "match", "matches")).toBe("match");
    expect(pluralize(0, "match", "matches")).toBe("matches");
    expect(pluralize(3, "match", "matches")).toBe("matches");
  });
});
