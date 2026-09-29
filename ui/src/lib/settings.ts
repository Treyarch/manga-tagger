import type { Config } from "./api";

type SettingsTab = {
  id: string;
  label: string;
  configKeys: readonly (keyof Config)[];
};

/** Ordered Settings navigation and ownership of persisted configuration fields. */
export const SETTINGS_TABS = [
  {
    id: "general",
    label: "General",
    configKeys: ["theme", "animate_interface", "title_languages"],
  },
  {
    id: "library",
    label: "Library",
    configKeys: ["library_roots", "scan_subfolders", "excluded_folders"],
  },
  {
    id: "archives",
    label: "Archives",
    configKeys: [
      "keep_cbr_original",
      "write_poster_on_save",
      "auto_save_metadata_on_switch",
    ],
  },
  {
    id: "scrapers",
    label: "Scrapers",
    configKeys: [
      "enabled_providers",
      "comicvine_api_key",
      "nautiljon_base_url",
      "nautiljon_api_key",
    ],
  },
  { id: "cache", label: "Cache", configKeys: [] },
] as const satisfies readonly SettingsTab[];

export type SettingsTabId = (typeof SETTINGS_TABS)[number]["id"];

/** Append a chosen folder without changing the existing order or adding duplicates. */
export function appendFolderPath(paths: readonly string[], path: string): string[] {
  return paths.includes(path) ? [...paths] : [...paths, path];
}

/** Remove only the selected folder from a Settings draft list. */
export function removeFolderPath(paths: readonly string[], path: string): string[] {
  return paths.filter((candidate) => candidate !== path);
}
