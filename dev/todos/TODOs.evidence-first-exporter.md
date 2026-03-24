# Evidence-First Exporter TODOs

Spec baseline: 2026-03-23

This file tracks the remaining exporter logic that still makes control-flow decisions from heuristics or coarse proxies instead of direct terminal evidence.

Goal:

- make `missing` classification evidence-first
- make route ordering evidence-first
- make skip/breaker/cache scope evidence-first
- reduce long-running exports caused by proxy-based decisions that keep expensive routes alive after terminal evidence already exists

## Current Main Panel

This file is now the primary execution panel for the evidence-first exporter pass.

The turn-level contract is:

1. remove remaining correctness-impacting proxy decisions
2. extend simulator coverage for the removed proxy families
3. run simulator/regression checks
4. when residual actionable/missing count is small, run targeted window retests first and only escalate to full live export if those narrow windows are clean or if broad benchmark validation is still needed
5. run a full live export on group `922065597` only after the targeted retests above have converged, or when verifying that a broad-path change did not regress benchmark/runtime behavior
6. only call the turn complete when `actionable_missing=0` and benchmark has not materially regressed

Targeted-first validation rule:

- if a new regression narrows down to a handful of `missing_after_napcat` assets or 1-2 retry windows, do not jump straight to another full export
- first retest those exact windows and fix the concrete evidence gap there
- only after the targeted windows are clean should we pay the cost of a full-group validation run

## Current Audit Snapshot

The latest strict audit found the remaining non-evidence decisions concentrated in four areas:

- `media_downloader.py`
  - month-bucket old-context skip
  - resolver-string-driven shared missing cache
  - timeout/breaker scopes that still mix retry suppression with terminal classification
  - topology/shape-first route ordering on some forward `video/file/speech` paths
- `media_bundle.py`
  - second-pass retry gating still partially keyed by asset family/result label instead of retry evidence
  - recent identity reuse was too weak/image-specific
- `provider.py`
  - source-based skip of parse-mult hydration
  - global “three strikes” disablement for forward/history enrichment
  - single-message fallback without positive identity proof
- `asset_simulator.py`
  - missing first-class matrices for targeted forward metadata payloads
  - missing multi-step slow-success / useless-success forward-expense coverage

## [2026-03-23] Completed In This Pass

- `media_bundle.py`
  - second-pass public retry gating is now evidence-first rather than image/result-label gated
  - recent identity reuse is no longer image-only and now keys off:
    - public token
    - direct `file_id`
    - normalized `remote_url`
    - `md5 + preferred_name`
- `provider.py`
  - removed source-based skip of parse-mult hydration for fast-history snapshots
  - removed global “three strikes” disablement for forward/history enrichment
  - removed blind single-message fallback without positive identity proof
- full live export validation on group `922065597`
  - `records=12593`
  - `elapsed=111.664s`
  - `history_source=napcat_fast_history_bulk`
  - `actionable_missing=0`
  - `background_missing=1207`
  - `final_missing_reason=[qq_expired_after_napcat:1204, qq_not_downloaded_local_placeholder:3]`
- remote URL recovery is no longer coupled to async prefetch runtime startup
  - if a valid live remote URL exists, downloader now has a synchronous fallback path when remote prefetch runtime is unavailable
  - targeted retest against the residual `2025-12-14` and `2026-01-10` windows now lands at:
    - `cluster_1: actionable_missing=0`
    - `cluster_2: actionable_missing=0`
- `forward image` slow-step instrumentation and ordering
  - substep trace now records:
    - `timestamp_iso`
    - `md5`
    - `source_path/source_path_kind`
    - `hint_url_kind/hint_url_host`
    - `attempt_url/attempt_url_kind/attempt_url_host`
    - `resolved_size_bytes`
  - `targeted_missing_retest.py` now also emits full progress/substep trace into `state/export_perf`
  - for forward `image` assets with:
    - live HTTP hint present
    - direct `forward_remote_url` already failed in-process
    - no public-token/file-id recovery handle
    - no hydrated local path yet
    downloader now prefers `forward_context_materialize` before metadata-only hydration
  - live narrow-window retest on `2025-12-14_19-10-26 .. 19-10-56` confirmed:
    - previous bad sample `3BE10FA97950F66D11876F8E815A763C.gif`
    - old path: `~33.6s`
    - new path: `~21.5s`
    - metadata timeout stage removed; remaining cost is the real NapCat-side materialize itself

## [2026-03-24] Latest Evidence-First Validation

