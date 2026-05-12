# Benshi Calibration Rubric

## Evidence Tiers

### Direct Observed Evidence
- Examples: visible text, reply structure, forward nesting, share/system markers, materialized media references
- Default confidence guidance: high
- Weighting rule: may support stable downstream schema candidates

### Context-Only Inference
- Examples: likely interpretation supported by surrounding text, repeated reactions, or bounded-window context
- Default confidence guidance: medium to low
- Weighting rule: keep separate from direct observations and require explicit uncertainty wording

### Unknown / Missing-Media Gaps
- Examples: missing image/video/file semantics, unavailable sticker detail, absent speech payload meaning
- Default confidence guidance: unknown
- Weighting rule: do not convert into pseudo-observed facts; preserve as uncertainty or deferred follow-up

### Adversarial / Motive Hypothesis
- Examples: hostile interpretation of a sender's likely intent, manipulative/social-strategy hypotheses, strongly uncharitable readings grounded in repeated behavior + second-order reactions
- Default confidence guidance: low to medium unless the text and surrounding reactions are unusually explicit
- Weighting rule: allowed, but must remain explicitly hypothetical and must not be presented as direct observation

## Calibration Questions
- Is the cue grounded in direct evidence or only context?
- Would the claim remain true if the missing media turned out to contradict the surrounding text?
- Does the current report separate observation from interpretation clearly enough?

## Future Weighting Guidance
- Weight direct observed evidence above context-only inference
- Weight context-only inference above pure unknowns only when text/context support is repeated and coherent
- Weight adversarial or motive hypotheses below direct observed evidence and never let them masquerade as fact
- Assign the lowest weight to missing-media hypotheses unless later multimodal recovery supplies direct evidence

## Current Stable Observation Dimensions
- `interaction_density`
- `information_density`
- `content_provenance`
- `narrative_coherence`
- `media_dependence`
- `uncertainty_load`
- `topic_type`
- `followup_value`

## Current Soft Role Labels
- `narrative_carrier`
- `relay_forwarder`
- `topic_initiator`
- `noise_broadcaster`
- `question_probe`
- `reaction_echoer`
- `resource_dropper`

## Guardrails
- Do not freeze a final low-level taxonomy from one pilot
- Do not merge inferred media meaning into direct evidence fields
- Do not hide uncertainty just because a report sounds plausible
- When `InferredItems = 0`, do not convert missing-media adjacency into causal explanation
