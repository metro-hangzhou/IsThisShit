# Claude Code Reference Program

## Purpose

This program owns:

- external Claude Code research synthesis
- local Claude Code source reading
- Claude Code architecture decomposition
- migration guidance for future analyzer redesign

## Default Output Structure

1. `Facts`
2. `Mechanisms`
3. `What Is Reusable`
4. `What Should Not Be Copied Blindly`
5. `Migration Notes`
6. `Concrete File Refs`

## Truth Sources

1. `AGENTS.md`
2. `dev/agents/programs/common_track_workflow/**`
3. official Claude Code docs
4. official Anthropic context-engineering cookbook/docs
5. local `claude-code/` source snapshot
6. long-form reference docs under `dev/reports/analysis/reference/claude_code/`

## Non-Negotiable Rules

- External articles are supporting evidence, not final truth.
- Official docs and local source outrank community reverse-engineering.
- Migration notes must distinguish:
  - reusable mechanism
  - implementation detail
  - speculative interpretation
- Do not collapse Claude Code architecture notes directly into `shi_analyzer` TODOs without explicit migration reasoning.
- Context/compact conclusions must stay token-budget aware and message-packet aware.
