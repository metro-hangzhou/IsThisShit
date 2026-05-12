# Analysis Context Refresh

Spec date: 2026-03-27

## Purpose

This document refreshes the analyzer-side working memory after exporter stabilization, corpus expansion, and source restoration.

It is the current checkpoint for:

- corpus ingest
- preprocess
- deterministic analysis
- `Benshi` analysis
- report-first LLM analysis
- common-track retro-review

## Current Ground Truth

### Exporter is no longer the main blocker

The exporter side is now strong enough that analyzer work should proceed without waiting for a zero-missing corpus.

Analyzer work must preserve:

- direct evidence
- context-only inference
- unknown gaps

as separate classes.

### Analyzer source baseline already exists

Restored baseline now visible in the worktree:

- `src/qq_data_process/`
- `src/qq_data_analysis/`

This is not a greenfield analyzer project.

The correct strategy is:

- restore
- validate
- continue from the existing baseline

not:

- redesign from scratch

## Corpus Roles

### Central dense baseline

- `dev/testdata/local/shi_group_751365230/`

Current fixed role:

- `central_reference_baseline`
- `dense_shi_baseline`
- `manual_review_anchor`
- `deletion_guard = true`

This corpus must not be renamed, deleted, or silently cleaned up.

### Large sparse corpora

Newly copied corpora:

- `dev/testdata/local/amd_guanren_group_712742342/`
- `dev/testdata/local/amd_guanren_group_763328502/`
- `dev/testdata/local/x3c_group_757773326/`

Current rule:

- treat all three as:
  - `large_group_corpus = true`
  - `shi_density = sparse_but_nontrivial`
  - `role_assignment = pending_after_initial_analysis`

Do not freeze their final analyzer roles before deterministic and report-first calibration.

## What Is Already Implemented

### `qq_data_process`

Already present:

- exporter/QCE/TXT adapters
- canonical ingest
- preprocess view build/load
- preprocess profiles
- chunking policies
- SQLite + vector-side infrastructure

### `qq_data_analysis`

Already present:

- `AnalysisService`
- deterministic agents
- `BenshiAnalysisPack`
- `BenshiMasterAgent`
- whole-window LLM path
- preprocess overlay entry into analysis materials

### Local baseline verification

Current local status after restoration:

- corpus-directory import path now resolves `dev/testdata/local/<corpus>/export.jsonl`
- the central baseline also works through its canonical local-corpus JSONL shape
- local corpus registry and central-baseline guard are now present
- preprocess adapter/service smoke is passing locally
- restored analysis/Benshi/LLM smoke subset is also passing locally
- lightweight preprocess + deterministic analysis smoke has now completed on all four local corpora
- deterministic local-corpus smoke checkpoints now show:
  - `shi_group_751365230`: preprocess + analysis smoke succeeds
  - `amd_guanren_group_712742342`: preprocess + analysis smoke succeeds
  - `x3c_group_757773326`: preprocess + analysis smoke succeeds, but is materially slower
  - `amd_guanren_group_763328502`: current default smoke budget timed out before preprocess/analysis completed

## What Is Still Missing

### 1. Stable corpus ingest facade

We still need one explicit analyzer-facing entry path for local corpus directories, not just ad hoc `export.jsonl` path passing.

### 2. Full analyzer-phase retro-review

The common-track workflow was introduced late.

So previously written:

- analyzer code
- analyzer docs
- Benshi design
- local corpus review artifacts

must all be brought under the same reviewer model, not assumed approved by age.

### 3. Role calibration across the 3 large corpora

We still have not determined:

- which large corpus is best as primary positive
- which is best as control
- which is best as diversity supplement

This must come from initial deterministic and report-first analysis, not intuition alone.

### 4. Large-corpus runtime budget policy

The current local smoke results imply:

- not all large corpora should share the same first-pass runtime budget
- `763328502` likely needs either:
  - a larger smoke timeout
  - a lighter first-pass preprocess profile
  - or a staged ingest strategy

before it becomes the default first-pass corpus

## Immediate Next Milestone

The next actual milestone is:

- corpus ingest + preprocess + deterministic analysis

in this order:

1. compare the completed 4-corpus smoke outputs
2. calibrate roles for the 3 large corpora
3. add a stable corpus-ingest facade so analyzer entry is not ad hoc path passing
4. deepen preprocess overlays where the smoke results show clear payoff
5. only then deepen `Benshi` / report-first work on the newly registered corpora

## What Not To Start With

Do not start with:

- OCR
- full VLM
- rigid taxonomy
- GUI analysis UX
- fine-tuning
- RAG optimization before corpus ingest is stable
