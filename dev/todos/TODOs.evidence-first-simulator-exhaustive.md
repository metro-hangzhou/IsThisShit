# Evidence-First Simulator Exhaustive TODOs

Spec baseline: 2026-03-23

This file is the execution panel for pushing the exporter simulator toward bounded exhaustive coverage under the new evidence-first decision model.

It does not aim to enumerate every raw QQ/NapCat payload byte-for-byte. That is not realistic.

Instead, the goal is:

- collapse raw payload chaos into a finite evidence model
- make exporter decisions a pure function of that evidence model
- exhaustively enumerate the bounded evidence space
- verify both:
  - correctness of terminal outcome
  - cost/timeout behavior of the chosen route plan

If we do this correctly, simulator coverage becomes close to "mathematical" coverage for the exporter's actual decision surface, even though QQ raw payload shapes remain open-ended.

## Why A New Panel Is Needed

Current simulator work is already strong, but it is still a mix of:

- targeted historical regressions
- bounded exhaustive scenario generators
- hand-picked matrix suites

That catches real bugs, but it is not yet organized around a single formal statement:

- "what exact evidence dimensions exist?"
- "which of them are authoritative?"
- "which combinations are reachable?"
- "what outcome must the exporter produce for each reachable combination?"

Without that formal layer, we can still miss:

- mixed-evidence aliasing
- route-order bugs that only appear when two weak signals coexist
- cost explosions where the final resolver is technically correct but reached too slowly
- cross-run or second-pass behavior that is only wrong under multi-stage state interaction
- transport/runtime coupling where a valid recovery proof exists but the implementation still fails because an async helper runtime is unavailable

## [2026-03-24] Latest Validation Snapshot

- bounded exhaustive simulator remains green after the latest evidence-first classifier changes:
  - `test_asset_simulator.py`: `36 passed`
  - asset resolution matrix mismatches: `0`
- the latest live-export-guided conclusion that must be modeled explicitly is:
  - `projected localhost /download unsupported + no local file` is not sufficient terminal evidence by itself
  - terminality must be based on the full proof chain:
    - authoritative remote terminal failure
    - unsupported projected localhost download
    - no local file / no hydrated local path
    - no remaining public/file-id/live-remote handle
- targeted manifest retests now confirm that the previous residual actionable windows can be eliminated by generic evidence-first rules rather than sample-specific hardcoding:
  - `cluster_1`: actionable `0`
  - `cluster_2`: actionable `0`
- next simulator-facing requirement:
  - encode this proof-chain rule directly into image terminality suites so that:
    - incomplete proof stays non-terminal
    - complete proof becomes terminal/background

## [2026-03-24] New Regression Shape That Simulator Must Lock Down

- latest broad regression was not a replay of the old forward-image windows
- it introduced 6 new actionable misses, all with the same top-level evidence surface:
  - top-level `image`
  - stale local `source_path`
  - direct `file_id` / public-token recovery handle present
  - `context_hydration` already attempted with no recovered local path
  - `public_token_get_image` returned payload, but only as remote URL
  - `public_token_get_image_remote_url` then failed
  - implementation still landed on `missing_after_napcat`
- simulator must therefore add a first-class suite for:
  - recent top-level image
  - stale local path
  - public-token payload with remote-only result
  - authoritative remote failure on that public remote URL
  - no remaining live handle
- expected oracle result:
  - `actual_resolver = qq_expired_after_napcat`
  - `actual_path_kind = missing`
  - zero cost-overrun tolerance
- explicit anti-regression requirement:
  - this suite must run for both `recent` and `old` ages
  - the result must be invariant to age once the proof chain is complete

## [2026-03-24] Perf-Driven Simulator Extension Targets

- the latest maintainer live perf slice:
  - `state/export_perf/cli_export_group_922065597_20260324_194611_882045_41096.report.json`
  shows two cost families that now deserve first-class simulator/replay coverage:
  - sparse forward-hydrate overfetch
    - `200` messages
    - `1` forward ref
    - `1` hydrated
    - `0.4453s`
  - repeated top-level `image` public-token remote-url failure
    - `16` calls
    - `1.0048s` total
    - all landing in `qq_not_downloaded_local_placeholder`
