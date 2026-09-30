import { describe, expect, it } from "vitest";
import appContract from "../../../tests/contracts/app-contracts.json";
import scanJobContract from "../../../tests/contracts/scan-job-result.json";

import {
  FIELD_COLUMNS,
  POLL_MS,
  FORM_FIELDS,
  PROVIDERS,
  SHARED_FIELDS,
  candidatesOf,
  cbrCount,
  claimJobSettlement,
  coverProviderFromWeb,
  canFetchCoverFromWeb,
  coverPageIndex,
  preserveDirtyFields,
  shouldRefetchLibrary,
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
  folderDropRequest,
  excludedFoldersAfterRemove,
  mangaChoices,
  mangaLabel,
  matchCoverSrc,
  thumbnailSrc,
  placeAfterLibrary,
  placeFromClick,
  preferredIssueNumber,
  preferredIssueId,
  renamePlanLines,
  requestsPage,
  savePatch,
  saveAllowsPendingNavigation,
  savePreservesDraft,
  scanRootLines,
  selectPlain,
  selectRange,
  selectToggle,
  selectionAfterEntries,
  selectionAfterFilter,
  selectionFromClick,
  seriesGroupLabel,
  seriesForSearch,
  switchGuard,
  volumesForShelf,
  volumesInPlace,
  type Candidate,
  type IssueCandidate,
  type Job,
  type ScanResult,
  type Volume,
  type WorkEntry,
} from "./library";
import { RENAME_TAGS } from "./rename";

function volume(path: string, extra: Partial<Volume> = {}): Volume {
  const name = path.split("/").pop() ?? path;
  return {
    path,
    root: path.slice(0, path.lastIndexOf("/")),
    name,
    extension: name.slice(name.lastIndexOf(".") + 1).toLowerCase(),
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
    locked_fields: "[]",
    ...extra,
  };
}

describe("cross-layer contracts", () => {
  it("matches fields, columns, providers, locks, and constructed forms", () => {
    expect([...FORM_FIELDS]).toEqual(appContract.form_fields);
    expect([...RENAME_TAGS]).toEqual(appContract.rename_tags);
    expect([...SHARED_FIELDS]).toEqual(appContract.shared_fields);
    expect(FIELD_COLUMNS).toEqual(appContract.field_columns);
    expect([...FORM_FIELDS]).toEqual(appContract.lockable_fields);
    expect(PROVIDERS.map(({ id }) => id)).toEqual(appContract.provider_ids);

    const one = formFromVolumes([volume("/books/a.cbz")]);
    const many = formFromVolumes([
      volume("/books/a.cbz"),
      volume("/books/b.cbz"),
    ]);
    expect(Object.keys(one!.values)).toEqual(appContract.form_fields);
    expect(Object.keys(many!.values)).toEqual(appContract.shared_fields);
  });

  it("matches API result keys", () => {
    const job = {
      id: "1",
      name: "Scan",
      state: "succeeded",
      error_type: "",
      error_message: "",
      result: null,
      completed: 0,
      total: 0,
    } satisfies Job;
    const scan = {
      written: [],
      unchanged: [],
      failed: [],
      deleted: [],
      skipped: [],
      incomplete: [],
      cancelled: false,
    } satisfies ScanResult;
    const candidate = {
      id: "",
      title: "",
      year: "",
      credit: "",
      count: "",
      summary: "",
      cover: "",
    } satisfies Candidate;
    const issue = {
      id: "",
      number: "",
      title: "",
      date: "",
      cover: "",
      summary: "",
    } satisfies IssueCandidate;
    const workEntry = {
      path: "",
      output_path: null,
      error_type: "",
      error_message: "",
      skipped: false,
    } satisfies WorkEntry;

    expect(Object.keys(job)).toEqual(appContract.api_result_keys.job);
    expect(Object.keys(scan)).toEqual(appContract.api_result_keys.scan);
    expect(Object.keys(candidate)).toEqual(appContract.api_result_keys.candidate);
    expect(Object.keys(issue)).toEqual(appContract.api_result_keys.issue);
    expect(Object.keys(workEntry)).toEqual(appContract.api_result_keys.work_entry);
  });
});

