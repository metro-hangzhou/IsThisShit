# Analysis Implementation Plan

## Scope

This plan covers the next execution span from the current exporter/corpus/preprocess baseline to the point where we can manually test:

- a basic data analysis agent
- an expired-content inference agent
- multimodal LLM calls through a user-supplied GPT-5.4-compatible relay

This document is intentionally execution-oriented. It is the bridge between the higher-level roadmap and the next round of parallel implementation work.

## Guardrails

- `raw` / bypass truth must remain intact.
- All preprocessing must write derived views, not mutate source corpus.
- Any message suppression for downstream analysis must be reversible through provenance.
- Expired/missing assets must remain explicit resource states, not be silently dropped.
- LLM providers must remain provider-agnostic at the runtime boundary.
- The local `shi_group_751365230` test set should currently be treated as:
  - `270 image` references fully aligned and analyzable
  - `5 video + 1 file` true expired/missing source objects
  - i.e. structurally usable for analysis, but not a ground-truth corpus for recovered video/file bodies

## Current Local Progress

截至 `2026-03-18`，本地不依赖 LLM 配额的关键接线已经推进到下面这个状态：

- `shi_focus` profile 已经能在真实导出：
  - `C:\\Users\\Peter\\Downloads\\Export+state\\exports\\group_751365230_20260317_215330_708558.jsonl`
  上成功跑通 preprocess smoke。
- 当前真实 smoke 产物位于：
  - `.tmp/shi_preprocess_smoke2/shi_focus_smoke2`
- 这轮 smoke 的结果：
  - `success_count = 6`
  - `error_count = 0`
  - `message_count = 97`
  - `thread_count = 190`
  - `asset_count = 30`
  - `annotation_count = 317`
- `expired_asset_inference_preprocessor` 之前因为 `qq_data_process.__init__ <-> preprocess_context.py` 的循环导入掉出插件列表；
  现在已经恢复，可重新出现在 `available_preprocessor_factories()`。
- `forward_bundle_expander` 之前对真实 exporter JSONL 只会给出：
  - `No forward bundles with expandable structure were found.`
  根因是：
  - `preprocess_context` 丢掉了原始 forward segment 的 `children/forward_depth`
  - `forward_expansion` 又过度依赖标准化好的 `extra.forward_messages`
  这两处现在都已修正。
- 修正后，在同一份真实导出上：
  - `forward_bundle_expander` 成功展开了 `108` 条 forward 外层消息
  - 例如：
    - `7613818789234658313 -> 6 inner messages`
    - `7613818789234658321 -> 7 inner messages`
    - `7613818792012013780 -> 3 inner messages`

### 当前仍待继续收口的点

- `context_filter_preprocessor` 虽然已经真实产生压缩视图，但还需要继续调参，避免把“搬 shi 主线里的边缘说明”过早压成 dev/debug 噪音。
- `forward_bundle_expander` 现在已经能识别并展开真实 forward，但对某些 deeply nested forward 的内层文本仍主要依赖：
  - `message.content` 预览
  - 原始 `children` 结构的保守提取
  还不是“完全重建 inner message 原文”的终局版本。
- `AnalysisService` 虽然已经支持 preprocess view 输入，但还没有针对这份 `shi_focus` 视图跑一轮真正的“基本分析 agent”本地 smoke。

### 新增本地 smoke：`shi_focus -> analysis runtime`

截至 `2026-03-18` 晚间，这条闭环已经在本地真实跑通：

- 先用旧 `PreprocessService` 把：
  - `C:\\Users\\Peter\\Downloads\\Export+state\\exports\\group_751365230_20260317_215330_708558.jsonl`
  导入最小 analysis state：
  - `.tmp/shi_analysis_state`
- 再将 preprocess view：
  - `.tmp/shi_preprocess_smoke2/shi_focus_smoke2`
  作为 `analysis_input`
- 运行：
  - `base_stats`
  - `content_composition`

产物位于：

- `.tmp/shi_analysis_smoke/summary.txt`
- `.tmp/shi_analysis_smoke/compact.json`
- `.tmp/shi_analysis_smoke_full/summary.txt`

#### 当前观察

- 自动时间窗 smoke 已经成功：
  - 选中了 `2026-03-06 00:54:56 -> 2026-03-06 01:29:17`
  - 这是一个高信号、以集中搬 shi forward 爆发为主的窗口
- 全时段 manual smoke 也已成功：
  - `message_count = 1075`
  - `processed_overlay_messages = 66`
  - `annotation_count = 125`