- simulator/replay next requirement:
  - classify not only outcome correctness, but also whether a given proof chain should:
    - skip repeated dead remote-url work
    - or avoid oversized forward-hydrate spans once forward density is known
- new bounded suites to add:
  - `top_level_image_public_remote_dead`
    - stale local path
    - public-token payload returns remote-only result
    - authoritative remote failure
    - no remaining live handle
    - expected result:
      - background missing
      - zero actionable drift
      - bounded low retry cost
  - `sparse_forward_hydrate_span`
    - vary:
      - window size
      - forward density
      - clustered vs isolated forward positions
    - expected result:
      - same final forward detail correctness
      - cost class should penalize over-wide hydrate windows when narrower exact evidence is available

## Hard Rule

From this point onward, simulator work should be driven by evidence dimensions, not by ad hoc "interesting scenarios".

The exporter should eventually be testable as:

1. normalize raw hints into evidence
2. score/select route plan from evidence
3. classify missing/success from evidence and route results
4. assert that every bounded evidence combination lands in:
   - the right outcome
   - the right cost class

## Current Deficits To Close

The current simulator is still missing a unified exhaustive framework for:

- multi-stage evidence interaction
  - first-pass miss
  - second-pass public retry
  - recent identity reuse
  - shared missing outcome reuse
  - reset boundary
- route-order correctness
  - not just "winner label"
  - but whether the chosen plan avoided unnecessary expensive routes
- evidence aliasing
  - same logical asset represented by different strong keys across time:
    - `public_token`
    - `file_id`
    - `remote_url`
    - `md5 + file_name`
    - `md5 + source leaf`
- terminal-vs-nonterminal proof separation
  - timeout is not always terminal
  - unavailable is not always terminal
  - blank payload is sometimes terminal, sometimes not
- unreachable-combination filtering
  - some Cartesian products are nonsense and should not pollute summary signals

## Main Design

### 1. Evidence Algebra

Create an explicit evidence schema for simulator and exporter logic.

Every synthetic asset state should be described by evidence dimensions instead of loose scenario names.

Candidate evidence dimensions:

- asset family
  - `image`
  - `video`
  - `file`
  - `speech`
  - `sticker`
- topology
  - `top_level`
  - `forward`
  - `nested_forward`
  - `forward_parent_missing`
- local evidence
  - no path
  - valid local path
  - stale local path
  - zero-byte local path
  - placeholder sibling-only
- remote evidence
  - no URL
  - live HTTP URL
  - dead HTTP URL
  - non-HTTP local-looking URL
  - relative URL
- public evidence
  - no token
  - token present
  - token route success
  - token route timeout
  - token route blank payload
  - token route not-found
  - token route unavailable
- direct-file-id evidence
  - no file_id
  - file_id in hint
  - file_id only in payload
  - direct-file-id success
  - timeout
  - not-found
  - blank payload
- forward-context evidence
  - no forward context
  - metadata ok
  - metadata timeout
  - metadata empty
  - metadata error
  - metadata unavailable
  - materialize ok
  - materialize timeout
  - materialize empty
  - materialize error
  - materialize unavailable
- identity evidence
  - exact `public_token`
  - exact `file_id`
  - exact normalized `remote_url`
  - exact `md5 + file_name`
  - exact `md5 + source_leaf`
  - md5 only
- route cache state
  - fresh
  - shared outcome hit
  - timeout breaker open
  - public timeout cached
  - direct-file-id timeout cached
  - forward metadata cached
- run boundary state
  - same pass
  - second pass
  - same run later asset
  - post-reset new run

### 2. Reachability Model

Not every Cartesian product is valid.

We need a reachability filter layer that declares combinations:

- reachable
- unreachable by construction
- logically contradictory

Examples:

- `top_level` + `forward_parent_missing` is unreachable
- `valid local path` + `stale local path` together is contradictory
- `token route success` with `no token` is contradictory

This filter is what makes bounded exhaustive testing realistic instead of exploding into garbage cases.

### 3. Outcome Oracle

Create an oracle layer that defines expected result from evidence, independent from the production downloader implementation.

The oracle should classify:

- expected resolver family
  - local hit
  - remote hit
  - public-token hit
  - direct-file-id hit
  - classified background missing
  - actionable unresolved
- expected path kind
  - local
  - remote
  - missing
- expected terminality
  - terminal missing
  - retryable/unresolved
