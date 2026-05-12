# Claude Code Reference Program

This program owns the reference-first study of Claude Code as an agent-system design benchmark.

It exists to support the `shi_analyzer` common-track retro-review and the planned move from a `window-first` analyzer to a `message-first` analyzer.

## Current Scope

- external Claude Code article/community/doc synthesis
- local Claude Code source reading
- reusable architecture notes
- migration notes for the local `shi_analyzer`

## Primary Outputs

- temporary external-research notebook:
  - [AGENT.md](AGENT.md)
- program contract:
  - [AGENTs.program.md](AGENTs.program.md)
- shared context:
  - [SHARED_CONTEXT.md](SHARED_CONTEXT.md)
- detailed long-term reference set:
  - [../../../reports/analysis/reference/claude_code/README.md](../../../reports/analysis/reference/claude_code/README.md)

## Why This Program Exists

The current analyzer has already shown a structural problem:

- too much `window-first`
- too much `carrier/provenance` bias
- not enough `shi core` / `message-first` reasoning

Before rewriting that analyzer, we want a stable reference set for:

- context management
- prompt-based compaction
- planning/execution mode separation
- subagent coordination
- permission/safety pipelines

Claude Code is not being copied wholesale. It is being used as a high-signal reference system for architecture study.
