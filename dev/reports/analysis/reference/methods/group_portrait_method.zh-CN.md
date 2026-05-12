# 群画像方法规范

**目标**：提供一个可热插拔的群画像插件规范，输入分析窗级结构化摘要，输出明确可追踪的画像结论与警示。

**输入**

- `analysis_window_runs`：每个窗口的 `judgment_verdicts`、`component_candidates`、`reaction_summary` 等结构化层。
- `distribution_context`：当前先验/baseline（例如 `shi_group_751365230`）的 component/family 回声。
- `multimodal_summary`：本窗口的 `image_caption_samples`、`visual_ref_count`、`missing_media_gaps`。
- `sampling_metadata`：窗口数量、覆盖消息数、抽样比例、选择策略说明。

**硬规则**

1. 群画像必须从多窗口聚合，而不是单条窗口 os  的结论。
2. 每条输出都要注明 `implementation_status`、`known_gaps`、`scope_statement`。
3. 所有 `component_family` 与 `reaction_verdict` 必须同时暴露 raw count 和 normalized ratio。
4. 以 `heuristic_warning` 块形式呈现“占位属性”—比如 `sampled`, `prototype`, `not posterior confirmed`。

**输出字段**

- `scope_statement`：覆盖比例/窗口采样说明。
- `component_summary`：family counts + ratios。
- `reaction_summary`：reaction verdict list + representative patterns。
- `transport_summary`：transport verdict counts + dominance hints。
- `implementation_status`：例如 `prototype_sampled_window_aggregation`。
- `known_gaps`：采样、多模态、posterior 缺失等声明。
- `heuristic_warning_block`：具体文本说明不能当 final truth。

**禁止事项**

- 不得在画像中隐去 sampling/heuristic 标签。
- 不得把 single-window verbatim 结论宣称为全群真相。
- 输出中不得直接用 `final`/`complete`/`production` 描述仍在试验中的结构。

**已知边界**

- 目前只可视为 `window-slice portrait`；若未来有 posterior 更新再提升版本号。
- 多模态仅收集明确定向 image/sticker caption，video/file 仍是 structural evidence。
- 画出的雷达/分布图始终基于 `component_family_counts` 计数非比率。

**实施说明**

将此 md 插件加载到全链路脚本时：

1. 传入 `analysis_window_runs`、`distribution`、`sampling`。
2. 按照 `group_portrait_method` 模型生成 markdown + json summary。
3. 让脚本写入 `group_profile.md`、`group_distribution.json` 时引用此模板生成结构化输出并附 warning block。
