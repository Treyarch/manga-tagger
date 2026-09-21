# [AGENTS.md](http://AGENTS.md)

Manga Tagger is a simple and clean app to easily rename, scrappe, tag and organise Mangas collections. This is a **spec-driven project**: `docs/README.md` and `docs/00-project-overview.md` define the workflow. Read them before writing code.

## Spec workflow

- New feature: spec first (`docs/NN-short-description.md`), then code. Specs must stay in sync with the code.
- Change to existing code: update or supersede the relevant spec *before* adjusting code.
- Spec frontmatter: a required `description` (one-sentence summary of the doc) plus `status: proposed | active | superseded` (`superseded` also sets `replacement: <doc name>`). No frontmatter means `proposed`.
- Every spec should have `Configuration`, `Testing`, and `Acceptance criteria` sections. `proposed` specs may carry `Open questions`, but all must be answered before the status flips to `active`.
- A feature is not complete without reasonably comprehensive unit tests.