- targeted manifest retest against:
  - `D:\Coding_Project\gittest20260316_t1\IsThisShit\exports\group_922065597_20260323_153041_110212.manifest.json`
- result:
  - `cluster_1 (2025-12-14_19-10-26 .. 19-10-56): actionable_missing=0, background_missing=3`
  - `cluster_2 (2026-01-10_16-54-39 .. 16-55-09): actionable_missing=0, background_missing=4`
- current evidence-first rule clarified during this pass:
  - `unsupported projected localhost download + no local file` is not terminal by itself
  - terminal image/background classification requires a complete proof chain such as:
    - original remote already expired or otherwise terminal
    - projected localhost download unsupported
    - no local file / no hydrated local path
    - no remaining public/file-id/live-remote recovery handle
- full live export on group `922065597` after the targeted retest convergence now lands at:
  - `records=12593`
  - `elapsed=109.587s`
  - `history_source=napcat_fast_history_bulk`
  - `actionable_missing=0`
  - `background_missing=1240`
  - `final_missing_reason=[qq_expired_after_napcat:1154, qq_not_downloaded_local_placeholder:86]`
- the former `2948/3150` stall signature is no longer a real slow asset path on the maintainer runtime:
  - sampled asset `BE6DFDF9BF0B50989E54D22DE5AE2E55.png`
  - final classification: `qq_not_downloaded_local_placeholder`
  - full asset step cost: `66ms`
  - `public_token_get_image`: `8ms`
  - `public_token_get_image_remote_url`: `51ms error`
- current full-trace maxima on the maintainer runtime:
  - slowest `materialize_assets` step: `0.765s`
  - slowest `materialize_asset_substep`: `context_hydration(video)=0.614s`
  - no `media_resolution_substep` timeout events remain in the full trace

## [2026-03-24] Regression Comparison: current actionable=6 vs last actionable=0 baseline

- last actionable-zero full-export baseline:
  - data:
    - `exports/group_922065597_20260324_011430_476759.jsonl`
  - manifest:
    - `exports/group_922065597_20260324_011430_476759.manifest.json`
  - trace:
    - `state/export_perf/cli_export_group_922065597_20260324_011320_022564_119740.jsonl`
  - baseline result:
    - `actionable_missing=0`
    - `background_missing=1240`
    - `final_missing_reason=[qq_expired_after_napcat:1154, qq_not_downloaded_local_placeholder:86]`

- current regressed full export:
  - data:
    - `exports/group_922065597_20260324_175228_915207.jsonl`
  - manifest:
    - `exports/group_922065597_20260324_175228_915207.manifest.json`
  - trace/report:
    - `state/export_perf/cli_export_group_922065597_20260324_175137_771039_36128.jsonl`
    - `state/export_perf/cli_export_group_922065597_20260324_175137_771039_36128.report.json`
  - regressed result:
    - `actionable_missing=6`
    - `background_missing=1234`
    - `final_missing_reason=[missing_after_napcat:6, qq_expired_after_napcat:1157, qq_not_downloaded_local_placeholder:77]`

- currently known diff:
  - all `6` newly actionable assets are top-level `image`
  - all `6` previously resolved to:
    - `qq_not_downloaded_local_placeholder`
  - all `6` now resolve to:
    - `missing_after_napcat`
  - all `6` share the same evidence shape:
    - stale/placeholder local path
    - direct `file_id`
    - relative `/gchatpic_new/...` hint URL
    - successful `public_token_get_image`
    - failed `public_token_get_image_remote_url`

- regression triage checklist:
  - [ ] diff `final_missing_reason` against the last actionable-zero baseline
  - [ ] diff `actionable_missing_reason` / newly reintroduced actionable assets only
  - [ ] diff retry-window count and exact windows when present
  - [ ] diff `history_source`
  - [ ] diff `forward_detail_count`
  - [ ] diff `prefetch_chunks / prefetch_timeout_count`
  - [ ] diff top slow stages
  - [ ] diff top slow asset substeps
  - [ ] explain whether the regression is:
    - route-plan drift
    - terminal-classification drift
    - instrumentation-only side effect

- required output for future full-export regressions:
  - [ ] `newly regressed assets only`
  - [ ] `same assets but slower route plan`
  - [ ] `same result but observability-only change` verdict

## [2026-03-24] New Regression To Eliminate Before Next Broad Validation

