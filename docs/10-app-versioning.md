---
description: A single application release version shared by Python packaging, the API, and Settings General.
status: active
---

# Application versioning

`src/manga_tagger/__init__.py` defines `__version__` as the single release version. Hatch reads it to produce dynamic project metadata; uv invalidates editable-build metadata when this file changes; wheel names and installed distribution metadata use this value. The UI package is private build tooling and does not maintain a separate app version.

Versions use `MAJOR.MINOR.PATCH`. Feature releases increment MINOR and reset PATCH to zero; bug-fix releases increment PATCH. Breaking changes increment MAJOR after 1.0; during 0.x, breaking changes increment MINOR and are documented. A release can group multiple changes under one version. Released versions must not be reused for changed artifacts. Feature implementation updates the release version unless it is explicitly part of an already bumped, unreleased batch. Refresh `uv.lock` after a version change, run both suites, rebuild the UI, and build a wheel before distributing it.

The next release is 0.2.1, fixing clean-checkout CI and installation ordering
after 0.2.0 added rename-template tag chips and version display.

`GET /api/app-info` returns `{ "version": "<__version__>" }` from the running backend. It does no library or configuration work. The client fetches it once at startup alongside config and theme, then passes the result to Settings. General shows a read-only Version row after Title languages. A failed request shows `Unavailable` and leaves the app usable. Save never sends the version as configuration.

## Configuration

No new configuration keys. Version belongs to the application release, not user preferences.

## Testing

- Python packaging configuration points Hatch at the single version definition; the lockfile records the dynamic editable project, and installed metadata matches the runtime version.
- The app-info API returns that version, including on an empty library, and does not write config or start a job.
- UI API tests verify the request and error handling. Settings rendering tests cover supplied versions and unavailable state as non-editable text.
- Release verification checks wheel metadata, embedded UI, console entry point, and launcher assets.

## Acceptance criteria

- Feature releases and fix releases follow the documented version policy.
- Python, wheel metadata, and the version shown in General agree.
- The version is visible without editing or saving settings.
- Version lookup failure does not prevent application startup.
- The 0.2.0 wheel contains the new rename chips and version display.
