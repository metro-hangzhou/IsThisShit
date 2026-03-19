# Technical Roadmap

> Last updated: 2026-03-19
> Scope: 记录、统筹、规划、指引当前项目的技术路线，并为后续开发、测试、文档与分支操作提供统一入口。

## 1. 文档目的

这份文档不是某一个子系统的说明书。

它的职责是：

- 记录当前项目处于哪一阶段
- 记录已经完成的关键工作
- 指引下一步主线开发应该往哪里走
- 把根目录主文档、`dev/agents/`、`dev/todos/`、`dev/documents/` 的关键文件串起来
- 为后续新增数据集、分析器、Agent、测试与分支归档提供统一导航

## 2. 当前总路线

当前主线可以压成 5 层：

1. 上游数据抓手
   - NapCat / OneBot / exporter
2. 语料与预处理底座
   - corpus
   - preprocess view
   - `shi_focus`
3. 分析基座
   - analysis substrate
   - candidate window selection
   - directive-aware rerank
4. 深度分析 Agent
   - `BenshiMasterAgent`
   - `BenshiMasterLlmAgent`
5. 后续扩展
   - `BenshiOntologyPack`
   - `BenshiExampleBank`
   - 成分分布 / 搬运结构分布
   - 非集中式群聊实战验证

## 3. 当前阶段判断

截至 `2026-03-19`，项目已经越过“只是导出器”的阶段。

当前主线阶段是：

- exporter 已可作为稳定上游
- preprocess/runtime 已能围绕 `shi_focus` 产出专项视图
- `BenshiMasterAgent` 已可对集中式搬史样本做：
  - 史判断
  - 史成分分析
  - 史描述层
  - 群友口吻渲染
  - 可选 reply probe

当前最主要的未完成工作是：

- 继续扩写和校准 `BenshiOntologyPack`
  - 目前已接入第一版程序模型与 prompt payload
  - 但还需要继续补 hard guidance / soft guidance / anti-patterns 的示例化表达
- 扩写 `BenshiExampleBank`
  - 当前已有首批种子例子，但负例和边界例子仍然偏少
- 扩写集中式样本的成分分布 / 搬运结构分布
  - 当前已有第一版基线，但还需要更细 family/subtype 归并
- 再用非集中式群聊窗口做实战校准

## 4. 里程碑日志

### [2026-03-06][001] 导出器与 NapCat 公共接口基线冻结

- 根规则以 [AGENTS.md](../../AGENTS.md) 为准
- NapCat 作为外部网关，不碰内部注入逻辑
- `JSONL + assets bundle + manifest` 成为正式导出基线

### [2026-03-14][002] 导出 fidelity / 运行分支 / NapCat 研究链成型

- NapCat/媒体恢复/forward 媒体规则被写入：
  - [NapCat_AGENTs.md](../../NapCat_AGENTs.md)
  - [NapCat.media_AGENTs.md](../agents/NapCat.media_AGENTs.md)
- exporter 的历史问题、性能、取证和保真链开始拆到专项 TODO

### [2026-03-17][003] 真实远程测试与集中式搬史样本确认

- 从朋友机器取回真实导出与 state
- 明确：
  - 正式缺失集中在 `video/file`
  - `image` 资产在当前集中样本中最终可对齐完整
- 项目内建立本地集中式搬史测试集：
  - `dev/testdata/local/shi_group_751365230/`

### [2026-03-18][004] preprocess / analysis substrate / shi_focus 接线完成

- `shi_focus` preprocess view 真实跑通
- `context_filter / forward_expansion / asset_recurrence / expired_asset_inference` 进入可用状态
- analysis runtime 开始能吃 preprocess view
- auto window selection 开始支持 `shi_focus` 偏置重排

### [2026-03-18][005] BenshiMasterAgent 第一版成型

- 新增：
  - `BenshiAnalysisPack`
  - `BenshiMasterAgent`
  - `BenshiMasterLlmAgent`
- 输出分层稳定为：
  - evidence
  - cultural interpretation
  - register
  - reply probe

### [2026-03-19][006] 史成分层 / 史描述层落地

- `shi_component_analysis_layer`
- `shi_description_layer`
- 集中式搬史样本上已能较稳定回答：
  - 什么是史
  - 史成分有哪些
  - 应该怎么描述这些史

### [2026-03-19][007] Ontology 阶段正式启动

- 明确下一主线不再是“继续堆几轮 prompt”
- 而是：
  - `BenshiOntologyPack`
  - `BenshiExampleBank`
  - `shi component / transport distribution`
  - 非集中式群聊实战对照

### [2026-03-19][008] 路线文档 / ontology 接线 / 本地 smoke 验证

- 新增：
  - [technical-roadmap.md](technical-roadmap.md)
  - [benshi_local_ontology.md](benshi_local_ontology.md)
  - [TODOs.benshi-ontology-pack.md](../todos/TODOs.benshi-ontology-pack.md)
  - [TODOs.benshi-example-bank.md](../todos/TODOs.benshi-example-bank.md)
  - [TODOs.benshi-distribution.md](../todos/TODOs.benshi-distribution.md)
