# Shi CLI Draft

This document records the future CLI facade direction for shi analysis.

## Status

Draft only.

This is not part of the current implementation scope.

## Product language

User-facing REPL command language is expected to favor abstract slash commands:

- `/sniff`
- `/eatShit`
- reserve `/autopsy`

## Boundary

- exporter remains independent
- analysis core remains independent
- CLI is only a future orchestration facade
- internal handlers and schemas should remain formal and stable even if REPL command text is slang-heavy

## Current non-goals

- do not implement these commands in the current stage
- do not couple new CLI commands into exporter or analysis internals
