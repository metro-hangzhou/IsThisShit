# TODOs: BenshiExampleBank

Spec baseline: 2026-03-19

## Goal

建立一套可复用的本地示例库，用于校准：

- 史判断
- 史描述
- 群友口吻
- 接茬能力

## P0. 示例分类

- [x] `good_judgment_examples`
- [ ] `bad_judgment_examples`
- [x] `good_description_examples`
- [ ] `bad_description_examples`
- [x] `good_reply_probe_examples`
- [ ] `bad_reply_probe_examples`
- [x] `negative_templates`

## P1. 当前数据源

- [x] 从 `dev/testdata/local/shi_group_751365230/` 里先抽第一批例子
- [x] 以当前人工审阅产物为主：
  - `benshi_llm_reply_probe_clusters_medium_shi_review.txt`
  - `benshi_llm_reply_probe_clusters_medium_review.txt`
  - `benshi_llm_reply_probe_clusters_medium_cluster_review.txt`
  - `benshi_ontology_smoke_review.txt`

## P2. 例子结构

- [x] 每条例子至少包含：
  - `example_id`
  - `window_or_slice_ref`
  - `input_excerpt`
  - `expected_direction`
  - `good_output`
  - `bad_output`
  - `review_notes`
- [x] 生成 `benshi_example_bank_manifest.json`
- [x] 生成中文人工审阅稿 `benshi_example_bank_review.txt`

## P3. 用途

- [x] 供 prompt few-shot 使用
- [x] 供人工校准使用
- [ ] 供 future distillation / tuning 使用
- [x] 已接入 `BenshiMasterLlmAgent` prompt 参考上下文

## P4. 当前种子基线

- [x] 产出首批种子例子：
  - `good_judgment_examples = 3`
  - `good_description_examples = 3`
  - `good_reply_probe_examples = 1`
  - `negative_templates = 4`
- [ ] 继续补 `bad_judgment_examples`
- [ ] 继续补 `bad_description_examples`
- [ ] 继续补 `bad_reply_probe_examples`
- [ ] 把 ontology anti-patterns 显式映射到例子库
- [ ] 把更多边界例子接入 live smoke 对照验证

## 验收标准

- [x] 至少 1 批集中式样本的高质量例子被整理完成
- [x] 能明显帮助区分：
  - 对路描述
  - 文绉绉废话
  - 泛化过度
  - 脑补过度
- [ ] 能覆盖“原义 vs popular 形态”这条 ontology 边界
