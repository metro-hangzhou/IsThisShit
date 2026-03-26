# Shared Context

## Program Goal

Build a NapCat-truth-backed, evidence-first simulator and exporter model that approaches mathematical coverage over the exporter's real decision space.

## Current Stage

- `full-dev` only
- simulator and orchestration stay local
- release branches are not the focus of this orchestration layer

## Current Facts

- Recent live traces proved that some previously missing dimensions were not modeled:
  - top-level speech terminal proof
  - forward image parent-scoped timeout reuse
- Those two families are now represented in the local simulator and the simulator is green again.
- Remaining goal is not to patch one more bug, but to formalize the full evidence space.

## Truth Source Priority

1. `NapCatQQ/` and `NapCat/` source
2. exporter source under `src/qq_data_integrations/napcat/` and `src/qq_data_core/`
3. tests
4. existing AGENT/TODO docs
5. live traces as gap evidence only

## Strategic Rules

- No pressure testing inside the logic simulator.
- No trace-specific hardcoding.
- No “close enough” coverage claims from case count alone.
- Infinite `forward` nesting must be handled by symbolic recursion and invariants, not by deep expansion.
- Materialization semantics must be modeled, not just resolver/path kind.

## Mandatory Files To Read

- `AGENTS.md`
- `dev/todos/TODOs.evidence-first-simulator-exhaustive.md`
- `dev/todos/TODOs.evidence-first-exporter.md`
- `dev/todos/TODOs.export-performance.md`

## Known Missing Truth Sources

If NapCat handbook files named in higher-level docs are missing from this checkout, record that fact explicitly. Do not silently ignore it.

