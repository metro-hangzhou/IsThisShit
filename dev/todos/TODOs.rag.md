# RAG TODOs

Spec baseline: 2026-03-08

This file tracks the retrieval and generation layer built on top of the preprocessing state.

Current product note:

- retrieval and generation are now primarily internal evidence services for analysis agents
- they are no longer planned as the default user-facing, query-first product shape
- the first dedicated LLM phase is report-first and whole-window-pack-based; RAG remains an internal evidence source, not the public product surface

## P0. Retrieval Contracts

- [x] Introduce retrieval-specific typed models:
  - `RetrievalConfig`
  - `RetrievedMessageHit`
  - `ContextBlock`
  - `RetrievalResult`
- [x] Keep retrieval and generation in `qq_data_process`, not in CLI code.
- [x] Make raw-identity retrieval require an explicit dangerous flag.
- [ ] Add analysis-oriented evidence contracts so agents can consume retrieval results without binding to RAG internals.

## P1. Embedding Runtime

- [x] Split document indexing embeddings from query embeddings.
- [x] Use `jinaai/jina-embeddings-v4` as the production embedding target.
- [x] Keep a deterministic provider for tests and offline-safe CI.
- [x] Route external model downloads through the local proxy and keep HF cache inside repository state paths.
- [x] Run a full live Jina v4 embedding validation against a real local state dir.
- [ ] Record GPU/CPU recommendations and local cache expectations.

## P2. Keyword + Vector Retrieval

- [x] Add SQLite FTS5 keyword search.
- [x] Add local vector search reader.
- [x] Add Reciprocal Rank Fusion for keyword/vector result merging.
- [x] Scope retrieval by:
  - run ID
  - chat raw ID
  - chat alias ID
  - timestamp interval
- [ ] Add retrieval over image assets once image semantics are no longer placeholder-only.

## P3. Context Building

- [x] Build context blocks from chunk memberships when available.
- [x] Fall back to local message windows when chunks are absent.
- [x] Keep chunk context optional and bounded.
- [ ] Add chunk-set selection when multiple chunk policies coexist in one state dir.
- [ ] Add chunk-aware deduplication and block compression for longer retrieval sessions.

## P4. Generation

- [x] Add a script-safe DeepSeek generator wrapper.
- [x] Keep DeepSeek model config at:
  - model: `deepseek-reasoner`
  - base URL: `https://api.deepseek.com`
  - env key: `DEEPSEEK_API_KEY`
- [x] Allow retrieval-only operation with no LLM call.
- [ ] Design a grounded answer schema with explicit evidence citation formatting.
- [ ] Add refusal/insufficient-evidence normalization.

## P5. Tooling

- [x] Add `scripts/run_rag_query.py`.
- [x] Let retrieval infer the latest run scope by default.
- [ ] Add a script for listing available runs and embedding policies.
- [ ] Add a script for rebuilding only vector indexes from an existing SQLite state.
- [ ] Add a dedicated SSD-targeted vector-index build path for large local states.

## P6. Quality And Evaluation

- [x] Add retrieval regression tests over local fixtures.
- [ ] Add fixture-driven precision sanity checks for:
  - exact keyword lookup
  - paraphrase-like retrieval
  - alias/raw projection correctness
- [ ] Add retrieval timing benchmarks on larger exported chat histories.
- [ ] Benchmark contiguous local vector store against prior Qdrant-based runs on HDD-backed states.
- [ ] Add error-path tests for missing Jina weights / missing DeepSeek API key.

## Deferred

- [ ] reranker implementation
- [ ] hybrid sparse+dense weighting tuning beyond simple RRF
- [ ] OCR/caption-backed image retrieval
- [ ] conversational memory / multi-turn RAG orchestration
- [ ] CLI query commands
- [ ] GUI analyzer integration
