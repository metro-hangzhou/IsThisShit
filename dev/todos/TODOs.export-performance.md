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

## [2026-03-25] Post Terminal-Prefetch + Write-Bundle Split Pass

Latest live small-window perf probe after this pass:

- data:
  - `exports/group_922065597_20260325_160848_899209.jsonl`
- manifest:
  - `exports/group_922065597_20260325_160848_899209.manifest.json`
- trace:
  - `state/export_perf/cli_export_group_922065597_20260325_160845_533113_11840.jsonl`
- report:
  - `state/export_perf/cli_export_group_922065597_20260325_160845_533113_11840.report.json`
- result:
  - `records=300`
  - `elapsed=5.303s`
  - `actionable_missing=0`
  - `background_missing=21`

Compared with the immediately previous `300`-message baseline:

- total elapsed:
  - `6.302s -> 5.303s`
- `app.fetch_snapshot`:
  - `1.3094s -> 1.1673s`
- `provider.fast_tail_bulk`:
  - `1.2609s -> 1.1422s`
- `bundle.materialize_snapshot_media`:
  - `1.7185s -> 1.3757s`
- `app.write_bundle`:
  - `1.7342s -> 1.3943s`
- `image:copy_asset_file:status=done`:
  - `0.2078s -> 0.1577s`

This pass specifically added:

- downloader-side terminal request-state preclassification during `prepare_for_export(...)`
  - terminal top-level image/file/video/speech requests can now be marked before remote/public/context scheduling
  - repeated background-missing assets no longer consume prefetch slots
- stronger evidence-first terminal closeout for top-level `file/video`
  - blank / zero-byte public payloads no longer require old-bucket heuristics on top-level assets
- `bundle.write_data_file` is now a first-class perf stage
  - `app.write_bundle` is no longer a pure black box
- copy traces now include:
  - `copy_mode`
  - `copy_chunk_count`
  - `copy_buffer_bytes`
  - `copy_bytes_total`
- report-side `copy_io_breakdown` now includes `throughput_mib_s`

Current interpretation after this pass:

- correctness stayed clean:
  - `actionable_missing=0`
- the highest-value remaining fetch/page-scan work is now clearly plugin-side:
  - `provider.fast_tail_bulk = 1.1422s`
  - plugin breakdown shows `2` page calls and `549ms` native/plugin elapsed inside the route
- the highest-value remaining asset/materialize work is now concentrated in:
  - cross-volume `image` copy clusters
  - `bundle_future_local_identity_evidence` first-writer copies
  - residual placeholder / expired image classification volume

Next execution board:

- [ ] promote bundle-local "first writer wins" earlier so `bundle_future_local_identity_evidence` becomes reuse more often and copy less often
- [ ] memoize stale-neighbor directory probes more aggressively across repeated image families
- [ ] re-run live benchmarks after a real NapCat restart so plugin-side sorted-output / page-call changes are actually loaded
- [ ] compare `provider.fast_tail_bulk` pre/post restart on both `limit=300` and full-history windows
- [ ] split any remaining `app.write_bundle` tail cost if `bundle.finalize_output_files` or `bundle.write_manifest` grows again

## [2026-03-25] Post Instrumentation + Evidence-First Trim Pass

Latest live small-window perf probe after this pass:

- data:
  - `exports/group_922065597_20260325_145634_228439.jsonl`
- manifest:
  - `exports/group_922065597_20260325_145634_228439.manifest.json`
- trace:
  - `state/export_perf/cli_export_group_922065597_20260325_145630_378038_1936.jsonl`
- report:
  - `state/export_perf/cli_export_group_922065597_20260325_145630_378038_1936.report.json`
- result:
  - `records=300`
  - `elapsed=6.302s`
  - `actionable_missing=0`
  - `background_missing=21`

This pass specifically added:

- report-side `copy_io_breakdown`
  - same-volume vs cross-volume
  - byte totals
  - size buckets
- top-level image terminal classification before `context_hydration`
- tighter `second_pass_public_retry` gating when request-state evidence is already terminal
- `forward image` metadata-first terminal closeout before remote/public retries
- bounded buffered cross-volume asset copy
  - keep RAM bounded
  - prefer sequential disk writes
  - do not hold whole export assets in memory

Current interpretation after this pass:

