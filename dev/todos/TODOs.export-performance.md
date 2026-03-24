# Export Performance Audit TODOs

Spec baseline: 2026-03-24

This panel tracks exporter performance work separately from evidence-first correctness.

Primary rule:

- correctness gates still win first
- but once `actionable_missing=0` is back, performance work must be driven by measured stage cost, not guesswork

## Current Baselines

### Last known actionable-zero full-export baseline

- data:
  - `exports/group_922065597_20260324_011430_476759.jsonl`
- manifest:
  - `exports/group_922065597_20260324_011430_476759.manifest.json`
- trace:
  - `state/export_perf/cli_export_group_922065597_20260324_011320_022564_119740.jsonl`
- result:
  - `records=12593`
  - `actionable_missing=0`
  - `background_missing=1240`
  - `missing_breakdown=[qq_expired_after_napcat:1154, qq_not_downloaded_local_placeholder:86]`

### Regression/perf-audit full export used for stage breakdown

- data:
  - `exports/group_922065597_20260324_175228_915207.jsonl`
- manifest:
  - `exports/group_922065597_20260324_175228_915207.manifest.json`
- trace:
  - `state/export_perf/cli_export_group_922065597_20260324_175137_771039_36128.jsonl`
- report:
  - `state/export_perf/cli_export_group_922065597_20260324_175137_771039_36128.report.json`
- result:
  - `records=12593`
  - `elapsed=113.238s`
  - `actionable_missing=6`
  - `background_missing=1234`

## What The Current Perf Audit Already Shows

### Stage breakdown from the latest full-export report

- `app.write_bundle`: `61.281s`
- `bundle.materialize_snapshot_media`: `61.0207s`
- `app.fetch_snapshot`: `47.9287s`
- `provider.fetch_snapshot_tail`: `47.9247s`
- `provider.fast_tail_bulk`: `8.9044s`
- `provider.finalize_snapshot`: `3.5612s`

### Scan/fetch findings

- `tail_scan` total elapsed: `47.9247s`
- embedded `forward_hydrate_s`: `35.4273s`
- `bulk_chunks`: `7`
- `pages_scanned`: `71`

### Forward enrichment findings

- `forward_expand_summary` showed:
  - `total_forwards=36`
  - `processed_forwards=36`
  - `resolved_forwards=5`
  - `history_retry_calls=62`
  - `history_retry_hits=0`
  - `get_forward_msg_calls=31`
  - `get_forward_msg_hits=0`
- interpretation:
  - forward/history enrichment is currently expensive
  - the hit rate in that audited run was effectively zero
  - this is now a first-class perf target, not just a correctness curiosity

### Materialize findings from the latest report

- aggregate materialize time still dominates
- top individual materialize steps were no longer timeout-scale:
  - slowest recorded asset step in the report snapshot was `~458ms`
  - many top remote/placeholder image substeps were in the `60-170ms` range
- interpretation:
  - current materialize slowness is now more aggregate-volume driven than "one asset stalls for 20s"
  - the next optimization target should be route-plan batching and repeated cheap-but-many remote/image work

## Report Completeness Requirements

The original perf report was useful but incomplete for operator review.

New minimum report fields now required:

- `total_elapsed_s`
- `fetch_stage_breakdown`
- `history_page_breakdown`
  - must include fast-bulk `tail_scan` pages, not just explicit `history_page_done`
- `scan_phase_breakdown`
- `materialize_stage_breakdown`
- `materialize_asset_breakdown`

The intent is:

- fetch/page-scan costs are readable without hand-parsing raw trace JSONL
- materialize costs are split between:
  - per-substep cost
  - per-asset-family/result cost
  - top slow individual assets

## Execution Tracks

### Track 1. Report Completeness And Replay

- [x] add report-level `fetch_stage_breakdown`
- [x] add report-level `scan_phase_breakdown`
- [x] make `history_page_breakdown` include bulk `tail_scan` rows
- [ ] rerun one full live export with the improved report schema
- [ ] confirm the new report directly answers:
  - where fetch time went
  - where page-scan time went
  - where materialize time went

### Track 2. Forward Enrichment Cost Reduction

- [ ] quantify per-forward cost surface from the improved report/traces
- [ ] separate:
  - `forward_hydrate_s`
  - `history_retry_calls/hits`
  - `get_forward_msg_calls/hits`
- [x] add a fast-plugin exporter route for forward detail hydration so Python no longer has to rely on `history_retry + get_forward_msg` as the first broad-path enrichment route
- [ ] after a real NapCat restart, rerun one live export and compare:
  - `fast_plugin_calls/hits`
  - `history_retry_calls/hits`
  - `get_forward_msg_calls/hits`
  against the current full-export regression/perf baseline
- [ ] reduce work on zero-yield forward enrichment paths
- [ ] verify any reduction does not regress `forward_detail_count`

### Track 3. Materialize Aggregate Cost Reduction

- [ ] bucket materialize time by:
  - asset family
  - resolver
  - missing class
- [ ] identify top repeated cheap-but-high-volume substeps
- [ ] identify whether remote image resolution is now dominated by:
  - public-token remote URL probes
  - forward remote URL downloads
  - stale placeholder classification
- [ ] optimize the dominant repeated path first, not just the slowest single asset

### Track 4. Baseline Comparison Guard

- [x] compare the latest 13000 full export against the last actionable-zero baseline
- [x] record the regression shape in evidence-first TODOs
- [ ] once performance work is done, rerun the same 13000 full export and compare against both:
  - actionable-zero baseline
  - regression/perf-audit run
- [ ] release gate:
  - no correctness regression
  - no unexplained benchmark regression

## Required Artifacts For The Next Full Validation

- full export JSONL
- full export manifest
- raw trace JSONL
- report JSON
- one short written comparison against:
  - last actionable-zero baseline
  - latest performance-audit regression run

## Exit Criteria

- improved report schema is exercised by a real full export
- fetch/page-scan/materialize costs are readable directly from the report
- next broad run keeps `actionable_missing=0`
- at least one of the two big cost surfaces is materially reduced:
  - fetch/page-scan
  - materialize aggregate