describe("shelf and selection", () => {
  it("adds a removed sidebar folder to exclusions once", () => {
    expect(excludedFoldersAfterRemove([], "/books/Extras")).toEqual([
      "/books/Extras",
    ]);
    expect(
      excludedFoldersAfterRemove(["/books/Extras"], "/books/Extras"),
    ).toEqual(["/books/Extras"]);
  });

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

  it("selects, toggles, and clears a place from sidebar clicks", () => {
    expect(placeFromClick(null, "/books/Claymore")).toBe("/books/Claymore");
    expect(placeFromClick("/books/Claymore", "/books/Other")).toBe(
      "/books/Other",
    );
    expect(placeFromClick("/books/Claymore", "/books/Claymore")).toBeNull();
    expect(placeFromClick("/books/Claymore", null)).toBeNull();
    expect(placeFromClick(null, null)).toBeNull();
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

  it("labels the blank series group as Untitled", () => {
    expect(seriesGroupLabel("")).toBe("Untitled");
    expect(seriesGroupLabel("   ")).toBe("Untitled");
    expect(seriesGroupLabel("  A Town Where You Live  ")).toBe(
      "A Town Where You Live",
    );
  });

  it("builds a thumbnail URL from the archive path", () => {
    expect(thumbnailSrc("/books/Claymore/a.cbz")).toBe(
      "/api/thumbnail?path=" + encodeURIComponent("/books/Claymore/a.cbz"),
    );
    expect(thumbnailSrc("/books/Claymore/a.cbz", "cache-1:cover-2")).toBe(
      "/api/thumbnail?path=" +
        encodeURIComponent("/books/Claymore/a.cbz") +
        "&revision=" +
        encodeURIComponent("cache-1:cover-2"),
    );
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
    expect(one?.values.Number).toEqual({
      value: "4",
      dirty: false,
      locked: false,
    });
    expect(one?.values.Pages).toBeUndefined();
    const edited = editField(one!, "Number", "9");
    expect(edited.values.Number).toEqual({
      value: "9",
      dirty: true,
      locked: false,
    });
    expect(editField(one!, "Number", "4").values.Number).toEqual({
      value: "4",
      dirty: false,
      locked: false,
    });
    expect(savePatch(edited)).toEqual({ Number: "9" });

    const many = formFromVolumes([
      volume("/books/a.cbz", { series: "Claymore", publisher: "Shueisha", manga: "No" }),
      volume("/books/b.cbz", { series: "Monster", publisher: "Shueisha", manga: "No" }),
    ]);
    expect(Object.keys(many?.values ?? [])).toContain("Manga");
    expect(Object.keys(many?.values ?? [])).toContain("AgeRating");
    expect(Object.keys(many!.values)).toEqual([...SHARED_FIELDS]);
    expect(many?.values.Series).toEqual({
      value: "",
      mixed: true,
      dirty: false,
      locked: false,
    });
    expect(many?.values.Publisher).toEqual({
      value: "Shueisha",
      mixed: false,
      dirty: false,
      locked: false,
    });
    expect(Object.values(many!.values).every((field) => field.dirty === false)).toBe(
      true,
    );
    const changed = editField(many!, "Publisher", "");
    expect(savePatch(changed)).toEqual({ Publisher: "" });
    expect(savePatch(changed).Series).toBeUndefined();
    expect(savePatch(changed).Number).toBeUndefined();
  });

  it("marks fields locked from the index and blocks edits", () => {
    const one = formFromVolumes([
      volume("/books/a.cbz", {
        series: "Claymore",
        locked_fields: '["Series"]',
      }),
    ]);
    expect(one?.values.Series.locked).toBe(true);
    expect(editField(one!, "Series", "Monster").values.Series.value).toBe("Claymore");
    const mixed = formFromVolumes([
      volume("/books/a.cbz", { series: "A", locked_fields: '["Series"]' }),
      volume("/books/b.cbz", { series: "A", locked_fields: "[]" }),
    ]);
    expect(mixed?.values.Series.locked).toBe(false);
    const both = formFromVolumes([
      volume("/books/a.cbz", { series: "A", locked_fields: '["Series"]' }),
      volume("/books/b.cbz", { series: "A", locked_fields: '["Series"]' }),
    ]);
    expect(both?.values.Series.locked).toBe(true);
  });

  it("guards volume and place switches for dirty forms", () => {
    expect(switchGuard(null, false)).toBe("proceed");
    expect(switchGuard(null, true)).toBe("proceed");
    const clean = formFromVolumes([volume("/books/a.cbz", { number: "4" })]);
    expect(switchGuard(clean, false)).toBe("proceed");
    expect(switchGuard(clean, true)).toBe("proceed");
    const dirty = editField(clean!, "Number", "9");
    expect(switchGuard(dirty, false)).toBe("confirm");
    expect(switchGuard(dirty, true)).toBe("autosave");
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
      "border-app-dirty text-app-dirty",
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
    expect(filled.values.PageCount).toEqual({
      value: "42",
      dirty: false,
      locked: false,
    });

    const kept = formFromVolumes([
      volume("/books/a.cbz", { page_count: "10", archive_page_count: 42 }),
    ])!;
    expect(kept.values.PageCount).toEqual({
      value: "10",
      dirty: false,
      locked: false,
    });

    const missing = formFromVolumes([
      volume("/books/a.cbz", { page_count: "", archive_page_count: null }),
    ])!;
    expect(missing.values.PageCount).toEqual({
      value: "",
      dirty: false,
      locked: false,
    });
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
  it("settles a startup scan exactly once after any busy observations", () => {
    const settled = new Set<string>();
    const scan: Job = {
      id: "1",
      name: "Scan",
      state: "queued",
      error_type: "",
      error_message: "",
      result: null,
      completed: 0,
      total: 0,
    };

    expect(claimJobSettlement(settled, scan)).toBe(false);
    scan.state = "running";
    expect(claimJobSettlement(settled, scan)).toBe(false);
    scan.state = "succeeded";
    expect(claimJobSettlement(settled, scan)).toBe(true);
    expect(claimJobSettlement(settled, scan)).toBe(false);
  });

  function saveJob(
    state: string,
    entries: unknown[],
  ) {
    return {
      id: "1",
      name: "Save",
      state,
      error_type: "",
      error_message: "",
      result: { entries },
      completed: entries.length,
      total: entries.length,
    };
  }

  it("preserves a one-file draft when the archive write fails", () => {
    const job = saveJob("succeeded", [
      { path: "/books/a.cbz", error_type: "ArchiveError", error_message: "write failed" },
    ]);
    expect(savePreservesDraft(job)).toBe(true);
    expect(saveAllowsPendingNavigation(job)).toBe(false);
  });

  it("preserves the shared draft after a partial batch failure", () => {
    const job = saveJob("succeeded", [
      { path: "/books/a.cbz", output_path: "/books/a.cbz" },
      { path: "/books/b.cbz", error_type: "ArchiveError", error_message: "write failed" },
    ]);
    expect(savePreservesDraft(job)).toBe(true);
    expect(saveAllowsPendingNavigation(job)).toBe(false);

    const rows = [
      volume("/books/a.cbz", { series: "Claymore" }),
      volume("/books/b.cbz", { series: "Claymore" }),
    ];
    const draft = editField(formFromVolumes(rows)!, "Publisher", "Kana");
    const rebuilt = formFromVolumes(rows)!;
    const kept = preserveDirtyFields(rebuilt, draft)!;
    expect(kept.values.Publisher.value).toBe("Kana");
    expect(kept.values.Publisher.dirty).toBe(true);
  });

  it("preserves a draft and blocks navigation when save is cancelled", () => {
    const job = saveJob("cancelled", [
      { path: "/books/a.cbz", output_path: "/books/a.cbz" },
    ]);
    expect(savePreservesDraft(job)).toBe(true);
    expect(saveAllowsPendingNavigation(job)).toBe(false);
  });

  it("allows navigation after an unchanged save with no entries", () => {
    const job = saveJob("succeeded", []);
    expect(savePreservesDraft(job)).toBe(false);
    expect(saveAllowsPendingNavigation(job)).toBe(true);
  });

  it("allows navigation after poster-only or index-refresh errors", () => {
    for (const error_message of ["poster failed", "index refresh failed"]) {
      const job = saveJob("succeeded", [
        {
          path: "/books/a.cbz",
          output_path: "/books/a.cbz",
          error_type: "FollowUpError",
          error_message,
        },
      ]);
      expect(savePreservesDraft(job)).toBe(false);
      expect(saveAllowsPendingNavigation(job)).toBe(true);
    }
  });

  it("counts selected CBRs using the library API's dotless extensions", () => {
    expect(cbrCount([volume("/books/a.cbr")])).toBe(1);
    expect(cbrCount([
      volume("/books/a.cbr"),
      volume("/books/b.CBR"),
      volume("/books/c.cbz"),
    ])).toBe(2);
    expect(cbrCount([])).toBe(0);
    expect(cbrCount([volume("/books/a.cbz")])).toBe(0);
    expect(cbrCount([volume("/books/a.cbr", { extension: "CBR" })])).toBe(1);
  });

  it("plans renames and confirms convert", () => {
    expect(POLL_MS).toBe(500);
    expect(
      renamePlanLines([
        { path: "/books/old.cbz", output_path: "/books/Claymore v01.cbz" },
        { path: "/books/bad.cbz", error_message: "conflict" },
      ]),
    ).toEqual(["old.cbz → Claymore v01.cbz", "bad.cbz: conflict"]);
    expect(entryErrorLines([{ path: "/books/a.cbz", error_message: "nope" }])).toEqual([
      "a.cbz: nope",
    ]);
    expect(convertConfirmMessage(1)).toBe(
      "Convert 1 CBR file to CBZ and delete the originals?",
    );
    expect(convertConfirmMessage(2)).toBe(
      "Convert 2 CBR files to CBZ and delete the originals?",
    );
    expect(
      scanRootLines({ skipped: ["/missing"], incomplete: ["/locked"] }),
    ).toEqual(["/missing was skipped.", "/locked was not fully scanned."]);
    expect(scanRootLines(null)).toEqual([]);
  });

  it("formats the scan job endpoint contract", () => {
    expect(scanRootLines(scanJobContract.result)).toEqual(
      scanJobContract.inspector_lines,
    );
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

describe("provider cover actions", () => {
  const config = { enabled_providers: ["mangadex", "anilist", "jikan", "comicvine", "nautiljon"], comicvine_api_key: "", nautiljon_base_url: "", nautiljon_api_key: "" };

  it.each([
    ["https://mangadex.org/title/11111111-2222-3333-4444-555555555555/name", "mangadex"],
    ["https://anilist.co/manga/12/name", "anilist"],
    ["https://myanimelist.net/manga/12/name", "jikan"],
    ["https://comicvine.gamespot.com/name/4050-12/", "comicvine"],
    ["https://comicvine.gamespot.com/name/4000-12/", "comicvine"],
    ["https://www.nautiljon.com/mangas/name.html", "nautiljon"],
    ["https://www.nautiljon.com/mangas/name/volume-3,42.html", "nautiljon"],
    ["https://www.nautiljon.com/mangas/volumes/name,03.html", "nautiljon"],
  ])("parses %s", (url, provider) => {
    expect(coverProviderFromWeb(url)).toBe(provider);
  });

  it.each(["", "bad", "http://anilist.co/manga/1", "https://anilist.co.evil/manga/1", "https://anilist.co/manga/1junk", "https://anilist.co/wrong/manga/1", "https://name@anilist.co/manga/1", "https://nautiljon.com/volume-1,42.html", "https://mangadex.org/title/------------------------------------"])("rejects %s", (url) => {
    expect(canFetchCoverFromWeb(url, config)).toBe(false);
  });

  it("requires enabled and configured providers", () => {
    expect(canFetchCoverFromWeb("https://anilist.co/manga/1", config)).toBe(true);
    expect(canFetchCoverFromWeb("https://anilist.co/manga/1", { ...config, enabled_providers: [] })).toBe(false);
    expect(canFetchCoverFromWeb("https://comicvine.gamespot.com/name/4050-12/", config)).toBe(false);
    expect(canFetchCoverFromWeb("https://comicvine.gamespot.com/name/4050-12/", { ...config, comicvine_api_key: "key" })).toBe(true);
    expect(canFetchCoverFromWeb("https://nautiljon.com/mangas/name.html", config)).toBe(false);
    expect(canFetchCoverFromWeb("https://nautiljon.com/mangas/name.html", { ...config, nautiljon_base_url: "https://wrapper.test", nautiljon_api_key: "key" })).toBe(true);
  });

  it("refreshes computed values without losing unsaved metadata", () => {
    const row = volume("/books/a.cbz", { archive_page_count: 2, web: "https://anilist.co/manga/1" });
    let draft = formFromVolumes([row])!;
    draft = editField(draft, "Web", "https://anilist.co/manga/2");
    draft = editField(draft, "Number", "3");
    const fresh = formFromVolumes([{ ...row, path: "/books/a-converted.cbz", archive_page_count: 3, page_count: "3" }])!;
    const merged = preserveDirtyFields(fresh, draft)!;
    expect(merged.values.Web).toEqual(draft.values.Web);
    expect(merged.values.Number).toEqual(draft.values.Number);
    expect(merged.values.PageCount.value).toBe("3");
    expect(merged.values.PageCount.dirty).toBe(false);
    expect(fresh.values.Web.value).toBe(row.web);
  });

  it("refetches on terminal Cover jobs and chooses the preview cover", () => {
    for (const state of ["succeeded", "failed", "cancelled"]) {
      expect(shouldRefetchLibrary({ id: "1", name: "Cover", state, error_type: "", error_message: "", result: null, completed: 1, total: 1 })).toBe(true);
    }
    expect(coverPageIndex(volume("/a.cbz", { cover_index: 2, archive_page_count: 3 }))).toBe(2);
    expect(coverPageIndex(volume("/a.cbz", { cover_index: null, archive_page_count: 3 }))).toBe(0);
  });
});
