# Common Track Workflow

Status: `draft_round_002`

## Purpose

Define the shared workflow used to read, redesign, review, revise, and approve repository subsystems.

## Core Roles

- `explorer`
  - extracts facts, structure, and contradictions from the current system
- `worker`
  - produces the redesign draft and responds to reviewer blockers
- `reviewer`
  - issues strict structured critiques and pass/fail blockers
- `main agent`
  - orchestrates rounds, dispatches work, integrates outputs, and owns acceptance and broad testing
- `user`
  - approves gate transitions at predefined checkpoints

## Mandatory Principles

- archive-first
- document-based strong routing before substantive work
- subagents-first execution by default
- delegated default model is `gpt-5.5`
- delegated default reasoning effort is `xhigh`
- main agent focuses on dispatch, acceptance, and overall testing
- all units must follow first-principles law
- workflow communication should stay flat and filesystem-backed
- evidence-first decision should beat meaningless timeout or path bloat once the decision threshold is met
- structured reviewer output
- explicit worker responses
- user-gated phase transitions
- no silent promotion from draft to canonical
