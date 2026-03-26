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

## [2026-03-25] Pure-Logic Simulator Reset

The simulator must now be treated as a **pure logic verifier**, not a hidden pressure test.

New hard rule:

- repeated identical requests must not be expanded and replayed just to simulate volume
- correctness suites must run on **evidence-equivalence classes**
- pressure / multiplicity behavior must be represented analytically (`unique_case + multiplicity`), not by constructing thousands of duplicate requests

What was fixed:

- forward-timeout matrix is now analytical instead of replaying request objects
- prefetch-planning matrix is now analytical instead of constructing `32/256/1024/4096/16384` real request dicts
- shared-outcome scope matrix now computes request keys directly instead of instantiating full downloader runs
- virtual-path asset resolution now avoids real filesystem setup/teardown
- prefetched resolver labels are normalized to logic-equivalent canonical resolvers in simulator results

Current validation snapshot after the pure-logic refactor:

- `tests/test_asset_simulator.py`: `39 passed`
- asset resolution matrix:
  - `668/668 matched`
  - `mismatched=0`
  - `cost_overruns=0`
- pair matrix:
  - `12/12 matched`
- cross-run reset matrix:
  - `12/12 matched`

This means the next expansion work should preserve the same discipline:

- new suites must add evidence classes, not duplicate volume
- any stress / scaling work belongs in a separate pressure model, not inside the logic simulator

## [2026-03-26] New Evidence Families Pulled In From Live Group Trace

The latest full-group traces exposed two real coverage holes that the old simulator abstraction had not modeled explicitly enough:

- top-level `speech`
  - `source_path=stale_local`
  - `context_hydration=ok`
  - `public_token_get_record=file not found`
  - `public_token_get_record_fallback=file not found`
  - this is now modeled as a first-class terminal-proof family rather than left implicit
- forward `image`
  - timeout suppression scope is now explicitly modeled as **parent-scoped** rather than token/file-scoped
  - same forward parent with new token or new file name still belongs to the same timeout suppression family

What was added:

- new simulator suite:
  - `top_level_speech_terminal_evidence`
- expanded timeout-scope matrix:
  - `image` now participates in `public_timeout_scope`
  - image same-parent/new-token and same-parent/new-file relationships are asserted as the same timeout scope

Current local status after this expansion:

- `tests/test_asset_simulator.py`: `45 passed`
- newly modeled cases now covered:
  - `top_level_speech_stale_public_not_found_fallback_terminal_recent`
  - `top_level_speech_stale_public_not_found_fallback_terminal_old`
  - `top_level_speech_stale_blank_public_payload_terminal_recent`
  - `top_level_speech_stale_blank_public_payload_terminal_old`
  - `image_same_parent_new_token`
  - `image_same_parent_same_token_new_file`

Interpretation:

- the simulator now formally covers the two live-trace families that had slipped through the older abstraction:
  - top-level speech terminal proof
  - forward-image parent-scoped timeout reuse
- this still does **not** mean "mathematical completeness" yet
- it does mean the simulator evidence space has been tightened using an actual production trace rather than another guessed scenario

## [2026-03-26] Formal Evidence Dimension Domains Added

The simulator now has an explicit domain table in code for the exporter evidence model:

- `asset_type`
- `topology`
- `forward_parent_state`
- `source_path_state`
- `hint_local_state`
- `hint_remote_state`
- `hint_file_id_state`
- `context_payload_state`
- `forward_payload_state`
- `forward_metadata_state`
- `forward_materialize_state`
- `public_result_state`
- `public_fallback_result_state`
- `direct_file_result_state`
- `prefetch_request_context_payload_state`
- `prefetch_media_state`
- `prefetch_forward_state`
- `prefetch_public_state`
- `prefetch_forward_timeout_cache_state`

There is also now a manifest summary function:

- `summarize_simulator_evidence_dimension_manifest()`

Current local snapshot:

- fully covered dimensions:
  - `asset_type`
  - `topology`
  - `forward_parent_state`
  - `source_path_state`
  - `hint_local_state`
  - `hint_remote_state`
  - `hint_file_id_state`
  - `direct_file_result_state`
  - `public_result_state`
  - all prefetch-state dimensions except `prefetch_request_context_payload_state`
- partially covered dimensions:
  - `context_payload_state`
  - `forward_payload_state`
  - `forward_metadata_state`
  - `forward_materialize_state`
  - `public_fallback_result_state`
  - `prefetch_request_context_payload_state`

