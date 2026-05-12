# Claude Code Reference Shared Context

## Goal

Build a reusable, indexed reference set for Claude Code that can inform:

- `shi_analyzer` retro-review
- message-first analyzer redesign
- future generic agent-system work

## Current Facts

- a local `claude-code/` source snapshot already exists in the repository root
- the current analyzer has already exposed structural issues:
  - `window-first` reasoning
  - `forward/carrier` bias
  - insufficient `message-first` `shi core` reasoning
- the user explicitly requested:
  - external research first
  - then local source reading
  - then detailed, decoupled md documentation

## Required Reading Order

1. official docs and cookbook
2. selected community reverse-engineering / long-form analysis
3. local `claude-code/` source snapshot
4. migration notes for local analyzer redesign

## Special Rule

This program is reference-first.

It should not silently mutate the analyzer implementation directly.

Its job is to produce a reusable knowledge base that makes the later analyzer redesign:

- more principled
- more decoupled
- more context-budget aware
