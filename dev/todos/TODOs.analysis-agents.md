# Analysis Agent TODOs

Spec baseline: 2026-03-08

This file tracks the target-driven analysis substrate and its pluggable analysis agents.

The current product shape is:

- user selects a group or friend
- user optionally selects a time range
- otherwise the system adapts a representative time window
- internal retrieval gathers evidence
- agents produce direct analysis outputs

This is not a query-first RAG UI.

Related phase note:

- first dedicated LLM work now lives in `TODOs.llm-analysis.md`
- this file remains focused on substrate and pluggable analysis agents rather than the report-first LLM iteration loop

## P0. Governance And Boundaries

- [x] Record that the repository now separates:
  - preprocessing/indexing substrate
  - analysis substrate
  - pluggable analysis agents
- [x] Record that `BenshiAgent` is not the system itself, but one future agent.
- [x] Record that the first delivery is:
  - `BaseStatsAgent`
  - `ContentCompositionAgent`
- [x] Record that image caption/OCR remains deferred.

## P1. Package Skeleton

- [ ] Create `src/qq_data_analysis/`.
- [ ] Add typed public models for:
  - `AnalysisTarget`
  - `AnalysisTimeScope`
  - `AnalysisJobConfig`
  - `AnalysisRunResult`
  - `AnalysisAgentOutput`
  - `AnalysisEvidenceItem`
- [ ] Add an `AnalysisAgent` interface with:
  - `agent_name`
  - `agent_version`
  - `prepare(...)`
  - `analyze(...)`
  - `serialize_result(...)`

## P2. Analysis Substrate

- [ ] Implement run/target resolution from preprocess state.
- [ ] Implement time-scope resolution:
  - manual range
  - auto-adaptive window
- [ ] Keep auto window selection explainable and replaceable.
- [ ] Record the chosen time window in analysis results.
- [ ] Keep all SQLite/Qdrant access inside substrate/service layers, not in agents.

## P3. Base Statistics Agent

- [ ] Implement `BaseStatsAgent`.
- [ ] Compute:
  - message count
  - sender count
  - time distribution
  - image ratio
  - forward ratio
  - reply ratio
  - low-information ratio
- [ ] Output:
  - human-readable overview
  - compact machine payload
  - evidence references when needed

## P4. Content Composition Agent

- [ ] Implement `ContentCompositionAgent`.
- [ ] Produce:
  - overall composition summary
  - seed-tag counts and open notes
  - candidate events
  - key participant profiles
  - evidence-backed findings
- [ ] Keep agent logic independent from a fixed chunking assumption.

## P5. Seed Tags And Feature Heuristics

- [ ] Add first-phase seed tags:
  - `forward_nested`
  - `forward_burst`
  - `image_heavy`
  - `emoji_heavy`
  - `low_information`
  - `topic_jump`
  - `reply_chain`
  - `repetitive_noise`
  - `absurd_or_bizarre`
  - `confusing_context`
- [ ] Explicitly support nested-forward depth and density as analyzable features.
- [ ] Keep tags extensible and allow open notes beyond fixed labels.
- [x] Promote `unsupported:16` multi-forward preview XML into first-class analyzable features instead of treating it as generic unsupported noise.
- [x] Extract forward-preview hints such as source label, preview speakers, preview text, image/video markers, and forwarded message count for later reference labeling.
- [ ] Start consuming normalized `forward/system/share` segments directly in analysis heuristics instead of relying mainly on raw `unsupported:*` token counts.

## P6. Internal Evidence Grounding

- [ ] Use RAG internally for:
  - candidate event evidence
  - key-person evidence
  - tag explanation support
- [ ] Do not expose a mandatory “preview hits first” UX step.
- [ ] Keep evidence retrieval configurable and replaceable.
- [ ] Leave context-builder strategy open for later tuning.

## P7. Output Format

- [ ] Keep dual outputs:
  - human report
  - compact machine output
- [ ] Use compact JSON rather than a custom delimited DSL.
- [ ] Add a local parser/expander from compact JSON to verbose JSON.
- [ ] Ensure findings carry evidence references.

## P8. LLM Guardrails

- [x] Keep LLM use optional and later-stage.
- [x] Default to alias identity in outputs.
- [x] Restrict first-stage inference to:
  - descriptive
  - behavioral
- [x] Do not emit high-confidence motivational judgments in V1.
- [x] Add a bounded LLM slice path:
  - choose one dense candidate-event slice
  - keep it to a few hundred messages
  - estimate prompt tokens before the request
  - persist actual API `usage` after the request
  - keep the secret config in `state/config/llm.local.json`
- [ ] Hand off whole-window bounded `analysis pack` generation to the dedicated LLM-analysis phase instead of growing ad hoc prompt logic inside generic agents.

## P9. Script-Level Tooling

- [x] Add a script entrypoint for running analysis jobs from a preprocess state directory.
- [ ] Support:
  - group/friend target selection
  - explicit or adaptive time scope
  - selecting one or more agents
  - writing human and compact outputs to disk
- [x] Add a separate script for direct DeepSeek-backed dense-slice analysis with:
  - local config file loading
  - console slice-plan display
  - token-budget display
  - usage logging in saved outputs

## P10. Tests

- [ ] Add doc routing tests for analysis TODO/doc visibility.
- [ ] Add a decoupling test that verifies `qq_data_analysis` does not import CLI/UI/NapCat modules.
- [ ] Add explicit time-range analysis tests.
- [ ] Add auto-adaptive window tests.
- [ ] Add nested-forward detection tests.
- [ ] Add alias-default-output tests.
- [ ] Add compact-JSON roundtrip tests.
- [ ] Add tests that `BaseStatsAgent` and `ContentCompositionAgent` can run independently.
- [x] Add tests for dense-slice LLM preparation and placeholder-key rejection.

## Deferred

- [ ] `BenshiAgent`
- [ ] richer people-image semantics
- [ ] OCR/caption-backed image analysis
- [ ] reranker-backed evidence refinement
- [ ] CLI/WebUI analysis commands
