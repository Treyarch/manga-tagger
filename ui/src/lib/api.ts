/** `fetch` against the API origin. There is no pywebview bridge. */

import type { Job } from "./library";

export class ApiError extends Error {
  error_type: string;

  constructor(error_type: string, error_message: string) {
    super(error_message);
    this.name = "ApiError";
    this.error_type = error_type;
  }
}

export type Config = {
  library_roots: string[];
  keep_cbr_original: boolean;
  write_poster_on_save: boolean;
  auto_save_metadata_on_switch: boolean;
  comicvine_api_key: string;
  nautiljon_base_url: string;
  nautiljon_api_key: string;
  title_languages: string[];
  enabled_providers: string[];
  theme: string;
  animate_interface: boolean;
};

export type SystemTheme = {
  mode: "light" | "dark";
  background: string;
  dark_background: string;
  lighter_background: string;
  foreground: string;
  dark_foreground: string;
  accent: string;
  selection: string;
  red: string;
  yellow: string;
  orange: string;
};

export type ConfigPutResult = {
  config: Config;
  job: Job | null;
};

/** Add roots to a Settings PUT only when their ordered normalized value changed. */
export function withChangedLibraryRoots(
  updates: Partial<Config>,
  currentRoots: string[],
  nextRoots: string[],
): Partial<Config> {
  const unchanged =
    nextRoots.length === currentRoots.length &&
    nextRoots.every((root, index) => root === currentRoots[index]);
  return unchanged ? updates : { ...updates, library_roots: nextRoots };
}

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) {
    if (response.status === 204) return undefined as T;
    const text = await response.text();
    if (text === "") return undefined as T;
    return JSON.parse(text) as T;
  }
  let error_type = "Error";
  let error_message = response.statusText;
  try {
    const body = JSON.parse(await response.text()) as {
      error_type?: string;
      error_message?: string;
    };
    if (body.error_type) error_type = body.error_type;
    if (body.error_message) error_message = body.error_message;
  } catch {
    /* The body was not the JSON error shape. */
  }
  throw new ApiError(error_type, error_message);
}

export function getConfig(): Promise<Config> {
  return fetch("/api/config").then((response) => parse<Config>(response));
}

export function getSystemTheme(): Promise<SystemTheme | null> {
  return fetch("/api/system-theme", { cache: "no-store" }).then((response) =>
    parse<SystemTheme | null>(response),
  );
}

export function putConfig(body: Partial<Config>): Promise<ConfigPutResult> {
  return fetch("/api/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }).then((response) => parse<ConfigPutResult>(response));
}

export function getJson<T>(path: string): Promise<T> {
  return fetch(path).then((response) => parse<T>(response));
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: "POST" };
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" };
    init.body = JSON.stringify(body);
  }
  return fetch(path, init).then((response) => parse<T>(response));
}
