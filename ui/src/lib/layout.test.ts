import { describe, expect, it } from "vitest";
import {
  SIDEBAR_DEFAULT_WIDTH,
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
  clampSidebarWidth,
  sidebarMaxWidth,
  sidebarWidthFromKey,
} from "./layout";

describe("sidebar layout", () => {
  it("keeps the default inside the fixed bounds", () => {
    expect(SIDEBAR_DEFAULT_WIDTH).toBeGreaterThan(SIDEBAR_MIN_WIDTH);
    expect(SIDEBAR_DEFAULT_WIDTH).toBeLessThan(SIDEBAR_MAX_WIDTH);
  });

  it("clamps pointer sizing to the fixed minimum and maximum", () => {
    expect(clampSidebarWidth(80, 1400)).toBe(SIDEBAR_MIN_WIDTH);
    expect(clampSidebarWidth(900, 1400)).toBe(SIDEBAR_MAX_WIDTH);
    expect(clampSidebarWidth(333.6, 1400)).toBe(334);
  });

  it("lowers the maximum to preserve the main pane in a narrow strip", () => {
    expect(sidebarMaxWidth(1000)).toBe(375);
    expect(clampSidebarWidth(480, 1000)).toBe(375);
    expect(sidebarMaxWidth(700)).toBe(SIDEBAR_MIN_WIDTH);
  });

  it("maps keyboard resizing to small and large clamped steps", () => {
    expect(sidebarWidthFromKey(240, "ArrowLeft", 1400)).toBe(232);
    expect(sidebarWidthFromKey(240, "ArrowRight", 1400, true)).toBe(272);
    expect(sidebarWidthFromKey(164, "ArrowLeft", 1400)).toBe(
      SIDEBAR_MIN_WIDTH,
    );
    expect(sidebarWidthFromKey(470, "ArrowRight", 1400, true)).toBe(
      SIDEBAR_MAX_WIDTH,
    );
    expect(sidebarWidthFromKey(240, "Home", 1400)).toBe(
      SIDEBAR_MIN_WIDTH,
    );
    expect(sidebarWidthFromKey(240, "End", 1000)).toBe(375);
    expect(sidebarWidthFromKey(240, "PageDown", 1400)).toBeNull();
  });
});
