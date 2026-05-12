# Subagent Execution Policy

Status: `draft_round_002`

## Core Rule

The workflow is subagents-first by default.

## Coverage Test

This rule cannot be satisfied merely by spawning a few agents.

It must answer:

- which task classes must be split by default
- which task classes may stay local to the main agent
- whether deviations are explicitly recorded

## Default Model Policy

- default delegated model: `gpt-5.5`
- default delegated reasoning effort: `xhigh`

## Main Agent Role

The main agent should primarily:

- classify task batches
- dispatch subagents
- integrate outputs
- run acceptance checks
- run broad regression and final validation

The main agent should not monopolize detailed exploration or drafting work when the task can be safely delegated.

## Exceptions

Main-agent-local work is still allowed when:

- the task is blocking and immediate
- the write scope is too tightly coupled
- delegation would duplicate work or create merge risk

## Mandatory Artifacts

The minimum runtime artifacts for this policy are:

- `task_dispatch_plan.md`
- `subagent_execution_ledger.json`
- `main_agent_action_ledger.md`