- 这说明：
  - preprocess overlay 已经能进入 analysis materials
  - 但当前 **time-window selection 仍然主要由 raw 材料驱动**

#### 当前边界

- `shi_focus` 目前更像“解释层 / overlay 层”：
  - 能给分析器补 `processed_text / decision_summary / annotations`
  - 但还不会提前主导“应该优先分析哪一段时间窗”
- 因此在 auto 模式下，我们现在看到的是：
  - raw 高信号搬 shi窗口被优先选中
  - preprocess overlay 只在所选窗口内部生效
- 这不算错误，但这是接下来值得继续做的一条增强：
  - 让 `directive-aware preprocess` 有能力参与时间窗偏置或候选窗口排序
- 这条增强的具体设计已经单独落到：
  - `dev/todos/TODOs.analysis-window-selection.md`

## Target Outcome

When this plan is complete, we should be able to:

1. build a corpus from an export
2. build a directive-aware preprocess view
3. run a basic analysis agent on either raw or processed inputs
4. run an expired-asset inference agent with structured context-expansion rounds
5. call a GPT-5.4-compatible multimodal endpoint for image-driven tests
6. save reports, prompts, usage, and evidence artifacts for manual inspection

## Workstream A: Corpus And Preprocess Stabilization

### A1. Corpus contract freeze

- Freeze the first public contract for:
  - `CorpusManifest`
  - `CorpusMessage`
  - `CorpusAsset`
  - `CorpusThread`
- Ensure resource states consistently use:
  - `available`
  - `missing`
  - `expired`
  - `placeholder`
  - `unsupported`
- Add validation checks so malformed corpus output fails loudly.

### A2. Preprocess view loader

- Implement `load_preprocess_view(...)`.
- Make preprocess views first-class runtime inputs, not just files on disk.
- Ensure views retain:
  - source corpus lineage
  - plugin provenance
  - directive snapshot
  - source message/asset references

### A3. Delivery profiles

- Finalize three runtime profiles:
  - `raw_only`
  - `processed_only`
  - `raw_plus_processed`
- Ensure downstream analyzers must declare which profile(s) they support.

## Workstream B: Directive-Aware Filtering

### B1. `context_filter_preprocessor`

Implement the first directive-consuming preprocessor for mixed-purpose groups such as `史数据统计群`.

It must support:

- preserving repost / 搬 shi / media-relay content
- compacting debugging / dev-ops / environment chatter
- annotating suppressed regions with reason labels
- preserving evidence windows around retained target content

### B2. Directive schema refinement

Refine `PreprocessDirective` with the fields most likely to matter in practice:

- `analysis_goal`
- `target_topics`
- `suppress_topics`
- `target_participants`
- `suppress_participants`
- `suppress_message_patterns`
- `suppress_non_target_chatter`
- `prefer_compaction_over_deletion`
- `relevance_policy`
- `noise_handling_mode`
- `preserve_evidence_window`

### B3. Output requirements

For each compacted/suppressed cluster, record:

- source message ids
- reason code
- short summary
- confidence
- whether a nearby evidence window was preserved

## Workstream C: Basic Analysis Agent

### C1. Basic deterministic analysis pack

Build a stable pack builder for first-pass analysis with:

- time-window summary
- participant summary
- topic windows
- tag/profile hints
- media coverage
- recurrence hints
- representative messages

### C2. Basic LLM analysis agent

Create a first real agent for broad analysis rather than only schema smoke:

- high-level content overview
- interaction pattern summary
- participant-role hints
- media dependence and uncertainty reporting
- candidate next-step recommendations

This agent must work on:

- `raw_plus_processed`
- optionally `processed_only` for compact windows

### C3. Artifact requirements

Each run must persist:

- input pack
- prompt text
- model/provider metadata
- report markdown
- compact structured output
- usage json
- evidence refs

## Workstream D: Expired Asset Inference Agent

### D1. Agent contract

This agent is specialized for `expired` / `missing` / `placeholder` assets whose content is no longer directly recoverable.

It must return only structured states:

- `resolved`
- `uncertain`
- `need_more_context`
- `unrecoverable`

### D2. Context request loop

Support iterative requests such as:

- `before_messages`
- `after_messages`
- `same_sender_window`
- `same_asset_occurrences`
- `forward_full_bundle`
- `related_topic_window`

### D3. Runtime budgets

Hard limits must be enforced:

- `max_rounds`
- `max_total_context_messages`
- `max_total_asset_refs`
- `max_runtime_s`

If the budget is exceeded without convergence, the agent must end in:

- `uncertain`
- or `unrecoverable`

### D4. Evidence discipline

The expired-content inference agent must never pretend it saw missing media.

