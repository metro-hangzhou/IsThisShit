# Analysis Window Selection And `shi_focus` Bias

## Purpose

This note turns the earlier discussion into a concrete implementation target for
manual review.

The goal is not to replace the current adaptive window selector. The goal is to
keep the current raw high-signal selector, then add a second-stage rerank when a
directive-aware preprocess view such as `shi_focus` is available.

In short:

- first pick candidate windows from raw substrate signals
- then rerank those candidates using task-aware preprocess evidence
- then record exactly why the final window was chosen

## Current State

### 1. What already works

- `AnalysisSubstrate._resolve_time_window(...)` already supports:
  - explicit manual range
  - `auto_adaptive`
- `auto_adaptive` currently relies on:
  - `_sessionize(...)`
  - `_window_signal_score(...)`
- this selection is explainable today because the chosen window already records:
  - `signal_score`
  - raw notes such as `messages=...`, `senders=...`, `rich_context=...`

### 2. What `shi_focus` currently does

`shi_focus` is currently an overlay/explanation layer, not a selection driver.

That means:

- raw messages are loaded first
- the time window is chosen from raw sessions
- preprocess overlays are only applied after the window is already selected

### 3. Real local evidence from the current smoke

On the real `group_751365230` sample:

- `auto_adaptive` selected:
  - `2026-03-06 00:54:56+08:00 -> 2026-03-06 01:29:17+08:00`
- that window is already useful because it contains the concentrated shi/forward dump
- but the general mechanism still remains:
  - raw chooses first
  - preprocess only explains afterward

On the full-range smoke:

- preprocess overlays clearly exist and are useful
- but they do not yet influence candidate selection

## Why This Is Worth Doing

For mixed-purpose groups, raw high-signal selection is necessary but not
sufficient.

Example for `史数据统计群`:

- some windows are high-signal because they contain:
  - forward bursts
  - repost chains
  - repeated assets
- some other windows are also high-signal because they contain:
  - debugging bursts
  - `/watch` / `/export` discussions
  - NapCat / OneBot troubleshooting

Without task-aware rerank, the selector may still choose a window that is
"important" in general, but not the most useful for the current analysis goal.

## Design Principle

Do not hard-switch from raw selection to preprocess selection.

Use a two-stage model:

### Stage A: Raw Candidate Generation

Keep the current substrate behavior:

- split all target messages into bounded sessions
- score them using `_window_signal_score(...)`
- sort by raw signal
- keep the top `N` candidate windows

This preserves:

- current behavior for generic analysis
- explainability
- compatibility with prior AGENT/TODO decisions

### Stage B: Directive-Aware Candidate Rerank

Only after Stage A, rerank the top `N` candidates using preprocess evidence.

This is where `shi_focus` enters.

The second-stage score should not replace raw score entirely. It should produce:

- `raw_signal_score`
- `directive_bias_score`
- `final_selection_score`

Recommended formula for the first implementation:

```text
final_selection_score =
  raw_signal_score
  + directive_bias_score
```

Where `directive_bias_score` is bounded and cannot swamp the raw score.

Recommended first bound:

- clamp `directive_bias_score` to `[-12.0, +12.0]`

## Candidate Window Bias Inputs

### Positive inputs

These should boost a candidate when the active profile is `shi_focus`.

#### 1. Forward density

Boost when the candidate contains:

- many `forward` segments
- many expanded forward bundles
- deeper nested forward structures

Reason:

- concentrated shi/repost activity is usually forward-heavy

#### 2. Asset recurrence density

Boost when the candidate contains:

- repeated image stems
- repeated forward bundles
- repeated repost-like assets/messages

Reason:

- recurrence is one of the strongest "搬 shi / 倒 shi / 重复传播" signals

#### 3. Target-like message ratio

Boost when `context_filter_preprocessor` indicates many messages are:

- retained
- target-like
- not marked as suppressed noise

Reason:

- this means preprocess agrees the window is aligned with the directive goal

#### 4. Signal media mix

Boost when the candidate contains higher density of:

- `forward`
- `image`
- `video`
- `file`

Reason:

- the current shi workload is materially multimodal

#### 5. Expired or missing asset context

Boost when the candidate includes:

- expired/missing assets with preserved surrounding context

Reason:

- these are still important to downstream shi analysis and reverse inference

### Negative inputs

These should down-rank a candidate under `shi_focus`.

#### 1. Suppressed-noise ratio

Penalty when many messages are compacted as:

- `strict_focus_non_target`
- `low_signal_chatter`
- `runtime_debug`
- `cli_workflow`
- `dev_ops`
- `analysis_dev`

#### 2. Debug keyword concentration

Penalty when the window has dense mentions of:

- NapCat
- OneBot
- `/watch`
- `/export`
- QR / login / proxy / branch / commit / benchmark

This should be weaker than the preprocess-derived penalty so we do not double
count too aggressively.

#### 3. Debug attachment density

Penalty when the window is rich in debug-file-like payloads such as:

- logs
- manifests
- summaries
- startup captures
- exported zip files used for troubleshooting

#### 4. Low-value operational chatter

Penalty when the window is dominated by short back-and-forth operational chatter
with weak media or repost evidence.