Meaning:

- we can now prove which evidence dimensions are modeled at all
- and which values still lack a witness scenario
- this is the new gate before claiming anything like near-exhaustiveness

Next execution rule:

- no new performance/correctness claim should be described as "near mathematical" unless:
  - all evidence dimensions are explicitly enumerated
  - every enumerated value is either:
    - covered by at least one scenario, or
    - explicitly excluded by a reachability rule with a written reason

## [2026-03-26] First Formal Evidence Outputs Landed

The program now has these local generated artifacts:

- `state/subagent_runs/coverage_reachability_surface/evidence_dimension_manifest.json`
- `state/subagent_runs/coverage_reachability_surface/global_evidence_registry.json`
- `state/subagent_runs/coverage_reachability_surface/value_witness_ledger.json`
- `state/subagent_runs/coverage_reachability_surface/cross_track_join_schema.json`
- `state/subagent_runs/coverage_reachability_surface/result_algebra_spec.json`
- `state/subagent_runs/napcat_truth_map_surface/output.md`
- `state/reviewer_runs/round_001/review_blockers.json`

Current local summary:

- simulator evidence dimension count: `29`
- unresolved value count: `84`
- current partial dimensions:
  - `chat_provenance`
  - `context_payload_state`
  - `filesystem_family`
  - `forward_materialize_state`
  - `forward_metadata_state`
  - `forward_payload_state`
  - `month_relation`
  - `ntqq_neighbor_class`
  - `placeholder_shell_profile`
  - `prefetch_request_context_payload_state`
  - `public_fallback_result_state`
  - `segment_path_provenance`
  - `speech_identity_profile`
  - `speech_md5_state`
  - `speech_original_format`
  - `speech_requested_out_format`

Current next witness priorities:

- `forward_payload_state`
- `context_payload_state`
- `public_fallback_result_state`

Current likely unreachable buckets to prove explicitly:

- large parts of `forward_materialize_state`
- `context_payload_state=remote_url` if code audit keeps showing it is not a real top-level recovery branch

## [2026-03-26] File-System Subagent Orchestration

The evidence-space program now also requires file-system-managed subagent orchestration.

New local structure:

- `dev/agents/subagents/`
- `dev/todos/subagents/`
- `state/subagent_runs/`
- `state/reviewer_runs/`

Rules:

- subagents must work from file context, not chat memory
- each track gets:
  - `AGENTs.<track>.md`
  - `TODOs.<track>.md`
  - `state/subagent_runs/<track>/input.md`
  - `state/subagent_runs/<track>/output.md`
  - `state/subagent_runs/<track>/notes.json`
- the first-principles reviewer uses:
  - `state/reviewer_runs/round_<n>/review_input.md`
  - `review_questions.md`
  - `review_blockers.json`
  - `review_resolution.md`

This is now part of the evidence-first contract, not optional process overhead.

Reviewer process rule:

- the first-principles reviewer must run continuously during development/testing
- not only at the end
- any batch of work that bypassed reviewer scrutiny must be fed into a later retro-review round before it can count toward closure

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
- [x] `second_pass_gate_stability_under_prefetch_variants`
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
- [x] `future_local_identity_promotion_order_matrix`
  - explicit three-step sequences:
    - weak miss -> strong recover -> weak repeat
    - strong terminal -> weak repeat
    - strong recover -> weak repeat
  - keep this separate from the already-finished non-poisoning pair matrix
  - current pure-logic matrix now locks:
    - image weak-first future-promotion across `top_level / forward / nested_forward`
    - image strong-first weak-later recent reuse
    - image later-strong-without-local negative case
    - image identity mismatch negative case
    - video image-only boundary
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
- landed pure-logic `second_pass_gate_stability_under_prefetch_variants` matrix:
  - no prefetch
  - pending future
  - done-but-unfinalized future
  - cached payload-only
  - cached remote-attempted-failed
  - cached terminal public outcome
  - request-state terminal placeholder / blank public payload
- landed `partial_parent_handle_sufficient` suite:
  - malformed forward/nested-forward parent with surviving:
    - local handle
    - live remote handle
    - direct `public_token`
    - direct `file_id`
  - plus the no-surviving-handle unresolved baseline
- landed `triplet_sequence` matrix:
  - weak request -> strong recovery -> weak repeat
  - current downloader-only invariant:
    - later strong recovery does not poison repeated weak requests
    - but it also does not auto-promote them
