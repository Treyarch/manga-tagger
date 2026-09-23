/** Client-side shelf, selection, form, and inspector rules from the shell spec. */

export const POLL_MS = 500;

export const OFFERED_RENAME_TEMPLATE = "{Series} v{Number:02}";

export const FORM_FIELDS = [
  "Title",
  "Series",
  "Number",
  "Volume",
  "Publisher",
  "PageCount",
  "LanguageISO",
  "AgeRating",
  "Manga",
  "Genre",
  "Summary",
  "Web",
  "CommunityRating",
  "Notes",
  "Year",
  "Month",
  "Day",
  "Writer",
  "Penciller",
  "Inker",
  "CoverArtist",
] as const;

export const SHARED_FIELDS = [
  "Series",
  "Publisher",
  "LanguageISO",
  "AgeRating",
  "Genre",
  "Manga",
  "Writer",
  "Penciller",
  "Inker",
  "CoverArtist",
] as const;

/** Readable inspector captions for ComicInfo element keys. */
export const FIELD_LABELS: Record<(typeof FORM_FIELDS)[number], string> = {
  Title: "Title",
  Series: "Series",
  Number: "Number",
  Volume: "Volume",
  Publisher: "Publisher",
  PageCount: "Page count",
  LanguageISO: "Language",
  AgeRating: "Age rating",
  Manga: "Manga",
  Genre: "Genre",
  Summary: "Summary",
  Web: "Web",
  CommunityRating: "Community rating",
  Notes: "Notes",
  Year: "Year",
  Month: "Month",
  Day: "Day",
  Writer: "Writer",
  Penciller: "Penciller",
  Inker: "Inker",
  CoverArtist: "Cover artist",
};

export function fieldLabel(name: string): string {
  return FIELD_LABELS[name as (typeof FORM_FIELDS)[number]] ?? name;
}

/** Amber text and border for unsaved inspector fields until Save rebuilds the form. */
export function dirtyFieldClass(dirty: boolean): string {
  return dirty
    ? "border-amber-600 text-amber-700 dark:border-amber-500 dark:text-amber-400"
    : "";
}

export const MANGA_OPTIONS = [
  "YesAndRightToLeft",
  "Yes",
  "No",
  "YesAndLeftToRight",
  "",
] as const;

const MANGA_LABELS: Record<(typeof MANGA_OPTIONS)[number], string> = {
  YesAndRightToLeft: "Yes (right to left)",
  Yes: "Yes",
  No: "No",
  YesAndLeftToRight: "Yes (left to right)",
  "": "",
};

export function mangaLabel(token: string): string {
  return MANGA_LABELS[token as (typeof MANGA_OPTIONS)[number]] ?? token;
}

export const PROVIDERS = [
  { id: "mangadex", label: "MangaDex" },
  { id: "anilist", label: "AniList" },
  { id: "jikan", label: "MyAnimeList" },
  { id: "comicvine", label: "Comic Vine" },
] as const;

const FIELD_COLUMNS: Record<string, string> = {
  Title: "title",
  Series: "series",
  Number: "number",
  Volume: "volume",
  Publisher: "publisher",
  PageCount: "page_count",
  LanguageISO: "language_iso",
  AgeRating: "age_rating",
  Manga: "manga",
  Genre: "genre",
  Summary: "summary",
  Web: "web",
  CommunityRating: "community_rating",
  Notes: "notes",
  Year: "year",
  Month: "month",
  Day: "day",
  Writer: "writer",
  Penciller: "penciller",
  Inker: "inker",
  CoverArtist: "cover_artist",
};

const LIBRARY_JOBS = new Set(["Scan", "Save", "Rename", "Convert"]);

export type Volume = {
  path: string;
  root: string;
  name: string;
  extension: string;
  status: string;
  error_type: string;
  error_message: string;
  cover_index: number | null;
  archive_page_count: number | null;
  title: string;
  series: string;
  number: string;
  volume: string;
  publisher: string;
  page_count: string;
  language_iso: string;
  age_rating: string;
  manga: string;
  genre: string;
  summary: string;
  web: string;
  community_rating: string;
  notes: string;
  year: string;
  month: string;
  day: string;
  writer: string;
  penciller: string;
  inker: string;
  cover_artist: string;
};

export type Place = { path: string; label: string };

export type Field = { value: string; dirty: boolean; mixed?: boolean };

export type InspectorForm = {
  mode: "one" | "many";
  values: Record<string, Field>;
};

export type Selection = { paths: string[]; anchor: string | null };

