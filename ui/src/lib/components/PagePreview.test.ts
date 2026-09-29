import { render } from "svelte/server";
import { describe, expect, it } from "vitest";

import type { Volume } from "../library";
import PagePreview from "./PagePreview.svelte";

const volume: Volume = {
  path: "/books/a.cbz",
  root: "/books",
  name: "a.cbz",
  extension: "cbz",
  status: "ok",
  error_type: "",
  error_message: "",
  cover_index: 0,
  archive_page_count: 2,
  title: "",
  series: "",
  number: "",
  volume: "",
  count: "",
  publisher: "",
  page_count: "",
  language_iso: "",
  age_rating: "",
  manga: "",
  genre: "",
  summary: "",
  web: "",
  community_rating: "",
  notes: "",
  year: "",
  month: "",
  day: "",
  writer: "",
  penciller: "",
  inker: "",
  cover_artist: "",
};

describe("PagePreview cover actions", () => {
  it("renders icon-only controls with text tooltips and accessible names", () => {
    const { body } = render(PagePreview, {
      props: {
        anchor: volume,
        coverActions: true,
        coverActionsDisabled: false,
      },
    });

    for (const label of ["Replace cover", "Insert cover"]) {
      const button = body.match(
        new RegExp(`<button[^>]*aria-label="${label}"[\\s\\S]*?</button>`),
      )?.[0];
      expect(button).toBeDefined();
      expect(button).toContain(`title="${label}"`);
      expect(button).toContain("<svg");
      expect(button).not.toContain(`>${label}<`);
    }
  });
});
