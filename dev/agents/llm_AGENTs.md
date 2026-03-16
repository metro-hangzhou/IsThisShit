# llm_AGENTs.md

> Last updated: 2026-03-10
> Scope: LLM-backed analysis generation that sits after preprocessing, retrieval, and analysis-substrate preparation.

## Purpose

This document defines the repository's dedicated LLM analysis layer.

It exists to turn already-prepared analysis materials into:

- high-level human-readable reports
- reusable machine-readable artifacts
- prompt and evaluation material for later schema tightening

This layer is intentionally placed:

- above `qq_data_process`
- inside the broader `qq_data_analysis` phase
- before any later visualizer or presentation program

The visualizer is out of scope here. The only requirement is that this layer must emit stable artifacts that a later visualizer can consume.

## Phase Contract

Current LLM phase goal:

- start abstract
- learn what the model notices
- iterate prompts with small real samples
- only later tighten outputs into structured low-level dimensions

The first-phase product is **not** a fine-grained `BenshiAgent`.

The first-phase product **is**:

- a bounded LLM analysis path over a selected group/friend time window
- an open-ended long-form report
- preserved evidence packs and run metadata for later human review
- enough machine-readable metadata to compare runs and converge toward a schema later

## First-Phase Shape

Default first-phase analysis unit:

- one group/friend time window as a whole

The time window may come from:

- explicit user selection
- substrate-side adaptive selection

But even when the unit is a whole time window:

- do not send the full raw chat history to the LLM
- always compress the window into an `analysis pack` first

The current phase is deliberately exploratory:

- prefer broad abstraction over early rigid classification
- allow the model to describe themes, atmosphere, anomalies, behavior patterns, and candidate directions for deeper analysis
- use manual review on a small number of real samples before freezing any stronger schema

## What The LLM Layer Owns

The LLM layer is responsible for:

- consuming an `analysis pack` prepared by substrate-side logic
- generating a high-level long report
- recording prompt, provider, model, and token-usage metadata
- persisting artifacts for comparison and later schema extraction
- supporting multiple prompt revisions on the same underlying pack

Current first implementation already provides:

- a reusable `AnalysisPack`
- a whole-window long-report analyzer
- prompt versions:
  - `benshi_window_v1`
  - `benshi_window_v2`
- a first text-only missing-media inference stage that keeps:
  - direct observed media evidence
  - context-only gap hypotheses
  - unresolved unknown gaps
  separate inside the saved pack
- saved artifacts for:
  - analysis pack
  - run metadata
  - usage
  - prompt snapshot
  - report body
- replay from a previously saved `analysis_pack.json`

## Current Reviewed Findings

After the first reviewed real-sample window reports (`export1`, `export2`, `export3`), the current stable direction is:

- keep the report-first workflow
- do not freeze a final low-level benshi taxonomy yet
- begin converging on a small set of stable soft dimensions and role labels

Current reviewed stable observation dimensions:

- `interaction_density`
- `information_density`
- `content_provenance`
- `narrative_coherence`
- `media_dependence`
- `uncertainty_load`
- `topic_type`
- `followup_value`

Current reviewed soft participant-role labels:

- `narrative_carrier`
- `relay_forwarder`
- `topic_initiator`
- `noise_broadcaster`
- `question_probe`
- `reaction_echoer`
- `resource_dropper`

Important calibration rule from those reviews:

- when `InferredItems = 0`, the LLM must not invent causal stories about missing media
- time adjacency may be reported as observation, but not upgraded into an explanation for topic shift or user intent

Reference review note:

- `../documents/benshi_report_review_20260312.md`

Current prompt-convergence step:

- `benshi_window_v2` keeps the long report, but now asks explicitly for:
  - `Stable Dimension Block`
  - `Soft Participant Roles`
  while still treating both as soft intermediate labels rather than final taxonomy
- early longer-context validation shows `benshi_window_v2` remains structurally usable on both medium and larger windows, but sparse-user role assignment can still overreach and must keep being reviewed sample by sample
- a first bounded multimodal augmentation path now exists for `benshi_window_v2`:
  - caption a small set of directly available exported images
  - expose them under `Image Caption Evidence`
  - combine those captions with text conservatively as direct evidence

The LLM layer does not own:

- NapCat access
- raw message export
- QQ media hydration
- SQLite or vector-store implementation details
- GUI/CLI presentation logic
- full OCR pipeline, large-scale image captioning, or final multimodal VLM reasoning as a repository-wide default
- final low-level benshi taxonomies

## Input Contract

The LLM must not receive arbitrary raw chat blobs directly.

It must consume an `analysis pack` prepared by the analysis substrate.

Minimum pack contents:

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

Important rule:

- the pack is the truth source for an LLM run
- prompt iteration may change
- pack content should stay replayable

## Output Contract

