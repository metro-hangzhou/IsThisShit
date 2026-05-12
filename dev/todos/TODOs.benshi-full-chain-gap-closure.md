# Benshi Full-Chain Gap Closure TODOs

Spec baseline: 2026-03-28

Purpose:

- audit the current `712` full-chain prototype honestly
- separate "already implemented" from "placeholder heuristic"
- prevent future runs and reports from presenting unfinished analysis as if it were production-complete
- prepare the next repair round under the common-track workflow

Current status:

- this file is a **pre-execution review TODO**
- user requested that repair work should start only after reviewing the gap list first

## P0. Workflow Disclosure Rule

- [ ] Add a new hard rule to [CommonTrackWorkflow.zh-CN.md](../handbooks/workbench/CommonTrackWorkflow.zh-CN.md):
  - when a feature is placeholder, heuristic, partial, sampled, or otherwise not production-complete, the workflow must emit an explicit warning block instead of letting it look "finished enough"
- [ ] Add the same rule to the relevant AGENT layer:
  - [major_AGENTs.md](../agents/major_AGENTs.md)
  - [llm_AGENTs.md](../agents/llm_AGENTs.md)
- [ ] Make that rule concrete rather than stylistic:
  - reports must include `implementation_status`
  - reports must include `placeholder_flags`
  - user-facing summaries must explicitly say which results are heuristics
  - `done/completed/final` wording must not be used for heuristic outputs without a warning block
- [ ] Add a reviewer check item:
  - "unfinished features were clearly disclosed"
  - "sampled runs were not described as full truth"

## P1. 712 Current User-Profile Gaps

- [ ] Replace the current "top-by counter" user profile aggregation with an explicitly scored persona model
- [ ] Stop presenting `group_pet_candidate` as strong logic while it is only:
  - reply-target counting
  - without alias merging
  - without mention graph
  - without reaction graph
- [ ] Stop presenting `top_shi_transporter` as if it meant "搬shi最狠" while it currently only means:
  - highest `forward_message_count`
- [ ] Stop presenting `top_talker` as if it meant a meaningful social role while it currently only means:
  - highest `message_count`
- [ ] Stop presenting `top_media_shipper` as if it meant a meaningful media persona while it currently only means:
  - highest `asset_message_count`
- [ ] Add raw-id resolution directly into output artifacts during test mode
- [ ] Add explicit confidence / strength labels for every persona result
- [ ] Distinguish:
  - message spam
  - real chatter
  - reactive chatter
  - transport behavior
  - media dumping

## P2. 712 Current Group-Distribution Gaps

- [ ] Stop presenting sampled-window aggregation as if it were whole-group exhaustive analysis
- [ ] Mark the current distribution result as:
  - sampled
  - window-bounded
  - non-exhaustive
- [ ] Replace raw count-only family aggregation with:
  - normalized ratios
  - window weighting
  - confidence notes
- [ ] Distinguish:
  - observed in sampled windows
  - inferred from prior/baseline
  - generalized posterior belief
- [ ] Do not call baseline usage "distribution alignment" unless posterior update actually happened
- [ ] Wire the real generalized-distribution update path into the chain instead of only reading the baseline path
- [x] Insert a neutral review-event / benshi-projection seam before reviewed samples.
  - current compatibility outputs still exist:
    - `window_review_cards`
    - `human_patch_deltas`
    - `reviewed_realized_samples`
  - but they are now generated from the new parsed layer:
    - `review_point_proposals`
    - `review_events`
    - `benshi_projections`
    - `candidate_policy_patches`

## P3. 712 Current Multimodal Gaps

- [ ] Stop letting the report read as if full multimodal understanding happened
- [ ] Explicitly state in artifacts that current direct multimodal reasoning only covers:
  - image
  - sticker
- [ ] Explicitly state that video/file currently remain:
  - structural evidence
  - media-state evidence
  - not content-level multimodal understanding
- [ ] Add per-caption confidence and drift flags
- [ ] Add visual-caption failure handling:
  - obvious off-topic caption
  - low-confidence caption
  - unresolved caption

## P4. 712 Current Reporting Gaps

- [ ] Add a report-level warning block at the top of:
  - `group_profile.md`
  - `user_profiles.json`
  - `group_distribution.json`
  - `run_manifest.json`
