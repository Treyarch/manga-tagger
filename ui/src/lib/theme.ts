/** Resolve the document `dark` class from the stored theme. */

export function resolveDark(theme: string, prefersDark: boolean): boolean {
  if (theme === "light") return false;
  if (theme === "dark") return true;
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
