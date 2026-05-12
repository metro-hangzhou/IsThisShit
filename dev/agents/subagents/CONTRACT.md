# Subagent Contract

This contract governs local subagent work for repository programs that use the shared reviewer / explorer / worker filesystem workflow.

Current programs:

- `exporter_evidence`
- `shi_analyzer`
- `common_track_workflow`

Program-specific overlays live under:

- `dev/agents/programs/<program>/`
- `dev/todos/programs/<program>/`
- `state/program_runs/<program>/`

## Goal

Move from ad-hoc development to a decision-complete, reviewable, filesystem-managed program workflow.

## Hard Rules

- Work from file-system context, not chat memory.
- Read `SHARED_CONTEXT.md` plus the program-specific and track-specific handbooks before writing conclusions.
- Treat the active program's declared truth sources as primary.
- Do not treat live traces as first truth source unless the active program contract explicitly says otherwise.
- Do not propose trace-specific or sample-specific hardcoding.
- Do not produce free-form essays. Use the required output structure.
- Retro-review is mandatory for pre-existing code, design, docs, and direction that predate the common-track workflow.
- Subagents must receive enough context to understand both the local task and the strategic reason the task exists.
- All roles must preserve first-principles thinking: if evidence already decides an outcome, do not hide behind needless timeout or hierarchy.
- Filesystem-mediated communication is intentionally flat: reviewer, explorer, worker, and main agent may challenge and correct one another directly through structured artifacts.
- Default execution mode is `subagents_first`.
- Default delegated model is `gpt-5.5`.
- Default delegated reasoning effort is `xhigh`.
- Main agent defaults to dispatch, integration, acceptance, and broad testing rather than monopolizing local implementation.
- Evidence-first direct judgment must outrank meaningless timeout, fallback sprawl, and path ritual once the decision threshold is met.

## Required Read Order

1. `AGENTS.md`
2. `dev/agents/major_AGENTs.md`
3. `dev/agents/GitBranch_AGENTs.md`
4. `dev/agents/CodeStrict_AGENTs.md`
5. `dev/agents/subagents/SHARED_CONTEXT.md`
6. program-level shared context under `dev/agents/programs/<program>/SHARED_CONTEXT.md`
7. program-level TODO overview under `dev/todos/programs/<program>/README.md`
8. track-specific `AGENTs.*.md`
9. track-specific `TODOs.*.md`
10. relevant retro-review entries under `state/reviewer_runs/program_retro_review_inventory.json`
11. when present, task-local routing/context artifacts such as:
   - `resolved_truth_sources.json`
   - `truth_source_usage.json`
   - `subagent_context_packet.json`

If a referenced handbook or doc does not exist, record `missing_truth_source` in `notes.json`.

## Allowed I/O

Each program track may only write inside:

- `state/subagent_runs/<track>/input.md`
- `state/subagent_runs/<track>/output.md`
- `state/subagent_runs/<track>/notes.json`
- `state/subagent_runs/<track>/resolved_truth_sources.json`
- `state/subagent_runs/<track>/truth_source_usage.json`
- `state/subagent_runs/<track>/subagent_context_packet.json`
- `state/subagent_runs/<track>/subagent_context_packet.md`
- `state/subagent_runs/<track>/challenge_register.json`
- `state/subagent_runs/<track>/objection_or_fast_fail_notice.md`

Program-level work may also write inside:

- `state/program_runs/<program>/`

Retro-review inventory lives at:

- `state/reviewer_runs/program_retro_review_inventory.json`
- `state/reviewer_runs/program_retro_review_inventory.md`

Reviewer writes only inside:

- `state/reviewer_runs/round_<n>/review_input.md`
- `state/reviewer_runs/round_<n>/review_questions.md`
- `state/reviewer_runs/round_<n>/review_blockers.json`
- `state/reviewer_runs/round_<n>/review_resolution.md`

## Required Output Structure

Default `output.md` structure for generic programs:

1. `Facts`
2. `Interfaces / Data Contracts`
3. `Already Implemented`
4. `Gaps / Risks`
5. `Proposed Changes`
6. `Concrete File Refs`

Program-specific overlays may replace this default if the program handbook says so.

Exporter-evidence overlay currently remains:

1. `Dimensions`
2. `Reachability Rules`
3. `Already Modeled`
4. `Missing / Partial`
5. `Recommended Simulator Families`
6. `Concrete File Refs`

## Reviewer Question Schema

Each reviewer question must include:

- `question_id`
- `category`
- `claim_under_review`
- `challenge`
- `required_evidence`
- `blocking`
- `resolution_status`

Allowed `category` values:

- `goal_fidelity`
- `truth_source_fidelity`
- `data_contract`
- `routing_fidelity`
- `citation_integrity`
- `execution_policy_fidelity`
- `subagent_coverage`
- `model_policy_fidelity`
- `main_agent_scope_integrity`
- `first_principles_fidelity`
- `path_bloat_risk`
- `communication_flatness`
- `evidence_decision_fidelity`
- `latency_waste_risk`
- `decision_quality`
- `causal_traceability`
- `state_space_completeness`
- `reachability_rigor`
- `evaluation_adequacy`
- `recursive_soundness`
- `output_semantics`
- `rollout_risk`
- `overfitting_risk`

Allowed `resolution_status` values:

- `open`
- `answered`
- `blocked`
- `closed`

## Blocker Rule

Do not describe any program as reviewer-cleared unless:

- the program-level contract is satisfied
- reviewer `blocking=true` count relevant to the claim is zero
- relevant retro-review batches are either:
  - closed
  - or explicitly marked non-blocking with a written reason

## Continuous Reviewer Rule

- The first-principles reviewer is not a final-stage check only.
- Reviewer work must run continuously alongside development and testing whenever an active program is evolving.
- Any major batch of code changes, contract changes, corpus changes, or test-surface changes must either:
  - be reviewed in the current reviewer round, or
  - be explicitly queued for the next reviewer round before new claims are made.

## Retroactive Review Rule

- If earlier development or testing work landed without passing through the first-principles reviewer track, that work must be reintroduced into the next reviewer round.
- Retro-review is mandatory for:
  - prior code
  - prior design
  - prior docs
  - prior direction-setting conclusions
  - existing local corpora and derived artifacts
- Do not assume "already implemented" means "already reviewer-approved".
- Use `state/reviewer_runs/program_retro_review_inventory.json` as the shared ledger of retro-review batches, question mapping, and citation gates.
