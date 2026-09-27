import type { SystemTheme } from "./api";

/** Resolve the document `dark` class from config and desktop state. */

export function resolveDark(
  theme: string,
  prefersDark: boolean,
  systemTheme: SystemTheme | null = null,
): boolean {
  if (theme === "light") return false;
  if (theme === "dark") return true;
  if (systemTheme) return systemTheme.mode === "dark";
  return prefersDark;
}

type ClassList = {
  add(name: string): void;
  remove(name: string): void;
  contains(name: string): boolean;
};

/** Put `dark` on `root` when the theme resolves dark, and remove it otherwise. */
export function applyDocumentClass(
  root: { classList: ClassList },
  dark: boolean,
): void {
  if (dark) root.classList.add("dark");
  else root.classList.remove("dark");
}

export const THEME_PROPERTIES = [
  "--app-window",
  "--app-view",
  "--app-raised",
  "--app-secondary",
  "--app-secondary-hover",
  "--app-quiet-hover",
  "--app-border",
  "--app-strong-border",
  "--app-text",
  "--app-muted",
  "--app-accent",
  "--app-on-accent",
  "--app-selection",
  "--app-dirty",
  "--app-danger",
  "--app-danger-hover",
  "--app-danger-text",
  "--app-on-danger",
] as const;

type ThemeProperty = (typeof THEME_PROPERTIES)[number];
export type ThemeTokens = Record<ThemeProperty, string>;

type StyleList = {
  setProperty(name: string, value: string): void;
  removeProperty(name: string): void;
};

type ThemeRoot = {
  classList: ClassList;
  style: StyleList;
};

type Rgb = [number, number, number];

function rgb(value: string): Rgb {
  const hex = value.slice(1);
  return [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16)) as Rgb;
}

function luminance(value: string): number {
  const channels = rgb(value).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrastRatio(a: string, b: string): number {
  const first = luminance(a);
  const second = luminance(b);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

function mix(start: string, end: string, amount: number): string {
  const from = rgb(start);
  const to = rgb(end);
  const channels = from.map((channel, index) =>
    Math.round(channel * (1 - amount) + to[index] * amount),
  );
  return `#${channels.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function ensureContrast(
  candidate: string,
  background: string,
  target: string,
  minimum = 4.5,
): string {
  if (contrastRatio(candidate, background) >= minimum) return candidate;
  if (contrastRatio(target, background) < minimum) return target;
  let low = 0;
  let high = 1;
  for (let index = 0; index < 12; index += 1) {
    const middle = (low + high) / 2;
    if (contrastRatio(mix(candidate, target, middle), background) >= minimum) high = middle;
    else low = middle;
  }
  return mix(candidate, target, high);
}

function contrastingText(fill: string, background: string, foreground: string): string {
  const backgroundRatio = contrastRatio(background, fill);
  const foregroundRatio = contrastRatio(foreground, fill);
  if (Math.max(backgroundRatio, foregroundRatio) >= 4.5) {
    return backgroundRatio > foregroundRatio ? background : foreground;
  }
  return contrastRatio("#000000", fill) > contrastRatio("#ffffff", fill)
    ? "#000000"
    : "#ffffff";
}

/** Convert Omarchy's palette roles into Manga Tagger's component roles. */
export function tokensFromSystemTheme(theme: SystemTheme): ThemeTokens {
  const dirty = theme.mode === "light" ? theme.orange : theme.yellow;
  return {
    "--app-window": theme.dark_background,
    "--app-view": theme.background,
    "--app-raised": theme.lighter_background,
    "--app-secondary": theme.lighter_background,
    "--app-secondary-hover": theme.selection,
    "--app-quiet-hover": theme.selection,
    "--app-border": theme.lighter_background,
    "--app-strong-border": ensureContrast(
      theme.lighter_background,
      theme.background,
      theme.foreground,
      2,
    ),
    "--app-text": theme.foreground,
    "--app-muted": ensureContrast(
      theme.dark_foreground,
      theme.background,
      theme.foreground,
    ),
    "--app-accent": theme.accent,
    "--app-on-accent": contrastingText(
      theme.accent,
      theme.background,
      theme.foreground,
    ),
    "--app-selection": theme.selection,
    "--app-dirty": ensureContrast(dirty, theme.background, theme.foreground),
    "--app-danger": theme.red,
    "--app-danger-hover": mix(theme.red, theme.dark_background, 0.15),
    "--app-danger-text": ensureContrast(theme.red, theme.background, theme.foreground),
    "--app-on-danger": contrastingText(theme.red, theme.background, theme.foreground),
  };
}

/** Apply the resolved built-in or Omarchy theme to the document root. */
export function applyTheme(
  root: ThemeRoot,
  theme: string,
  prefersDark: boolean,
  systemTheme: SystemTheme | null,
): void {
  const followsSystem = theme !== "light" && theme !== "dark";
  const palette = followsSystem ? systemTheme : null;
  applyDocumentClass(root, resolveDark(theme, prefersDark, palette));
  if (palette) {
    const tokens = tokensFromSystemTheme(palette);
    for (const property of THEME_PROPERTIES) root.style.setProperty(property, tokens[property]);
  } else {
    for (const property of THEME_PROPERTIES) root.style.removeProperty(property);
  }
}