- expected cost class
  - cheap
  - bounded moderate
  - must not exceed timeout budget

This is critical:

- simulator should not merely replay the current implementation
- it must compare implementation behavior against a smaller formal oracle

### 4. Cost Oracle

Correct final classification is not enough.

For each reachable evidence combination, we also need an expected upper bound on:

- client calls
- fast-plugin calls
- remote attempts
- expensive timeout-bearing route attempts

### 5. Transport Independence Guard

Evidence-first correctness is not just about classification.

If exporter evidence already proves a live recovery route exists, that route must not become unavailable merely because:

- async remote prefetch runtime failed to start
- a background worker pool is disabled
- prefetch submission returns no future

Simulator and unit-level matrices should therefore separately cover:

- decision-surface correctness
- transport/runtime independence of the chosen route

The simulator should fail when:

- result is correct but route cost is materially above expectation

This is how we catch "technically correct but drags export for minutes" bugs.

## New Work Tracks

## Track A. Formal Evidence Catalog

- [ ] add a first-class `EvidenceVector` / `ReachabilityResult` / `ExpectedOutcome` layer to `asset_simulator.py`
- [ ] define every current exporter decision in terms of evidence dimensions
- [ ] add a "dimension coverage report" so we can see:
  - which evidence dimensions participate in production decisions
  - which ones are not yet represented in the simulator

Acceptance:

- a generated report can list all evidence fields and the number of reachable states exercised per field/value

## Track B. Reachable Cartesian Enumerator

- [ ] build a generator that enumerates bounded combinations over the evidence algebra
- [ ] add a reachability filter so impossible combinations are explicitly skipped, not silently absent
- [ ] emit counts for:
  - raw combinations
  - unreachable combinations
  - reachable combinations
  - covered combinations

Acceptance:

- we can say exactly how many reachable evidence combinations exist under the current bounded model

## Track C. Outcome Oracle Separation

- [ ] implement a simulator-side oracle that does not call downloader logic
- [ ] compare downloader result against oracle result for every reachable combination
- [ ] separate:
  - resolver mismatch
  - path-kind mismatch
  - terminality mismatch
  - cost-overrun mismatch

Acceptance:

- summaries must show mismatch counts per category, not just one `matched` boolean

## Track D. Multi-Stage Exhaustive Matrices

We need bounded exhaustive coverage not only for single requests, but for sequences.

- [ ] add exhaustive two-step matrices:
  - early weak miss -> later strong success
  - early background missing -> later strong success
  - early timeout -> later cached skip
  - early unresolved -> second-pass retry success
- [ ] add exhaustive three-step matrices:
  - first asset miss
  - second asset shared alias success
  - third asset post-reset behavior
- [ ] add exhaustive cache-interaction matrices:
  - shared outcome cache
  - recent identity reuse
  - public timeout cache
  - forward timeout breaker
  - forward metadata cache

Acceptance:

- sequence matrices must prove no poisoning across:
  - strong identity aliases
  - same-run later recovery
  - reset boundaries

## Track E. Evidence-First Forward Image Matrix

This is now the most important family because recent real regressions came from forward images.

- [ ] build an exhaustive forward-image matrix over:
  - `remote_url` state
  - `public_token` state
  - `forward_metadata` state
  - `local path` state
  - `identity alias` state
  - `same-run later success` presence/absence
- [ ] assert:
  - when a later same-identity strong success exists, earlier missing entries are healed
  - when no later success exists, terminal background/actionable classification is evidence-correct
  - metadata cache does not poison sibling assets

Acceptance:

- no forward-image mismatch remains in the exhaustive reachable matrix

## Track F. Evidence-First Video/File/Speech Cost Surface

This family is where long stalls happen.

- [ ] build exhaustive cost-surface matrices for:
  - public-token timeout
  - direct-file-id timeout
  - forward metadata timeout
  - forward materialize timeout
  - dead remote URL
- [ ] track worst-case theoretical elapsed cost under:
  - same parent many siblings
  - many parents one sibling each
  - mixed recent/old
  - mixed route-health states
- [ ] assert bounded upper cost after breaker/cache rules

Acceptance:

- no reachable combination can accumulate an unbounded timeout storm without either:
  - terminal classification
  - or a documented bounded retry budget

