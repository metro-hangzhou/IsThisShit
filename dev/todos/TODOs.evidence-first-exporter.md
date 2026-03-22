# Evidence-First Exporter TODOs

Spec baseline: 2026-03-23

This file tracks the remaining exporter logic that still makes control-flow decisions from heuristics or coarse proxies instead of direct terminal evidence.

Goal:

- make `missing` classification evidence-first
- make route ordering evidence-first
- make skip/breaker/cache scope evidence-first
- reduce long-running exports caused by proxy-based decisions that keep expensive routes alive after terminal evidence already exists

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
