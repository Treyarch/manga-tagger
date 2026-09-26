/** Top-center action toast queue and job summary wording. */

import {
  candidatesOf,
  entriesOf,
  issuesOf,
  type Job,
  type WorkEntry,
} from "./library";

export const TOAST_MS = 5000;

export type ToastTone = "ok" | "error";

export type ToastIcon =
  | "check"
  | "save"
  | "pencil"
  | "fileArchive"
  | "scanSearch"
  | "listOrdered"
  | "refreshCw"
  | "alert";

export type ToastItem = {
  id: number;
  message: string;
  tone: ToastTone;
  icon: ToastIcon;
};

export type JobToast = {
  message: string;
  tone: ToastTone;
  icon: ToastIcon;
};

type Listener = (items: ToastItem[]) => void;

let nextId = 1;
let items: ToastItem[] = [];
const listeners = new Set<Listener>();
const timers = new Map<number, ReturnType<typeof setTimeout>>();

function emit(): void {
  const snapshot = items.slice();
  for (const listener of listeners) listener(snapshot);
}

function defaultIcon(tone: ToastTone): ToastIcon {
  return tone === "error" ? "alert" : "check";
}

function jobIcon(job: Job, tone: ToastTone): ToastIcon {
  if (tone === "error") return "alert";
  switch (job.name) {
    case "Search":
      return "scanSearch";
    case "Issues":
      return "listOrdered";
    case "Load":
      return "check";
    case "Save":
      return "save";
    case "Rename":
      return "pencil";
    case "Convert":
      return "fileArchive";
    case "Scan":
      return "refreshCw";
    default:
      return "check";
  }
}

/** Subscribe to the toast list. Calls `fn` immediately with the current items. */
export function subscribeToasts(fn: Listener): () => void {
  listeners.add(fn);
  fn(items.slice());
  return () => {
    listeners.delete(fn);
  };
}

export function listToasts(): ToastItem[] {
  return items.slice();
}

export function pushToast(
  message: string,
  tone: ToastTone = "ok",
  icon?: ToastIcon,
): number {
  const id = nextId++;
  items = [...items, { id, message, tone, icon: icon ?? defaultIcon(tone) }];
  timers.set(
    id,
    setTimeout(() => {
      dismissToast(id);
    }, TOAST_MS),
  );
  emit();
  return id;
}

export function dismissToast(id: number): void {
  const timer = timers.get(id);
  if (timer !== undefined) {
    clearTimeout(timer);
    timers.delete(id);
  }
  const next = items.filter((item) => item.id !== id);
  if (next.length === items.length) return;
  items = next;
  emit();
}

/** Clear every toast and timer. Tests use this between cases. */
export function clearToasts(): void {
  for (const timer of timers.values()) clearTimeout(timer);
  timers.clear();
  items = [];
  emit();
}

function entryOk(entry: WorkEntry): boolean {
  return !entry.error_message;
}

function batchToast(
  verb: string,
  unit: string,
  counted: WorkEntry[],
  icon: ToastIcon,
): JobToast {
  const total = counted.length;
  const ok = counted.filter(entryOk).length;
  if (ok === total) {
    return { message: `${verb} ${ok} ${unit}.`, tone: "ok", icon };
  }
  return { message: `${verb} ${ok} of ${total}.`, tone: "ok", icon };
}

function failedToast(fallback: string, job: Job): JobToast {
  const message = job.error_message.trim() !== "" ? job.error_message : fallback;
  return { message, tone: "error", icon: jobIcon(job, "error") };
}

/** Short toast for a terminal job, or null when cancelled / unknown. */
export function jobToastMessage(job: Job): JobToast | null {
  if (job.state === "cancelled") return null;
  if (job.state !== "succeeded" && job.state !== "failed") return null;

  if (job.name === "Search") {
    if (job.state === "failed") return failedToast("Scrape failed.", job);
    const n = candidatesOf(job.result).length;
    return {
      message: n === 0 ? "No matches." : `Found ${n} matches.`,
      tone: "ok",
      icon: jobIcon(job, "ok"),
    };
  }

  if (job.name === "Issues") {
    if (job.state === "failed") return failedToast("Issues failed.", job);
    if (issuesOf(job.result).length === 0) {
      return {
        message: "No issues available.",
        tone: "ok",
        icon: jobIcon(job, "ok"),
      };
    }
    return null;
  }

  if (job.name === "Load") {
    if (job.state === "failed") return failedToast("Load failed.", job);
    return {
      message: "Metadata loaded.",
      tone: "ok",
      icon: jobIcon(job, "ok"),
    };
  }

  if (job.name === "Scan") {
    if (job.state === "failed") return failedToast("Scan failed.", job);
    return {
      message: "Library updated.",
      tone: "ok",
      icon: jobIcon(job, "ok"),
    };
  }

  if (job.name === "Save") {
    if (job.state === "failed") return failedToast("Save failed.", job);
    const counted = entriesOf(job.result);
    const total = counted.length;
    const ok = counted.filter(entryOk).length;
    if (ok === total && total === 1) {
      return {
        message: "Issue updated.",
        tone: "ok",
        icon: jobIcon(job, "ok"),
      };
    }
    return batchToast("Saved", "issues", counted, jobIcon(job, "ok"));
  }

  if (job.name === "Rename") {
    if (job.state === "failed") return failedToast("Rename failed.", job);
    return batchToast(
      "Renamed",
      "files",
      entriesOf(job.result),
      jobIcon(job, "ok"),
    );
  }

  if (job.name === "Convert") {
    if (job.state === "failed") return failedToast("Convert failed.", job);
    const counted = entriesOf(job.result).filter((entry) => !entry.skipped);
    return batchToast("Converted", "files", counted, jobIcon(job, "ok"));
  }

  return null;
}