- latest full export regression artifact:
  - trace: `D:\Coding_Project\IsThisShit\state\export_perf\cli_export_group_922065597_20260324_175137_771039_36128.jsonl`
  - report: `D:\Coding_Project\IsThisShit\state\export_perf\cli_export_group_922065597_20260324_175137_771039_36128.report.json`
  - manifest: `D:\Coding_Project\IsThisShit\exports\group_922065597_20260324_175228_915207.manifest.json`
- baseline zero-actionable references that this regression must be compared against:
  - `D:\Coding_Project\IsThisShit\state\export_perf\cli_export_group_922065597_20260323_034139_599938_98080.jsonl`
  - `D:\Coding_Project\IsThisShit\state\export_perf\cli_export_group_922065597_20260323_044222_445135_101008.jsonl`
  - `D:\Coding_Project\gittest20260316_t1\IsThisShit\exports\group_922065597_20260323_153041_110212.manifest.json`
- regression signature:
  - baseline: `records=12593`, `actionable_missing=0`
  - latest: `records=12593`, `actionable_missing=6`, `background_missing=1234`
  - latest new retry windows:
    - `2025-12-08_14-06-41 .. 14-07-11`
    - `2025-12-14_22-16-54 .. 22-17-24`
    - `2025-12-17_20-04-24 .. 20-04-54`
    - `2026-01-05_21-00-34 .. 21-01-04`
    - `2026-01-06_09-33-09 .. 09-33-39`
    - `2026-01-15_14-50-01 .. 14-50-31`
- shared evidence shape across all 6 latest actionable misses:
  - top-level `image`
  - stale local `source_path`
  - direct `file_id`/public-token handle exists
  - `context_hydration` ran and still produced no resolved local path
  - `public_token_get_image` succeeded but only yielded remote URL
  - `public_token_get_image_remote_url` then failed on the public remote URL
  - final classifier still returned `missing_after_napcat`
- working hypothesis:
  - `public-token image` classification still contains a residual proxy/age gate
  - evidence is already sufficient to classify terminally, but `_classify_missing_from_public_payload(...)` is still guarded by `old_bucket/expired_candidate` in a way that recent top-level images do not cross
- required fix:
  - remove the residual age gate from top-level image terminal classification in the public-token path
  - classifier must use the complete evidence chain directly:
    - no resolved local path
    - no unexhausted live remote URL
    - stale/zero local hint or other broken local evidence
    - public-token route exhausted
    - authoritative remote failure evidence from the public remote URL when available
- validation rule for this regression:
  - do not rerun full export first
  - first add unit/simulator coverage for this exact top-level image public-token failure shape
  - then run targeted retests for the 6 new retry windows
  - only when those windows return `actionable_missing=0` should broad full-export validation be paid again

## [2026-03-24] Latest Perf Probe After Report/Provider Hardening

- fresh live validation slice:
  - command: `app.py export-history group 922065597 --limit 300 --format jsonl`
  - data:
    - `exports/group_922065597_20260324_194615_379684.jsonl`
  - manifest:
    - `exports/group_922065597_20260324_194615_379684.manifest.json`
  - trace/report:
    - `state/export_perf/cli_export_group_922065597_20260324_194611_882045_41096.jsonl`
    - `state/export_perf/cli_export_group_922065597_20260324_194611_882045_41096.report.json`
- current probe result:
  - `records=300`
  - `elapsed=7.856s`
  - `history_source=napcat_fast_history_bulk`
  - `actionable_missing=0`
  - `background_missing=14`
  - `final_missing_reason=[qq_not_downloaded_local_placeholder:14]`
- report contract outcome:
  - `history_page_breakdown` is now non-empty and no longer double-counts `tail_scan` summary rows
  - `tail_bulk_chunk_breakdown` is now non-empty
  - `tail_forward_hydrate_windows` is now non-empty and now carries:
    - window message count
    - forward ref count
    - hydrated count
    - oldest/newest message ids

## [2026-03-24] Post-Restart Forward-Image Regression Was A Route-Ordering Bug, Not A New Fetch/Page Problem

- after a real NapCat restart and plugin refresh, the next live `limit=300` probe regressed badly:
  - old report:
    - `state/export_perf/cli_export_group_922065597_20260324_211731_189427_48916.report.json`
  - result:
    - `records=300`
    - `elapsed=92.606s`
    - `history_source=napcat_fast_history_bulk`
    - `actionable_missing=0`
    - `bundle.materialize_snapshot_media ~= 87.301s`
    - `slowest_materialize_step_s ~= 12.103s`
