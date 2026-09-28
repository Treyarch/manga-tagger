import { describe, expect, it } from "vitest";
import { withChangedLibraryRoots, type Config } from "./api";

describe("Settings config updates", () => {
  it("omits unchanged roots so unrelated settings can save during a job", () => {
    const update = withChangedLibraryRoots(
      { theme: "dark" } as Partial<Config>,
      ["/books", "/manga"],
      ["/books", "/manga"],
    );

    expect(update).toEqual({ theme: "dark" });
    expect("library_roots" in update).toBe(false);
  });

  it("includes changed and empty roots so the returned scan can be watched", () => {
    expect(withChangedLibraryRoots({}, ["/books"], ["/manga"])).toEqual({
      library_roots: ["/manga"],
    });
    expect(withChangedLibraryRoots({}, ["/books"], [])).toEqual({
      library_roots: [],
    });
  });
});
