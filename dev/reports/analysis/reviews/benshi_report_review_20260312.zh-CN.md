# 搬史报告复审 2026-03-12

对应 canonical 英文文件：

- [benshi_report_review_20260312.md](benshi_report_review_20260312.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_analysis_slice_20260327/source_snapshot/benshi_report_review_20260312.md`

## 这份文件在 cleaned slice 里的角色

它是：

- `reviews`
- 对 earlier report 输出的复审总结

它不是：

- 当前规则总法
- 当前执行计划

## 它最稳定的结论

这份 review 里最值得保留的不是逐段评论，而是这些稳定观察维度：

- `interaction_density`
- `information_density`
- `content_provenance`
- `narrative_coherence`
- `media_dependence`
- `uncertainty_load`
- `topic_type`
- `followup_value`

以及这批 soft role labels：

- `narrative_carrier`
- `relay_forwarder`
- `topic_initiator`
- `noise_broadcaster`
- `question_probe`
- `reaction_echoer`
- `resource_dropper`

## 这份 review 里最重要的警告

### 1. missing media 上的因果过度推断

模型很容易从：

- weird question
- image burst
- serious disclosure

这种相邻关系里脑补解释链。

这份 review 的核心提醒是：

- adjacency 不是 explanation

### 2. 从低信息重复行为里推 motive 过头

重复发图可以支持：

- `noise_broadcaster`
- `repetitive_noise`

但不能轻易直接当作事实支持：

- 恶意意图
- 社交操控
- 地位策略

更准确的规则应当是：

- 这些更重的判断**不是永远禁止**
- 但它们只能进入：
  - 二阶推理层
  - 动机假说层
  - 敌意/恶意解释层
- 并且必须同时满足：
  - 有足够充分的直接证据或二阶反应证据
  - 明确写成假说，不伪装成直接观察事实
  - 给出置信度与反证边界

### 3. 先保软标签，不要过早冻结 taxonomy

它最有价值的结论其实是：

- 当前适合的是 free report + stable dimension block + soft role labels
- 还不适合直接冻结终态 schema
