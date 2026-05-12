# Subagent Context Injection Policy

Status: `draft_round_003`

## Core Rule

Subagents must not receive only a narrow local task description.

They must also receive enough strategic context to understand:

- why this task exists
- what larger program goal it serves
- what rules and truth sources govern it
- what bad local optimization would look like

## Minimum Injection Layers

1. task-local scope
2. active program context
3. must-read truth-source chain
4. current review pressure / known blockers
5. strategic objective and failure boundary

## Mandatory Artifacts

A subagent must have before substantive execution:

- `subagent_context_packet.json`
- optional human mirror: `subagent_context_packet.md`

Minimum fields must include:

- `program`
- `round`
- `task_scope`
- `parent_goal`
- `why_this_subtask_exists`
- `success_criteria`
- `failure_boundary`
- `must_read_files`
- `related_batches`
- `strategic_notes`
- `known_wrong_paths`
- `may_directly_challenge`

## Failure Pattern To Avoid

Do not create subagents that merely obey local instructions while missing the strategic reason they should challenge those instructions.

## Validator Goal

Validator should eventually check:

- context packet exists
- required fields are present
- the packet carries strategic context rather than only local task description
