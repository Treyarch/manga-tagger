import { describe, expect, it } from "vitest";

import {
  POLL_MS,
  convertConfirmMessage,
  editField,
  entryErrorLines,
  filenameStem,
  filterVolumes,
  formFromVolumes,
  initialPageIndex,
  jobLabel,
  folderDropRequest,
  parseRootLines,
  placeAfterLibrary,
  renamePlanLines,
  requestsPage,
  savePatch,
  scanRootLines,
  selectPlain,
  selectRange,
  selectToggle,
  selectionAfterEntries,
  selectionAfterFilter,
  selectionFromClick,
  seriesForSearch,
  volumesInPlace,
  type Volume,
} from "./library";

function volume(path: string, extra: Partial<Volume> = {}): Volume {
  const name = path.split("/").pop() ?? path;
  return {
    path,
    root: path.slice(0, path.lastIndexOf("/")),
    name,
    extension: name.slice(name.lastIndexOf(".")),
    status: "ok",
    error_type: "",
    error_message: "",
    cover_index: 0,
    archive_page_count: 3,
    title: "",
    series: "",
    number: "",
    volume: "",
    publisher: "",
    page_count: "",
    language_iso: "",
    age_rating: "",
    manga: "",
    genre: "",
    summary: "",
    web: "",
    community_rating: "",
    notes: "",
    year: "",
    month: "",
    day: "",
    writer: "",
    penciller: "",
    inker: "",
    cover_artist: "",
    ...extra,
  };
}

describe("shelf and selection", () => {
  it("keeps a place's direct volumes and filters by series", () => {
    const rows = [
      volume("/books/Claymore/a.cbz", { series: "Claymore" }),
      volume("/books/Claymore/extra/v01.cbz", { series: "Claymore" }),
      volume("/books/Other/b.cbz", { series: "Other" }),
    ];
    expect(volumesInPlace(rows, "/books/Claymore").map((row) => row.name)).toEqual([
      "a.cbz",
    ]);
    expect(filterVolumes(rows, "clay").map((row) => row.series)).toEqual([
      "Claymore",
      "Claymore",
    ]);
    expect(filterVolumes(rows, "   ")).toHaveLength(3);
  });

  it("follows plain, range, and toggle clicks", () => {
    const visible = ["a", "b", "c", "d"];
    const plain = selectPlain(visible, "b");
    expect(selectRange(visible, plain, "d")).toEqual({
      paths: ["b", "c", "d"],
      anchor: "b",
    });
    const toggled = selectToggle(visible, selectPlain(visible, "c"), "a");
    expect(toggled).toEqual({ paths: ["a", "c"], anchor: "c" });
    expect(selectToggle(visible, toggled, "c").anchor).toBe("a");
    expect(
      selectionFromClick(visible, plain, "d", { shift: true, toggle: false }).anchor,
    ).toBe("b");
  });

  it("moves a hidden anchor to the first remaining path", () => {
    const selection = selectToggle(
      ["a", "b", "c"],
      selectPlain(["a", "b", "c"], "a"),
      "b",
    );
    expect(selectionAfterFilter(["b", "c"], selection)).toEqual({
      paths: ["b"],
      anchor: "b",
    });
  });
});

