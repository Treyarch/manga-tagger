/** English count agreement: 1 → singular; 0 and 2+ → plural. */
export function pluralize(
  count: number,
  singular: string,
  plural = `${singular}s`,
): string {
  return count === 1 ? singular : plural;
}
