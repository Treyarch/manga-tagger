/** Rename-template tags and caret-safe insertion shared by the dialog and tests. */

export const RENAME_TAGS = [
  "Title",
  "Series",
  "Number",
  "Volume",
  "Count",
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

export type RenameTag = (typeof RENAME_TAGS)[number];

export function renameToken(tag: RenameTag): string {
  return `{${tag}}`;
}

export function insertRenameToken(
  value: string,
  token: string,
  selectionStart: number | null,
  selectionEnd: number | null,
): { value: string; caret: number } {
  const start = Math.min(Math.max(selectionStart ?? value.length, 0), value.length);
  const end = Math.min(
    Math.max(selectionEnd ?? start, start),
    value.length,
  );
  return {
    value: `${value.slice(0, start)}${token}${value.slice(end)}`,
    caret: start + token.length,
  };
}
