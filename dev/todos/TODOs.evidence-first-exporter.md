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
