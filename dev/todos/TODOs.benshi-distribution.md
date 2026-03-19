# TODOs: Benshi Distribution

Spec baseline: 2026-03-19

## Goal

在集中式搬史样本上先建立：

- 史成分分布
- 搬运结构分布
- 包装层分布

作为后续非集中式群聊的对照基线。

## P0. 分布维度

- [x] `shi_component_distribution`
- [x] `transport_pattern_distribution`
- [x] `packaging_distribution`
- [x] `uncertainty_distribution`

## P1. 首批样本

- [x] 基于 `dev/testdata/local/shi_group_751365230/`
- [x] 先从当前集中式 `49` 条 canonical 样本出结果
- [x] 同时纳入 `147` 条 occurrence 统计和当前选窗结果

## P2. 输出形态

- [x] 结构化 JSON
- [x] 中文人工审阅稿
- [x] 能指出：
  - 主成分
  - 次成分
  - 返场/套娃/图串等搬运结构
- [x] 已生成：
  - `benshi_distribution_baseline.json`
  - `benshi_distribution_review.txt`
- [x] 已接入 `BenshiMasterLlmAgent` prompt 参考上下文

## P3. 后续扩展

- [ ] 等非集中式群聊数据到位后，生成同口径对照结果
- [ ] 支持比较：
  - 集中式 vs 非集中式
  - 高密度搬运窗 vs 混合闲聊窗
- [ ] 补更细的 family-level / subtype-level 归并
- [ ] 把 image cluster 结果正式并入长期分布口径

## 验收标准

- [x] 当前集中式样本能产出稳定分布结果
- [x] 结果可用于后续 prompt / ontology / example bank 校准
