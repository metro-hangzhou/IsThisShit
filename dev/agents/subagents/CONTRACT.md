# Subagent Contract

This contract governs all local subagent work for the evidence-first exporter program.

## Goal

Move from ad-hoc bug reaction to a decision-complete, NapCat-truth-backed evidence model for exporter behavior.

## Hard Rules

- Work from file-system context, not chat memory.
- Read `SHARED_CONTEXT.md` plus the track-specific `AGENTs.*.md` and `TODOs.*.md` before writing conclusions.
- Treat NapCat source and exporter source as the primary truth sources.
- Do not treat live traces as first truth source. They are evidence for gaps, not the definition of the system.
- Do not propose trace-specific or sample-specific hardcoding.
- Do not run broad searches outside the named scope of the track.
- Do not produce free-form essays. Use the required output structure.

## Required Read Order

1. `AGENTS.md`
2. `dev/todos/TODOs.evidence-first-simulator-exhaustive.md`
3. `dev/todos/TODOs.evidence-first-exporter.md`
4. `dev/todos/TODOs.export-performance.md`
5. `dev/agents/subagents/SHARED_CONTEXT.md`
6. Track-specific `AGENTs.*.md`
7. Track-specific `TODOs.*.md`

If a referenced handbook or doc does not exist, record `missing_truth_source` in `notes.json`.

## Allowed I/O

Each track may only write inside:

- `state/subagent_runs/<track>/input.md`
- `state/subagent_runs/<track>/output.md`
- `state/subagent_runs/<track>/notes.json`

Reviewer writes only inside:

- `state/reviewer_runs/round_<n>/review_input.md`
- `state/reviewer_runs/round_<n>/review_questions.md`
- `state/reviewer_runs/round_<n>/review_blockers.json`
- `state/reviewer_runs/round_<n>/review_resolution.md`

## Required Output Structure

Every `output.md` must contain these sections in order:

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
- `state_space_completeness`
- `reachability_rigor`
- `recursive_soundness`
- `output_semantics`
- `overfitting_risk`

Allowed `resolution_status` values:

- `open`
- `answered`
- `blocked`
- `closed`

## Blocker Rule

Do not describe the evidence space as near-complete unless:

- every dimension is registered
- every dimension value is either:
  - covered by witness
  - or unreachable with a written reason
- reviewer `blocking=true` count is zero

## Continuous Reviewer Rule

- The first-principles reviewer is not a final-stage check only.
- Reviewer work must run continuously alongside development and testing whenever the evidence-space program is actively evolving.
- Any major batch of code changes, simulator-family additions, manifest changes, or test-surface changes must either:
  - be reviewed in the current reviewer round, or
  - be explicitly queued for the next reviewer round before new claims are made.

## Retroactive Review Rule

- If earlier development or testing work landed without passing through the first-principles reviewer track, that work must be reintroduced into the next reviewer round.
- Retro-review is mandatory for:
  - new dimension domains
  - new reachability rules
  - new symbolic recursive families
  - new result-algebra fields
  - new witness/unreachable adjudications
- Do not assume "already implemented" means "already reviewer-approved".
