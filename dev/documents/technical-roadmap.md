# Technical Roadmap

> Last updated: 2026-03-20
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

当前主线可以压成 6 层：

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
5. 本地史学知识底座
   - `BenshiOntologyPack`
   - `BenshiExampleBank`
   - 成分分布 / 搬运结构分布
6. 运行稳定性与发布验证
   - `main` / `runtime` 发布线
   - `full-dev` 本地开发线
   - CLI / NapCat runtime 一致性

## 3. 当前阶段判断

截至 `2026-03-20`，项目已经处于“双主线并进”状态：

- 一条主线是 `Benshi` 深度分析能力持续扩写
- 另一条主线是 exporter / CLI / NapCat runtime 的运行稳定性修复

当前阶段判断：

- exporter 已可作为稳定上游
- preprocess/runtime 已能围绕 `shi_focus` 产出专项视图
- `BenshiMasterAgent` 已可对集中式搬史样本做：
  - 史判断
  - 史成分分析
  - 史描述层
  - 群友口吻渲染
  - reply probe
- 运行面当前新增重点是：
  - 分支更新策略固定
  - release 线导出/补全兼容性回归修复
  - `full-dev` NapCat vendored runtime 完整性修复
  - 大群导出前向超时与进度链路稳定性验证

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

### [2026-03-20][011] 分支策略固定与运行稳定性问题显式归档

- 分支更新策略进一步明确：
  - 仅 `main` 的 `start_cli.bat` 允许自动从 remote fast-forward 更新
  - `full-dev` / `runtime` 以及其它非 `main` 分支默认不自动更新
- `full-dev` 曾出现：
  - 根目录 `start_napcat_logged.bat` 缺失
  - vendored NapCat runtime 缺 `path-to-regexp/dist/index.js` 与 `qs/dist/qs.js`
  - 直接导致 `/login` 阶段 NapCat WebUI 未就绪或 Node 模块缺失
- release 线曾出现导出/补全回归：
  - `begin_export_download_tracking(...)` 缺失
  - `settle_export_download_progress(...)` 缺失
  - 直接导致 `/export group ...` 补全或导出链在 `NapCatMediaDownloader` 处崩溃
- 朋友机器上的超大群导出又暴露出一条运行面问题：
  - `forward_context_metadata` 在 `/hydrate-forward-media` 路径上持续 `12s` timeout
  - 需要继续沿 release/runtime 稳定性线跟进
- 对应追踪已写入：
  - [git_branching_plan.md](git_branching_plan.md)
  - [TODOs.release-runtime-stability.md](../todos/TODOs.release-runtime-stability.md)
  - [TODOs.export-performance.md](../todos/TODOs.export-performance.md)

### [2026-03-20][012] 导出收尾回归 / forward timeout 短路 / quick login 接入

- 现场新增故障确认：
  - 大窗导出在收尾阶段因 `NapCatMediaDownloader.settle_export_download_progress(...)` 缺失而崩溃
  - 超大 forward 内层图片会在 `forward_context_metadata -> /hydrate-forward-media` 上逐 sibling 触发重复 `12s` timeout
- 当前主线修复：
  - 为 downloader 补回 `settle_export_download_progress(...)`
  - 对同一 forward parent 的 metadata timeout 增加本轮进程内短路缓存，避免 sibling 资产线性重复超时
  - `/login` 增加 quick login 路径，优先尝试 NapCat WebUI 的本机快速登录候选，再回退二维码
  - export/status 输出增加显式 `status=` 字段，并且仅对 `success / failed / in progress` 做颜色标记
- 这轮验证重点：
  - 2000 条级别群导出不再在收尾阶段因 progress helper 缺失崩溃
  - 大窗 forward metadata timeout 数量下降，不再每个 sibling 都完整吃一次 12 秒
  - 已登录本机 QQ 的情况下，`/login` 可优先走 quick login

## 5. 当前主线任务

当前主线开发按优先级排序：

1. `BenshiOntologyPack` 扩写
2. `BenshiExampleBank` 扩写
3. `成分分布 / 搬运结构分布` 扩写
4. release/runtime 稳定性修复与回归
5. 非集中式群聊实战

## 6. 当前可用测试/审阅产物

### 集中式搬史本地测试集

- `dev/testdata/local/shi_group_751365230/`

关键人工审阅文件：

- `manual_review_hierarchy.txt`
- `benshi_llm_reply_probe_medium_review.txt`
- `benshi_llm_reply_probe_clusters_medium_review.txt`
- `benshi_llm_reply_probe_clusters_medium_cluster_review.txt`
- `benshi_llm_reply_probe_clusters_medium_shi_review.txt`

## 7. 工作流规则

### 分支规则

以 [git_branching_plan.md](git_branching_plan.md) 为准：

- `full-dev`
  - 默认开发分支
  - 只本地提交，不默认推远端
  - 不自动拉 remote 更新
- `main`
  - 发布/归档/验证分支
  - 允许在 `start_cli.bat` 中自动检查并 fast-forward 自身
