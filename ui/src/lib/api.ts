/** `fetch` against the API origin. There is no pywebview bridge. */

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
  comicvine_api_key: string;
  title_languages: string[];
  theme: string;
};

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T;
  let error_type = "Error";
  let error_message = response.statusText;
  try {
    const body = (await response.json()) as {
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

export function putConfig(body: Partial<Config>): Promise<Config> {
  return fetch("/api/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }).then((response) => parse<Config>(response));
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
