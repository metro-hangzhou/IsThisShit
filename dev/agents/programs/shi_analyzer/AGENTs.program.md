# Shi Analyzer Program

## Purpose

This program owns:

- corpus ingest
- preprocess
- deterministic analysis
- analysis pack generation
- report-first `Benshi` / `shi` analysis

## Default Output Structure

1. `Facts`
2. `Interfaces / Data Contracts`
3. `Already Implemented`
4. `Gaps / Risks`
5. `Proposed Changes`
6. `Concrete File Refs`

## Truth Sources

1. `AGENTS.md`
2. `dev/agents/major_AGENTs.md`
3. `dev/agents/process_AGENTs.md`
4. `dev/agents/llm_AGENTs.md`
5. `dev/agents/Benshi_AGENTs.md`
6. analysis/preprocess TODO docs
7. local corpora under `dev/testdata/local/`
