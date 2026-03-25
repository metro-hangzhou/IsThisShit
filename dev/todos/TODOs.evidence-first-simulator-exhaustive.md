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

## [2026-03-25] New Top Priority: Asset Distribution Exhaustiveness

The current simulator has become strong at bounded evidence families, but we still need a stronger guarantee against performance/route-order patches quietly reintroducing `missing_after_napcat`, especially in forwarded trees.

New hard requirement:

- every meaningful asset-distribution family that the exporter can observe must be represented in simulator space
- this includes not only single-asset states, but also how assets are distributed across:
  - top-level messages
  - forward trees
  - nested-forward trees
  - repeated-identity clusters across multiple messages
  - mixed-family bundles inside one forward parent
- simulator must explicitly assert that new performance optimizations do not convert:
  - previous `background_missing`
  - or previous `reused/copied`
  into new `actionable_missing`

Concrete execution tracks to add now:

- `Track A. Forward / Nested-Forward Asset Distribution Matrix`
  - enumerate:
    - single forward child
    - sparse forward siblings
    - dense forward siblings
    - nested-forward with top-level mixed assets
    - nested-forward with repeated identity across depths
    - forward parent missing / malformed / partially hydrated
  - cover asset families:
    - `image`
    - `video`
    - `file`
    - `speech`
    - `sticker`
  - required oracle:
    - no new `actionable_missing`
    - route order must not regress into unnecessary `context_hydration` / public retry / remote retry

- `Track B. Repeated Identity Distribution Matrix`
  - same underlying asset reappears as:
    - top-level -> top-level
    - top-level -> forward
    - forward -> nested-forward
    - weak key first, strong key later
    - strong key first, weak key later
  - required oracle:
    - same-run caches and second-pass promotion must preserve or improve outcome
    - performance patches must not break reuse and accidentally create fresh actionable misses

- `Track C. Route-Order / Prefetch / Second-Pass Interaction Matrix`
  - cross product of:
    - prefetch hit / miss / payload-only / payload+remote
    - direct public-token outcome
    - context payload outcome
    - second-pass retry eligibility
    - bundle future-local evidence
  - required oracle:
    - evidence-complete terminal assets short-circuit early
    - recent recoverable assets remain recoverable
    - no `prefetch`/`second-pass` ordering change may turn a former background or reuse case into `missing_after_napcat`

- `Track D. Performance Patch Anti-Regression Matrix`
  - every newly added acceleration branch must have a paired simulator suite that proves:
    - lower or equal cost class
    - unchanged or improved final resolver
    - zero actionable drift
  - current must-cover branches:
    - top-level image terminal classifier
    - direct public-token prefetch reuse
    - future-local identity evidence
    - forward metadata dedupe
    - sparse forward hydrate narrowing

- `Track E. Distribution Coverage Summary`
  - simulator CLI must emit a coverage summary showing:
    - which asset families
    - which topologies
    - which distribution patterns
    - which route-order branches
    are currently exercised
  - this summary should become the fast answer to:
    - “did we actually simulate this family before shipping the optimization?”

Immediate acceptance gate before broad performance work continues:

- [ ] add forward/nested-forward distribution suites for all five asset families
- [ ] add repeated-identity cross-topology suites
- [ ] add prefetch/second-pass interaction suites
- [ ] add anti-regression expectations specifically for `actionable_missing`
- [ ] ensure simulator summary reports coverage by family/topology/distribution branch

Concrete high-risk matrices confirmed by the latest code audit:

- [ ] `prefetch_payload_only_then_context_payload_terminal`
  - top-level / forward / nested-forward `image`
  - direct public-token prefetch returns payload-only or remote-attempted-failed
  - context later returns `no-path` or `stale-local-path`
  - oracle:
    - never regress to `missing_after_napcat` once the combined proof chain is terminal
- [x] `request_state_vs_payload_state_terminal_equivalence`
  - same evidence, two route plans:
    - request-state early skip
    - payload-state post-context classification
  - oracle:
    - same terminal/background result
    - no actionable drift
- [ ] `second_pass_gate_stability_under_prefetch_variants`
  - vary:
    - prefetch empty
    - payload-only
    - remote-attempted-failed
    - runtime unavailable
    - cached terminal classification
  - oracle:
    - recoverable assets remain recoverable
    - already-terminal assets remain skipped
