# Shi Analyzer Retro Review Scope

This file defines what must be re-reviewed under the common-track workflow because the generic reviewer / explorer / worker workbench arrived late.

## Must Re-review

- restored `src/qq_data_process/**`
- restored `src/qq_data_analysis/**`
- restored analyzer / preprocess tests
- `dev/testdata/local/shi_group_751365230/**`
- the 3 newly copied large-group corpora under `dev/testdata/local/`
- analysis / preprocess / Benshi / LLM md documents
- existing `Benshi` artifacts and manual-review anchors already stored under `dev/testdata/local/shi_group_751365230/`

## Goal

Do not assume:

- older code is implicitly approved
- older docs still match current code
- older corpus-role assumptions are still valid

The retro-review must answer:

1. what is already implemented
2. what is only directional documentation
3. which historical choices still hold
4. which historical choices need iteration before the analyzer moves deeper