- `BenshiOntologyPack` 已接入：
  - `BenshiAnalysisPack`
  - `BenshiMasterAgent`
  - `Benshi` prompt payload
- 本地验证完成：
  - `tests/test_benshi_master_agent.py` 通过
  - 本地 `run_benshi_local_smoke.py` 已在真实 `shi_focus` 视图上跑通

### [2026-03-19][009] ExampleBank 种子基线 / 分布基线落地

- 新增种子资产生成链：
  - `src/qq_data_analysis/benshi_seed_artifacts.py`
  - `scripts/build_benshi_seed_artifacts.py`
  - `tests/test_benshi_seed_artifacts.py`
- 在集中式样本上生成：
  - `benshi_example_bank_manifest.json`
  - `good_judgment_examples.jsonl`
  - `good_description_examples.jsonl`
  - `good_reply_probe_examples.jsonl`
  - `negative_templates.jsonl`
  - `benshi_example_bank_review.txt`
  - `benshi_distribution_baseline.json`
  - `benshi_distribution_review.txt`
- 当前集中式基线已经具备：
  - 例子库种子
  - 成分/搬运结构基线
  - 图像簇分布摘要

### [2026-03-19][010] ExampleBank / Distribution prompt 接入与 live smoke

- `BenshiMasterLlmAgent` 现已支持显式注入：
  - `example_bank_manifest_path`
  - `distribution_baseline_path`
- `benshi_prompting.py` 已把：
  - `ontology_pack`
  - `example_bank_context`
  - `distribution_baseline_context`
  作为同一轮 prompt 参考上下文输入
- `run_benshi_live_llm_smoke.py` 现已支持：
  - `--dataset-dir`
  - `--example-bank-manifest`
  - `--distribution-baseline`
  并会在审阅稿中显式写出启用状态
- 新一轮 live 审阅产物：
  - `benshi_llm_reply_probe_clusters_examples_dist_medium_review.txt`
  - `benshi_llm_reply_probe_clusters_examples_dist_medium_shi_review.txt`

## 5. 当前主线任务

当前主线开发按优先级排序：

1. `BenshiOntologyPack` 扩写
   - 从 `Q群群友史.docx` 继续补 hard guidance / soft guidance / anti-patterns
2. `BenshiExampleBank` 扩写
   - 在已有种子上继续补负例、边界例子、ontology 映射
3. `成分分布 / 搬运结构分布` 扩写
   - 从首版基线继续补 family/subtype 归并和对照口径
4. `非集中式群聊实战`
   - 用未来拿到的新窗口做校准和反例验证

## 6. 当前可用测试/审阅产物

### 集中式搬史本地测试集

- `dev/testdata/local/shi_group_751365230/`

关键人工审阅文件：

- `manual_review_hierarchy.txt`
- `benshi_llm_reply_probe_medium_review.txt`
- `benshi_llm_reply_probe_clusters_medium_review.txt`
- `benshi_llm_reply_probe_clusters_medium_cluster_review.txt`
- `benshi_llm_reply_probe_clusters_medium_shi_review.txt`

### 当前最重要的审阅锚点

如果只看一份，优先看：

- `dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_shi_review.txt`
- `dev/testdata/local/shi_group_751365230/benshi_example_bank_review.txt`
- `dev/testdata/local/shi_group_751365230/benshi_distribution_review.txt`

它是当前“什么是史 / 史成分 / 怎么描述史”的第一版人工审阅基线。

## 7. 工作流规则

### 分支规则

以 [git_branching_plan.md](git_branching_plan.md) 为准：

- `full-dev`
  - 默认开发分支
  - 只本地提交，不默认推远端
- `main`
  - 发布/归档/验证分支
- `runtime`
  - 运行面/发布验证分支

### 文档规则

- 新 TODO 默认放：
  - `dev/todos/`
- 新 AGENT handbooks 默认放：
  - `dev/agents/`
- 较长说明、路线、ontology、review 归档默认放：
  - `dev/documents/`
- 根目录只保留总入口和高信号总则

### 测试规则

- 优先本地 deterministic / unit tests
- LLM live test 只在：
  - prompt/pack 有关键变化
  - 或需要人工审阅真实输出时
  才进行
- 所有关键 live run 都应保留：
  - output json
  - human report
  - review txt
  - run summary

### 默认推进风格

- 除非用户明确要求逐步确认或暂停，大步推进优先于碎步往返
- 默认先分析“下一阶段的大方向都有哪些可以一起做”
- 然后把不冲突的任务打包成一轮并发推进
- 当用户已经授权子代理并发时，优先把探索、实现、脚本升级、测试校准拆成多线程同时做

## 8. 文档路由总表

### 8.1 根目录总则

- [AGENTS.md](../../AGENTS.md)
  - 仓库级工程规则、导出契约、NapCat 公共接口约束
- [NapCat_AGENTs.md](../../NapCat_AGENTs.md)
  - NapCat 主索引与媒体/运行时路由