## Track G. Machine Drift / Payload Drift

We also need a bounded model for operator-machine differences.

- [ ] add machine-drift dimensions:
  - route available vs unavailable
  - route returns timeout vs empty vs error
  - public payload returns:
    - `url`
    - `remote_url`
    - blank file
    - local file path
    - zero-byte local file
- [ ] add payload-shape drift dimensions for:
  - share/card media hints
  - malformed nested-forward wrappers
  - sticker/static/dynamic partial metadata

Acceptance:

- every production parser branch consuming these hints has at least one exhaustive bounded suite

## Track H. Summary-First Reporting

- [ ] extend CLI simulator output with:
  - reachable combination counts
  - mismatch category counts
  - cost-overrun category counts
  - uncovered-dimension warnings
- [ ] add "newly failing only" and "coverage hole only" outputs

Acceptance:

- we can quickly see whether a change:
  - broke correctness
  - widened cost
  - or left a dimension uncovered

## Track I. Baseline-Replay Regression Harness

- [ ] encode the last actionable-zero full export as a replay baseline
- [ ] replay current regressed actionable windows against the same evidence model
- [ ] assert:
  - no newly actionable terminal mismatches
  - no new cost overruns
  - no empty report fields for covered stages
- [ ] add matrix families for:
  - baseline vs regressed route-plan divergence
  - report completeness invariants
  - same asset, different stage timing surface cost drift
  - sparse forward-hydrate span cost divergence
  - top-level image public-remote dead-route cost divergence

## Track J. Performance Report Completeness As A Replay Contract

- [ ] require replay/baseline runs to validate report schema, not just correctness/cost
- [ ] assert presence and non-emptiness of:
  - `total_elapsed_s`
  - `history_page_breakdown`
  - `materialize_stage_breakdown`
  - `materialize_asset_breakdown`
  - `top_materialize_steps`
  - `top_materialize_substeps`
- [ ] enforce per-row metadata contracts for covered sections so a report can be compared mechanically instead of by hand

## Track K. Performance Review Board Inputs

- [ ] make replay/simulator outputs emit a normalized optimization queue:
  - empty-section regressions
  - newly slow route families
  - aggregate-cost hotspots
  - correctness-vs-cost tension points
- [ ] keep that queue aligned with the live full-export baseline so reviewer output becomes executable TODO input, not one-off commentary

## Immediate Execution Plan

Phase 1. Formalize the evidence model

- [ ] introduce explicit evidence-vector objects
- [ ] encode reachability rules
- [ ] encode outcome oracle skeleton

Phase 2. Replace scenario-first summaries

- [ ] add exhaustive enumerator for the new evidence algebra
- [ ] keep existing hand-written matrices as regression fixtures
- [ ] make exhaustive matrix the primary gate

Phase 3. Attack real remaining actionable surface

- [ ] run exhaustive forward-image matrix
- [ ] run exhaustive multi-stage alias/reuse matrix
- [ ] run exhaustive timeout-cost matrix for `video/file/speech`
- [ ] fix any mismatches before any new full live export

Phase 4. Then reconnect to live validation

- [ ] run targeted retry windows first when residual actionable count is small
- [ ] only then run full export on group `922065597`
- [ ] compare:
  - benchmark
  - `final_missing_reason`
  - `actionable_missing_reason`

## Exit Criteria

Call this plan complete only when all of the following are true:

- exhaustive evidence matrices have a formal reachable-state count
- oracle-vs-implementation mismatches are `0`
- cost overruns are `0`
- no uncovered high-impact evidence dimensions remain
- exhaustive/replay suites must reproduce the last actionable-zero baseline for all known regressed windows
- report completeness must show non-empty fetch/page/materialize sections whenever those stages were exercised
- targeted live retests for residual actionable windows are clean
- full live export on group `922065597` ends with:
  - `actionable_missing=0`
  - stable benchmark
  - no new route-stall signature

## Practical Note

True mathematical completeness over raw QQ/NapCat payloads is impossible because upstream can emit arbitrary new or malformed shapes.

What we can do, and should do, is get mathematically close over the exporter's real decision surface by:

- reducing raw payloads to a closed evidence algebra
- proving exhaustive coverage over that algebra
- keeping shape-drift suites for raw payload adapters at the boundary

That is the standard we should now build toward.