## `shi_focus` Rerank Rules

The first implementation should only activate directive-aware rerank when:

- a preprocess input is present
- and the directive/view kind is one of:
  - `shi_focus`
  - `meme_focus`
  - future explicit repost-focused profiles

For generic jobs, keep the current raw selector unchanged.

### Recommended first-pass bias recipe

For each candidate window:

1. start from `0.0`
2. add:
   - `+2.0` if `forward_bundle_count` is meaningfully above baseline
   - `+2.0` if `nested_forward_count` is above baseline
   - `+1.5` if `recurrence_cluster_density` is above baseline
   - `+1.5` if `retained_target_ratio` is high
   - `+1.0` if `expired_context_hits > 0`
   - `+1.0` if multimodal asset mix is rich
3. subtract:
   - `-2.0` if suppressed-noise ratio is high
   - `-1.5` if debug keyword density is high
   - `-1.5` if debug attachments dominate
   - `-1.0` if low-value chatter ratio is high
4. clamp into `[-12.0, +12.0]`

This should stay intentionally conservative.

## Required Rationale Output

The chosen window must record not just the final numbers, but why the bias was
applied.

Recommended rationale structure:

```text
auto-adaptive selected raw candidate #2 and reranked it with shi_focus bias
(raw_signal_score=34.25; directive_bias_score=+5.50; final_selection_score=39.75;
raw_notes=messages=103, senders=6, rich_context=..., signals=forward_burst/image_heavy;
bias_notes=forward_density_boost=+2.0, recurrence_boost=+1.5,
target_ratio_boost=+1.5, debug_penalty=-0.5, suppressed_noise_penalty=0.0)
```

This keeps the selector:

- explainable
- replaceable
- auditable during manual review

## Guardrails

### 1. Never hard-delete candidates due to preprocess alone

Rerank candidates. Do not silently filter them out.

Why:

- debugging windows can still matter as evidence
- hard filtering makes mistakes harder to detect

### 2. Do not let preprocess become the new truth source

The preprocess layer provides:

- hints
- overlays
- compression
- annotations

It must not redefine the underlying raw chat truth.

### 3. Keep manual range behavior unchanged

If the user explicitly sets a manual time range:

- do not apply automatic rerank
- only annotate afterward

### 4. Keep the bias profile-specific

Do not globally apply `shi_focus` penalties to all analyses.

## Implementation Touchpoints

### Primary file

- `src/qq_data_analysis/substrate.py`

### Functions likely to change

#### `_resolve_time_window(...)`

Current role:

- choose manual/full/auto adaptive window

Next role:

- generate raw top-`N` session candidates
- rerank them if a compatible preprocess profile is present

#### `_sessionize(...)`

Current role:

- produce bounded session groups

Likely unchanged structurally.

#### `_window_signal_score(...)`

Current role:

- compute raw signal score from message/session features

Keep this function as the raw score source.

Do not overload it with directive logic.

#### New helper: `_candidate_window_bias_score(...)`

Proposed new helper:

- consumes:
  - candidate messages
  - preprocess overlay context
  - directive metadata
- returns:
  - `bias_score`
  - `bias_notes`

#### New helper: `_collect_window_overlay_stats(...)`

Proposed new helper:

- counts overlay-derived signals inside a candidate window
- examples:
  - retained target ratio
  - suppressed noise ratio
  - recurrence hit count
  - forward expansion density
  - expired asset context hits

### Supporting files

- `src/qq_data_analysis/preprocessors/context_filter.py`
  - reuse labels and cluster semantics
- `src/qq_data_process/preprocess_profiles.py`
  - read profile metadata such as `shi_focus`
- `src/qq_data_analysis/models.py`
  - may need a small extension if we want structured bias details in `ResolvedTimeWindow`

## Local Validation Plan

### Test 1: Current shi sample

Input:

- real `group_751365230` export
- `shi_focus` preprocess view

Expected:

- the current concentrated repost/forward dump remains highly ranked
- rationale includes explicit `shi_focus` bias notes

### Test 2: Debug-heavy window

Construct or locate a high-signal debug/dev window in the same group.

Expected:

- it may still appear in raw top-`N`
- but should be reranked lower than the concentrated shi dump

### Test 3: No preprocess view

Run the same analysis without preprocess input.

Expected:

- selection behavior remains identical to current raw auto-adaptive logic

### Test 4: Manual range

Provide an explicit manual range.

Expected:

- no rerank is applied
- rationale remains manual

## Review Checklist

When reviewing this design, the main questions are:

- does `shi_focus` bias help pick the right windows without hiding evidence?
- are the positive signals aligned with actual shi/repost behavior?
- are the negative signals too aggressive for mixed-purpose groups?
- is the rationale detailed enough for manual audit?
- is top-`N` rerank safer than direct preprocess-driven replacement?

## Recommended Next Coding Step

Implement the rerank as a narrow enhancement, not a substrate rewrite:

1. keep `_window_signal_score(...)` unchanged
2. add top-`N` candidate collection in `_resolve_time_window(...)`
3. add `_candidate_window_bias_score(...)`
4. add rationale output with raw + bias notes
5. run local smoke on `group_751365230`