- provider anti-regression tests added for:
  - fast-bulk re-sort when `messages_sorted_ascending` is false
  - history fallback when forward-detail batch returns `ok=true` but empty messages
- validation after this pass:
  - `tests/test_asset_simulator.py`: `43 passed`
  - asset resolution matrix: `688/688 matched`
  - pair matrix: `12/12 matched`
  - triplet matrix: `4/4 matched`
  - second-pass gate matrix: `10/10 matched`
- still missing the full provider partial-detail contract matrix
- [x] `optimization_coverage_manifest`
  - maintain a table mapping each acceleration branch to:
    - code branch
    - paired simulator suite
    - invariant protected
  - pure-logic coverage manifest now reports:
    - case-family counts
    - `asset_type x topology` coverage
    - prefetch-seed shape counts
    - parent-state coverage by topology
    - optimization seam counts
    - sequence-family counts
    - explicit coverage gaps
  - no unpaired performance branch should be considered release-complete

## [2026-03-25] Progress Update: Promotion Matrix + Coverage Manifest

This pass stayed local to full-dev and added two pieces that were previously only hand-waved in TODOs:

- `future_local_identity_promotion_order_matrix`
  - now implemented as a dedicated pure-logic matrix, separate from downloader pair/triplet
  - validation result: `8/8 matched`
- `summarize_simulator_coverage_manifest()`
  - joins single-scenario catalog, second-pass gate cases, pair/triplet sequences, and promotion-order cases
  - validation currently shows:
    - single scenarios: `688`
    - second-pass gate cases: `10`
    - pair cases: `12`
    - triplet cases: `4`
    - promotion-order cases: `8`
    - `single_scenario_family_topology_missing = []`
    - `promotion_image_topology_missing = []`

Validation after this pass:

- `tests/test_asset_simulator.py`: `45 passed`
- asset resolution matrix: `688/688 matched`
- pair matrix: `12/12 matched`
- triplet matrix: `4/4 matched`
- second-pass gate matrix: `10/10 matched`
- future-local promotion matrix: `8/8 matched`

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

## [2026-03-25] Progress Update: Full-Snapshot Forward Detail + Second-Pass Gate

This pass closed two of the highest-value anti-regression gaps called out by the code audits:

- `provider_forward_detail_antiregression`
  - full-export integration is now explicitly covered for:
    - `batch ok + empty payload -> history fallback`
    - `batch partial items -> uncovered target single fast-plugin fallback`
    - `batch ok + malformed/no data -> do not count as covered`
    - `mixed already-resolved + terminal unavailable -> preserve both metadata counters`
  - provider batch prefetch logic is now stricter:
    - `ok=True` no longer counts as covered unless payload shape is structurally valid
    - valid empty `messages=[]` remains covered and falls through to history fallback
    - malformed `ok` items remain eligible for single fast-plugin fallback

- `second_pass_gate_stability_under_prefetch_variants`
  - downloader tests now lock the gate across:
    - no prefetch state
    - pending future
    - future done but not finalized
    - cached payload-only prefetch
    - cached remote-attempted-failed prefetch
    - cached terminal public outcome
    - terminal top-level request-state placeholder
    - terminal `_context_payload` placeholder

Next highest-value simulator work now is no longer the basic gate itself, but the missing simulator expression power:

- done in the latest pure-logic pass:
  - `prefetch_seeded_forward_media_interactions`
    - `video / file / speech`
    - `forward / nested_forward`
    - seeded `prefetched_forward_state`, `public_prefetch_state`, and `forward_timeout_cache_state`
    - now locks three important invariants:
      - live remote evidence can still win under seeded prefetch state
      - `remote_attempted_failed` alone is not auto-terminal proof
      - payload-only forward prefetch with no live handle can still settle terminally
- add a prefetch-state seeding runner for:
  - `_public_token_prefetch_cache`
  - `_public_token_prefetch_futures`
  - `_prefetched_media_payloads`
  - `_prefetched_forward_media_payloads`
  - request-level `_context_payload`
- add explicit scenario dimensions for:
  - `hint_file_id_state = none | public_token | direct_file_id`
  - composite payload states such as:
    - `public_token + empty_local`
    - `public_token + stale_local`
    - `public_token + zero_local`
- `future_local_identity_cross_topology` is partially complete
  - unresolved/recoverable cross-topology cases are now covered
  - weak-key-first vs strong-key-first promotion still needs dedicated `future_local_identity_promotion_order_matrix` coverage

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