It may use:

- filename
- asset type
- repeated occurrences
- forward context
- surrounding text
- reply structure
- same-sender context
- multimodal captions from surviving sibling assets

It may not fabricate:

- OCR output from expired images
- direct visual/video content claims without supporting evidence

For the current `shi_group_751365230` local test set specifically:

- the `5 video + 1 file` missing assets have already been manually checked in QQ
- they still show a cover or download button, but clicking download reports resource expiry
- therefore downstream analysis should model them as:
  - `context available`
  - `content body unavailable`
  - suitable for contextual inference / weighting, not literal content reconstruction

### D5. Reused-path semantics for downstream analysis

The analysis layer must be compatible with a future exporter optimization where:

- same-content duplicate assets are stored as one physical file
- multiple message/asset references reuse that one exported path

This means downstream preprocessors and analyzers must not assume:

- one exported file path == one unique logical asset reference

Instead they should rely on:

- message ids
- asset ids
- lineage / provenance
- recurrence clusters
- resource state

and treat exported file paths as a materialization detail, not the canonical identity of an analysis object.

## Workstream E: Multimodal Support For Testing

### E1. First-class multimodal inputs

Prepare adapters for:

- image
- gif
- video
- audio
- file

First-stage expectation:

- image captioning support is required
- gif/video/audio/file may initially produce scaffold records or fallback summaries

### E2. Multimodal test harness

Create a small manual harness that can:

- load a corpus/preprocess view
- pick target assets
- call the configured multimodal provider
- save returned captions / summaries / usage

### E3. Relay compatibility

The OpenAI-compatible client must be the primary manual test path for GPT-5.4 relay testing.

Minimum successful test:

- text analysis call succeeds
- image caption call succeeds
- outputs are persisted and referenced back into analysis artifacts

## Benchmark Plan

### Parameter sweep goal

We do not need to chase a globally optimal setting. The practical goal is to find:

- one stable default value
- or a narrow stable range

for GPT-5.4-compatible relay testing across:

- reasoning effort
- temperature
- timeout
- output budget

### First-pass recommended matrix

- `reasoning_effort`
  - `medium`
  - `high`
  - `xhigh`
- `temperature`
  - `0.0`
  - `0.2`
- `timeout_s`
  - `120`
  - `240`
- `max_output_tokens`
  - `800`
  - `1600`
- `repetitions`
  - `2`

### Expanded matrix

- `reasoning_effort`
  - `low`
  - `medium`
  - `high`
  - `xhigh`
- `temperature`
  - `0.0`
  - `0.2`
  - `0.4`
- `timeout_s`
  - `60`
  - `120`
  - `240`
- `max_output_tokens`
  - `800`
  - `1600`

### Benchmark tasks

- `text_analysis_smoke`
- `text_structured_json_smoke`
- `text_long_context_window`
- `image_caption_smoke`

### Benchmark artifact bundle

The benchmark planner should generate:

- `benchmark_manifest.json`
- `benchmark_matrix.json`
- `benchmark_result_schema.json`
- `README.md`

The current entrypoint is:

- `scripts/benchmark_openai_compatible_llm.py`

## Workstream F: LLM Provider Runtime

### F1. Config model

Keep provider configuration provider-agnostic but explicitly support:

- `openai_compatible`
- `deepseek`

### F2. Required runtime fields

- `api_key`
- `base_url`
- `model`
- `proxy_url`
- `temperature`
- `timeout_s`

### F3. Manual operator path

The operator must be able to:

1. edit a local config file
2. set GPT-5.4 relay credentials
3. run the smoke/manual tests without touching source code

### F4. Parameter benchmark scaffold

- Add a dedicated script:
  - `scripts/benchmark_openai_compatible_llm.py`
- The script must support plan generation for parameter sweeps across:
  - `reasoning_effort`
  - `temperature`
  - `timeout_s`
  - `max_output_tokens`
  - optional multimodal/image smoke tasks
- The first implementation may remain `plan-only`, but it must write:
  - benchmark manifest
  - parameter matrix
  - result schema
  - human-readable operator README

### F5. Initial benchmark matrix

Recommended first pass:

- `reasoning_effort`
  - `medium`
  - `high`
  - `xhigh`
- `temperature`
  - `0.0`
  - `0.2`
- `timeout_s`
  - `120`
  - `240`
- `max_output_tokens`
  - `800`
  - `1600`
- repetitions
  - `2`

Expanded sweep for later rounds:

- `reasoning_effort`
  - `low`
  - `medium`
  - `high`
  - `xhigh`