- `runtime`
  - 运行面/发布验证分支
  - 不自动拉 remote 更新

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
- 运行面修复进入 `main` / `runtime` 前，应优先补最小回归测试

### 默认推进风格

- 除非用户明确要求逐步确认或暂停，大步推进优先于碎步往返
- 默认先分析“下一阶段的大方向都有哪些可以一起做”
- 然后把不冲突的任务打包成一轮并发推进

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
- [major_AGENTs.md](../agents/major_AGENTs.md)
- [CodeStrict_AGENTs.md](../agents/CodeStrict_AGENTs.md)
- [process_AGENTs.md](../agents/process_AGENTs.md)
- [llm_AGENTs.md](../agents/llm_AGENTs.md)
- [Benshi_AGENTs.md](../agents/Benshi_AGENTs.md)
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
- [TODOs.release-runtime-stability.md](../todos/TODOs.release-runtime-stability.md)

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
- [git_branching_plan.md](git_branching_plan.md)
- [benshi_local_ontology.md](benshi_local_ontology.md)
- `Q群群友史.docx`

## 9. 当前判断：哪些该看，哪些不用反复看

### 当前最值得反复引用

- `AGENTS.md`
- `major_AGENTs.md`
- `Benshi_AGENTs.md`
- `TODOs.analysis-implementation-plan.md`
- `TODOs.benshi-master-agent.md`
- `Q群群友史.docx`
- `benshi_calibration_rubric.md`
- `TODOs.release-runtime-stability.md`

### 当前主要作为归档/中长期参考

- `开源项目《QQ群搬史(屎)分析仪》AI 设计与实现深度技术报告.docx`
- `开源项目《QQ群搬史(屎)分析仪》深度调研与方案报告.pdf`

## 10. 下一步执行建议

最推荐的执行顺序：

1. 继续扩写 `BenshiOntologyPack`
2. 继续扩写 `BenshiExampleBank`
3. 沿 release/runtime 稳定性线补：
   - forward metadata timeout
   - 导出进度链路回归
   - full-dev NapCat runtime 完整性检查
4. 等非集中式群聊数据到位后，立即做对照验证

## 11. 2026-03-20 Release / Runtime Hotfix Log

### [2026-03-20][012] 分支策略与运行面行为复核

- 现场确认：
  - `full-dev/start_cli*.bat` 不自动拉 remote 更新
  - `runtime/start_cli*.bat` 不自动拉 remote 更新
  - `main/start_cli.bat` 仅在当前分支真实为 `main` 时才执行 fetch/pull
- 运行辅助：
  - `full-dev/start_napcat_logged.bat` 已恢复，便于本地 NapCat 观察

### [2026-03-20][013] CLI 登录链增加 quick login 分支

- 触发背景：
  - 纯二维码登录会增加维护/测试摩擦
  - 用户本地 QQ 往往已经在线，适合优先走 NapCat WebUI quick login
- 本轮动作：
  - REPL `/login` 已支持 quick login first
  - `app.py login` 命令行入口已补齐同样行为
  - 若 quick login 不可用，仍自动回退到二维码流程
- 现场验证：
  - live smoke 输出：
    - `quick_login_candidate=ㅤㅤㅤㅤㅤㅤㅤㅤ (1507833383)`
    - `QQ quick login succeeded.`
    - `uin=3956020260`

### [2026-03-20][014] 导出进度状态显式着色

- 新约束：
  - 仅对 `status=success|failed|in progress` 本身着色
  - success=green
  - failed=red
  - in progress=yellow
  - 其余字段保持原样
- 已落点：
  - CLI 命令输出
  - Slash REPL 进度输出
  - watch 视图
- 现场验证：
  - live `export-history` 已出现：
    - `status=in progress export_progress: ...`
    - `status=success export_progress: ...`
    - `status=failed export_progress: asset substep timeout ...`

### [2026-03-20][015] 大窗导出回归：收尾崩溃已修，forward metadata timeout 降噪

- 原现场故障：
  - 大群导出在收尾阶段抛：
    - `'NapCatMediaDownloader' object has no attribute 'settle_export_download_progress'`
  - 同一个 forward parent 下，多个兄弟 asset 会重复打 `forward_context_metadata` 的 12 秒 timeout
- 本轮动作：
  - 补回 `NapCatMediaDownloader.settle_export_download_progress(...)`
  - 为 `forward_context_metadata` 增加同父级 timeout 短路缓存
- live 验证：
  - 命令：
    - `app.py export-history group "蕾米二次元萌萌群" --limit 2000 --format jsonl`
  - 结果：
    - `records=2000`
    - `elapsed_s≈40.2`
    - 无 `settle_export_download_progress` 崩溃
    - 只记录到 1 条代表性 `forward_context_metadata` timeout，而非整串兄弟图重复刷屏
- 当前解释：
  - 这类超时仍然真实存在，但已从“重复放大故障”收敛成“单点慢点”
