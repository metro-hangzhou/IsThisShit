# Benshi_AGENTs.md

> Last updated: 2026-03-19
> Scope: the repository's first deep-analysis agent for 搬史/吃史 understanding, subculture-aware interpretation, and optional 接茬能力评测.

## Purpose

This document defines the first true deep-analysis agent in the repository:

- `BenshiMasterAgent`

Its job is not just to summarize a chat window.

Its job is to:

- understand what kind of `史` is present
- explain why it counts as `史`
- ground that judgment in direct evidence and context
- recognize 搬史 / 运史 / 二手转运 patterns
- preserve uncertainty when media is missing
- optionally demonstrate that it "gets the joke" by producing a plausible 接茬 or reaction in the same subcultural register

This agent is the first plugin whose target is not generic chat analysis, but a specific QQ-group subculture.

## Non-Goals

This agent is not:

- the canonical truth source
- a replacement for preprocess, retrieval, or analysis substrate
- a pure style-transfer model
- a freeform roast bot with no evidence grounding
- a final fine-tuned persona model in the current phase

In particular:

- do not let "会说抽象话" replace "知道为什么这是史"
- do not let persona tone contaminate evidence fields
- do not let "接得上话茬" be treated as proof unless evidence understanding is already strong

## Architectural Position

Current layering remains:

- exporter
- corpus
- preprocess views
- analysis substrate
- pluggable agents

`BenshiMasterAgent` lives in the pluggable-agent layer and consumes:

- raw references
- preprocess views such as `shi_focus`
- substrate-prepared analysis packs
- optional multimodal evidence packs

It must remain hot-pluggable.

That means:

- no hard dependency from substrate core into the agent
- no agent-specific assumptions baked into canonical message models
- no requirement that every analysis run must invoke this agent

## Design Principle

The agent must separate five things that humans often blur together:

1. `what is present`
   - direct observed text/media/forward structure
2. `what kind of 史 it is`
   - type, provenance, transport mode, density, quality
3. `why it counts as 史`
   - absurdity,错位,包浆, context collapse, resonance
4. `how a heavy-user would react`
   - subculture-aware interpretation
5. `how one might 接这坨史`
   - optional continuation probe

The first three are evidence work.

The fourth is culture interpretation.

The fifth is a capability probe, not the primary truth layer.

## Cultural Baseline

This agent must align with repository-local benshi reference documents under `dev/documents/`.

Current stable cultural signals already present in those docs include:

- `认知落差`
- `语境跨度 / 脱水性`
- `视觉包浆 / cyber-patina`
- `反馈整齐度 / resonance consistency`
- `原生史`
- `工业史`
- `典中典史`
- `外源史`
- `二手史`
- `二阶史`
- `运史官`
- `看后不转`
- `搬史税`

The agent should treat these as local project concepts, not as universal internet ontology.

## Agent Shape

`BenshiMasterAgent` should internally behave like a composite agent with separable stages.

### Stage A: Evidence Synthesis

Produce a grounded evidence block from:

- direct text
- reply chains
- forward/nested-forward structure
- asset recurrence
- share/system markers
- available multimodal captions
- missing-media gaps

Output focus:

- what happened in the window
- who transported what
- where interpretation is blocked

### Stage B: Benshi Judgment

Judge:

- whether the pack materially contains `史`
- whether it is high-value / low-value / mixed / uncertain
- what type of `史` is present
- whether the content is:
  - native in-group generation
  - imported external material
  - repeated transport
  - industrial repetition

This stage must stay calibrated:

- direct observed evidence > context-only inference > unknown gaps

### Stage C: Cultural Interpretation

Explain why it is `史` in terms humans in this subculture would recognize.

Examples of questions this stage should answer:

- where is the absurdity
- where is the错位
- whether this is "原生逆天" or "工业流水线废史"
- whether the fun comes from the content itself or from群友反应
- whether it has "典中典" potential

### Stage D: Register Renderer

Render an outward-facing interpretation in a chosen register.

Important:

- the current target register is not neutral analyst prose
- it should sound like a highly online meme-literate Chinese netizen
- it may carry irreverence, sarcasm, and subcultural shorthand

But:

- it must not fabricate evidence
- it must not rewrite uncertainty into false certainty

### Stage E: Reply Continuation Probe

Optional.

Produce one or more plausible `接茬` candidates that show the model actually understands:

- the joke format
- the implied stance
- the likely follow-up rhythm

This is not mandatory for every run.

It is a useful competence test:

- if the agent can explain the 史 and also接得上话茬 without being out of register, that is strong evidence it really "吃到了" the content

## Output Contract

The agent must emit layered outputs rather than a single undifferentiated blob.

### 1. Structured Evidence Layer

Must remain relatively neutral and auditable.

Suggested fields:

- `agent_name`
- `agent_version`
- `target_window`
- `evidence_summary`
- `direct_observations`
- `context_inferences`
- `missing_media_gaps`
- `transport_pattern`
- `participant_roles`
- `shi_presence`
- `shi_type_candidates`
- `confidence`

### 2. Shi Component Analysis Layer

This layer answers:

- 这坨史主要是由哪些成分堆起来的
- 哪些成分是主成分，哪些只是边角料
- 结构上的发酵剂到底是什么

