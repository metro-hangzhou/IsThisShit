# TODOs: Benshi Master Agent

Spec baseline: 2026-03-18

This file tracks the first deep-analysis plugin agent for QQ 搬史 / 吃史 analysis.

It is intentionally later than:

- exporter
- corpus
- preprocess
- basic analysis substrate

But it is now earlier than:

- broader generic persona systems
- model fine-tuning
- large-scale autonomous meme agents

## P0. Definition And Boundaries

- [x] Freeze the public agent name:
  - `BenshiMasterAgent`
- [x] Record that this is the repository's first deep-analysis agent.
- [x] Record that it must remain hot-pluggable.
- [x] Record that it is not the truth source.
- [x] Record that evidence, interpretation, and persona rendering are separate layers.
- [x] Record that "会接史的下话茬" is an optional competence probe, not the primary evidence layer.

## P1. Input Contract

- [x] Define a dedicated `BenshiAnalysisPack` or equivalent extension of current analysis-pack format.
- [x] Include:
  - target metadata
  - chosen time window
  - selected messages
  - forward / nested-forward summaries
  - recurrence summaries
  - participant-role candidates
  - asset summaries
  - missing-media gaps
  - preprocess overlay summaries
- [x] Extend the pack with:
  - `shi_component_summaries`
  - `shi_description_profile`
- [x] Ensure the pack can be built from:
  - raw-only
  - processed-only
  - raw-plus-processed
- [x] Ensure the agent can consume `shi_focus` output without assuming chunk existence.

## P2. Cultural Schema Draft

- [x] Draft first-phase `shi_type_candidates`:
  - `原生史`
  - `工业史`
  - `典中典史`
  - `外源史`
  - `二手史`
  - `混合/二阶史`
  - `未定型`
- [x] Draft first-phase `shi_quality_band`:
  - `高价值`
  - `中价值`
  - `低价值`
  - `工业废史`
  - `不确定`
- [x] Draft first-phase "why this is shi" cues:
  - `认知落差`
  - `语境错位`
  - `脱水性`
  - `包浆/视觉身份`
  - `群体共振`
  - `复读/转运价值`
- [x] Draft first-phase `shi_component` vocabulary:
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
- [x] Keep all labels soft and reviewable, not frozen ontology.

## P3. Agent Output Contract

- [x] Define structured output layer:
  - `direct_observations`
  - `context_inferences`
  - `unknowns`
  - `transport_pattern`
  - `shi_presence`
  - `shi_type_candidates`
  - `shi_quality_band`
  - `confidence`
- [x] Define `shi_component_analysis_layer`:
  - `definition`
  - `component_candidates`
  - `dominant_components`
  - `transport_components`
  - `content_components`
  - `component_rationale`
  - `confidence`
  - `quality_band`
- [x] Define `shi_description_layer`:
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
- [x] Define cultural interpretation layer:
  - `why_this_is_shi`
  - `absurdity_mechanism`
  - `packaging_notes`
  - `resonance_notes`
  - `classicness_potential`
- [x] Define stylized outward commentary layer:
  - `voice_profile`
  - `rendered_commentary`
- [x] Define optional reply-probe layer:
  - `candidate_followups`
  - `followup_rationale`
  - `followup_confidence`

## P4. Voice And Register

- [x] Define first voice profile:
  - `cn_high_context_benshi_commentator_v1`
- [x] Write explicit style constraints:
  - not formal report prose
  - more like a heavily online meme-literate Chinese netizen
  - can use sarcasm, disdain, subcultural shorthand
  - must remain comprehensible
- [x] Write explicit prohibitions:
  - no fabricated media facts
  - no false certainty
  - no drifting into generic literary ranting
- [x] Keep voice rendering as a detachable post-step instead of mixing it into evidence fields.

## P5. Reply-Probe Capability

- [x] Define what counts as a good `接茬` output.
- [x] Require:
  - register fit
  - joke comprehension
  - stance coherence
  - non-generic continuation
