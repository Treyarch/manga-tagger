/** Pure sizing rules for the resizable application panes. */

export const SIDEBAR_DEFAULT_WIDTH = 240;
export const SIDEBAR_MIN_WIDTH = 160;
export const SIDEBAR_MAX_WIDTH = 480;
export const INSPECTOR_WIDTH = 384;
export const MAIN_PANE_MIN_WIDTH = 240;
export const SIDEBAR_SEPARATOR_WIDTH = 1;
export const SIDEBAR_KEYBOARD_STEP = 8;
export const SIDEBAR_KEYBOARD_LARGE_STEP = 32;

export function sidebarMaxWidth(paneStripWidth: number): number {
  const available =
    paneStripWidth -
    INSPECTOR_WIDTH -
    MAIN_PANE_MIN_WIDTH -
    SIDEBAR_SEPARATOR_WIDTH;
  return Math.max(
    SIDEBAR_MIN_WIDTH,
    Math.min(SIDEBAR_MAX_WIDTH, Math.floor(available)),
  );
}

export function clampSidebarWidth(
  requestedWidth: number,
  paneStripWidth: number,
): number {
  return Math.max(
    SIDEBAR_MIN_WIDTH,
    Math.min(sidebarMaxWidth(paneStripWidth), Math.round(requestedWidth)),
  );
}

export function sidebarWidthFromKey(
  currentWidth: number,
  key: string,
  paneStripWidth: number,
  shiftKey = false,
): number | null {
  const step = shiftKey
    ? SIDEBAR_KEYBOARD_LARGE_STEP
    : SIDEBAR_KEYBOARD_STEP;
  if (key === "ArrowLeft") {
    return clampSidebarWidth(currentWidth - step, paneStripWidth);
  }
  if (key === "ArrowRight") {
    return clampSidebarWidth(currentWidth + step, paneStripWidth);
  }
  if (key === "Home") return SIDEBAR_MIN_WIDTH;
  if (key === "End") return sidebarMaxWidth(paneStripWidth);
  return null;
}
