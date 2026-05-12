# TODOs: BenshiOntologyPack

Spec baseline: 2026-03-19

## Goal

把 `Q群群友史.docx` 中关于：

- 史的原义
- 类型学
- 判准
- 运史官机制
- 当前 popular shi 形态

沉成可被 `BenshiMasterAgent` 直接消费的程序资产。

## P0. 文档与知识底稿

- [x] 将 `Q群群友史.docx` 的核心定义固化为可维护 markdown 底稿
- [x] 维护 `dev/reports/analysis/reference/benshi_local_ontology.md`
- [x] 标注 hard guidance / soft guidance / anti-patterns

## P1. 程序模型

- [x] 新增 `BenshiOntologyPack` 模型
- [x] 新增：
  - `origin_definition`
  - `formation_dimensions`
  - `taxonomy`
  - `quality_rubric`
  - `transport_theory`
  - `popular_forms`
  - `hard_guidance`
  - `soft_guidance`
  - `anti_patterns`

## P2. 接入 BenshiAnalysisPack

- [x] 在 `BenshiAnalysisPack` 中加入 `ontology_pack`
- [x] 在 pack builder 中构建默认 ontology
- [x] 保证 ontology 不依赖外部 LLM 才能生成

## P3. Prompt 接入

- [x] 在 `benshi_prompting.py` 中加入 ontology pack 的压缩版输入
- [x] 明确让模型区分：
  - 史的原义
  - 当前 popular shi 形态
  - 当前窗口实际体现出的成分
- [x] 保证 ontology 注入不会明显推爆 prompt 体积

## P4. 输出与审阅

- [x] 在 review 输出中体现 ontology 已参与判断
- [x] 至少能看到：
  - 当前判断是否引用了原义
  - 是否引用了类型学
  - 是否区分了 popular 形态与本义

## P5. 验收标准

- [x] 单测证明 ontology 已进入 `BenshiAnalysisPack`
- [x] 单测证明 ontology 已进入 prompt payload
- [x] live / smoke 结果中能看到更明确的“原义 vs popular 形态”区分
- [ ] 人工审阅认为：
  - agent 不再只是会吃这一批集中式样本
  - 而是开始按本地 ontology 在判断