export type Job = {
  id: string;
  name: string;
  state: string;
  error_type: string;
  error_message: string;
  result: unknown;
  completed: number;
  total: number;
};

export type WorkEntry = {
  path: string;
  output_path?: string | null;
  error_type?: string;
  error_message?: string;
  skipped?: boolean;
};

export type Candidate = { id: string; title: string; detail: string; cover: string };

/** Same-origin img src for a candidate cover. MangaDex CDN is proxied. */
export function matchCoverSrc(cover: string): string {
  const trimmed = cover.trim();
  if (trimmed === "") return "";
  try {
    const host = new URL(trimmed).hostname;
    if (host === "uploads.mangadex.org") {
      return `/api/cover?url=${encodeURIComponent(trimmed)}`;
    }
  } catch {
    return trimmed;
  }
  return trimmed;
}

export function casefold(value: string): string {
  return value.normalize("NFKC").toLowerCase().replaceAll("ß", "ss");
}

export function directoryKey(path: string): string {
  if (path.length > 1) return path.replace(/[\\/]+$/, "");
  return path;
}

export function parentPath(path: string): string {
  const text = directoryKey(path);
  const index = Math.max(text.lastIndexOf("/"), text.lastIndexOf("\\"));
  if (index < 0) return text;
  if (index === 0) return text.slice(0, 1);
  return directoryKey(text.slice(0, index));
}

export function baseName(path: string): string {
  const text = directoryKey(path);
  const index = Math.max(text.lastIndexOf("/"), text.lastIndexOf("\\"));
  return index >= 0 ? text.slice(index + 1) : text;
}

export function filenameStem(name: string): string {
  const base = baseName(name);
  const dot = base.lastIndexOf(".");
  if (dot <= 0) return base;
  return base.slice(0, dot);
}

export function volumesInPlace(rows: Volume[], placePath: string): Volume[] {
  const place = directoryKey(placePath);
  return rows
    .filter((row) => parentPath(row.path) === place)
    .slice()
    .sort((left, right) =>
      left.name < right.name ? -1 : left.name > right.name ? 1 : 0,
    );
}

export function volumesForShelf(
  rows: Volume[],
  placePath: string | null,
): Volume[] {
  if (placePath === null) {
    return rows
      .slice()
      .sort((left, right) =>
        left.name < right.name ? -1 : left.name > right.name ? 1 : 0,
      );
  }
  return volumesInPlace(rows, placePath);
}

export type SeriesGroup = { series: string; volumes: Volume[] };

/** Groups by trimmed series: blank first, then case-folded series name. */
export function groupVolumesBySeries(rows: Volume[]): SeriesGroup[] {
  const buckets = new Map<string, Volume[]>();
  for (const row of rows) {
    const series = row.series.trim();
    const bucket = buckets.get(series);
    if (bucket) bucket.push(row);
    else buckets.set(series, [row]);
  }
  const named = [...buckets.keys()]
    .filter((series) => series !== "")
    .sort((left, right) => {
      const a = casefold(left);
      const b = casefold(right);
      return a < b ? -1 : a > b ? 1 : left < right ? -1 : left > right ? 1 : 0;
    });
  const groups: SeriesGroup[] = [];
  const blank = buckets.get("");
  if (blank) groups.push({ series: "", volumes: blank });
  for (const series of named) {
    groups.push({ series, volumes: buckets.get(series)! });
  }
  return groups;
}

export function selectPlain(visible: string[], path: string): Selection {
  return { paths: [path], anchor: path };
}

export function selectRange(
  visible: string[],
  selection: Selection,
  path: string,
): Selection {
  if (
    selection.anchor === null ||
    !visible.includes(selection.anchor) ||
    !visible.includes(path)
  ) {
    return selectPlain(visible, path);
  }
  const start = visible.indexOf(selection.anchor);
  const end = visible.indexOf(path);
  const low = Math.min(start, end);
  const high = Math.max(start, end);
  return { paths: visible.slice(low, high + 1), anchor: selection.anchor };
}

export function selectToggle(
  visible: string[],
  selection: Selection,
  path: string,
): Selection {
  const selected = new Set(selection.paths);
  if (selected.has(path)) {
    selected.delete(path);
    const paths = visible.filter((item) => selected.has(item));
    let anchor = selection.anchor;
    if (anchor === null || !paths.includes(anchor)) {
      anchor = paths[0] ?? null;
    }
    return { paths, anchor };
  }
  selected.add(path);
  const paths = visible.filter((item) => selected.has(item));
  const anchor = selection.paths.length === 0 ? path : selection.anchor;
  return { paths, anchor };
}

