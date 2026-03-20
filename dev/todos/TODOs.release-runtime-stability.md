# Release / Runtime Stability TODOs

Spec baseline: 2026-03-20

This file tracks release-branch (`main` / `runtime`) and local runtime integrity issues that are easy to miss when the main development focus is on exporter/analyzer features.

## Problem Statement

Recent field failures showed that the project has two separate but related stability risks:

1. release branches can regress on small compatibility entrypoints even when core logic is otherwise correct
2. `full-dev` can drift into a locally broken vendored NapCat runtime state even though the branch is not meant to auto-update

## Recorded Incidents

### [2026-03-20][001] CLI update policy must stay branch-specific

- Confirmed policy:
  - only `main/start_cli.bat` should auto-update from remote
  - `full-dev` must not auto-update
  - `runtime` must not auto-update
  - other branches must default to no auto-update
- Risk:
  - shared launcher edits can accidentally re-enable auto-update on local-only branches

### [2026-03-20][002] `full-dev` lost `start_napcat_logged.bat`

- Symptom:
  - local runtime helper batch file disappeared from `full-dev`
- Impact:
  - lower observability during local NapCat startup/debugging
- Guardrail:
  - keep the logged launcher present on `full-dev`

### [2026-03-20][003] Release exporter progress API regression

- Symptom on release lines:
  - `NapCatMediaDownloader` missing `begin_export_download_tracking(...)`
  - later field report also showed missing `settle_export_download_progress(...)`
- Impact:
  - `/export group ...` completion/export path can fail before real export work proceeds
- Required follow-up:
  - keep downloader progress helper API compatibility covered by release-branch regression tests

### [2026-03-20][004] `full-dev` vendored NapCat runtime missing dist artifacts

- Symptom:
  - `/login` failed before WebUI became ready
  - NapCat backend threw:
    - missing `path-to-regexp/dist/index.js`
- Confirmed missing runtime artifacts:
  - `path-to-regexp/dist/index.js`
  - `qs/dist/qs.js`
- Impact:
  - local NapCat runtime could not boot correctly on `full-dev`
- Guardrail:
  - vendored runtime completeness checks should cover required `node_modules/*/dist/*` artifacts

### [2026-03-20][005] Friend machine huge export still hits forward metadata timeout

- Symptom:
  - large group export can spend repeated `12s` timeouts on:
    - `media_resolution_substep substep=forward_context_metadata`
  - plugin route involved:
    - `/plugin/napcat-plugin-qq-data-fast/api`
    - `/hydrate-forward-media`
- Impact:
  - very large exports can look stalled or fail after repeated timeout chains
- Status:
  - still an active investigation/fix lane

### [2026-03-20][006] Large export can crash during final progress settlement

- Symptom:
  - export body already produced progress output
  - final crash:
    - `'NapCatMediaDownloader' object has no attribute 'settle_export_download_progress'`
- Impact:
  - large export can fail at the final materialization/progress-settlement stage even after doing real work
- Guardrail:
  - downloader progress helper methods must be treated as a compatibility contract:
    - `begin_export_download_tracking(...)`
    - `export_download_progress_snapshot(...)`
    - `settle_export_download_progress(...)`

### [2026-03-20][007] Need branch-safe quick login to reduce QR friction

- Symptom:
  - operator flow still falls back to QR too often even when local QQ authorization already exists
- Desired behavior:
  - `/login` should first attempt NapCat quick login through WebUI candidate accounts
  - QR should remain as fallback, not the only path
- Guardrail:
  - quick login must not remove QR fallback
  - quick login support should work without changing the branch auto-update policy

### [2026-03-20][008] `app.py login` and REPL `/login` must stay behavior-compatible

- Symptom:
  - quick login was initially wired in REPL first, while command-line `app.py login` still only did QR flow
- Impact:
  - operator behavior diverges depending on entrypoint
  - troubleshooting gets noisy because REPL and non-REPL screenshots no longer mean the same thing
- Guardrail:
  - `app.py login` and REPL `/login` must share:
    - quick login first
    - QR fallback second
    - same observable status prints where practical

### [2026-03-20][009] Large live export now completes, but still has genuine forward metadata slow spots

- Live validation:
  - `app.py export-history group "蕾米二次元萌萌群" --limit 2000 --format jsonl`
  - completed in about `40.2s`
  - no longer crashed on `settle_export_download_progress(...)`
- Residual signal:
  - one real `forward_context_metadata` timeout still occurred on a deep forward image context
  - final missing breakdown remained dominated by:
    - `qq_not_downloaded_local_placeholder`
- Interpretation:
  - crash regression is fixed
  - repeated sibling timeout amplification is reduced
  - deep forward metadata hydration still needs targeted performance/fidelity follow-up

## Current Fix / Guardrail Tasks

- [ ] Keep CLI launcher policy explicit in regression review:
  - `main` may auto-update itself
  - `full-dev` / `runtime` may not
- [ ] Keep `start_napcat_logged.bat` present on `full-dev`
- [ ] Add or maintain release regression tests for downloader progress helper methods:
  - `begin_export_download_tracking(...)`
  - `settle_export_download_progress(...)`
- [ ] Add a runtime integrity checklist for vendored NapCat dependencies on `full-dev`
- [ ] Investigate and reduce residual `forward_context_metadata` timeout cost on large exports
- [ ] Record friend-machine failures into perf/forensics docs when new logs arrive
- [ ] Keep quick-login path covered by regression tests so QR fallback remains intact
- [ ] Keep `app.py login` and REPL `/login` behavior-compatible in regression coverage

## Related Files

- [technical-roadmap.md](../documents/technical-roadmap.md)
- [git_branching_plan.md](../documents/git_branching_plan.md)
- [TODOs.export-performance.md](TODOs.export-performance.md)
- [TODOs.export-optimization.md](TODOs.export-optimization.md)
