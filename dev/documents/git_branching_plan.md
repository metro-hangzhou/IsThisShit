# Git Branching Plan

This repository now treats Git layout as a first-class maintenance concern.

## Parent Repository Branch Roles

### `full-dev`

Tracks the main exporter repository for development work:

- source code under `src/`
- tests under `tests/`
- developer-facing planning/docs under `dev/`
- helper scripts under `scripts/`
- vendored NapCat runtime under `NapCat/`

Default daily development must happen on `full-dev`.

This branch is the normal working branch for:

- new feature development
- analysis / preprocess / LLM substrate work
- refactors
- experimental or iterative implementation
- developer-facing planning and design notes

It must not track generated or machine-local output such as:

- `dist/`
- `exports/`
- `state/`
- `.tmp/`
- `.venv/`
- `.idea/`

### `runtime`

Tracks the minimal runtime/update surface for operators:

- runtime entrypoints
- `src/`
- start scripts
- vendored `NapCat/`
- user-facing runtime docs such as `CLI_USAGE.md`

It must not track developer-facing materials such as:

- `dev/`
- `tests/`
- most helper scripts

### `main`

Acts as the primary release/archive branch for the generally usable project state.

`main` should be used for:

- release-shaped snapshots
- operator-facing updates
- shareable or testable runtime states
- remote archival checkpoints

It should not be treated as the default day-to-day development branch.

## Branch Workflow Rule

Normal development workflow:

1. Work on `full-dev` by default.
2. Treat `main` and `runtime` as release / validation / archival branches.
3. Use `main` and `runtime` for:
   - publishable checkpoints
   - local validation against a cleaner runtime surface
   - behavior comparison against development state

## Sync / Archive Rule

When a change set is large, important, or meaningfully changes behavior:

- commit the relevant state on `full-dev`
- prepare corresponding `main` and `runtime` snapshots as needed
- push `main` and `runtime` to the remote repository for archival / rollback reference

This keeps remote history useful as a deployment and validation record, while preserving `full-dev` as the main ongoing development lane.

## NapCatQQ Rule

`NapCatQQ/` is intentionally **not** tracked by the parent repository branches.

Reason:

- it is a separate upstream-tracking checkout
- it carries a custom local branch
- it must retain the ability to merge future upstream `NapCatQQ` updates when QQ changes

Therefore:

- do not flatten `NapCatQQ/` into ordinary parent-repo files
- do not treat it as disposable local clutter
- do not rely on parent-branch Git history to preserve its merge relationship

Current maintenance expectation:

- keep `NapCatQQ/` as an independent nested repository
- update it separately from the parent repo
- when upstream QQ/NapCat changes require it, merge upstream `NapCatQQ` into the custom local branch there

## NapCat Runtime Local State Rule

The parent repository should also avoid tracking machine-local NapCat runtime state, including:

- `NapCat/config.json`
- `NapCat/napcat/cache/`
- `NapCat/napcat/config/*.json`

Those files are operator-local runtime state and are expected to vary across machines.