describe("form", () => {
  it("builds one volume and a shared form", () => {
    const one = formFromVolumes([volume("/books/a.cbz", { number: "4" })]);
    expect(one?.mode).toBe("one");
    expect(one?.values.Number).toEqual({ value: "4", dirty: false });
    expect(one?.values.Pages).toBeUndefined();
    const edited = editField(one!, "Number", "9");
    expect(edited.values.Number).toEqual({ value: "9", dirty: true });
    expect(savePatch(edited)).toEqual({ Number: "9" });

    const many = formFromVolumes([
      volume("/books/a.cbz", { series: "Claymore", publisher: "Shueisha", manga: "No" }),
      volume("/books/b.cbz", { series: "Monster", publisher: "Shueisha", manga: "No" }),
    ]);
    expect(Object.keys(many?.values ?? [])).toContain("Manga");
    expect(many?.values.Series).toEqual({ value: "", mixed: true, dirty: false });
    expect(many?.values.Publisher).toEqual({
      value: "Shueisha",
      mixed: false,
      dirty: false,
    });
    expect(Object.values(many!.values).every((field) => field.dirty === false)).toBe(
      true,
    );
    const changed = editField(many!, "Publisher", "");
    expect(savePatch(changed)).toEqual({ Publisher: "" });
    expect(savePatch(changed).Series).toBeUndefined();
    expect(savePatch(changed).Number).toBeUndefined();
  });

  it("uses series for scrape only when it is set and not mixed", () => {
    const one = formFromVolumes([volume("/books/a.cbz", { series: " Claymore " })])!;
    expect(seriesForSearch(one)).toBe(" Claymore ");
    expect(seriesForSearch(editField(one, "Series", "  "))).toBe("");
    const many = formFromVolumes([
      volume("/books/a.cbz", { series: "A" }),
      volume("/books/b.cbz", { series: "B" }),
    ])!;
    expect(seriesForSearch(many)).toBe("");
    expect(filenameStem("Claymore v02.cbz")).toBe("Claymore v02");
  });
});

describe("jobs and dialogs", () => {
  it("labels progress, plans renames, and confirms convert", () => {
    expect(POLL_MS).toBe(500);
    expect(jobLabel({ name: "Save", completed: 3, total: 40 })).toBe("Save 3/40");
    expect(jobLabel({ name: "Scan", completed: 0, total: 0 })).toBe("Scan");
    expect(
      renamePlanLines([
        { path: "/books/old.cbz", output_path: "/books/Claymore v01.cbz" },
        { path: "/books/bad.cbz", error_message: "conflict" },
      ]),
    ).toEqual(["old.cbz → Claymore v01.cbz", "bad.cbz: conflict"]);
    expect(entryErrorLines([{ path: "/books/a.cbz", error_message: "nope" }])).toEqual([
      "a.cbz: nope",
    ]);
    expect(convertConfirmMessage(2)).toBe(
      "Convert 2 CBR files to CBZ and delete the originals?",
    );
    expect(
      scanRootLines({ skipped: ["/missing"], incomplete: ["/locked"] }),
    ).toEqual(["/missing was skipped.", "/locked was not fully scanned."]);
    expect(scanRootLines({})).toEqual([]);
  });

  it("updates saved paths and drops a failed path that left the library", () => {
    const next = selectionAfterEntries(
      { paths: ["/books/a.cbz", "/books/b.cbz"], anchor: "/books/a.cbz" },
      [
        { path: "/books/a.cbz", output_path: "/books/a-new.cbz" },
        { path: "/books/b.cbz", error_message: "failed" },
      ],
      new Set(["/books/a-new.cbz"]),
    );
    expect(next).toEqual({ paths: ["/books/a-new.cbz"], anchor: "/books/a-new.cbz" });
  });

  it("turns a folder drop into a roots request", () => {
    expect(folderDropRequest({ paths: ["/books", "", 3, "/other"] })).toEqual({
      paths: ["/books", "/other"],
    });
    expect(folderDropRequest(null)).toEqual({ paths: [] });
    expect(folderDropRequest({ paths: "nope" })).toEqual({ paths: [] });
  });

  it("rejects a relative settings root and keeps absolute ones", () => {
    expect(parseRootLines("\n/books\n\n").roots).toEqual(["/books"]);
    expect(parseRootLines("/books\nrelative").error).toBe("Paths must be absolute.");
  });

  it("starts the preview at the cover and skips a failed archive", () => {
    expect(initialPageIndex(null, 4)).toBe(0);
    expect(initialPageIndex(9, 4)).toBe(0);
    expect(initialPageIndex(2, 4)).toBe(2);
    expect(initialPageIndex(0, 0)).toBeNull();
    expect(requestsPage(volume("/books/a.cbz", { status: "failed" }))).toBe(false);
    expect(placeAfterLibrary(null, [{ path: "/books", label: "books" }])).toBe(
      "/books",
    );
    expect(placeAfterLibrary("/gone", [{ path: "/books", label: "books" }])).toBe(
      "/books",
    );
  });
});
