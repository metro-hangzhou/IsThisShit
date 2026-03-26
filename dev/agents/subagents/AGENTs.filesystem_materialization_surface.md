# AGENTs.filesystem_materialization_surface

## Scope

Analyze filesystem/path provenance and bundle materialization in:

- `src/qq_data_core/media_bundle.py`
- `src/qq_data_core/normalize.py`
- path/materialization-related docs that actually exist in this checkout

## Goal

Extract first-class dimensions for:

- path provenance
- filesystem family
- NTQQ vs legacy layout
- month drift
- placeholder shell classes
- same-volume vs cross-volume copy
- materialization outcomes

## Do Not

- redesign copy logic
- treat performance-only I/O distinctions as resolver truth unless they change semantics

