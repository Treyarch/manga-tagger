import appContract from "../../../tests/contracts/app-contracts.json";
import { describe, expect, it } from "vitest";

import { RENAME_TAGS, insertRenameToken, renameToken } from "./rename";

describe("rename template tags", () => {
  it("matches every ComicInfo tag supported by the backend", () => {
    expect([...RENAME_TAGS]).toEqual(appContract.rename_tags);
    expect(RENAME_TAGS.map(renameToken)).toContain("{Volume}");
  });

  it("inserts at the caret and leaves the caret after the token", () => {
    expect(insertRenameToken("Series 01", "{Number}", 7, 7)).toEqual({
      value: "Series {Number}01",
      caret: 15,
    });
  });

  it("replaces a selection and safely clamps missing or invalid positions", () => {
    expect(insertRenameToken("Series XX", "{Number}", 7, 9)).toEqual({
      value: "Series {Number}",
      caret: 15,
    });
    expect(insertRenameToken("Series", "{Title}", null, null)).toEqual({
      value: "Series{Title}",
      caret: 13,
    });
    expect(insertRenameToken("Series", "{Title}", -4, 99)).toEqual({
      value: "{Title}",
      caret: 7,
    });
  });
});
