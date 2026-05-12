# Flat Communication Policy

Status: `draft_round_003`

## Core Rule

Any workflow unit may directly challenge another unit through structured filesystem artifacts when evidence or first-principles reasoning shows a local rule, task framing, or implementation path is wrong.

## Applies To

- reviewer
- explorer
- worker
- main agent
- subagents

## Allowed Direct Challenge Targets

- reviewer findings
- worker draft assumptions
- main-agent task framing
- subagent local task framing

## Constraint

Flat communication must remain:

- structured
- attributable
- file-backed
- reviewable

Not informal chat-style interruption.

## Mandatory Artifact

Flat communication needs at least one canonical carrier:

- `challenge_register.json`

Optional human mirrors:

- `cross_role_challenges.md`
- `objection_or_fast_fail_notice.md`

If direct challenge is allowed, a traceable challenge carrier must exist.
