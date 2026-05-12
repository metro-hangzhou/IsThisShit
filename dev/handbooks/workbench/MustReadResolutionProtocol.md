# Must-Read Resolution Protocol

Status: `draft_round_002`

## Required Outputs

Every round must resolve a must-read set before worker output is considered legitimate.

Required files:

- `resolved_truth_sources.json`
- `resolved_truth_sources.md`

## Minimum Fields

- `task_scope`
- `resolved_domains`
- `must_read_files`
- `expanded_files`
- `missing_required_files`
- `routing_status`

## Rules

- `must_read_files` must be deterministic from the router registry and task scope
- `missing_required_files` must never be silently ignored
- if routing is not `ready`, the round may continue only in blocked or design-only mode