- root cause was not bulk page scanning or tail fetch itself:
  - forward `image` route ordering still allowed repeated `public_token_get_image` timeout work to survive even after forward metadata/local evidence had already proved there was no usable local recovery
  - the same failure shape could reappear through both:
    - `_resolve_from_forward_payload_candidate(...)`
    - `_pick_forward_asset_match(...)`
- the route plan is now tightened so that:
  - forward-image terminal classification runs before public-token retry once forward metadata/local evidence already proves the asset is dead
  - after a public-token remote-url attempt fails, downloader re-runs evidence-first missing classification immediately instead of drifting back to `missing_after_napcat`
- live probe after the fix:
  - new report:
    - `state/export_perf/cli_export_group_922065597_20260324_215702_598580_49144.report.json`
  - result:
    - `records=300`
    - `elapsed=8.734s`
    - `history_source=napcat_fast_history_bulk`
    - `actionable_missing=0`
    - `background_missing=21`
    - `bundle.materialize_snapshot_media ~= 3.321s`
    - `slowest_materialize_step_s ~= 0.315s`
- observed effect on the previously bad forward-image family:
  - no `public_token_get_image timeout` chain remains
  - `forward_remote_url:error` is now `~7-10ms`
  - `forward_context_metadata:ok` is now `~20-51ms`
  - final outcome is terminal background classification instead of a 12s timeout loop
- next hotspot interpretation after this fix:
  - fetch-side bulk/page work is no longer masked by forward-image storms
  - the current visible tops on the same `300`-message slice are now:
    - `app.fetch_snapshot ~= 1.607s`
    - `provider.fast_tail_bulk ~= 1.557s`
    - `bundle.materialize_snapshot_media ~= 3.321s`
    - `app.write_bundle ~= 3.355s`
    - oldest/newest seqs
    - oldest/newest timestamps
  - `materialize_stage_breakdown` and `materialize_asset_breakdown` are non-empty
- current measured hotspot order from this probe:
  - `public_token_get_image_remote_url:error`
    - `16` calls
    - `1.0048s` total
  - `forward_remote_url:ok`
    - `7` calls
    - `0.8197s` total
  - first sparse forward-hydrate window:
    - `200` messages
    - `1` forward ref
    - `1` hydrated
    - `0.4453s`
- current interpretation:
  - local copy/finalize I/O is no longer the top next optimization target on the maintainer runtime
  - remaining ROI is concentrated in:
    - top-level image public-token remote-failure path
    - sparse forward-hydrate overfetch
    - baseline-vs-current report completeness/diff automation

## Remaining Non-Evidence Decisions After This Pass

The main remaining non-evidence control-flow is now concentrated in downloader route planning and pool shaping:

- placeholder classification still partly uses path-shape proxy before enough authoritative failure proof is assembled
- timeout/breaker/cache scope still carries legacy bucket-style memory in some code paths
- forward route ordering still uses topology/shape hints more than explicit recoverability proof on some branches
- prefetch pool/batch shaping still keys mainly off request volume rather than actionable unresolved composition

## Exit Criteria

- evidence-first matrices green
- no new simulator mismatch or cost overrun
- release-focused regression green
- full live export on group `922065597` completes with:
  - `actionable_missing=0`
  - stable `history_source`
  - no material benchmark regression vs current baseline

### Release Gate: correctness baseline

- do not sync release lines if the latest full export on `922065597` regresses from the last actionable-zero baseline
- `actionable_missing=0` is a hard gate
- if the gate is violated:
  - targeted retests must converge first
  - only then is another full export considered authoritative

## Track 7. Export Perf Report Contract

- [x] persist `total_elapsed_s` alongside `elapsed_s` for stable report consumers
- [x] emit non-empty `history_page_breakdown` for fast-bulk tail fetches via synthetic chunk-backed page rows
- [x] emit explicit:
  - `materialize_stage_breakdown`
  - `materialize_asset_breakdown`
- [ ] define required sections for every full-export performance report:
  - fetch stage breakdown
  - page/chunk breakdown
  - forward expand breakdown
  - materialize stage breakdown
  - top slow assets
  - top slow substeps
- [ ] fail validation if a covered stage produces an unexpectedly empty report section

## Track 8. Phase Metadata Normalization

- [x] extend materialize report schema so grouped rows keep:
  - `asset_type`
  - `asset_role`
  - `status`
  - `resolver`
  - `missing_kind`
  - `substep`
- [x] instrument local materialization internals with per-substep timing for:
  - `allocate_export_path`
  - `ensure_export_parent`
  - `copy_asset_file`
  - second-pass identity reuse / public retry / second-pass copy
