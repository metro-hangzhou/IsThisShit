# Shared Context

## Program Goal

Operate repository programs through a filesystem-managed reviewer / explorer / worker workflow that preserves truth sources, explicit contracts, and retro-reviewability.

## Current Stage

- `full-dev` only for local development orchestration
- exporter acquisition layer is now treated as upstream foundation
- active next-stage focus is:
  - corpus ingest
  - preprocess
  - deterministic analysis
  - report-first `shi` / `Benshi` analysis

## Current Facts

- the exporter side is strong enough to stop being the only development focus
- analyzer/preprocess source trees exist in `HEAD` and may need restoration in the local worktree before continuing
- `shi_group_751365230` is the dense central reference corpus and reviewer anchor
- large-group corpora should be treated as pending-role-assignment inputs until initial analyzer calibration finishes

## Truth Source Priority

1. `AGENTS.md`
2. program-specific source trees
3. tests
4. existing AGENT/TODO/docs
5. live traces or local corpora only as evidence inputs, not as replacement for code/doc truth

## Strategic Rules

- do not let exporter-specific output templates define all future programs
- preserve retro-reviewability for old and new batches alike
- do not silently treat restored or historical code as already reviewer-approved
- keep direct evidence, context-only inference, and unknown gaps separate in analyzer-facing work

## Mandatory Files To Read

- `AGENTS.md`
- the active program handbook under `dev/agents/programs/`
- the active program TODO under `dev/todos/programs/`
- subsystem AGENT/TODO files relevant to the batch

## Known Missing Truth Sources

If NapCat handbook files named in higher-level docs are missing from this checkout, record that fact explicitly. Do not silently ignore it.