- [x] `future_local_identity_cross_topology`
  - `top_level -> top_level`
  - `top_level -> forward`
  - `forward -> top_level`
  - `forward -> nested_forward`
  - `nested_forward -> top_level`
  - with weak-key-first and strong-key-first permutations
- [ ] `prefetch_strategy_branch_matrix`
  - branches:
    - eager remote prefetch preferred
    - direct public-token prefetch preferred
    - both skipped due terminal request-state proof
  - across top-level / forward / nested-forward image families
- [ ] `provider_forward_detail_antiregression`
  - plugin says sorted ascending / partial detail / missing detail
  - sparse vs dense forward density
  - oracle:
    - skipping `tail_forward_hydrate` or re-sort must not drop forward/nested-forward asset evidence

## [2026-03-25] Progress Snapshot

- landed `request_state_payload_state_terminal_equivalence` simulator suite:
  - `top_level_image_weak_gchatpic_context_no_path_{recent,old}`
  - `top_level_image_weak_gchatpic_context_stale_local_{recent,old}`
  - `top_level_image_local_download_dead_{recent,old}`
- landed additional cross-topology pair guard:
  - `nested_forward_terminal_then_top_level_public_remote`
- provider anti-regression tests added for:
  - fast-bulk re-sort when `messages_sorted_ascending` is false
  - history fallback when forward-detail batch returns `ok=true` but empty messages
- still missing the broader prefetch/second-pass interaction matrix and the full provider partial-detail contract matrix
- [ ] `optimization_coverage_manifest`
  - maintain a table mapping each acceleration branch to:
    - code branch
    - paired simulator suite
    - invariant protected
  - no unpaired performance branch should be considered release-complete

## [2026-03-25] Progress Update: Provider Guard + Cross-Topology Pair Coverage

This pass landed two concrete pieces of the above panel:

- provider trust-boundary guards are now enforced in code and tests:
  - fast-bulk `messages_sorted_ascending=true` is no longer trusted blindly
  - tail forward hydrate is no longer skipped merely because the batch-detail method exists; bulk messages must also already carry resolved forward content
- simulator now covers additional repeated-identity cross-topology distributions through pair/cross-run cases:
  - `top_level -> forward` image unresolved -> remote recovery
  - `forward -> nested_forward` image unresolved -> remote recovery
  - `top_level -> forward` video timeout -> direct-file-id remote recovery
  - `top_level -> nested_forward` file timeout -> direct-file-id remote recovery
  - `nested_forward -> top_level` terminal image -> public-token remote recovery

Remaining gap after this pass:

- `provider_forward_detail_antiregression` is only partially complete
  - sorted-flag wrong and tail-hydrate skip boundaries are now locked
  - partial/empty batch-detail success semantics for full export still need explicit coverage
- `future_local_identity_cross_topology` is partially complete
  - unresolved/recoverable cross-topology cases are now covered
  - weak-key-first vs strong-key-first promotion still needs dedicated matrix coverage

## [2026-03-24] Post-Restart Regression Lockdown Added In This Pass

- the latest post-restart forward-image regression was reproduced against the bounded evidence matrix and reduced to two concrete simulator gaps:
  - valid NapCat relative HTTP recovery paths must use canonical `/download?...` shapes
  - top-level dead-public-remote image terminality must stay invariant across both `recent` and `old` ages once the proof chain is complete
- simulator-side fixes now in place:
  - relative HTTP route modeling now emits valid NapCat-style `/download?...` paths instead of unsupported pseudo-relative shapes
  - relative remote URL joining now uses canonical `urljoin(...)` normalization so the simulated remote map matches the exporter's actual URL resolution path
  - the matrix now explicitly locks:
    - `top_level_image_public_token_dead_remote_recent`
    - `top_level_image_public_token_dead_remote_old`
- exporter-side rule now mirrored by simulator oracle:
  - if `public_token_get_image` yields only a remote URL
  - and that authoritative remote URL fails
  - and there is still no recovered local path / no remaining live handle
  - outcome must be:
    - `actual_resolver = qq_expired_after_napcat`
    - `actual_path_kind = missing`
- validation after this pass:
  - bounded resolution matrix mismatches: `0`
  - changed simulator guard subset:
    - `test_asset_simulator.py -k "matrix_matches_expectations or matrix_includes_core_failure_and_remote_recovery_paths"` -> `8 passed`

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
