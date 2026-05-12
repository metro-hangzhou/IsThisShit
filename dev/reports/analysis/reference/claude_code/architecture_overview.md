# Claude Code Architecture Overview

## System-Level View

Claude Code is best understood as a layered agent runtime with five major strata:

1. context construction
2. query lifecycle orchestration
3. context-growth management
4. execution-mode and coordination policy
5. permission/safety enforcement

The important engineering point is that these strata are not collapsed into one giant prompt builder.

## 1. Context Construction

The system constructs a stable prompt prefix from:

- default or custom system prompt
- user context
- system context

The local source shows that:

- `userContext` primarily carries `CLAUDE.md` and memory-file content plus current date
- `systemContext` primarily carries git snapshot and optional cache-breaker injection

Important consequence:

- the system is designed to reuse a stable prefix rather than recompute everything per turn

This matters for our analyzer because:

- stable ontology/rubric/group prior should become a cached prefix
- per-run message evidence should remain the variable packet

## 2. Query Lifecycle Orchestration

`QueryEngine` is the orchestration spine.

It owns:

- message history and normalized API message construction
- tool loop state
- cache-safe parameters
- compaction integration
- mode integration
- transcript/session storage
- permission denial tracking

This means Claude Code is not architected as:

- prompt builder
- then random tool runner

It is architected as a single lifecycle manager with explicit side subsystems.

## 3. Context-Growth Management

Claude Code treats context growth as an operational systems problem.

The relevant mechanisms include:

- auto compaction
- session-memory compaction
- micro compaction
- stripping images/documents before summary
- dropping reinjected attachments before summary
- preserving a recent suffix after compaction
- retrying when compaction itself hits prompt-too-long

The system is not trying to preserve perfect transcript fidelity.
It is trying to preserve productive continuation state.

## 4. Execution Modes and Coordination

Claude Code has execution-regime changes rather than mere prompt variants.

Key examples:

- plan mode
- coordinator mode
- worker/subagent flows

The architecture lesson is:

- mode should change:
  - permission behavior
  - orchestration strategy
  - delegation policy
  - context behavior

not just the wording of one instruction block.

## 5. Permission and Safety Pipeline

Permissions are not treated as a single boolean.

The runtime composes:

- rule-based allow/deny/ask
- working-dir and sandbox checks
- filesystem/path safety checks
- dangerous-rule stripping
- classifier-based auto approval
- hook-based noninteractive fallback

This is one of the clearest engineering patterns in the system:

- safety is a decision pipeline
- not one flag

## What Is Most Relevant To Our Analyzer

### Reusable patterns

- stable context prefix
- prompt-based compact summary
- explicit token budgeting
- execution modes as first-class states
- coordinator/worker split
- pipeline-style safety/evidence gating

### Patterns that should not be copied blindly

- shell/tool permission specifics
- coding-task assumptions about files and tests
- transcript-level semantics that do not map to message-graph semantics

## Main Takeaway

Claude Code’s strongest architectural lesson is not any one feature.

It is this:

- context is managed as a scarce system resource
- orchestration is separate from execution
- modes are explicit
- summary/compact is treated as a structured continuation mechanism

This makes it a useful reference for our future message-first analyzer redesign.
