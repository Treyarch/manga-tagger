/** Clear-cache result wording and thumbnail revision composition. */

export function cacheResultMessage(removed: number): string {
  if (removed === 0) return "Cache is already empty.";
  return `Cleared ${removed} cached ${removed === 1 ? "thumbnail" : "thumbnails"}.`;
}

export async function clearThumbnailCache(
  request: () => Promise<{ removed: number }>,
  onCleared: () => void,
): Promise<string> {
  const result = await request();
  onCleared();
  return cacheResultMessage(result.removed);
}

export function thumbnailRevision(
  cacheRevision: number,
  coverRevision: string,
): string {
  const parts: string[] = [];
  if (cacheRevision > 0) parts.push(`cache-${cacheRevision}`);
  if (coverRevision !== "") parts.push(`cover-${coverRevision}`);
  return parts.join(":");
}