- [ ] Add explicit fields:
  - `implementation_status`
  - `sampling_status`
  - `heuristic_status`
  - `known_gaps`
- [ ] Stop letting the final report read like a polished product when it is still a first-chain prototype
- [ ] Add direct code-method references in final artifacts so readers can trace the current heuristic source
- [ ] Ensure every placeholder/heuristic item also carries the new mandatory “implementation status” block described in the governance documents so reviewers immediately see the warning text instead of assuming completion.

## P5. 712 Current Full-Chain Product Gaps

- [ ] Wire the human dual-track review path into the full-chain script instead of skipping it completely
- [ ] Consume `review_events` / `benshi_projections` from an authoritative full-chain path instead of stopping at compatibility artifacts under `review_packets/parsed/`
- [ ] Wire candidate/stable patch ingestion into the chain
- [ ] Wire reviewed-sample routing into:
  - `core_positive_pool`
  - `edge_case_pool`
  - `negative_or_holdout_pool`
  - `uncertainty_boundary_pool`
- [ ] Wire posterior delta generation into the run
- [ ] Wire policy-state promotion review into the run instead of implying alignment happened automatically

## P6. 712 Current Selection And Aggregation Gaps

- [ ] Rework candidate-window selection beyond the current:
  - `2 high + 2 medium + 1 low`
- [ ] Add explicit selection rationale into artifacts:
  - why this window was chosen
  - what it represents
  - what it does not represent
- [ ] Weight per-window outputs by:
  - message count
  - confidence
  - media density
  - transport density
- [ ] Stop mixing all windows as if each one contributed equally by default

## P7. Acceptance Before Next "Product-Shaped" Demo

- [ ] No persona output may be shown without:
  - metric definition
  - confidence
  - known limitations
- [ ] No group distribution may be shown without:
  - sampling disclaimer
  - weighting rule
  - posterior-update status
- [ ] No multimodal claim may be shown without:
  - modality coverage statement
  - unresolved modality statement
- [ ] No final-style summary may be shown without:
  - top warning block if heuristics are still placeholders

## Review Note

This TODO intentionally blocks "keep polishing the same misleading surface".

The next repair round should first make the chain **honest**, then make it **strong**.

2026-04-07 addendum:

- the current “front few review points feel wrong” issue on `amd_712` is now traced more precisely
- corpus role is not the main root cause
- the older review-packet builder currently anchors cards in this order:
  - `captioned_asset`
  - `missing_media`
  - `forward`
  - `reaction`
  - `signal`
- this means a sparse-corpus candidate can be semantically useful while still opening on weak first-review cards
- use `state/program_runs/shi_analyzer/round_017/METHOD_REDESIGN_INPUT_20260407.md` as the prerequisite method packet before the next full-chain repair round

2026-04-07 live-run addendum:

- a fresh real run at `state/group_analysis_runs/amd_guanren_group_712742342/run_20260407_174750/` confirms the same corpus can yield on-target analyzer windows
- selected windows `001 / 003 / 008` all land in the expected sparse-corpus territory:
  - `二手史`
  - `多图串搬运`
  - `反应史`
  - `套娃forward包浆 / 视频壳缺本体`
- therefore:
  - `amd_712` itself is not the blocker
  - the misleading surface is still mainly the old review-point/card-anchor layer
- live round note:
  - `state/program_runs/shi_analyzer/round_018/review_resolution.md`

2026-04-08 chain-honesty addendum:

- the first live sparse-fix attempt exposed a real chain bug:
  - model emitted the new sparse-fix fields
  - JSON truncated before closure
  - parser silently fell back
  - artifacts looked superficially valid while the new design was effectively dropped
- this is now explicitly fixed:
  - `benshi_llm_agent` validates sparse-fix contract completeness
  - `run_benshi_group_full_analysis.py` fails fast on invalid sparse-fix contract
- current validating run:
  - `state/group_analysis_runs/amd_guanren_group_712742342/run_20260408_020228/`
- this means the next full-chain blocker is no longer minimum LLM-chain honesty
- the next blocker returns to:
  - review-point quality
  - human feedback integration
  - posterior/policy downstream use
