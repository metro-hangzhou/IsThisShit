# Planning, Execution, Permissions, And Subagents

## Why This Topic Matters

The current `shi_analyzer` has been too strongly coupled:

- one analyzer trying to do selection, interpretation, scheduling, and review guidance at once

Claude Code is a useful counterexample because it splits:

- mode
- orchestration
- execution
- permissions

## `QueryEngine` As The Lifecycle Spine

The local source shows that `QueryEngine` is not just a convenience wrapper.

It owns:

- session message lifecycle
- context assembly integration
- compaction hooks
- permission handling
- tool loop state
- persistence and transcript behavior

This means system behavior changes are attached to the engine lifecycle, not hidden in random command handlers.

For our redesign, this suggests:

- central analyzer runtime
- plus separable subsystems for:
  - message probing
  - relation assembly
  - cross-window aggregation
  - review scheduling

## Plan Mode

### What Claude Code does

The `/plan` command is intentionally thin.

It mainly:

- transitions permission/mode state
- opens or shows the plan file
- delegates policy details elsewhere

The architectural lesson is:

- planning is a regime change
- not just a prompt change

### Migration implication

For our analyzer, we should distinguish explicit execution regimes such as:

- `design_or_retro_review_mode`
- `message_probe_mode`
- `relation_assembly_mode`
- `cross_window_aggregation_mode`
- `review_packet_mode`

Different modes should change:

- budget policy
- evidence thresholds
- allowed operations
- summary schema

## Coordinator Mode

`coordinatorMode.ts` is deliberately narrow.

It provides:

- resume-time mode matching
- worker capability context
- a strongly opinionated coordinator system prompt

The prompt strongly separates:

- coordinator synthesis
- worker execution
- verification responsibility

Key lessons:

- the coordinator should synthesize and decide
- workers should execute bounded tasks
- continue-vs-spawn should depend on context overlap

This is extremely relevant to our redesign because the user is already asking for:

- common-track workflow
- first-principles review
- structured redesign instead of monolithic prompt tweaking

## Subagent Spawning

`spawnMultiAgent.ts` treats subagent execution like infrastructure.

It handles:

- model inheritance
- permission propagation
- backend selection
- identity bookkeeping
- session/team mechanics

This separation matters more than the UI mechanics.

The reusable pattern is:

- subagent identity/config
- permission regime
- execution backend

should be decoupled concerns

For us, this suggests a future split between:

- analyzer coordinator
- message analyzers
- relation extractors
- verification/audit workers

without forcing all of that into one giant class or prompt.

## Permission Pipeline

The permission system is layered:

- explicit allow/deny/ask rules
- sandbox and working-dir checks
- filesystem/path safety
- dangerous-rule stripping
- classifier auto-approval
- hook-based noninteractive path
- fail-closed fallback

The strongest transferable lesson is not the exact implementation.

It is the design style:

- sensitive decisions should flow through ordered gates

## Direct Analog For Our Analyzer

We need a similar ordered-gate evidence pipeline:

1. direct message-core evidence
2. relation-bound supporting evidence
3. weak proximity context
4. carrier/provenance metadata
5. fallback uncertainty

The current analyzer often flattens these into one blended confidence signal.
That is one of the reasons `forward` and other carrier features can dominate.

## Dangerous-Rule Stripping As A Design Pattern

Claude Code strips permission rules that would nullify auto-mode safety.

For us, the analogous step is:

- detect heuristics that would nullify `shi core` judgment

Examples:

- `forward-heavy shortcuts`
- `image-shell shortcuts`
- `reaction-density shortcuts`

If those heuristics are allowed to dominate, the analyzer can appear accurate while actually reasoning from the wrong layer.

## Headless / Noninteractive Paths

Claude Code distinguishes:

- interactive approvals
- hook-driven noninteractive paths
- fail-closed fallback

For our batch work this is relevant because we also need distinct paths for:

- headless smoke
- budget-limited deterministic runs
- reviewed runs
- full human-auditable runs

These should not silently blur into one another.

## Main Migration Lessons

1. planning should be a real mode
2. coordinator and workers should be separated
3. evidence should flow through a pipeline of trust classes
4. dangerous carrier heuristics should be stripped before confidence is claimed
5. batch/headless behavior should be explicit, not accidental
