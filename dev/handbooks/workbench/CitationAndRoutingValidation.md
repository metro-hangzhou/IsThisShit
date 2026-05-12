# Citation And Routing Validation

Status: `draft_round_002`

## Purpose

Make routing auditable after the fact.

## Required Evidence

- `resolved_truth_sources.json`
- `truth_source_usage.json`

## `truth_source_usage.json` Minimum Fields

- `resolved_truth_sources_ref`
- `files_read`
- `files_cited`
- `claims_to_sources`

## Reviewer Enforcement

Reviewer may issue:

- `routing_fidelity`
- `citation_integrity`

blockers whenever:

- must-read files were not read
- claims are unsupported by cited sources
- supporting reports are cited as if they were primary truth
