# Exporter Evidence Shared Context

## Goal

Keep the exporter and simulator evidence model reviewer-auditable and reusable by downstream analyzer work.

## Current Facts

- exporter acquisition is no longer the only active development focus
- exporter evidence still remains the authoritative upstream state model for missing/media/materialization semantics
- legacy exporter tracks continue to use the exporter-specific output overlay

## Truth Sources

1. `NapCat_AGENTs.md` and child handbooks
2. exporter source under `src/qq_data_integrations/napcat/` and `src/qq_data_core/`
3. exporter regression tests
4. reviewer round artifacts

## Special Rule

Do not let analyzer-facing convenience erase exporter evidence distinctions such as:

- actionable vs background missing
- direct evidence vs context-only inference
- token/path/materialization provenance
