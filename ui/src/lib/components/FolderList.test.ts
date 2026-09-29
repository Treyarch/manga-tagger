import { render } from "svelte/server";
import { describe, expect, it } from "vitest";

import FolderList from "./FolderList.svelte";

describe("FolderList", () => {
  it("renders browsable folder rows with trailing accessible remove buttons", () => {
    const { body } = render(FolderList, {
      props: {
        label: "Library roots",
        addLabel: "Add library folder",
        paths: ["/books", "/manga/long folder"],
        emptyText: "No library folders.",
        onBrowse: () => undefined,
        onRemove: () => undefined,
      },
    });

    expect(body).toContain("Library roots");
    expect(body).toContain('aria-label="Add library folder"');
    expect(body).toContain("folder-plus");
    expect(body).toContain('title="/books"');
    expect(body).toContain('aria-label="Remove /books"');
    expect(body).toContain('aria-label="Remove /manga/long folder"');
    expect(body.indexOf("/books")).toBeLessThan(
      body.indexOf('aria-label="Remove /books"'),
    );
  });

  it("renders the supplied empty state without remove controls", () => {
    const { body } = render(FolderList, {
      props: {
        label: "Excluded folders",
        addLabel: "Add excluded folder",
        paths: [],
        emptyText: "No excluded folders.",
        onBrowse: () => undefined,
        onRemove: () => undefined,
      },
    });

    expect(body).toContain("No excluded folders.");
    expect(body).toContain('aria-label="Add excluded folder"');
    expect(body).not.toContain('aria-label="Remove ');
  });
});