- `actionable_missing=0` still holds on the latest live probe
- the remaining copy cost is now better measurable, and cross-volume copy is explicitly visible
- the remaining downloader waste is more concentrated in:
  - top-level stale-local `image`
  - terminal `file/video` negative chains
  - sparse `forward image` metadata probes

## [2026-03-25] Current Main Perf Snapshot After Fetch + Materialize Speedup Pass

Latest live full export used for this audit:

- data:
  - `exports/group_922065597_20260325_030622_196612.jsonl`
- manifest:
  - `exports/group_922065597_20260325_030622_196612.manifest.json`
- trace:
  - `state/export_perf/cli_export_group_922065597_20260325_030608_299742_55008.jsonl`
- report:
  - `state/export_perf/cli_export_group_922065597_20260325_030608_299742_55008.report.json`
- result:
  - `records=12593`
  - `elapsed=30.786s`
  - `actionable_missing=1154`
  - `background_missing=159`

Current broad-stage costs:

- `app.fetch_snapshot`: `11.4263s`
- `provider.fetch_snapshot_tail`: `11.4218s`
- `provider.fast_tail_bulk`: `8.825s`
- `provider.tail_forward_hydrate`: `0.2074s`
- `provider.finalize_snapshot`: `1.0127s`
- `bundle.materialize_snapshot_media`: `15.9658s`
- `app.write_bundle`: `16.1799s`

Current materialize hotspots:

- `image:copy_asset_file:status=done`
  - `710` copies
  - `1.9455s`
- `image:context_hydration:status=ok`
  - `21` calls
  - `0.7313s`
- `image:forward_context_metadata:status=ok`
  - `13` calls
  - `0.4988s`
- `image:unknown:status=copied:resolver=direct_local_path`
  - `477` assets
  - `3.2869s`
- `image:unknown:status=missing:resolver=missing_after_napcat`
  - `1205` assets
  - `2.4237s`
- `image:unknown:status=copied:resolver=stale_source_neighbor`
  - `157` assets
  - `1.1s`
- `image:unknown:status=copied:resolver=bundle_future_local_identity_evidence`
  - `76` assets
  - `0.5381s`

Current interpretation:

- fetch/page scanning is no longer the only dominant cost
- the current largest remaining surface is aggregate bundle/materialize work
- raw `copy_asset_file` is not the only issue:
  - cross-volume copy is real
  - stale-neighbor lookup is still repeated many times
  - future-local identity reuse still has a "first copy, later reuse" gap
- remaining probe cost is now concentrated in:
  - old top-level `image`
  - a handful of `file/video` negative terminal chains

### Important report caveats from the current audit

- top-level `pages_scanned` is still misleading for `history_full_bulk`
  - top-level report currently shows `0`
  - but `provider.fast_tail_bulk` and `history_page_breakdown` both show `65`
- `app.write_bundle` still wraps several different costs into one stage:
  - data-file write
  - bundle materialize
  - staged/final path swap
  - manifest write
- `provider.fast_tail_bulk` is still a plugin-side black box
  - current report does not expose plugin internal:
    - fetch rounds
    - anchor chase rounds
    - reply/reference parse counts
    - native/history API call counts

## [2026-03-24] Full-History Scan Route Was Still On The Old Per-Page Path Until This Pass

- user-side `@final_content @earliest_content` broad exports were still reporting:
  - `scanning full history pages=71 ... elapsed~=28s`
- root cause:
  - `fetch_full_snapshot()` had never been switched to fast bulk
  - only tail-oriented paths were using `/history-tail-bulk`
  - full-history broad exports were still doing `71` front-end page fetches through `_fetch_history_page(...)`
- this pass changes full-history to `fast_full_bulk` first, with per-page retry only as fallback
- direct maintainer live benchmark on group `922065597` after the change:
  - `messages=12593`
  - `pages_scanned=71`
  - `bulk_chunks=7`
  - `provider.fast_full_bulk = 9.1365s`
  - `provider.finalize_snapshot = 20.2898s`
  - `provider.fetch_full_snapshot = 29.4657s`
- interpretation:
  - full-history page scanning itself did drop materially:
    - from `~28s` broad front-end scan time
    - to `~9.1s` bulk fetch time
  - the new dominant cost inside `fetch_full_snapshot()` is now `provider.finalize_snapshot`
    - mainly forward/detail enrichment
    - not raw page acquisition

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
- [ ] add byte-level materialize/copy buckets by:
  - asset family
  - same-volume vs cross-volume
  - size bucket
  - source root kind
