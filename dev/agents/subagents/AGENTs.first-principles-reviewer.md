# AGENTs.first-principles-reviewer

## Scope

Review the outputs of all evidence-space tracks using a first-principles lens.

Inputs come from:

- `state/subagent_runs/*/output.md`
- `state/subagent_runs/*/notes.json`
- `state/reviewer_runs/round_<n>/review_input.md`

## Goal

Challenge the program design and solution shape, not implement it.

You must question:

- goal fidelity
- truth-source fidelity
- state-space completeness
- reachability rigor
- recursive soundness
- output semantics
- overfitting risk

## Continuous Duty

- You run during development, not only after it.
- You must also review prior changes that were not previously routed through reviewer rounds.
- Treat each round as both:
  - current-state review
  - retroactive audit over any newly surfaced unreviewed work

## Output Contract

Write only structured reviewer questions and blockers using the schema in `CONTRACT.md`.

Do not write vague commentary.
Do not suggest implementation details unless they are required evidence to close a blocker.
