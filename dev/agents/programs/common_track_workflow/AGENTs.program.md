# Common Track Workflow Program

## Purpose

This program owns the refactor of the shared reviewer / explorer / worker workflow itself.

It exists so the workflow can be reviewed under the same standards it applies to other programs.

## Current Phase

- `phase_0_workflow_refactor`
- archive-first
- user-gated
- no broader repo refactor until this workflow passes review

## Truth Sources

1. `AGENTS.md`
2. `dev/agents/subagents/CONTRACT.md`
3. `dev/agents/subagents/SHARED_CONTEXT.md`
4. `dev/agents/programs/**`
5. `dev/todos/programs/**`
6. `state/reviewer_runs/**`
7. `state/program_runs/**`

## Non-Negotiable Rules

- Archive before rewriting workflow-bound contracts or indexes.
- Do not delete old workflow artifacts.
- Do not silently mark user gates as passed.
- Reviewer output must stay structured.
- Worker responses must be explicit and round-scoped.

## Development Execution Mode

- Light tasks may be completed locally by the main agent without mandatory subagent dispatch.
- A light task means:
  - a single-file or low-coupling change
  - local UI polish
  - a small fix that does not materially expand cross-module contracts or the test surface
- Heavier tasks must use parallel subagents under the common-track workflow.
- A heavier task means:
  - cross-component or cross-subsystem change
  - work that needs structured reviewer critique or blocker recheck
  - a batch that changes runtime behavior, data contracts, asset chains, primary interaction structure, or validation scope
- For heavier tasks, the main agent defaults to:
  - explicitly stating the task-weight judgment
  - launching parallel reviewer / explorer / worker tracks
  - integrating results
  - running final acceptance and documentation backfill
- Current additional model policy:
  - whenever subagents are used, use `gpt-5.5`
  - reasoning effort must be `xhigh`
  - do not temporarily downgrade to other models or lower reasoning effort for speed, cost, or habit
- Do not disguise a heavier common-track task as an ordinary one-off local tweak.

## Verification Autonomy

- Small-scale validation runs do not require a fresh user approval round.
- A small-scale validation run means a bounded local smoke test, one short live/session probe, a targeted frontend render check, or a narrow backend contract verification whose purpose is to verify a just-made change.
- For these checks, the agent should run the validation directly, record what was run, and report the artifact/session id afterward.
- This does not authorize destructive actions, broad batch jobs, release syncs, large-cost model sweeps, or long-running production exports; those still need explicit scope judgment and, when risky, user approval.
