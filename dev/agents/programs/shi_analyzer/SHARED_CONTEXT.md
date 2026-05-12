# Shi Analyzer Shared Context

## Goal

Build a report-first, uncertainty-preserving analyzer that can ingest exported QQ corpora, preprocess them into reusable views, and run deterministic plus benshi-oriented analysis without re-coupling to exporter internals.

## Current Facts

- `src/qq_data_process/` and `src/qq_data_analysis/` already exist and must be treated as the true baseline
- `shi_group_751365230` is the dense central reference baseline and manual-review anchor
- the three newly copied large-group corpora are intentionally left as pending-role-assignment inputs until initial analysis calibration is complete
- current active phase is importer + preprocess + deterministic analysis, not final benshi taxonomy convergence

## Truth Sources

1. `dev/agents/process_AGENTs.md`
2. `dev/agents/llm_AGENTs.md`
3. `dev/agents/Benshi_AGENTs.md`
4. analyzer and preprocess source under `src/qq_data_process/` and `src/qq_data_analysis/`
5. analyzer/preprocess tests
6. local corpora and reviewer artifacts

## Non-Goals Right Now

- OCR
- full VLM/image reasoning
- rigid final taxonomy
- GUI/CLI analysis frontend
- preemptive large-group role assignment before initial calibration
