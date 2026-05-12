# Shi Analyzer Readiness Report

Spec date: 2026-03-27

## Executive Summary

The exporter side is now good enough to stop being the main blocker for the next phase.

The two exports under `C:\Users\Peter\Downloads\AMD+管人` are structurally usable as analyzer input:

- JSONL message records are present and well-formed
- companion manifests are present
- asset states are explicit rather than silently dropped
- forward-heavy content is preserved strongly enough to support early-stage `搬史/吃史` analysis

The biggest conclusion is:

- the repository should now begin the **preprocess + analysis-pack + whole-window report** phase in earnest
- it should **not** keep waiting for a hypothetical zero-missing corpus

Remaining background missing does not block first-phase analyzer work, as long as the analyzer treats:

- direct evidence
- context-only inference
- unknown gaps

as distinct evidence classes.

## Context

This report combines:

- restored design documents under `dev/agents/` and `dev/todos/`
- the current repository phase guidance
- the two exports under `C:\Users\Peter\Downloads\AMD+管人`

Documents used most heavily:

- [AGENTS.md](/d:/Coding_Project/IsThisShit/AGENTS.md)
- [major_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/major_AGENTs.md)
- [process_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/process_AGENTs.md)
- [llm_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/llm_AGENTs.md)
- [Benshi_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/Benshi_AGENTs.md)
- [TODOs.analysis-implementation-plan.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.analysis-implementation-plan.md)
- [TODOs.preprocess.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.preprocess.md)
- [TODOs.llm-analysis.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.llm-analysis.md)

## Documentation Recovery

The previously missing `dev/agents/*.md` and `dev/todos/*.md` files were not actually absent from branch history.

Current finding:

- they were still tracked in `HEAD`
- they had become deleted in the local working tree
- they have now been restored from `HEAD`

This matters because several of those documents define the intended next phase for the analyzer stack, especially:

- `process_AGENTs.md`
- `llm_AGENTs.md`
- `Benshi_AGENTs.md`
- analysis/preprocess TODO files

## Export Audit

### Export A

Files:

- `group_712742342_20260326_232716_568964.jsonl`
- `group_712742342_20260326_232716_568964.manifest.json`

Manifest summary:

- chat: `group 712742342 AMD传说玩家交流群①`
- `record_count = 10299`
- `metadata.source = napcat_fast_history_bulk`
- `forward_detail_count = 37`
- asset summary:
  - `total = 2141`
  - `copied = 1220`
  - `reused = 532`
  - `missing = 389`
  - `error = 0`
- missing breakdown:
  - `qq_expired_after_napcat = 334`
  - `qq_not_downloaded_local_placeholder = 55`

Interpretation:

- structurally healthy
- moderate asset volume
- relatively low missing burden compared with the larger corpus
- good candidate for:
  - control corpus
  - mixed-signal corpus
  - false-positive suppression tests for the future `搬史` analyzer

### Export B

Files:

- `group_763328502_20260326_230718_228507.jsonl`
- `group_763328502_20260326_230718_228507.manifest.json`

Manifest summary:

- chat: `group 763328502 零螔调查中心`
- `record_count = 75729`
- `metadata.source = napcat_fast_history_bulk+napcat_fast_history`
- `forward_detail_count = 541`
- `forward_structure_unavailable_count = 1`
- asset summary:
  - `total = 21484`
  - `copied = 2677`
  - `reused = 8042`
  - `missing = 10765`
  - `error = 0`
- missing breakdown:
  - `qq_expired_after_napcat = 10257`
  - `qq_not_downloaded_local_placeholder = 508`

Interpretation:

- structurally healthy even at large scale
- strongly relevant to `搬史/运史/转运` analysis because:
  - large message volume
  - high forward-detail count
  - rich multimodal traffic
- the missing burden is heavy, but it is explicitly classified as background-only rather than actionable/exporter-bug missing

This is suitable as the primary positive corpus for early-stage `shi` analysis, provided the analyzer keeps uncertainty explicit.

## JSONL Quality

Sampled JSONL records show the expected canonical message fields are present.

Observed keys include:

