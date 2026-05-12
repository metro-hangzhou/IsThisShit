# 群分布方法规范

**目标**：以 md 插件形式规定如何从已分析窗口的结构层输出多维分布，附带采样与 posterior 状态说明。

**输入**

- `window_runs` 中的 `compact_payload.{shi_component_analysis_layer, judgment_verdicts, unknown_boundary_layer}`。
- 每窗 `multimodal_summary` 和 `image_caption_samples`。
- `sampling_metadata` 包括 total window messages/ coverage ratio。

**核心表达**

1. 统计 component label、family label、reaction verdict、transport verdict、unknown boundaries、multimodal counts。
2. 输出 raw `component_counts` 以及求和后归一化的 `family_ratios`。
3. 引入 `analysis_scope` 字段表示采样窗口覆盖、消息数、权重措施。
4. 明示 `posterior_update_status`/`sampling_status`/`baseline_alignment_status`。

**输出字段**

- `component_counts`
- `component_family_counts`
- `component_family_ratios`
- `reaction_verdict_counts`
- `transport_verdict_counts`
- `unknown_boundary_counts`
- `analysis_scope`（coverage ratio + weighting rule）
- `sampling_status`/`posterior_update_status`/`baseline_alignment_status`
- `heuristic_warning_lines`

**禁止事项**

- 不得润色为“whole-group distribution”或“truth”。
- 不得省略 sampling ratio、heuristic_status、warning block。
- 不得在 riot 其中的 posterity align + counts 里混淆 `baseline context` 与 `posterior update`。

**已知边界**

- 当前分布仅覆盖 selected windows；若 future posterior delta 才能 generalize.
- Current multimodal counts only reflect explicit image/sticker captions.
- Unknown boundary list is exhaustive per window but not across the entire corpus.

**使用说明**

脚本调用时加载此 md，并将 `distribution` JSON + radar 图/markdown 交给 renderer。
每次 artifact 写出之前，先在 md 插件里重新计算 `analysis_scope.coverage_ratio`。