- [ ] normalize shared perf-event metadata across:
  - fetch/page scan
  - forward expansion
  - materialize first pass
  - materialize second pass
- [ ] make byte-size metadata mandatory where a file copy or remote download actually completed

## Track 9. Fetch/Scan Hotspot Reduction

- [x] confirm from the `20260324` full-export report that the main fetch hotspot is `forward_hydrate_s`, not raw `fast_tail_bulk`
- [x] add first-class perf rows for each bulk forward-hydrate window/chunk so the `35s+` tail forward cost is decomposed instead of living only in `scan_summary`
- [ ] quantify zero-hit retry work inside finalize/forward enrichment:
  - `history_retry_calls`
  - `history_retry_hits`
  - `get_forward_msg_calls`
  - `get_forward_msg_hits`
- [ ] gate forward-history retries on stronger evidence when the current run already predicts zero recovery value
- [ ] reduce sparse forward-hydrate overfetch:
  - current maintainer slice still pays `~445ms` to hydrate `200` messages for `1` forward ref
  - next pass should compare:
    - current `page_size` window
    - smaller fixed windows
    - density-aware minimal covering span

## Track 10. Full Export Perf Gate

- [ ] compare every new full export against the last actionable-zero baseline on:
  - total elapsed
  - fetch elapsed
  - materialize elapsed
  - forward hydrate elapsed
  - top slow asset p95/p99
- [ ] define an explicit acceptable regression budget instead of only saying `no material benchmark regression`

## Track 11. Replay Diff Reporter

- [ ] emit a fixed diff summary for baseline-vs-current full exports:
  - newly regressed assets only
  - same assets but slower route plan
  - new empty report sections
  - stage delta table vs baseline

## Track 12. Perf Review Board

- [ ] maintain a ranked optimization queue grouped by:
  - high ROI
  - correctness-sensitive
  - observability gap
  - external NapCat-bound
- [ ] keep the current top-ranked buckets visible:
  - top-level `image` public-token remote-url failures (`public_token_get_image_remote_url:error`)
  - sparse forward hydrate cost inside fetch
  - zero-hit finalize/forward retries
  - aggregate forward `image` remote downloads

## Track 1. Evidence-First Terminal Classification

Current direction already landed:

- old-forward `video/file/speech` no longer rely primarily on age for several terminal classifications
- `terminal_evidence_age_invariance` simulator coverage now proves recent/old parity for a focused set of terminal cases

Remaining work:

- `media_downloader.py::_classify_image_local_placeholder_missing(...)`
  - current issue:
    - placeholder status can still be inferred mainly from path shape / zero-byte patterns
  - target:
    - only classify `qq_not_downloaded_local_placeholder` after at least one authoritative route has failed or returned empty
  - desired evidence:
    - forward/context hydrate empty/error/unavailable
    - public token blank / not-found / known-bad
    - direct local probe confirms placeholder siblings only

- `media_downloader.py::_classify_missing_from_public_payload(...)`
  - current issue:
    - some branches still normalize through bucket/proxy context before classifying terminally
  - target:
    - normalize terminal public-payload evidence into one proof layer first:
      - blank payload
      - zero-byte local payload
      - known missing classification
      - dead remote-only payload
      - not-found
    - classify from proof layer, not bucket/topology

- `media_downloader.py::_allow_old_forward_missing_without_stale_local_hint(...)`
  - current issue:
    - function name and semantics still reflect historical/proxy policy
  - target:
    - allow terminal classification without stale local hints only when another terminal proof exists

## Track 2. Evidence-Scoped Cache And Breaker

- `media_downloader.py::_old_context_bucket(...)`
  - current issue:
    - month/age bucket is still used as control identity
  - target:
    - replace control-flow bucket with failure-signature scope
  - candidate signature fields:
    - asset family
    - topology
    - route
    - stale/zero local hint
    - no-live-url
    - direct-file-id presence
    - public-token presence
    - actual failure mode:
      - timeout
      - unavailable
      - empty
      - blank payload
      - not-found

- `media_downloader.py::_should_skip_old_bucket(...)`
  - current issue:
    - skip currently keys off bucket memory rather than same-proof replay
  - target:
    - skip only when same asset identity or same failure signature already produced terminal evidence in current run

- `media_downloader.py::_note_old_bucket_failure(...)`
- `media_downloader.py::_note_old_bucket_success(...)`
- `media_downloader.py::_note_old_bucket_expired_like(...)`
  - current issue:
    - route memory is bucket-scoped and coarse
  - target:
    - route memory should be proof-scoped, not month-scoped