First-phase output is primarily:

- a human-readable long report

But every LLM run must also emit minimal machine artifacts:

- `analysis_pack.json`
- `llm_run_meta.json`
- `report.txt` or `report.md`
- `usage.json`

Current script-level entrypoint:

- `scripts/run_llm_window_analysis.py`

Recommended additional fields in machine artifacts:

- provider
- model
- prompt version
- chosen time scope
- pack summary
- warnings
- observed dimensions
- candidate axes for later structuring

Important first-phase rule:

- weak evidence is allowed
- strict per-claim evidence binding is not yet mandatory
- but the underlying evidence pool and prompt/run metadata must always be preserved for later audit and refinement

## Provider Rules

Provider policy in this phase is provider-agnostic first.

Meaning:

- keep the public configuration and runtime interfaces generic
- do not hard-code the LLM layer around one provider's response shape

Reference provider currently documented:

- DeepSeek
- `base_url = https://api.deepseek.com`

Also supported now:

- OpenAI-compatible `POST /v1/responses`
- this is the preferred path for custom relay/base-url providers that mirror OpenAI's current text-generation API shape
- note from 2026-03-10 live test: an OpenAI-compatible relay may still expose `/models` successfully while timing out on real generation calls; provider availability must be judged by an actual minimal generation probe, not by `/models` alone
- 2026-03-12 live confirmation: the relay at `http://107.148.225.11:2095/v1` returned a usable `/models` list and accepted multimodal `input_image` requests on `gpt-5.4` through `/v1/responses`

Current repository experience that should be remembered:

- bounded-slice analysis has already produced usable outputs with `deepseek-chat`
- `deepseek-reasoner` can spend too much completion budget on reasoning before emitting useful final content
- current first-pass token estimation is still optimistic; a real whole-window run estimated `2520` input tokens but actually consumed `4739` prompt tokens, so budget checks must be treated as lower-bound guidance rather than hard prediction
- 2026-03-12 longer-context `benshi_window_v2` runs kept the new soft-dimension/soft-role structure stable on both:
  - a `260`-message full-day export1 slice
  - an `842`-message 90-minute export3 slice
- those same 2026-03-12 runs confirmed the estimator is still materially low:
  - export1 v2 long window: estimated `4833`, actual prompt `8496`
  - export3 v2 long window: estimated `4417`, actual prompt `7711`
  - until recalibrated, assume real prompt tokens may land around `1.7x-1.8x` the current estimate on larger v2 runs
- a 2026-03-12 multimodal export1 run with `gpt-5.4` plus `Image Caption Evidence` reached:
  - prompt `9250`
  - completion `5636`
  - total `14886`
  and showed that direct image-caption evidence can materially enrich long reports even before a dedicated benshi agent exists

Network rule for this layer:

- DeepSeek currently uses direct default networking
- do not route DeepSeek through the local external-download proxy unless this is explicitly re-decided later
- current OpenAI-compatible relay testing also uses direct default networking unless a future provider explicitly requires a proxy

## Iteration Strategy

The iteration strategy for this phase is:

1. run a small number of real time-window analyses
2. inspect the long reports manually
3. compare outputs against human expectations
4. adjust prompt wording, pack layout, and report structure
5. only after repeated stability, derive a more formal schema

The current implementation supports this workflow directly by allowing:

- build-from-state execution
- plan-only dry runs
- replay from a saved pack with a new prompt version or provider config

This means:

- free-form exploration first
- semi-structured convergence second
- low-level agent specialization third

Do not invert this order.

## Downstream Direction

The long-term downstream path is:

1. preprocess and retrieval prepare stable materials
2. first-phase LLM emits broad long reports
3. humans review and stabilize useful recurring dimensions
4. later runs become semi-structured
5. specialized agents such as `BenshiAgent` can then consume those stabilized dimensions

The future visualizer should consume saved LLM artifacts rather than forcing the LLM layer to become presentation-specific.

## Guardrails

Keep these rules active in this phase:

- do not send full 12k+ raw histories by default
- record token estimates before remote calls when possible
- treat token estimates as optimistic until the estimator is recalibrated against real usage
- record actual usage after calls
- preserve prompt/config snapshots
- preserve pack snapshots
- treat text-only missing-media inference as secondary evidence only
- do not merge context-only media hypotheses back into canonical observed message fields
- default to alias-safe identity views unless an explicit dangerous override is approved elsewhere
- do not treat first-phase open-ended reports as final truth labels

## Relation To Other Docs

- `AGENTS.md`
  - stable repository-wide engineering rules
- `major_AGENTs.md`
  - phase routing and cross-subsystem orchestration
- `process_AGENTs.md`
  - preprocessing, retrieval, and analyzer-facing boundaries before the LLM layer
- `TODOs.llm-analysis.md`
  - implementation sequencing for this subsystem
