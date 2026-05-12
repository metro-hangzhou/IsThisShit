# LLM Analysis TODOs

Spec baseline: 2026-03-10

This file tracks the first dedicated LLM analysis phase that sits above the existing analysis substrate.

Current phase principle:

- first abstract
- then refine
- only later descend into lower-level, more concrete agent schemas

## P0. Governance And Boundaries

- [x] Add a dedicated `llm_AGENTs.md`.
- [x] Record that this LLM layer is:
  - above preprocessing and retrieval
  - inside the analysis stack
  - before the future visualizer
- [x] Record that the first-phase product is an open-ended long report, not a fine-grained `BenshiAgent`.
- [x] Record that the visualizer is out of scope for this phase.
- [x] Record that every critical LLM finding or prompt/runtime constraint must be written back into the relevant AGENTs/TODOs proactively.

## P1. Input Pack Contracts

- [x] Define `AnalysisPack` for LLM-facing input.
- [x] Include at least:
  - target metadata
  - chosen time scope
  - pack summary
  - basic statistics
  - candidate-event summaries
  - representative message samples
  - content-composition summaries
  - known special content types
  - optional retrieval snippets
  - message reference pool
- [x] Ensure LLM runs replay from saved packs rather than raw database queries alone.
- [x] Record that a whole time window may be the analysis unit, but it still must be compressed before the LLM call.

## P2. First-Phase LLM Output

- [x] Define the first-phase default output as:
  - open-ended long-form human report
  - minimal machine-readable metadata
- [x] Preserve machine artifacts:
  - `analysis_pack.json`
  - `llm_run_meta.json`
  - `report.txt` or `report.md`
  - `usage.json`
- [x] Add weakly structured metadata fields for later convergence:
  - `observed_dimensions`
  - `candidate_axes_for_structuring`
- [ ] Do not require formal compact semantic JSON in the first iteration.

## P3. Prompt Iteration Workflow

- [x] Support explicit prompt versioning.
- [x] Save prompt snapshots next to outputs.
- [x] Support repeated runs on the same saved pack with different prompt versions.
- [x] Add `benshi_window_v2` as the first structured-soft prompt revision.
  - add `Stable Dimension Block`
  - add `Soft Participant Roles`
  - keep both blocks soft/intermediate rather than final taxonomy
- [x] Add a first bounded multimodal augmentation experiment.
  - caption a small image sample with a live OpenAI-compatible model
  - inject those results into `Image Caption Evidence`
  - keep it as a bounded report helper, not a final benshi agent
- [ ] Design the review loop around:
  - small real samples
  - human manual assessment
  - iterative prompt adjustment
- [ ] Before the next sparse-corpus prompt iteration wave, lock the review-point method first.
  - do not keep tuning prompts against the current `712` review entry surface as if it were already the right human-supervision target
  - current method-redesign input: `state/program_runs/shi_analyzer/round_017/METHOD_REDESIGN_INPUT_20260407.md`
  - fresh live evidence: `state/group_analysis_runs/amd_guanren_group_712742342/run_20260407_174750/`
  - this live run selected semantically on-target sparse windows; the bigger remaining mismatch is review-entry design, not analyzer impossibility on `amd_712`
- [x] Add a first explicit sparse-review prompt correction branch before the next live retest.
  - new version:
    - `benshi_master_v1_sparse_review_fix1`
  - current correction round:
    - `state/program_runs/shi_analyzer/round_020/review_resolution.md`
  - purpose:
    - stop leaking whole-window verdict into weak local anchors
    - reduce over-prioritization of isolated asset-only and plain missing-media cards
    - make review-surface guidance explicit in model output before the next live sparse-corpus run
- [x] Insert a neutral human-review event layer before benshi-specific posterior/policy artifacts.
  - landed in:
    - `src/qq_data_analysis/models.py`
    - `src/qq_data_analysis/review_projection.py`
    - `src/qq_data_analysis/review_service.py`
    - `scripts/parse_benshi_review_packets.py`
  - current human review persistence is now:
    - `ReviewPointProposal`
    - `HumanReviewTaskDecision`
    - `HumanReviewEvent`
  - benshi outputs are now projections, not the direct saved-review truth layer
- [x] Record first reviewed real-sample findings in a reusable note.
  - current note: `../reports/analysis/reviews/benshi_report_review_20260312.md`
  - current stable direction: free report plus soft role/dimension convergence, not final taxonomy
- [x] Add cross-window aggregation output for group-level calibration.
  - current output now includes:
    - `cross_window_group_profile_prior`
    - `cross_window_component_distribution`
    - `cross_window_interaction_summary`
  - landed in:
    - `scripts/run_benshi_group_full_analysis.py`
    - `src/qq_data_analysis/models.py`
  - purpose:
    - move from single-window reviewed loop to group-level analyzer baseline
    - keep `shi core` and `carrier/provenance` separated at cross-window summary level too
- [x] Harden OpenAI-compatible live runs against transport timeouts beyond streaming fallback.
  - `responses` non-stream path now retries/falls back on retryable `httpx` transport errors too
  - `chat/completions` paths now also retry retryable transport errors
  - current live lesson from `2026-04-14`:
    - cross-window aggregation landed cleanly
    - one live retest still timed out on candidate_008 after candidate_001/003 completed
    - analyzer baseline should therefore be treated as ready for broader controlled testing, but long runs still need timeout-aware operational expectations
- [x] Add a first text-only missing-media inference stage to the pack/prompt flow.
  - keep inferred gap semantics separate from direct observed evidence
  - keep unknown gaps explicit when context is too weak
- [ ] Do not introduce rigid low-level classification prompts before the report style stabilizes.

## P4. Provider And Runtime Policy