- `media_downloader.py::_should_skip_forward_timeout_storm(...)`
- `media_downloader.py::_forward_timeout_storm_key(...)`
  - current issue:
    - breaker scope is still coarse and partially proxy-based
  - target:
    - breaker should open on repeated evidence signatures, not age/month grouping

- `media_downloader.py::_should_share_missing_outcome(...)`
- `media_bundle.py::_asset_recent_identity_key(...)`
  - current issue:
    - recent/old sharing still uses proxy rules
  - target:
    - share `missing` only when terminality is evidence-backed and identity confidence is high

## Track 3. Evidence-First Route Planning

- `media_downloader.py::resolve_for_export(...)`
  - current issue:
    - major branching is still heavily topology-first (`forward` vs `top_level`)
  - target:
    - derive route order from available evidence:
      - valid local path
      - live remote URL
      - public token
      - direct file_id
      - forward context completeness
    - use topology as metadata, not the primary decision gate

- `media_downloader.py::_has_forward_parent_marker(...)`
  - current issue:
    - marker-only forward detection can trigger forward-special handling too early
  - target:
    - require minimum usable forward evidence before taking forward-special branches

- `media_downloader.py::_should_prefer_direct_file_id_before_targeted_materialize(...)`
  - current issue:
    - now improved, but still tied to a specific candidate profile
  - target:
    - choose route ordering from recoverability evidence score

- `media_downloader.py::_pick_forward_asset_match(...)`
  - current issue:
    - candidate ranking still uses heuristic matching
  - target:
    - rank by recoverability evidence first, heuristic similarity second

## Track 4. Evidence-First Prefetch And Pool Shaping

- `media_downloader.py::_should_skip_eager_remote_prefetch(...)`
  - current issue:
    - suppression is still partly proxy-driven
  - target:
    - prefetch only when there is an unexhausted live remote route and no stronger completed path

- `media_downloader.py::_configure_prefetch_pools_for_requests(...)`
- `media_downloader.py::_prefetch_batch_size_for_request_count(...)`
- `media_downloader.py::_prefetch_batch_timeout_s(...)`
  - current issue:
    - request-count-driven shaping can overfit volume instead of real actionable work
  - target:
    - pool sizing and batch shaping should key off actionable composition:
      - unresolved live remote candidates
      - unresolved public-token candidates
      - unresolved forward-context candidates
      - already-terminal / already-shared cases should not shape pool pressure

## Track 5. Forward Detail Enrichment / Provider Proofing

- `provider.py::_known_unavailable_forward_ids`
- `provider.py::_known_unavailable_history_keys`
- `provider.py::skip_forward_msg_fallback`
- `provider.py::skip_history_retry`
  - current issue:
    - forward structure unavailability caches are still threshold/sequence driven
  - target:
    - split:
      - hard terminal structure-unavailable
    - transient route failure
    - parse-mult/history mismatch
    - do not let one coarse failure family suppress all later forward retries

## Track 6. Instrumentation-Driven Regression Triage

- [ ] keep the last actionable-zero full export as an explicit comparison baseline
- [ ] compare every new full export against that baseline before treating a run as healthy
- [ ] explain every newly reintroduced actionable asset
- [ ] explain every empty or partial report field
- [ ] maintain a benchmark comparison table for:
  - fetch
  - finalize
  - materialize
  - total elapsed
- [ ] ensure observability changes are correctness-neutral before release sync

## Simulator Expansion Required

To support the tracks above, extend simulator coverage with:

- `evidence_scoped_bucket_replacement`
  - same proof, different month/age bucket -> same decision

- `placeholder_authoritative_proof_matrix`
  - placeholder-looking local paths without route proof must stay unresolved
  - placeholder-looking local paths with route proof may become terminal

- `topology_equivalence_matrix`
  - top-level vs forward with equivalent evidence should converge

- `prefetch_actionable_work_matrix`
  - same request count, different actionable composition -> different pool sizing

- `forward_match_recoverability_matrix`
  - multiple forward candidates with different evidence strengths -> strongest recoverable candidate wins

## Suggested Execution Order

1. `evidence_scoped_cache_and_breaker`
2. `placeholder_authoritative_proof_matrix`
3. `topology_equivalence_matrix`
4. `prefetch_actionable_work_matrix`
5. `forward_match_recoverability_matrix`
6. `provider_identity_and_reason_scope`
7. `full_live_export_validation_922065597`