export function selectionFromClick(
  visible: string[],
  selection: Selection,
  path: string,
  mods: { shift: boolean; toggle: boolean },
): Selection {
  if (mods.shift) return selectRange(visible, selection, path);
  if (mods.toggle) return selectToggle(visible, selection, path);
  return selectPlain(visible, path);
}

export function selectionAfterFilter(
  visible: string[],
  selection: Selection,
): Selection {
  const selected = new Set(selection.paths);
  const paths = visible.filter((item) => selected.has(item));
  let anchor = selection.anchor !== null && paths.includes(selection.anchor)
    ? selection.anchor
    : null;
  if (anchor === null && paths.length > 0) anchor = paths[0];
  return { paths, anchor };
}

function fieldText(row: Volume, name: string): string {
  const column = FIELD_COLUMNS[name] as keyof Volume;
  const value = row[column];
  if (value === null || value === undefined) return "";
  return String(value);
}

/** Archive page count text when ComicInfo left PageCount blank. */
export function pageCountFill(row: Volume): string | null {
  if (fieldText(row, "PageCount").trim() !== "") return null;
  const count = row.archive_page_count;
  if (count === null || count <= 0) return null;
  return String(count);
}

export function formFromVolumes(rows: Volume[]): InspectorForm | null {
  if (rows.length === 0) return null;
  if (rows.length === 1) {
    const values: Record<string, Field> = {};
    for (const name of FORM_FIELDS) {
      let value = fieldText(rows[0], name);
      if (name === "PageCount") {
        const filled = pageCountFill(rows[0]);
        if (filled !== null) value = filled;
      }
      values[name] = { value, dirty: false };
    }
    return { mode: "one", values };
  }
  const values: Record<string, Field> = {};
  for (const name of SHARED_FIELDS) {
    const texts = rows.map((row) => fieldText(row, name));
    if (texts.every((text) => text === texts[0])) {
      values[name] = { value: texts[0], mixed: false, dirty: false };
    } else {
      values[name] = { value: "", mixed: true, dirty: false };
    }
  }
  return { mode: "many", values };
}

export function editField(
  form: InspectorForm,
  key: string,
  value: string,
): InspectorForm {
  const values: Record<string, Field> = {};
  for (const [name, field] of Object.entries(form.values)) {
    values[name] = { ...field };
  }
  const updated: Field = { value, dirty: true };
  if ("mixed" in form.values[key]) updated.mixed = false;
  values[key] = updated;
  return { mode: form.mode, values };
}

export function formIsDirty(form: InspectorForm | null): boolean {
  if (form === null) return false;
  return Object.values(form.values).some((field) => field.dirty);
}

export function savePatch(form: InspectorForm): Record<string, string> {
  const patch: Record<string, string> = {};
  for (const [key, field] of Object.entries(form.values)) {
    if (!field.dirty || key === "Pages") continue;
    if (form.mode === "many" && (key === "Number" || key === "Volume")) continue;
    patch[key] = field.value;
  }
  return patch;
}

export function seriesForSearch(form: InspectorForm | null): string {
  const field = form?.values.Series;
  if (!field || field.mixed) return "";
  if (field.value.trim() === "") return "";
  return field.value;
}

export function selectionKey(selection: Selection): string {
  return `${selection.anchor ?? ""}\n${selection.paths.join("\n")}`;
}

export function placeAfterLibrary(
  current: string | null,
  places: Place[],
): string | null {
  if (current !== null && places.some((place) => place.path === current)) {
    return current;
  }
  return null;
}

export function initialPageIndex(
  coverIndex: number | null,
  pageCount: number | null,
): number | null {
  if (pageCount === null || pageCount <= 0) return null;
  if (coverIndex === null || coverIndex < 0 || coverIndex >= pageCount) return 0;
  return coverIndex;
}

export function requestsPage(volume: Volume): boolean {
  if (volume.status === "failed") return false;
  return volume.archive_page_count !== null && volume.archive_page_count > 0;
}

export function jobLabel(job: Pick<Job, "name" | "completed" | "total">): string {
  if (job.total > 0) return `${job.name} ${job.completed}/${job.total}`;
  return job.name;
}

export function isBusy(job: Job | null): boolean {
  return job !== null && (job.state === "queued" || job.state === "running");
}

export function shouldRefetchLibrary(job: Job): boolean {
  return (
    LIBRARY_JOBS.has(job.name) &&
    (job.state === "succeeded" || job.state === "failed" || job.state === "cancelled")
  );
}

