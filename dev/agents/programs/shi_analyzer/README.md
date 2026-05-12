# Shi Analyzer Program

This program owns corpus ingest, preprocess, deterministic analysis, report-first benshi analysis, and analyzer-side redesign / retro-review.

Current milestone:

- corpus registration for 4 local corpora
- exporter JSONL + manifest importer compatibility
- preprocess smoke
- deterministic analysis smoke
- analyzer-side reviewer lane bootstrap
- Claude Code reference workbench for analyzer redesign
- message-first benshi analyzer redesign spec + first scaffolding
- Claude-Code-derived unified chat orchestrator runtime implementation-doc set

Current local corpora:

- `shi_group_751365230` as dense central reference baseline / manual-review anchor
- `amd_guanren_group_712742342` as sparse reviewed-calibration anchor corpus
- `amd_guanren_group_763328502` as sparse high-volume calibration corpus
- `x3c_group_757773326` as sparse daily-interaction diversity corpus

Current analyzer redesign direction:

- stop deepening the old `window-first + carrier-biased` analyzer
- move to:
  - `message_probe`
  - `relation_graph`
  - `message_packet`
  - `window_constructor`
  - `group_aggregation`
- keep context/token budget explicit from the start
- prefer prompt-based structured compact over RAG-style compact for analyzer continuity

Current orchestrator-design phase:

- do not jump straight to runtime code
- first land implementation-focused technical docs that are directly derived from:
  - local `claude-code/` source
  - local Claude Code analysis notes
- the new runtime target is:
  - `ChatOrchestratorEngine`
  - `MissionProfile`-driven missions
  - explicit context / lifecycle / mode / tool / analytics / artifact runtimes
- `shi_analysis` remains the first mission, but the runtime itself must stay open-ended and decoupled

Current implementation-doc set:

- `dev/reports/analysis/reference/methods/chat_orchestrator_runtime_overview.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_context_runtime.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_lifecycle_engine.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_mode_runtime.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_tool_runtime.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_analytics_runtime.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_mission_profiles.zh-CN.md`
- `dev/reports/analysis/reference/methods/chat_orchestrator_future_extension_surface.zh-CN.md`