- [TODOs.md](../../TODOs.md)
  - 根级总 TODO 入口

### 8.2 `dev/agents/` 专项手册

- [INDEX.md](../agents/INDEX.md)
  - AGENT 手册总索引
- [major_AGENTs.md](../agents/major_AGENTs.md)
  - 仓库阶段、权威顺序、总编排
- [CodeStrict_AGENTs.md](../agents/CodeStrict_AGENTs.md)
  - 严格生产硬化视角
- [process_AGENTs.md](../agents/process_AGENTs.md)
  - preprocess/corpus/chunk/index 规则
- [llm_AGENTs.md](../agents/llm_AGENTs.md)
  - LLM/report-first 分析政策
- [Benshi_AGENTs.md](../agents/Benshi_AGENTs.md)
  - 搬史/吃史深度分析 Agent 规则
- [NapCat.docs_AGENTs.md](../agents/NapCat.docs_AGENTs.md)
- [NapCat.source_AGENTs.md](../agents/NapCat.source_AGENTs.md)
- [NapCat.community_AGENTs.md](../agents/NapCat.community_AGENTs.md)
- [NapCat.media_AGENTs.md](../agents/NapCat.media_AGENTs.md)

### 8.3 `dev/todos/` 当前主线与专项 TODO

总索引：

- [INDEX.md](../todos/INDEX.md)

当前主线强相关：

- [TODOs.analysis-platform-roadmap.md](../todos/TODOs.analysis-platform-roadmap.md)
- [TODOs.analysis-implementation-plan.md](../todos/TODOs.analysis-implementation-plan.md)
- [TODOs.analysis-window-selection.md](../todos/TODOs.analysis-window-selection.md)
- [TODOs.analysis-agents.md](../todos/TODOs.analysis-agents.md)
- [TODOs.benshi-master-agent.md](../todos/TODOs.benshi-master-agent.md)
- [TODOs.benshi-ontology-pack.md](../todos/TODOs.benshi-ontology-pack.md)
- [TODOs.benshi-example-bank.md](../todos/TODOs.benshi-example-bank.md)
- [TODOs.benshi-distribution.md](../todos/TODOs.benshi-distribution.md)
- [TODOs.preprocess.md](../todos/TODOs.preprocess.md)
- [TODOs.llm-analysis.md](../todos/TODOs.llm-analysis.md)
- [TODOs.rag.md](../todos/TODOs.rag.md)

上游与运行侧支撑：

- [TODOs.export-optimization.md](../todos/TODOs.export-optimization.md)
- [TODOs.export-performance.md](../todos/TODOs.export-performance.md)
- [TODOs.export-fidelity.md](../todos/TODOs.export-fidelity.md)
- [TODOs.export-forensics.md](../todos/TODOs.export-forensics.md)
- [TODOs.export-cli.md](../todos/TODOs.export-cli.md)
- [TODOs.napcat-research.md](../todos/TODOs.napcat-research.md)
- [TODOs.production-review.md](../todos/TODOs.production-review.md)
- [TODOs.code-review-risk-register.md](../todos/TODOs.code-review-risk-register.md)

### 8.4 `dev/documents/` 参考与归档

- [INDEX.md](INDEX.md)
- [README.md](README.md)
- [git_branching_plan.md](git_branching_plan.md)
- [benshi_calibration_rubric.md](benshi_calibration_rubric.md)
- [benshi_report_review_20260312.md](benshi_report_review_20260312.md)
- [benshi_review_checklist.md](benshi_review_checklist.md)
- [benshi_local_ontology.md](benshi_local_ontology.md)
- `Q群群友史.docx`
- `开源项目《QQ群搬史(屎)分析仪》AI 设计与实现深度技术报告.docx`
- `开源项目《QQ群搬史(屎)分析仪》深度调研与方案报告.pdf`

## 9. 当前判断：哪些该看，哪些不用反复看

### 当前最值得反复引用

- `AGENTS.md`
- `major_AGENTs.md`
- `Benshi_AGENTs.md`
- `TODOs.analysis-implementation-plan.md`
- `TODOs.benshi-master-agent.md`
- `Q群群友史.docx`
- `benshi_calibration_rubric.md`
- `benshi_llm_reply_probe_clusters_medium_shi_review.txt`

### 当前主要作为归档/中长期参考

- `开源项目《QQ群搬史(屎)分析仪》AI 设计与实现深度技术报告.docx`
- `开源项目《QQ群搬史(屎)分析仪》深度调研与方案报告.pdf`

## 10. 下一步执行建议

最推荐的执行顺序：

1. 扩写 `BenshiOntologyPack`
2. 扩写 `BenshiExampleBank`
3. 扩写集中式样本的成分分布/结构分布
4. 等非集中式群聊数据到位后，立即做对照验证

这条顺序的意义是：

- 先把“史是什么”固化
- 再把“怎么判断/怎么描述/怎么接茬”校准
- 最后再扩到更脏、更复杂、更真实的窗口