- `temperature`
  - `0.0`
  - `0.2`
  - `0.4`
- `timeout_s`
  - `60`
  - `120`
  - `240`
- `max_output_tokens`
  - `800`
  - `1600`

### F6. Benchmark output contract

The benchmark harness should emit, at minimum:

- `benchmark_manifest.json`
- `benchmark_matrix.json`
- `benchmark_result_schema.json`
- `README.md`

And the execution-phase result format must be able to capture:

- `case_id`
- `task_id`
- `reasoning_effort`
- `temperature`
- `timeout_s`
- `max_output_tokens`
- `duration_s`
- `status`
  - `planned`
  - `ok`
  - `timeout`
  - `transport_error`
  - `parse_error`
  - `validation_error`
- `finish_reason`
- response length
- usage snapshot
- validation flags
- request/response artifact paths

### F7. Benchmark acceptance thresholds

Text smoke:

- success rate `>= 0.95`
- timeout rate `<= 0.05`
- empty-output rate `<= 0.02`
- median latency `<= 35s`
- p95 latency `<= 90s`

Structured JSON smoke:

- success rate `>= 0.90`
- timeout rate `<= 0.05`
- structured parse failure rate `<= 0.10`

Long-context window:

- success rate `>= 0.85`
- timeout rate `<= 0.10`
- median latency `<= 75s`
- p95 latency `<= 150s`

Image caption smoke:

- success rate `>= 0.90`
- timeout rate `<= 0.10`
- non-empty output required

## Workstream G: Test Sequence

### Phase 1. Corpus + preprocess smoke

- build corpus from a real export
- build directive-aware preprocess view
- verify raw/proccessed lineage and view manifest

### Phase 2. Basic analysis agent smoke

- run a broad analysis job on a known window
- verify artifacts and summary quality

### Phase 3. Expired-agent loop smoke

- pick several confirmed expired assets
- verify the agent can:
  - request more context
  - stop at budget
  - output `uncertain` / `unrecoverable` cleanly

### Phase 4. GPT-5.4 multimodal manual test

- configure relay api key / url / model
- run text analysis test
- run image caption test
- store all artifacts

#### 当前进展

截至 `2026-03-18` 晚间，这一步已经完成第一轮真实小样本 smoke：

- 测试脚本：
  - `scripts/llm_multimodal_smoke.py`
- 输入 pack：
  - `dev/testdata/local/shi_group_751365230/multimodal_smoke_pack.zh.json`
- 真实 run 目录：
  - `state/llm_multimodal_smoke/smoke_20260318_204156_310837`
- 使用模型：
  - `gpt-5.4`
- 输出语言：
  - `中文`
- 样本规模：
  - `6` 张图
- 本轮用量：
  - `prompt_tokens = 6279`
  - `completion_tokens = 3346`
  - `total_tokens = 9625`

#### 当前结论

- GPT-5.4 relay 的多模态图像输入已经真实跑通
- 模型能区分：
  - 现实照片/视频截图
  - 拼接图
  - 社媒主页截图
  - 吐槽图
  - 二次元头像/表情图
- 模型当前表现出较好的约束性：
  - 能把“图像事实”和“上下文标签”分开
  - 没有明显把标签直接当成图像事实
- 当前产物副本已放到：
  - `dev/testdata/local/shi_group_751365230/multimodal_medium_review.txt`
  - `dev/testdata/local/shi_group_751365230/multimodal_medium_report.md`

#### 仍待继续的点

- 这轮只覆盖 `6` 张图的小样本，不代表全部 `270 image`
- 还没有做：
  - 多图聚类/相似图分组
  - 图文联合 analysis pack
  - 与 `shi_focus` 时间窗和 recurrence 特征的深度联动

### Phase 5. Combined scenario

- run preprocess with directive
- run basic analysis agent
- run expired-content inference agent
- inspect whether processed view reduces dev/debug noise while retaining repost signals

## Acceptance Criteria

We can consider this stage complete when:

- preprocess views are first-class loadable inputs
- `context_filter_preprocessor` works on mixed-purpose groups
- the basic analysis agent produces stable artifact sets
- the expired-asset inference agent supports structured context expansion
- GPT-5.4-compatible text + image manual tests succeed
- all outputs remain provenance-safe and reversible back to raw message ids

## Immediate Next Parallel Split

Recommended split for the next 6-agent implementation round:

1. preprocess view loader + runtime wiring
2. context filter preprocessor + directive schema refinement
3. basic deterministic pack builder improvements
4. basic analysis agent artifact/report path
5. expired-asset inference context loop
6. multimodal/openai-compatible manual test harness
