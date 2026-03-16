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
