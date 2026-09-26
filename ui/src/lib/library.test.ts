import { describe, expect, it } from "vitest";

import {
  POLL_MS,
  FORM_FIELDS,
  SHARED_FIELDS,
  candidatesOf,
  clampProvider,
  convertConfirmMessage,
  editField,
  enabledProviderOptions,
  entryErrorLines,
  dirtyFieldClass,
  fieldLabel,
  filenameStem,
  formFromVolumes,
  groupVolumesBySeries,
  initialPageIndex,
  issuesOf,
  jobLabel,
  folderDropRequest,
  mangaChoices,
  mangaLabel,
  matchCoverSrc,
  parseRootLines,
  placeAfterLibrary,
  preferredIssueNumber,
  preferredIssueId,
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
  volumesForShelf,
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
    count: "",
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
  it("keeps a place's direct volumes and shelves by place", () => {
    const rows = [
      volume("/books/Claymore/a.cbz", { series: "Claymore" }),
      volume("/books/Claymore/extra/v01.cbz", { series: "Claymore" }),
      volume("/books/Other/b.cbz", { series: "Other" }),
    ];
    expect(volumesInPlace(rows, "/books/Claymore").map((row) => row.name)).toEqual([
      "a.cbz",
    ]);
    expect(volumesForShelf(rows, null).map((row) => row.name)).toEqual([
      "a.cbz",
      "b.cbz",
      "v01.cbz",
    ]);
    expect(volumesForShelf(rows, "/books/Claymore").map((row) => row.name)).toEqual([
      "a.cbz",
    ]);
  });

  it("groups blank series first, then named series alphabetically", () => {
    const rows = [
      volume("/books/z.cbz", { series: "Zebra" }),
      volume("/books/a2.cbz", { series: "Aposimz" }),
      volume("/books/plain.cbz", { series: "" }),
      volume("/books/a1.cbz", { series: "Aposimz" }),
      volume("/books/spaced.cbz", { series: "  " }),
    ];
    const groups = groupVolumesBySeries(rows);
    expect(groups.map((group) => group.series)).toEqual(["", "Aposimz", "Zebra"]);
    expect(groups[0].volumes.map((row) => row.name)).toEqual([
      "plain.cbz",
      "spaced.cbz",
    ]);
    expect(groups[1].volumes.map((row) => row.name)).toEqual([
      "a2.cbz",
      "a1.cbz",
    ]);
  });

  it("proxies MangaDex covers through /api/cover", () => {
    expect(
      matchCoverSrc("https://uploads.mangadex.org/covers/a/b.jpg.256.jpg"),
    ).toBe(
      "/api/cover?url=" +
        encodeURIComponent("https://uploads.mangadex.org/covers/a/b.jpg.256.jpg"),
    );
    expect(matchCoverSrc("https://s4.anilist.co/file/x.jpg")).toBe(
      "https://s4.anilist.co/file/x.jpg",
    );
    expect(matchCoverSrc("  ")).toBe("");
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
    expect(editField(one!, "Number", "4").values.Number).toEqual({
      value: "4",
      dirty: false,
    });
    expect(savePatch(edited)).toEqual({ Number: "9" });

    const many = formFromVolumes([
      volume("/books/a.cbz", { series: "Claymore", publisher: "Shueisha", manga: "No" }),
      volume("/books/b.cbz", { series: "Monster", publisher: "Shueisha", manga: "No" }),
    ]);
    expect(Object.keys(many?.values ?? [])).toContain("Manga");
    expect(Object.keys(many?.values ?? [])).toContain("AgeRating");
    expect(Object.keys(many!.values)).toEqual([...SHARED_FIELDS]);
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

  it("maps ComicInfo keys to readable field captions", () => {
    expect(fieldLabel("PageCount")).toBe("Page count");
    expect(fieldLabel("LanguageISO")).toBe("Language");
    expect(fieldLabel("AgeRating")).toBe("Age rating");
    expect(fieldLabel("CommunityRating")).toBe("Community rating");
    expect(fieldLabel("CoverArtist")).toBe("Cover artist");
    expect(fieldLabel("Number")).toBe("Issue");
    expect(fieldLabel("Count")).toBe("Volumes");
    expect(fieldLabel("Title")).toBe("Title");
    expect(FORM_FIELDS.every((name) => fieldLabel(name).length > 0)).toBe(true);
  });

  it("returns amber dirty classes only when the field is dirty", () => {
    expect(dirtyFieldClass(false)).toBe("");
    expect(dirtyFieldClass(true)).toBe(
      "border-amber-600 text-amber-700 dark:border-amber-500 dark:text-amber-400",
    );
  });

  it("maps Manga tokens to readable select captions", () => {
    expect(mangaLabel("YesAndRightToLeft")).toBe("Yes (right to left)");
    expect(mangaLabel("YesAndLeftToRight")).toBe("Yes (left to right)");
    expect(mangaLabel("Yes")).toBe("Yes");
    expect(mangaLabel("No")).toBe("No");
    expect(mangaLabel("")).toBe("");
    expect(mangaLabel("WeirdToken")).toBe("WeirdToken");
    expect(mangaChoices("WeirdToken")).toEqual([
      "YesAndRightToLeft",
      "Yes",
      "No",
      "YesAndLeftToRight",
      "",
      "WeirdToken",
    ]);
  });

  it("fills PageCount from the archive when ComicInfo left it blank", () => {
    const filled = formFromVolumes([
      volume("/books/a.cbz", { page_count: "", archive_page_count: 42 }),
    ])!;
    expect(filled.values.PageCount).toEqual({ value: "42", dirty: false });

    const kept = formFromVolumes([
      volume("/books/a.cbz", { page_count: "10", archive_page_count: 42 }),
    ])!;
    expect(kept.values.PageCount).toEqual({ value: "10", dirty: false });

    const missing = formFromVolumes([
      volume("/books/a.cbz", { page_count: "", archive_page_count: null }),
    ])!;
    expect(missing.values.PageCount).toEqual({ value: "", dirty: false });
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

  it("filters and clamps enabled providers", () => {
    expect(enabledProviderOptions(["mangadex", "nope", "nautiljon"])).toEqual([
      { value: "mangadex", label: "MangaDex" },
      { value: "nautiljon", label: "Nautiljon" },
    ]);
    expect(enabledProviderOptions([])).toEqual([]);
    expect(clampProvider("anilist", ["mangadex", "anilist"])).toBe("anilist");
    expect(clampProvider("jikan", ["mangadex", "anilist"])).toBe("mangadex");
    expect(clampProvider("jikan", [])).toBe("");
  });

  it("starts the preview at the cover and skips a failed archive", () => {
    expect(initialPageIndex(null, 4)).toBe(0);
    expect(initialPageIndex(9, 4)).toBe(0);
    expect(initialPageIndex(2, 4)).toBe(2);
    expect(initialPageIndex(0, 0)).toBeNull();
    expect(requestsPage(volume("/books/a.cbz", { status: "failed" }))).toBe(false);
    expect(placeAfterLibrary(null, [{ path: "/books", label: "books" }])).toBe(
      null,
    );
    expect(placeAfterLibrary("/gone", [{ path: "/books", label: "books" }])).toBe(
      null,
    );
    expect(
      placeAfterLibrary("/books", [{ path: "/books", label: "books" }]),
    ).toBe("/books");
  });

  it("maps search candidates from the job result", () => {
    expect(
      candidatesOf({
        candidates: [
          {
            id: "1",
            title: "Claymore",
            year: 2001,
            credit: "Yagi",
            count: 27,
            summary: "A story.",
            cover: "https://example.com/c.jpg",
          },
          null,
          { title: "Bare" },
        ],
      }),
    ).toEqual([
      {
        id: "1",
        title: "Claymore",
        year: "2001",
        credit: "Yagi",
        count: "27",
        summary: "A story.",
        cover: "https://example.com/c.jpg",
      },
      {
        id: "",
        title: "Bare",
        year: "",
        credit: "",
        count: "",
        summary: "",
        cover: "",
      },
    ]);
    expect(candidatesOf(null)).toEqual([]);
    expect(candidatesOf({ candidates: "nope" })).toEqual([]);
  });

  it("maps issues from the job result", () => {
    expect(
      issuesOf({
        issues: [
          {
            id: 10,
            number: 1,
            title: "First",
            date: "2001-03",
            cover: "https://example.com/1.jpg",
            summary: "One",
          },
          null,
          { number: "2" },
        ],
      }),
    ).toEqual([
      {
        id: "10",
        number: "1",
        title: "First",
        date: "2001-03",
        cover: "https://example.com/1.jpg",
        summary: "One",
      },
      {
        id: "",
        number: "2",
        title: "",
        date: "",
        cover: "",
        summary: "",
      },
    ]);
    expect(issuesOf(null)).toEqual([]);
    expect(issuesOf({ issues: "nope" })).toEqual([]);
  });

  it("reads preferred issue number from the form", () => {
    expect(preferredIssueNumber(formFromVolumes([volume("/a.cbz", { number: "3" })]))).toBe(
      "3",
    );
    expect(preferredIssueNumber(null)).toBe("");
  });

  it("picks the preferred issue id by normalized number", () => {
    const issues = [
      { id: "a", number: "1" },
      { id: "b", number: "02" },
      { id: "c", number: "10.5" },
    ];
    expect(preferredIssueId(issues, "2")).toBe("b");
    expect(preferredIssueId(issues, "10.5")).toBe("c");
    expect(preferredIssueId(issues, "99")).toBe("a");
    expect(preferredIssueId(issues, "")).toBe("a");
    expect(preferredIssueId([], "2")).toBeNull();
  });
});