export function cbrCount(rows: Volume[]): number {
  return rows.filter((row) => row.extension.toLowerCase() === ".cbr").length;
}

export function convertConfirmMessage(count: number): string {
  return `Convert ${count} CBR files to CBZ and delete the originals?`;
}

export function isAbsolutePath(value: string): boolean {
  if (value.startsWith("/")) return true;
  if (value.startsWith("\\\\")) return true;
  return /^[A-Za-z]:[\\/]/.test(value);
}

export function folderDropRequest(detail: unknown): { paths: string[] } {
  if (typeof detail !== "object" || detail === null || !("paths" in detail)) {
    return { paths: [] };
  }
  const paths = (detail as { paths: unknown }).paths;
  if (!Array.isArray(paths)) return { paths: [] };
  return {
    paths: paths.filter((path): path is string => typeof path === "string" && path !== ""),
  };
}

export function parseRootLines(text: string): { roots: string[]; error: string | null } {
  const roots = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "");
  for (const root of roots) {
    if (!isAbsolutePath(root)) return { roots: [], error: "Paths must be absolute." };
  }
  return { roots, error: null };
}

export function parseLanguages(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

export function entryErrorLines(entries: WorkEntry[]): string[] {
  return entries
    .filter((entry) => entry.error_message)
    .map((entry) => `${baseName(entry.path)}: ${entry.error_message}`);
}

export function renamePlanLines(entries: WorkEntry[]): string[] {
  return entries.map((entry) => {
    if (entry.error_message || !entry.output_path) {
      return `${baseName(entry.path)}: ${entry.error_message ?? ""}`;
    }
    return `${baseName(entry.path)} → ${baseName(entry.output_path)}`;
  });
}

/** Sentences for roots the result names as skipped or incomplete. */
export function scanRootLines(result: {
  skipped?: string[];
  incomplete?: string[];
}): string[] {
  const lines: string[] = [];
  for (const path of result.skipped ?? []) lines.push(`${path} was skipped.`);
  for (const path of result.incomplete ?? []) {
    lines.push(`${path} was not fully scanned.`);
  }
  return lines;
}

export function selectionAfterEntries(
  selection: Selection,
  entries: WorkEntry[],
  libraryPaths: Set<string>,
): Selection {
  const replacements = new Map<string, string>();
  const dropped = new Set<string>();
  for (const entry of entries) {
    if (entry.output_path) replacements.set(entry.path, entry.output_path);
    else if (entry.error_message && !libraryPaths.has(entry.path)) {
      dropped.add(entry.path);
    }
  }
  const mapped = selection.paths
    .filter((path) => !dropped.has(path))
    .map((path) => replacements.get(path) ?? path)
    .filter((path) => libraryPaths.has(path));
  const anchorSource = selection.anchor;
  let anchor = anchorSource === null ? null : (replacements.get(anchorSource) ?? anchorSource);
  if (anchor !== null && (dropped.has(anchorSource ?? "") || !mapped.includes(anchor))) {
    anchor = mapped[0] ?? null;
  }
  if (anchor === null && mapped.length > 0) anchor = mapped[0];
  return { paths: mapped, anchor };
}

export function candidatesOf(result: unknown): Candidate[] {
  if (result === null || typeof result !== "object" || !("candidates" in result)) {
    return [];
  }
  const raw = (result as { candidates?: unknown }).candidates;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    if (item === null || typeof item !== "object") return [];
    const row = item as {
      id?: unknown;
      title?: unknown;
      detail?: unknown;
      cover?: unknown;
    };
    return [
      {
        id: String(row.id ?? ""),
        title: String(row.title ?? ""),
        detail: String(row.detail ?? ""),
        cover: String(row.cover ?? ""),
      },
    ];
  });
}

export function entriesOf(result: unknown): WorkEntry[] {
  if (result === null || typeof result !== "object" || !("entries" in result)) {
    return [];
  }
  const raw = (result as { entries?: unknown }).entries;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    if (item === null || typeof item !== "object") return [];
    const row = item as WorkEntry;
    return [row];
  });
}

export function formOf(result: unknown): InspectorForm | null {
  if (result === null || typeof result !== "object" || !("form" in result)) return null;
  const form = (result as { form?: InspectorForm }).form;
  if (!form || (form.mode !== "one" && form.mode !== "many") || !form.values) {
    return null;
  }
  return form;
}

export function mangaChoices(current: string): string[] {
  const options: string[] = [...MANGA_OPTIONS];
  if (current !== "" && !options.includes(current)) options.push(current);
  return options;
}
