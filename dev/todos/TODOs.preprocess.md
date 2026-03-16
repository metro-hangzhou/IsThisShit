# Preprocess TODOs

Spec baseline: 2026-03-08

This file tracks the preprocessing subsystem that begins after chat export.

See also: `TODOs.rag.md` for the retrieval/generation layer that now sits on top of preprocessing.

## P0. Governance And Contracts

- [x] Create `major_AGENTs.md`.
- [x] Create `process_AGENTs.md`.
- [x] Add a preprocess entry link to `TODOs.md`.
- [x] Add repository-visible references to preprocessing docs from `AGENTS.md`.
- [x] Lock the current preprocessing phase boundary:
  - offline ingest and indexing only
  - no OCR/caption in the preprocessing path
  - reserved DeepSeek config without embedding any provider-specific coupling into ingest

## P1. Package Skeleton

- [x] Create `src/qq_data_process/`.
- [x] Add typed public interfaces for:
  - `ImportSource`
  - `PreprocessJobConfig`
  - `CanonicalMessageRecord`
  - `ChunkPolicy`
  - `EmbeddingPolicy`
  - `IdentityProjectionPolicy`
  - `PreprocessRunResult`
- [x] Keep `qq_data_process` free of CLI imports and terminal UI dependencies.

## P2. Input Adapters

- [x] Implement `ExporterJsonlAdapter`.
- [x] Implement `QceJsonAdapter`.
- [x] Implement `TxtTranscriptAdapter`.
- [x] Mark input fidelity as:
  - `high`
  - `compat`
  - `lossy`
- [x] Normalize all inputs into one canonical message layer before persistence.

## P3. Canonical Storage

- [x] Create a SQLite schema for:
  - import runs
  - chats
  - participants raw
  - participants alias
  - messages
  - message assets
  - chunk sets
  - chunks
  - chunk memberships
  - artifacts
- [x] Store chunk metadata separately from message truth.
- [x] Persist provenance and fidelity for every imported run.
- [x] Add SQLite FTS5 over message content/text content for keyword retrieval.

## P4. Chunk Policies

- [x] Define `ChunkPolicy`.
- [x] Implement `NoChunkPolicy`.
- [x] Implement `WindowChunkPolicy`.
- [x] Implement `TimeGapChunkPolicy`.
- [x] Implement `HybridChunkPolicy`.
- [x] Persist:
  - `chunk_policy_name`
  - `chunk_policy_version`
  - `chunk_policy_params`
- [x] Ensure downstream code can operate when no chunks exist.

## P5. Embeddings And Image Features

- [x] Define embedding provider interfaces.
- [x] Reserve `jinaai/jina-embeddings-v4` as the target production embedding configuration.
- [x] Add a lightweight development/test embedding provider.
- [x] Add a real Jina v4 runtime provider behind lazy loading and policy config.
- [x] Create local vector collections:
  - `text_units`
  - `image_assets`
- [x] Implement first-phase image handling:
  - keep references
  - build image vectors
  - mark future multimodal parse as deferred
- [x] Add embedding-space compatibility checks so one state dir cannot silently mix vector spaces.

## P6. Identity Projection

- [x] Implement raw identity storage.
- [x] Implement globally stable alias mapping.
- [x] Default outward projections to alias.
- [x] Add `danger_allow_raw_identity_output`.
- [x] Ensure the dangerous option is core-policy-based, not CLI-only.

## P7. Service Layer

- [x] Implement `PreprocessService.run(...)`.
- [x] Return a `PreprocessRunResult` with:
  - run ID
  - source type
  - fidelity
  - sqlite path
  - qdrant location
  - message count
  - asset count
  - chunk set count
  - warnings
- [x] Keep the service callable by future CLI, GUI, and analyzer code without adapter-specific coupling.
- [x] Add a script-level entrypoint for running preprocess jobs without any terminal UI dependency.

## P8. Test Coverage

- [x] Add doc existence and basic contract tests.
- [x] Add JSONL import tests.
- [x] Add QCE JSON import tests.
- [x] Add TXT import tests.
- [x] Add chunk-policy tests.
- [x] Add alias stability tests.
- [x] Add dangerous raw-output gating tests.
- [x] Add text/image vector indexing tests.
- [x] Add a decoupling test that verifies `qq_data_process` does not import `qq_data_cli`.

## Deferred

- [ ] OCR execution
- [ ] caption generation
- [ ] multimodal image understanding
- [ ] image semantic backfill into the local vector store
- [ ] reranker model choice
- [ ] GUI/CLI adapters for preprocessing and retrieval
