# Claude Code Reference Index

This directory stores the long-term, reusable Claude Code reference set.

It is meant to be:

- detailed
- decoupled
- reusable beyond the current `shi_analyzer` redesign

## Document Map

- [external_research.md](external_research.md)
  - external docs/community synthesis
- [architecture_overview.md](architecture_overview.md)
  - Claude Code system-level architecture summary
- [context_and_compaction.md](context_and_compaction.md)
  - context assembly, prompt compaction, token budgeting, session memory
- [planning_execution_permissions.md](planning_execution_permissions.md)
  - planning mode, coordinator mode, subagents, permissions, safety
- [file_index.md](file_index.md)
  - important file-by-file map for the local `claude-code/` snapshot
- [function_index.md](function_index.md)
  - important functions and their roles
- [migration_notes_for_shi_analyzer.md](migration_notes_for_shi_analyzer.md)
  - concrete migration guidance for the future message-first analyzer

## How To Use This Reference Set

1. read `external_research.md` for the high-level framing
2. read `architecture_overview.md`
3. branch into:
   - `context_and_compaction.md`
   - `planning_execution_permissions.md`
4. use `file_index.md` and `function_index.md` for source navigation
5. use `migration_notes_for_shi_analyzer.md` when designing local changes