Suggested fields:

- `definition`
- `component_candidates`
- `dominant_components`
- `transport_components`
- `content_components`
- `component_rationale`
- `confidence`
- `quality_band`

Recommended first-phase component vocabulary:

- `外源史`
- `二手史`
- `工业史`
- `补档返场史`
- `配文史`
- `拼盘史`
- `截图壳子史`
- `群聊切片史`
- `低俗猎奇史`
- `包浆史`
- `单人主导倾倒`
- `套娃 forward`
- `多图串搬运`
- `重复图串/单图回放`
- `视频壳缺本体`

### 3. Shi Description Layer

This layer answers:

- 到底该怎么把这坨史描述对路
- 什么是一句话定义
- 什么写法是对路的，什么写法会写歪

Suggested fields:

- `what_is_shi_definition`
- `one_line_definition`
- `component_breakdown`
- `descriptive_tags`
- `how_to_describe_this_shi`
- `description_axes`
- `good_description_patterns`
- `bad_description_patterns`
- `unknown_boundaries`
- `example_descriptors`

### 4. Cultural Interpretation Layer

Suggested fields:

- `why_this_is_shi`
- `absurdity_mechanism`
- `context_collapse_mechanism`
- `packaging_or_patina_notes`
- `resonance_notes`
- `quality_assessment`
- `classicness_potential`

### 5. Register Layer

Suggested fields:

- `voice_profile`
- `register_constraints`
- `rendered_commentary`

This layer is allowed to be spicy.

It is not allowed to overwrite the structured layer.

### 6. Optional Reply Probe Layer

Suggested fields:

- `reply_probe_enabled`
- `candidate_followups`
- `followup_rationale`
- `followup_confidence`

## Voice / Persona Rules

The desired voice is not "professional analyst".

The desired outward register is closer to:

- 高强度网上冲浪用户
- 梗密度高
- 能理解地狱笑话、政治笑话、平台梗、群聊梗
- 能区分好史、工业史、伪史、转运废料

But the implementation must separate:

- `voice_profile`
- `evidence_profile`

Recommended first voice profile:

- `cn_high_context_benshi_commentator_v1`

It should prefer:

- 中文互联网语感
- 群聊口吻
- 轻蔑、吐槽、抽象感
- but still readable and bounded

It should avoid:

- pretending to have seen missing media
- turning uncertainty into hard claims
- purely literary flourish with no analytical value

## Plugin Boundary

This agent must enter the repository as a hot-pluggable analysis component.

Recommended public shape:

- `BenshiMasterAgent`
- implements the generic analysis-agent interface
- optionally composes helper preprocessors or provider adapters internally

Recommended dependencies:

- `shi_focus` preprocess view
- candidate window metadata
- recurrence summaries
- forward expansion summaries
- optional multimodal evidence snippets

Not allowed:

- direct CLI dependencies
- direct NapCat/runtime dependencies
- assuming a fixed chunking strategy

## Evaluation

The evaluation target is not "sounds smart".

The evaluation target is:

### Core competence

- can it tell what kind of `史` it is looking at
- can it explain why it is `史`
- can it decompose the `史成分`
- can it explain how this window should be described without写歪
- can it separate direct evidence from inference
- can it identify transport mode and 史 quality

### Subculture competence

- can it use the local benshi vocabulary correctly
- can it distinguish:
  - `原生史`
  - `工业史`
  - `典中典史`
  - `外源史`
  - `二手史`
  - mixed/hybrid forms
- can it notice "运史官" behavior and repetition patterns

### Register competence

- does it stop sounding like a formal report writer
- does it sound like someone who actually gets the joke
- can it produce a plausible 接茬 without going out of register

### Calibration competence

- does it keep missing-media claims bounded
- does it avoid motive inflation
- does it avoid treating adjacency as explanation

## Delivery Strategy

Do not jump straight to fine-tuning.

Phase order should be:

1. build stable evidence packs
2. build first structured `BenshiMasterAgent` output
3. add voice rendering as a separate layer
4. add reply-probe as an optional capability test
5. collect reviewed examples
6. only then consider distillation or tuning

## Immediate Implementation Focus

The first repository-usable version should:

- consume a `shi_focus` analysis pack
- emit a structured `benshi_judgment.json`
- emit a structured `shi_component_analysis_layer`
- emit a structured `shi_description_layer`
- emit a stylized `benshi_commentary.txt`
- optionally emit `reply_probe.json`

That is enough to validate whether the agent understands shi at all before chasing larger model-training ambitions.

## Current Baseline

The current concentrated local review set under:

- `dev/testdata/local/shi_group_751365230/`

already provides a first repository baseline for what this agent should learn to say.

Current stable baseline conclusions on that set:

- the window is best described as a `单人主导的高密度外源二手搬运拼盘`
- dominant components are:
  - `外源史`
  - `二手史`
  - `单人主导倾倒`
  - `补档返场史`
  - `拼盘史`
- recurring structural cues include:
  - `套娃 forward`
  - `图串返场`
  - `截图壳`
  - `视频壳缺本体`

The current review artifact that best captures this baseline is:

- `dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_shi_review.txt`

Treat that file as the current manual-review anchor before moving to noisier non-concentrated group windows.
