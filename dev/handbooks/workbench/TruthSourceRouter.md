# Truth Source Router

Status: `draft_round_002`

## Purpose

Define how the workflow resolves the required handbook and document chain for a task before substantive work begins.

## Core Rule

No substantive work is considered valid unless a routing step has first produced:

- `resolved_truth_sources.json`
- `truth_source_usage.json`

## Responsibilities

- detect active task domains
- expand must-read chains
- mark missing required files
- hand deterministic reading obligations to worker and subagents

## Routing Priority

1. repo-wide root handbooks
2. domain handbooks
3. program-specific handbooks
4. supporting plans and reports

## Enforcement

- validator checks routing artifacts exist
- reviewer can issue `routing_fidelity` blockers
- unresolved routing means the round cannot be considered closed