- [x] Reject:
  - bland safe continuations
  - tone-deaf moralizing
  - random meme spam with no relation to the pack
- [x] Keep this probe optional in production runs.

## P6. Data And Evaluation Set

- [x] Build the first reviewed local benshi test set from:
  - `dev/testdata/local/shi_group_751365230/`
- [x] Split examples into:
  - high-signal forward-heavy samples
  - industrial/noisy samples
  - mixed debug-noise contamination samples
  - missing-media/expired-media samples
- [x] Add manual reviewer template for:
  - `why_is_this_shi`
  - `what_kind_of_shi`
  - `how_good_is_this_shi`
  - `can_the_agent_get_the_joke`
- [x] Add a compact review artifact for candidate reply probes.
- [x] Add a compact review artifact for:
  - `什么是史`
  - `史成分有哪些`
  - `应该怎么描述这些史`

## P7. Runtime Integration

- [x] Implement `BenshiMasterAgent` under `src/qq_data_analysis/`.
- [x] Implement `BenshiMasterLlmAgent`.
- [ ] Register it through the agent registry rather than hard-coding it into substrate.
- [x] Ensure it can run after:
  - `BaseStatsAgent`
  - `ContentCompositionAgent`
  or independently when the pack already exists.
- [x] Persist outputs under analysis-run directories in stable machine-readable files.

## P8. Prompt / Pack Iteration

- [x] Draft `benshi_master_v1` prompt:
  - evidence first
  - culture interpretation second
  - style render third
- [x] Draft `benshi_master_v1_reply_probe` prompt:
  - only for optional follow-up generation
- [x] Reuse current calibration rules:
  - direct evidence > context inference > unknown
- [x] Add explicit anti-overreach rules for missing media.
- [x] Feed `shi_component_summaries` and `shi_description_profile` into prompt payload.
- [ ] Calibrate reply-probe further against more non-concentrated group windows.

## P9. Local Non-LLM Validation

- [x] Add pack builders and schema validators that can run without remote model access.
- [x] Add snapshot/schema tests for:
  - pack shape
  - output schema
  - voice-profile config
- [x] Add deterministic fixture tests for:
  - forward-heavy windows
  - debug-heavy windows
  - missing-media windows
- [x] Add dedicated tests for:
  - new component-analysis layer
  - new description layer
  - LLM payload/parse compatibility

## P10. LLM Validation

- [x] Run first live `medium` tests on reviewed local shi packs.
- [x] Compare:
  - neutral evidence quality
  - cultural interpretation usefulness
  - voice fit
  - reply-probe competence
- [x] Save:
  - prompt snapshot
  - analysis pack
  - model output
  - reviewer notes
- [x] Keep the first target modest:
  - one or a few dense packs
  - manual review first
  - no immediate large-scale batch run
- [x] Run first cluster-aware multimodal `medium` test with representative images.
- [x] Produce dedicated `shi_review` artifact for manual review.
- [ ] Expand from concentrated dump baseline to non-concentrated real group windows.
- [ ] Add component-distribution output across multiple windows.

## P11. Future Distillation Path

- [ ] If prompt-based runs become stable, define a reviewed example bank.
- [ ] Separate:
  - `evidence examples`
  - `shi judgment examples`
  - `voice rendering examples`
  - `reply probe examples`
- [ ] Do not start fine-tuning until reviewed examples are good enough to support real calibration.

## Open Questions

- [ ] Should `shi_quality_band` be scalar, ordinal, or tag-based?
- [ ] How much persona spice is too much before evidence quality drops?
- [ ] Should reply-probe outputs be one-liners only, or allow short multi-turn continuations?
- [ ] Should `典中典潜力` stay descriptive or become a scored dimension later?
- [ ] When aggregating across multiple windows, should `shi_component_distribution` weight by:
  - message count
  - transport density
  - media density
  - or reviewer-confirmed representative value?
