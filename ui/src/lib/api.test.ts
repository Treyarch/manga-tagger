import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getAppVersion,
  withChangedLibraryDiscovery,
  withChangedLibraryRoots,
  type Config,
} from "./api";

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

  it("includes only changed library discovery settings", () => {
    const current = {
      library_roots: ["/books"],
      excluded_folders: [],
      scan_subfolders: true,
    };
    expect(
      withChangedLibraryDiscovery({ theme: "dark" }, current, {
        ...current,
        excluded_folders: ["/books/Extras"],
        scan_subfolders: false,
      }),
    ).toEqual({
      theme: "dark",
      excluded_folders: ["/books/Extras"],
      scan_subfolders: false,
    });
    expect(withChangedLibraryDiscovery({}, current, current)).toEqual({});
  });
});


describe("application version", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("fetches the running backend version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ version: "0.2.0" })));
    vi.stubGlobal("fetch", fetchMock);
    expect(await getAppVersion()).toBe("0.2.0");
    expect(fetchMock).toHaveBeenCalledWith("/api/app-info");
  });

  it.each([{}, { version: 2 }, { version: "" }, { version: "  " }, null])("handles missing or invalid version metadata %j", async (info) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(info))));
    expect(await getAppVersion()).toBeNull();
  });

  it("keeps version lookup optional on network or HTTP failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await getAppVersion()).toBeNull();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 })));
    expect(await getAppVersion()).toBeNull();
  });
});
