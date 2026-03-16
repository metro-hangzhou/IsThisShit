# Benshi Report Review 2026-03-12

Reviewed reports:

- `state/analysis_runs/benshi_export1/llm_window_group_chat_84123c930f_20260311_230048.report.md`
- `state/analysis_runs/benshi_export2/llm_window_group_chat_91cae08295_20260311_230551.report.md`
- `state/analysis_runs/benshi_export3_strict_causal/llm_window_group_chat_5db2ef9aa4_20260312_152248.report.md`

This note records what now looks stable enough to guide the next prompt/schema iteration without freezing a final low-level taxonomy.

## What Looked Stable Across Samples

### Stable observation dimensions

These dimensions appeared repeatedly across the three reviewed windows and were understandable without needing multimodal OCR/VLM support.

1. `interaction_density`
   - message count
   - sender concentration
   - whether a few users dominate the window

2. `information_density`
   - `low_information`
   - `repetitive_noise`
   - how much of the window is short reactions, image placeholders, or minimal acknowledgements

3. `content_provenance`
   - native in-group discussion
   - nested forwards / relayed outside material
   - link/share driven content

4. `narrative_coherence`
   - is there one clear story line
   - several parallel fragments
   - or mostly noise with only one short high-signal pocket

5. `media_dependence`
   - how much meaning is carried by image/video/file payloads
   - whether the text still stands on its own when media is missing

6. `uncertainty_load`
   - how much of the report must remain `unknown`
   - whether missing media blocks causal claims, topic interpretation, or user-intent judgments

7. `topic_type`
   - technical / hobby / repair discussion
   - relay / gossip / outside-group transport
   - personal-event / personal-status disclosure
   - ambient joke/noise traffic

8. `followup_value`
   - which messages/assets are most worth recovering next
   - whether the best next step is media recovery, wider time window, or user-history review

### Stable participant-role labels

These are not final ontology labels. They are first useful text-side role labels that the reports can name consistently.

- `narrative_carrier`
  - user who carries the most coherent text story in the window
  - strongest in export3 (`user_18b9d9bcd7`)

- `relay_forwarder`
  - user mainly importing outside context through nested forwards or shared external material
  - strongest in export2

- `topic_initiator`
  - user who starts the visible topic branch or provides the first anchor statement

- `noise_broadcaster`
  - user dominating the window through repeated images, very short captions, or repeated low-information posts
  - strongest in export3 (`user_c72d192d7e`)

- `question_probe`
  - user who asks clarifying or provocative questions that reveal topic shifts
  - visible in export2 and export3

- `reaction_echoer`
  - user whose main role is short emotional or alignment responses (`?`, `节哀`, short confirmations)

- `resource_dropper`
  - user sharing files, links, app cards, or reference materials that move the discussion forward
  - visible in export1 and export2

## What The Reports Already Do Well

- They reliably surface high-level window shape instead of drowning in line-by-line chat replay.
- They detect when a window is mostly low-information noise versus when there is a coherent subthread.
- They already separate direct text evidence from missing-media constraints much better than before.
- They produce useful next-step suggestions, especially around which assets or time slices are worth inspecting next.

## Recurring Failure Modes

### 1. Causal overreach around missing media

Even after tightening, the model still likes to drift toward:

- "topic X was triggered by a missing image"
- "user intention was probably Y because of the missing image"

This is better now, but still needs ongoing pressure in the prompt and in review.

### 2. Motive inflation from repeated low-information behavior

Repeated image sends are often enough for:

- `noise_broadcaster`
- `repetitive_noise`
- "possible disruption"

But they are not enough for:

- malicious intent
- deliberate derailment
- social-status strategy

Those stronger claims should remain out of scope unless text evidence is explicit.

### 3. Turning adjacency into explanation

The model often treats this sequence as more explanatory than it really is:

- weird question
- missing image burst
- serious disclosure

Time adjacency is a stable observation dimension.
It is not yet a stable explanation dimension.

## Practical Prompt Direction

Next prompt versions should keep the report broad, but ask more explicitly for:

1. `window_shape`
   - one paragraph on density / coherence / noise

2. `participant_roles`
   - assign only the soft labels above when text evidence is sufficient
   - allow `unclear` if not enough evidence

3. `direct_storyline`
   - the clearest text-native storyline, if one exists

4. `relay_or_transport_pattern`
   - whether the window is mostly native talk, forwarding, or mixed

5. `media_dependence_and_unknowns`
   - what remains blocked by missing assets

6. `next_recovery_targets`
   - specific files or short time ranges worth recovering next

## What Seems Stable Enough For Later Structuring

These now look stable enough to become semi-structured fields later:

- `window_shape`
- `interaction_density_level`
- `information_density_level`
- `content_provenance_mode`
- `media_dependence_level`
- `uncertainty_load_level`
- `primary_storyline_present`
- `primary_storyline_kind`
- `participant_role_candidates[]`

## What Still Looks Too Early

These should still stay out of the next schema freeze:

- hard `BenshiAgent` judgment labels
- final `原生史 / 工业史 / 典中典史 / 外源史 / 二手史` classification from one window alone
- motive labels for repeat image senders
- image-content claims when the image is missing

## Recommended Immediate Next Step

Move the next prompt iteration from "free report only" to:

- free report + stable role block + stable dimension block

But keep the labels soft, reviewable, and explicitly non-final.