- [ ] identify top repeated cheap-but-high-volume substeps
- [ ] identify whether remote image resolution is now dominated by:
  - public-token remote URL probes
  - forward remote URL downloads
  - stale placeholder classification
- [ ] optimize the dominant repeated path first, not just the slowest single asset

### Track 5. Asset Copy / Bundle I/O Deep Dive

- [x] add `copy_io_breakdown` to perf report
- [x] record:
  - `source_drive`
  - `target_drive`
  - `same_volume`
  - `bytes_total`
  - size bucket
- [x] add bounded buffered cross-volume copy
  - prefer sequential disk writes
  - keep memory bounded instead of whole-file RAM caching
- [ ] validate on full export whether cross-volume buffered copy beats plain `copyfile`
- [ ] consider first-writer promotion for `bundle_future_local_identity_evidence`
- [ ] consider preallocated canonical rel-paths for same-identity asset groups

### Track 6. Old Image / File Probe-Cost Reduction

- [x] top-level image terminal evidence now runs before `context_hydration`
- [x] `second_pass_public_retry` now short-circuits on request-state terminal evidence
- [x] `forward image` metadata payload now classifies terminal missing before remote/public retry
- [ ] keep shrinking top-level stale-local image `context_hydration` count
- [ ] revisit top-level `file/video` blank direct-file-id payload classification against live traces
- [ ] verify the remaining `missing_after_napcat` samples are truly missing and not late-recoverable

### Track 7. Plugin-Side Fetch Telemetry And Page-Scan Reduction

- [ ] expose plugin route-level stats in report:
  - call count
  - total ms
  - avg ms
  - max ms
- [ ] evaluate plugin-side double-sort removal for bulk fetch
- [ ] evaluate slimmer full-bulk payload shape for full-history scanning
- [ ] split `full` vs `tail` fetch strategy instead of one global bulk strategy

### Track 5. Asset Copy / Bundle I/O Deep Dive

- [ ] split `app.write_bundle` into independent timed stages:
  - `bundle.write_data_file`
  - `bundle.replace_data_file`
  - `bundle.swap_assets_dir`
  - `bundle.write_manifest`
- [ ] add `write_data(...)` timing and bytes metadata:
  - `record_count`
  - `bytes_written`
  - `avg_bytes_per_record`
  - `jsonl_buffer_flush` cost
- [ ] add `copy_asset_file` report metadata:
  - `copied_bytes`
  - `source_drive`
  - `target_drive`
  - `same_volume`
  - `size_bucket`
- [ ] preallocate export target paths by stable asset identity in `media_bundle.py`
- [ ] promote same-identity first-writer reuse earlier so follower assets do not reach their own copy branch
- [ ] evaluate whether target-exists-and-size-match can skip duplicate copy work safely for repeated identities

### Track 6. Old Image / File Probe-Cost Reduction

- [ ] add evidence-first terminal closeout for `file/video` assets that already have:
  - no local path
  - negative `context_hydration`
  - negative `direct_file_id_get_file`
  - no live remote URL
- [ ] prevent those `file/video` assets from falling into `second_pass_public_retry` once terminal evidence already exists
- [ ] tighten `context_hydration` entry conditions for top-level stale-local `image`
  - especially `relative /gchatpic_new/...` with no live downloadable handle
- [ ] feed `forward_context_metadata` payload into terminal missing classification instead of treating it as advisory only
- [ ] break down `missing_after_napcat` into finer evidence families in the perf report:
  - `top_level_stale_local_no_live_remote`
  - `file_direct_id_negative`
  - `forward_metadata_no_live_remote`

### Track 7. Plugin-Side Fetch Telemetry And Page-Scan Reduction

- [ ] add plugin debug stats for `history_full_bulk`:
  - `plugin_fetch_rounds`
  - `anchor_chase_rounds`
  - `raw_message_count`
  - `reply_lookup_count`
  - `parse_reply_count`
  - `parse_forward_count`
  - `native_history_calls`
- [ ] fix report top-level `pages_scanned` so bulk/full-bulk values are reflected consistently
- [ ] continue reducing zero-yield `tail_forward_hydrate` windows after the current sparse-history pass
- [ ] compare next live run against the current `30.786s` snapshot after telemetry lands

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
