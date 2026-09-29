# Code review remediation

This checklist tracks the findings from the full repository review. Manga Tagger is spec-driven, so each implementation task must update the named active specification before changing code.

## Recommended order

1. Secure CBR extraction.
2. Preserve drafts when a save has per-file failures.
3. Correct Settings-triggered scans and job tracking.
4. Repair scan-root result reporting.
5. Remove duplicate page-listing work.
6. Consolidate duplicated contracts and remove dead helpers.
7. Bring user-facing documentation and dependency validation up to date.

## 1. Secure CBR extraction

- [x] Update `docs/01-archives-and-comicinfo.md` with explicit extraction safety rules for every CBR operation, not only cover replacement.
- [x] Reject symbolic links and other non-regular extracted entries before reading them or adding them to a CBZ.
- [x] Verify that every resolved extracted path remains inside the temporary extraction directory.
- [x] Decide whether member names must be validated before invoking `unar`; document the chosen boundary.
- [x] Apply the same validation to single-member reads, metadata saves, conversion, and cover writes.
- [x] Add tests for symlinks, path traversal attempts, nested safe members, and cleanup after rejection.

Done when a crafted CBR cannot make Manga Tagger read or package a file outside its temporary extraction directory, and the original archive remains unchanged after rejection.

## 2. Preserve drafts after save failures

- [x] Update `docs/04-application-shell.md` to define navigation behavior for a job that succeeds overall but contains per-file error entries.
- [x] Treat a pending-navigation save as successful only when every archive write that was required succeeded.
- [x] Keep the current selection and dirty form when any required archive write fails.
- [x] Define how poster-only and index-refresh errors affect navigation, since metadata may already be safely written.
- [x] Preserve dirty values for failed files after an ordinary partial batch save instead of silently rebuilding them as clean.
- [x] Add UI tests for one-file failure, partial batch failure, cancellation, an unchanged/empty save, and poster-only failure.

Done when no save failure can silently discard an unsaved metadata draft or navigate away from the affected selection.

## 3. Correct Settings scans and job tracking

- [x] Update `docs/04-application-shell.md` to define whether unchanged `library_roots` should enqueue a scan and how the client receives the scan job id.
- [x] Stop sending `library_roots` from Settings when the roots were not changed, or compare old and new roots in the API before enqueueing.
- [x] Allow unrelated settings such as theme and provider credentials to be saved while another job is active, as the current spec intends.
- [x] Return the scan job from a root-changing Settings save so the client can watch the exact id without racing `/api/jobs/current`.
- [x] Make startup scan completion discoverable even when it finishes before the first UI poll.
- [x] Add integration tests for unchanged roots, changed roots, empty roots, very fast scans, startup scans, and settings saves during another job.

Done when every root-changing scan is observed exactly once, unrelated settings do not trigger scans, and the shelf refreshes after both fast and slow scans.

## 4. Repair scan-root result reporting

- [x] Reconcile `ScanResult`, the shell job payload, and the TypeScript consumer.
- [x] Preserve the distinction between a skipped root and an incomplete root.
- [x] Emit one stable API shape and use the same field names in Python, TypeScript, tests, and `docs/04-application-shell.md`.
- [x] Add an end-to-end contract test that passes a real scan result through the job endpoint into the client formatting helper.

Done when the inspector shows `{path} was skipped.` for a missing root and `{path} was not fully scanned.` for an unreadable/incomplete root.

## 5. Remove duplicate page-listing work

- [ ] Update `docs/01-archives-and-comicinfo.md` or `docs/04-application-shell.md` if the page-read API boundary changes.
- [ ] Introduce a member-based page read, or return the resolved member name with the read result, so the route does not list the archive twice.
- [ ] Keep index bounds checking and media-type selection in one clear layer.
- [ ] Add instrumentation tests proving one CBZ central-directory listing and one CBR `lsar` invocation per preview request.

Done when one preview request lists the archive once and reads/extracts only the requested page member.

## 6. Consolidate duplicated contracts and dead helpers

- [ ] Inventory duplicated field lists, provider ids, column mappings, selection transitions, form construction, and cover URL parsing across Python and TypeScript.
- [ ] Mark each duplication as intentional boundary code or choose one source of truth.
- [ ] Prefer generated client contracts or explicit cross-layer contract tests where sharing runtime code is impractical.
- [ ] Remove unused helpers such as `thumbnail_bytes` if no supported caller needs them.
- [ ] Keep `save_many` only if its standalone core API remains intentional and tested; document why the application shell does not use it.
- [ ] Add drift tests for form fields, shared fields, provider ids, API result keys, and lockable fields.

Done when duplicated behavior is either eliminated or guarded by a test that fails when the Python and TypeScript contracts diverge.

## 7. Documentation and dependency validation

- [ ] Update `README.md` so scan progress/cancellation matches the current UI.
- [ ] Add `enabled_providers` and `animate_interface` to the README configuration table.
- [ ] Add specs 06, 07, and 09 to the README spec index.
- [ ] Decide and document the supported Python versions rather than relying on an unbounded `>=3.12` claim without a tested matrix.
- [ ] Add a committed dependency lockfile or explicit compatible version bounds for reproducible development and CI.
- [ ] Run the full API test suite on every supported Python version, including a minimal FastAPI `TestClient` smoke test.
- [ ] Resolve the Python 3.14 `TestClient` hang by upgrading/pinning the compatible FastAPI, Starlette, HTTPX, and AnyIO combination, or temporarily cap the supported Python range.

Done when the README matches all active specs and the complete Python and UI test suites pass from a clean, reproducible install on every supported runtime.

## Final verification

- [ ] All affected specs are active and synchronized with the implementation.
- [ ] Full Python suite passes, including all API tests.
- [ ] Full UI unit suite and production build pass.
- [ ] Security regression fixtures remain hermetic and contain no host filesystem paths.
- [ ] Manual smoke test covers startup scan, Settings root changes, partial save failure, CBR conversion, and scan-root error display.
