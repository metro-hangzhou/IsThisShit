# Git Branching Plan

This repository now treats Git layout and runtime behavior as first-class maintenance concerns.

## Parent Repository Branch Roles

### `full-dev`

Tracks the main exporter repository for development work:

- source code under `src/`
- tests under `tests/`
- developer-facing planning/docs under `dev/`
- helper scripts under `scripts/`
- vendored NapCat runtime under `NapCat/`

Default daily development must happen on `full-dev`.

`full-dev` is a local-first development branch:

- commit locally and frequently
- do not treat remote push as the default action
- do not auto-update from remote in `start_cli`

### `runtime`

Tracks the minimal runtime/update surface for operators:

- runtime entrypoints
- `src/`
- start scripts
- vendored `NapCat/`
- user-facing runtime docs such as `dev/handbooks/runtime/CLIUsage.md`

`runtime` is a release/validation branch:

- do not use it as the default coding branch
- do not auto-update from remote in `start_cli`
- push it to remote only for release/archive checkpoints

### `main`

Acts as the primary release/archive branch for the generally usable project state.

`main` should be used for:

- release-shaped snapshots
- operator-facing updates
- shareable or testable runtime states
- remote archival checkpoints

`main` is currently the only branch allowed to auto-update itself from remote inside `start_cli.bat`, and even there the guard must remain strict:

- only auto-update when `git branch --show-current` is exactly `main`
- never auto-update `full-dev`, `runtime`, or any other branch through the shared launcher

## Branch Workflow Rule

Normal development workflow:

1. Work on `full-dev` by default.
2. Commit locally on `full-dev` as work accumulates.
3. Do not push `full-dev` to remote as part of the normal workflow.
4. Treat `main` and `runtime` as release / validation / archival branches.
5. Use `main` and `runtime` for:
   - publishable checkpoints
   - local validation against a cleaner runtime surface
   - behavior comparison against development state

## CLI / Runtime Launcher Rule

Current launcher policy is part of branch policy:

- `main/start_cli.bat`
  - may check `origin/main`
  - may fast-forward itself when already on branch `main`
- `full-dev/start_cli*.bat`
  - must stay local-only
  - must not fetch or pull automatically
- `runtime/start_cli*.bat`
  - must stay local-only
  - must not fetch or pull automatically

Related field note from `2026-03-20`:

- `full-dev` once lost `start_napcat_logged.bat`; treat that launcher as required local runtime tooling and keep it present on `full-dev`
- release branches once regressed on exporter progress helper methods while `main` still auto-updated; this reinforces that launcher/update policy and runtime/API compatibility need to be tracked together

## Sync / Archive Rule

When a change set is large, important, or meaningfully changes behavior:

- commit the relevant state on `full-dev`
- prepare corresponding `main` and `runtime` snapshots as needed
- push `main` and `runtime` to the remote repository for archival / rollback reference
- do not push `full-dev` unless the workflow rule is deliberately changed later

## NapCat Runtime Local State Rule

The parent repository should avoid tracking machine-local NapCat runtime state, including:

- `NapCat/config.json`
- `NapCat/napcat/cache/`
- `NapCat/napcat/config/*.json`

Those files are operator-local runtime state and are expected to vary across machines.

However, vendored runtime completeness still matters.

Current field note:

- `full-dev` experienced a runtime failure because vendored `node_modules` lacked:
  - `path-to-regexp/dist/index.js`
  - `qs/dist/qs.js`
- this caused `/login` startup to fail before NapCat WebUI became ready
- treat compiled runtime dependency artifacts required by the shipped NapCat runtime as part of branch integrity, not optional clutter
