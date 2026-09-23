import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Job } from "./library";
import {
  TOAST_MS,
  clearToasts,
  dismissToast,
  jobToastMessage,
  listToasts,
  pushToast,
  subscribeToasts,
} from "./toast";

function job(partial: Partial<Job> & Pick<Job, "name" | "state">): Job {
  return {
    id: "1",
    error_type: "",
    error_message: "",
    result: null,
    completed: 0,
    total: 0,
    ...partial,
  };
}

describe("jobToastMessage", () => {
  it("returns null for cancelled and non-terminal states", () => {
    expect(jobToastMessage(job({ name: "Save", state: "cancelled" }))).toBeNull();
    expect(jobToastMessage(job({ name: "Save", state: "running" }))).toBeNull();
  });

  it("summarizes scrape search results", () => {
    expect(
      jobToastMessage(
        job({
          name: "Search",
          state: "succeeded",
          result: {
            candidates: [
              {
                id: "a",
                title: "A",
                year: "",
                credit: "",
                count: "",
                summary: "",
                cover: "",
              },
            ],
          },
        }),
      ),
    ).toEqual({ message: "Found 1 matches.", tone: "ok" });
    expect(
      jobToastMessage(
        job({ name: "Search", state: "succeeded", result: { candidates: [] } }),
      ),
    ).toEqual({ message: "No matches.", tone: "ok" });
    expect(
      jobToastMessage(
        job({
          name: "Search",
          state: "failed",
          error_message: "rate limited",
        }),
      ),
    ).toEqual({ message: "rate limited", tone: "error" });
    expect(
      jobToastMessage(job({ name: "Search", state: "failed" })),
    ).toEqual({ message: "Scrape failed.", tone: "error" });
  });

  it("summarizes load and scan", () => {
    expect(jobToastMessage(job({ name: "Load", state: "succeeded" }))).toEqual({
      message: "Metadata loaded.",
      tone: "ok",
    });
    expect(jobToastMessage(job({ name: "Scan", state: "succeeded" }))).toEqual({
      message: "Library updated.",
      tone: "ok",
    });
    expect(
      jobToastMessage(job({ name: "Load", state: "failed", error_message: "" })),
    ).toEqual({ message: "Load failed.", tone: "error" });
    expect(
      jobToastMessage(job({ name: "Scan", state: "failed", error_message: "boom" })),
    ).toEqual({ message: "boom", tone: "error" });
  });

  it("counts save rename and convert entries", () => {
    expect(
      jobToastMessage(
        job({
          name: "Save",
          state: "succeeded",
          result: {
            entries: [
              { path: "/a.cbz", output_path: "/a.cbz" },
              { path: "/b.cbz", output_path: "/b.cbz" },
            ],
          },
        }),
      ),
    ).toEqual({ message: "Saved 2 volumes.", tone: "ok" });

    expect(
      jobToastMessage(
        job({
          name: "Rename",
          state: "succeeded",
          result: {
            entries: [
              { path: "/a.cbz", output_path: "/A.cbz" },
              { path: "/b.cbz", error_message: "conflict" },
            ],
          },
        }),
      ),
    ).toEqual({ message: "Renamed 1 of 2.", tone: "ok" });

    expect(
      jobToastMessage(
        job({
          name: "Convert",
          state: "succeeded",
          result: {
            entries: [
              { path: "/a.cbz", skipped: true },
              { path: "/b.cbr", output_path: "/b.cbz" },
              { path: "/c.cbr", error_message: "bad" },
            ],
          },
        }),
      ),
    ).toEqual({ message: "Converted 1 of 2.", tone: "ok" });

    expect(
      jobToastMessage(
        job({ name: "Save", state: "succeeded", result: { entries: [] } }),
      ),
    ).toEqual({ message: "Saved 0 volumes.", tone: "ok" });

    expect(
      jobToastMessage(job({ name: "Save", state: "failed" })),
    ).toEqual({ message: "Save failed.", tone: "error" });
  });
});

describe("toast queue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearToasts();
  });

  afterEach(() => {
    clearToasts();
    vi.useRealTimers();
  });

  it("pushes items and notifies subscribers", () => {
    const seen: number[][] = [];
    const stop = subscribeToasts((items) => {
      seen.push(items.map((item) => item.id));
    });
    const id = pushToast("Saved 1 volumes.");
    expect(listToasts()).toEqual([
      { id, message: "Saved 1 volumes.", tone: "ok" },
    ]);
    expect(seen.at(-1)).toEqual([id]);
    stop();
  });

  it("dismisses on click helper and after five seconds", () => {
    const id = pushToast("Library updated.");
    dismissToast(id);
    expect(listToasts()).toEqual([]);

    const later = pushToast("Metadata loaded.", "ok");
    vi.advanceTimersByTime(TOAST_MS - 1);
    expect(listToasts()).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(listToasts().find((item) => item.id === later)).toBeUndefined();
  });
});