- [x] Keep public config provider-agnostic.
- [x] Keep DeepSeek as the first documented reference provider.
- [x] Support an OpenAI-compatible `POST /v1/responses` provider path for relay/base-url deployments.
- [x] Record:
  - `https://api.deepseek.com`
  - direct networking by default
  - no local external-download proxy for DeepSeek unless re-decided later
- [x] Preserve:
  - token estimates
  - actual usage
  - timeout/retry settings
  - provider/model metadata
- [x] Keep provider-specific response parsing isolated from the rest of the analysis layer.
- [ ] Recalibrate token estimation against real runs.
  - 2026-03-10 baseline: a whole-window run estimated `2520` input tokens but used `4739` prompt tokens with DeepSeek.
  - treat the current estimate as a lower-bound heuristic until corrected
  - 2026-03-12 `benshi_window_v2` longer-context runs were still low by a similar margin:
    - export1 full-day: estimated `4833`, actual prompt `8496`
    - export3 90-minute: estimated `4417`, actual prompt `7711`
  - current practical rule: on larger v2 runs, assume actual prompt tokens may be roughly `1.7x-1.8x` the estimate until the estimator is fixed
- [ ] Add a provider health probe before long runs.
  - 2026-03-10 note: one OpenAI-compatible relay returned `/models` normally but timed out for both minimal `/responses` and `/chat/completions` generation requests.
  - do not treat `/models` success as sufficient proof that generation is usable
  - 2026-03-12 note: the relay at `http://107.148.225.11:2095/v1` returned `/models` successfully and also accepted multimodal `input_image` requests on `gpt-5.4`

## P5. First Real Deliverable

- [x] Add a first script-safe entrypoint for whole-window LLM analysis.
- [x] Support:
  - group/friend target selection
  - explicit or adaptive time scope
  - saved analysis packs
  - saved report + meta + usage artifacts
- [x] Keep the first deliverable centered on:
  - broad topic summary
  - atmosphere summary
  - anomaly summary
  - candidate behavior directions
  - next-step suggestions for schema refinement

## P6. Evidence And Review Policy

- [x] Allow weak evidence in phase one.
- [x] Still preserve:
  - evidence pack
  - representative message pool
  - prompt/config snapshot
  - token usage
- [x] Keep missing-media gap hypotheses explicitly labeled as context-only rather than observed fact.
- [ ] Add a manual review checklist for each sample:
  - what the model noticed correctly
  - what it overgeneralized
  - what dimensions humans care about but the model missed
  - which dimensions seem stable enough to formalize later
- [x] Review a small set of real reports and extract first stable soft labels.
  - current reviewed dimensions:
    - interaction_density
    - information_density
    - content_provenance
    - narrative_coherence
    - media_dependence
    - uncertainty_load
    - topic_type
    - followup_value
  - current reviewed soft roles:
    - narrative_carrier
    - relay_forwarder
    - topic_initiator
    - noise_broadcaster
    - question_probe
    - reaction_echoer
    - resource_dropper

## P7. Convergence Roadmap

- [ ] After enough reviewed samples, define a semi-structured schema candidate.
- [ ] Next convergence step: add a soft `role + dimension` block to the report without freezing a final benshi taxonomy.
- [x] Add the first soft `role + dimension` block to the report.
- [ ] Decide whether `Image Caption Evidence` should become a stable semi-structured pack field beyond the current bounded experiment.
- [ ] Decide when to split the broad report into:
  - event-level analysis
  - person-level analysis
  - later `BenshiAgent`
- [ ] Keep this as a second-stage milestone, not a first-stage assumption.
- [ ] Reconcile report-first LLM outputs with sparse-corpus review-point generation.
  - dense baseline and sparse real-group corpora should not share the exact same first-card / first-review-entry policy
  - current repo-wide knowledge map: `state/program_runs/shi_analyzer/round_017/KNOWLEDGE_MAP_20260407.md`
  - current live sparse-corpus check: `state/program_runs/shi_analyzer/round_018/review_resolution.md`
  - `2026-04-08` live sparse-fix retest now passed on the real Windows host `.venv`
  - current lock: `state/program_runs/shi_analyzer/round_021/review_resolution.md`
  - chain lesson:
    - do not trust new prompt fields until `llm_contract_valid=true`
    - truncated sparse-fix JSON previously caused fake-success fallback
    - that path is now fail-fast in the live runner
  - `2026-04-08` scheduling-layer repair:
    - primary review queue is now built from current model-positive evidence anchors
    - prior human `non_shi_window/high` reviews affect scheduling suppression only
    - prior reviewed events remain forbidden as prompt answer-key leakage
    - see: `state/program_runs/shi_analyzer/round_022/review_resolution.md`

## P8. Tests And Acceptance

- [ ] Add doc-routing tests so `llm_AGENTs.md` and this TODO are discoverable from top-level docs.
- [x] Add tests for:
  - pack serialization
  - prompt version persistence
  - usage persistence
  - replay of a saved pack without rebuilding it from scratch
- [ ] Add acceptance criteria for the first stage:
  - a small real time-window sample can produce a long report
  - token usage is recorded
  - prompt/config is replayable
  - outputs are stable enough for manual comparison across prompt revisions
- [x] Add a script-level regression test for live sparse-run progress emission.
  - current lock: `tests/test_benshi_group_full_analysis_script.py`
  - bug caught by real run on `2026-04-07`: `WindowsPath` failed JSON serialization inside `ProgressEmitter.emit(...)`

## Deferred

- [ ] strict evidence-per-claim enforcement
- [ ] formal compact semantic JSON schema
- [ ] event-level LLM specialization
- [ ] person-level long-term profiles
- [ ] `BenshiAgent`
- [ ] OCR/caption/multimodal image reasoning
- [ ] visualizer implementation