- `chat_type`
- `chat_id`
- `chat_name`
- `sender_id`
- `sender_name`
- `sender_card`
- `message_id`
- `message_seq`
- `timestamp_ms`
- `timestamp_iso`
- `content`
- `text_content`
- `image_file_names`
- `uploaded_file_names`
- `emoji_tokens`
- `segments`
- `group_id`
- `extra`

This is strong enough for the preprocessing layer described in [process_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/process_AGENTs.md), because:

- canonical message truth is preserved
- structured segment order is preserved
- inline content remains available for text-first indexing
- assets and resource states remain externally inspectable

Observed segment families in sampled records include:

- `text`
- `system`
- `image`
- `reply`
- `emoji`
- `forward`
- `sticker`
- `share`
- `video`
- `file`

This is especially important because the downstream analyzer is expected to reason over:

- repost / relay / forward structure
- system/share context
- media dependence
- missing-media uncertainty

## Manifest Quality

The manifests are structurally useful, but there is one practical compatibility note:

- these exports use the older top-level manifest shape:
  - `schema_version`
  - `chat_type`
  - `chat_id`
  - `chat_name`
  - `metadata`
  - `asset_summary`
  - `missing_breakdown`
  - `assets`
- they do **not** use the newer nested `content_summary` shape

This is not a blocker.

It does mean the analyzer-side import adapter should explicitly support:

1. top-level manifest v1
2. newer `content_summary`-wrapped manifest shape

The adapter should normalize both into one internal corpus manifest model.

## Fit Against Analyzer Design

### Fit Against `process_AGENTs.md`

The exports satisfy the current preprocess phase assumptions well enough:

- input source is exporter JSONL plus companion manifest
- message truth remains independent from chunking
- missing assets are explicit resource states
- image references remain preserved for later feature/vector work
- forward-heavy content still survives as structured content rather than flattened plain text only

This means the next phase should **not** be more exporter surgery by default.

It should be:

- ingest
- preprocess views
- storage/indexing
- retrieval
- analysis pack construction

### Fit Against `llm_AGENTs.md`

The exports are good enough to begin the current intended first-phase LLM workflow:

- choose target group and time scope
- build an `analysis pack`
- run broad whole-window reports
- preserve prompt/run/evidence artifacts
- only later descend into stricter schemas

The exports do **not** need zero missing media for this phase.

They do need:

- direct evidence preserved
- missing media kept explicit
- context-only inference kept separate

Current exporter output is already close enough to support that.

### Fit Against `Benshi_AGENTs.md`

`BenshiMasterAgent` is evidence-first and subculture-aware.

The exports now support Stage A and Stage B well enough to begin:

- Evidence Synthesis
- Benshi Judgment

because they preserve:

- direct text
- system/share/forward structure
- explicit resource gaps
- participant identity signals
- image/sticker/file/video presence

What is still not ready for a final, low-level `BenshiAgent` rollout by default:

- fully trusted multimodal body semantics for every missing asset
- a frozen low-level taxonomy
- exhaustive OCR/caption/image reasoning

So the correct move is:

- begin broad report-first `shi` analysis
- do **not** jump straight to rigid fine-grained taxonomy enforcement

## Readiness Judgment

### Normal

Yes.

The exports are normal from the perspective of this project.

### Usable

Yes.

They are usable as analyzer input now.

### Pleasant / Practical

Mostly yes.

Why:

- JSONL is canonical and easy to ingest
- manifests provide asset-state side channels
- asset directories are present
- missing states are explicit

Main rough edge:

- manifest schema compatibility needs a thin adapter because both old and new summary layouts may exist in the wild

### Final-goal fit for the `shi` analyzer

Yes, with one important nuance:

- they are sufficient for the current **first-phase analyzer architecture**
- they are not a perfect corpus for final multimodal ground truth

That is acceptable because the current analyzer design, per the restored docs, is intentionally:

- report-first
- uncertainty-preserving
- schema-later

## What The Analyzer Should Start Doing Now

The `shi` analyzer should start on these tasks immediately:

### 1. Exporter JSONL + Manifest dual-shape importer

