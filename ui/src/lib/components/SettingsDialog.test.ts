import { render } from "svelte/server";
import { describe, expect, it } from "vitest";
import type { Config } from "../api";
import SettingsDialog from "./SettingsDialog.svelte";

const config: Config = {
  library_roots: [], excluded_folders: [], scan_subfolders: true,
  keep_cbr_original: true, write_poster_on_save: true,
  auto_save_metadata_on_switch: false, comicvine_api_key: "",
  nautiljon_base_url: "", nautiljon_api_key: "", title_languages: ["fr", "en"],
  enabled_providers: [], theme: "system", animate_interface: false,
};

describe("Settings app version", () => {
  it.each(["0.2.0", "1.3.7", null])("shows %s as read-only information on General", (appVersion) => {
    const { body } = render(SettingsDialog, { props: {
      config, appVersion, onClose: () => undefined,
      onSaved: () => undefined, onCacheCleared: () => undefined,
    } });
    expect(body).toContain(">Version</dt>");
    expect(body).toContain(`aria-label="App version">${appVersion ?? "Unavailable"}</dd>`);
    expect(body.indexOf("Title languages")).toBeLessThan(body.indexOf(">Version</dt>"));
    expect(body).not.toMatch(/<input[^>]*aria-label="App version"/);
  });
});