Priority: highest

Implement one importer path that:

- ingests exporter JSONL
- optionally ingests companion manifest
- normalizes both top-level manifest v1 and newer `content_summary` forms

Output:

- canonical corpus records
- explicit asset-state table
- import-run metadata

### 2. Corpus + preprocess ingestion for real positive and control corpora

Priority: highest

Use the two exports differently:

- `group_763328502`
  - primary positive corpus for `搬史/运史/转运` analysis
- `group_712742342`
  - mixed/control corpus for noise suppression and false-positive control

This is valuable because a `shi` analyzer that only sees a positive corpus is likely to overfit.

### 3. Forward-aware evidence synthesis

Priority: high

Because `group_763328502` has:

- `forward_detail_count = 541`

the analyzer should begin by emphasizing:

- forward bundle expansion
- transport pattern detection
- relay/repost chains
- content provenance summaries

This aligns directly with [Benshi_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/Benshi_AGENTs.md), which explicitly cares about:

- `搬史`
- `运史`
- `二手史`
- `外源史`
- `transport pattern`

### 4. Missing-media aware evidence layers

Priority: high

The analyzer should explicitly separate:

- direct observed evidence
- context-only inferred evidence
- unknown blocked evidence

Why:

- `group_763328502` has heavy background missing
- but those missing assets are still informative as **uncertainty load** and **media dependence**
- they must not be silently dropped

### 5. Whole-window and candidate-window report-first analysis

Priority: high

Do not start with a fine-grained hard classifier.

Start with:

- whole-window analysis packs
- bounded candidate windows
- high-level reports
- manual review loop

This is exactly what [llm_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/llm_AGENTs.md) says the current phase should do.

### 6. Negative/control calibration

Priority: medium-high

Before claiming the analyzer “gets 搬史”, test that it does **not** over-detect it in the AMD group.

That means the analyzer should explicitly report:

- uncertainty
- low-value / mixed-value windows
- non-史 chatter

instead of trying to force every window into a `shi` judgment.

## What The Analyzer Should Not Start With

Do not start with these as the primary milestone:

- OCR-first pipelines
- full multimodal image reasoning
- final rigid `BenshiAgent` low-level taxonomy
- GUI/terminal presentation polish
- vector-search perfection before corpus import is stable
- any assumption that missing media must be solved before analysis can begin

Those are later-phase concerns according to the restored design docs.

## Immediate Technical Plan

Recommended near-term execution order:

1. Implement exporter JSONL + manifest compatibility importer
2. Import both `AMD+管人` corpora into canonical corpus storage
3. Build `raw_only` and `raw_plus_processed` analysis profiles
4. Run preprocess with:
   - forward expansion
   - context filtering
   - expired/missing asset inference labels
5. Build first `analysis pack` generator for:
   - whole-window
   - candidate high-signal window
6. Run first broad report-first analysis on:
   - `group_763328502` as positive corpus
   - `group_712742342` as control corpus
7. Review outputs manually before freezing any stronger schema

## Risks

### 1. Manifest schema drift

Risk:

- old top-level manifest and newer `content_summary` manifest may both exist

Mitigation:

- normalize both shapes in the importer

### 2. Overfitting to positive corpora

Risk:

- analyzer learns to call everything `史`

Mitigation:

- use `AMD传说玩家交流群①` as control/mixed corpus

### 3. Missing media treated as silent nulls

Risk:

- analyzer hallucinates confidence where evidence is missing

Mitigation:

- preserve explicit gap states through preprocess and analysis-pack layers

### 4. Jumping too early into fine-grained taxonomy

Risk:

- brittle schema before enough reviewed outputs exist

Mitigation:

- stay report-first, schema-later

## Final Verdict

The exporter has reached the point where it should stop being treated as the main blocker.

These two exports are:

- structurally valid
- analyzable
- strong enough for the current preprocess + analysis-pack + whole-window report phase

The next serious engineering work should now move to the analyzer side:

- canonical ingest
- preprocess views
- retrieval substrate
- report-first `shi` analysis

not another open-ended exporter stabilization loop.
