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

### [2026-03-20][033] `/login` quick-login completion and `start_cli` launcher update handoff hardened

- `/login` quick-login completion in classic Windows console no longer auto-applies the first QQ candidate during menu navigation
- login completion navigation now keeps the buffer text stable during `Tab/Up/Down`; the selected QQ number is only inserted on explicit accept
- compat-mode REPL sessions now use readline-like completion rendering for login-style flows to reduce horizontal menu corruption in classic console hosts
- `start_cli.bat` now hands off to the freshly updated launcher script after a successful `git pull`, so launcher/runtime changes can take effect in the same run
- when the fetched diff touches NapCat runtime paths or launcher helpers, `start_cli` now marks the run for a best-effort NapCat service restart before starting the CLI
- repo-scoped NapCat restart logic now lives in:
  - [restart_napcat_service.ps1](../../restart_napcat_service.ps1)

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

### [2026-03-20][013] reviewer 模式继续收敛导出阻塞与 operator 误判面

- 继续以“朋友机器大群导出”作为 reviewer 主样本，确认两类根因：
  - 真正的主链阻塞
  - 看起来像挂了但其实只是 background missing / fast path 降级 / wrong-session 的误判
- 本轮已落地：
  - `cleanup_remote_cache()` 不再等待 stale prefetch futures，避免“数据和 manifest 已写完，但 CLI 还卡住不退出”
  - REPL `data_count` 导出页大小策略与 CLI 对齐，不再意外扩大 page-size
  - deep-forward metadata 空结果 / route error / timeout 的 sibling 短路缓存继续补强
  - old placeholder image 只在没有 prefetched usable payload/path 时才短路为背景缺失，避免误伤可恢复老图
- 本轮 live 结论：
  - `group 922065597 limit=2000`
    - 维持 `copied=341 reused=100 missing=129`
    - `actionable_missing=0`
    - 剩余 missing 全是 background-only
  - `private 1507833383 limit=100`
    - `missing=0`

### [2026-03-20][014] deep-forward 命中后的重复打树与来源可见性补强

- `NapCatMediaDownloader` 现已对相同 forward parent 的 metadata 成功 payload 做本轮进程内缓存：
  - 同一组 sibling asset 不再反复重打 `/hydrate-forward-media` 再全树匹配
- forward 命中后的恢复顺序改为：
  1. 本地 path
  2. forward remote URL
  3. public token action
- operator 可见性补强：
  - `export_summary` 现可显示：
    - `history_source`
    - `history_fallback=partial`
    - `forward_detail_count`
    - `forward_structure_unavailable`
  - app / REPL 首屏结果行也会带：
    - `src=...`
    - `history_fallback=...`
    - `fwd_gap=...`
- 当前判定：
  - asset timeout / 阻塞主矛盾已明显下降
  - 可以继续往下更狠地刁 deep-forward / route downgrade / operator guardrail

### [2026-03-20][015] forward route 与普通 context route 健康状态拆分

- exporter 现在不再用一个全局 kill switch 同时关闭：
  - `/hydrate-media`
  - `/hydrate-forward-media`
- 当前行为：
  - forward route 单独不可用时，只关闭 deep-forward hydration
  - ordinary context route 仍保持可用
  - 反之亦然
- 价值：
  - 减少“某一路由抖了一次，整个进程都像降级成慢路径”的误伤
  - 更贴近朋友机器那种环境漂移/插件局部异常的真实故障形态

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
- 本地账号约束：
  - 默认只使用 `3956020260` 作为本地 live 测试账号
  - 未经用户明确说明，不得切换或尝试其它本地 QQ 账号

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
- 修正说明：
  - 早期一轮现场输出曾把“已有在线会话复用”误记成“quick login 成功”
  - 后续已修正为：
    - 若 NapCat 已有可用在线会话，则明确打印 `QQ already logged in.`
    - 不再把已有会话误写成 quick login 成功

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

### [2026-03-20][016] 本地 live 测试账号固定

- 新约束：
  - 本地测试账号默认固定为 `3956020260`
  - 未经用户明确说明，不再尝试其它 quick login 候选账号
  - 本地 live/export 测试目标默认固定为：
    - `group 922065597` `蕾米二次元萌萌群`
    - `private 1507833383`
- 原因：
  - 避免误用用户机器上其它长期在线账号
  - 避免把“已有会话复用”和“切换账号成功”混淆

### [2026-03-20][017] quick login 现场故障收敛：启动期与运行中是两套链路

- 新现场结论：
  - NapCat quick login 不能只理解成一条链
  - 现场已确认至少存在两套相关路径：
    1. 启动期命令行参数：
       - `-q <uin>`
    2. WebUI 启动后自动 quick-login / 手动 quick-login：
       - `NAPCAT_QUICK_ACCOUNT`
       - `WebUiConfig.autoLoginAccount`
       - `/QQLogin/SetQuickLoginQQ`
       - `/QQLogin/SetQuickLogin`
- 现场症状：
  - 用户机器上的 NapCat 控制台仍出现：
    - `没有 -q 指令指定快速登录，将使用二维码登录方式`
    - 随后又按默认历史候选去碰 `1507833383`
  - 说明至少在该次现场里，NapCat 最终没有按预期吃到“指定账号=3956020260”的启动语义
- 本轮收敛动作：
  - Python 侧 wrapper 已确认会在显式传入 `quick_login_uin` 时生成：
    - `call "...launcher-win10.bat" -q 3956020260`
  - 同时新增防守型环境变量注入：
    - `NAPCAT_QUICK_ACCOUNT=3956020260`
  - 这样即使某一层没按预期消费 `-q`，NapCat 启动后的 WebUI 自动 quick-login 也仍会优先落到同一账号
  - 另已为 wrapper 增加启动命令诊断输出，便于后续对照现场日志
- 当前解释：
  - 若仍看到 NapCat 去碰 `1507833383`，优先怀疑：
    - 该轮启动并未使用显式账号参数路径
    - 或者该轮是旧进程/旧二维码页继续复用，而非 fresh start

### [2026-03-20][018] 本地 quick-login 账号覆盖改为统一本地文件

- 新现场发现：
  - `NapCat/napcat/config/webui.json` 中仍存在历史：
    - `autoLoginAccount = 1507833383`
  - 这意味着任何没有显式传入 `-q` / `NAPCAT_QUICK_ACCOUNT` 的手动 NapCat 启动，都可能被旧账号抢跑
- 本轮修正：
  - `NapCatSettings.from_env()` 现在会读取本地覆盖文件：
    - `state/config/napcat_quick_login_uin.txt`
  - `start_napcat_logged.bat` 也会读取同一文件
  - 若该文件存在且启动参数里没有显式 `-q`，logged 启动器会自动补：
    - `-q <uin>`
    - `NAPCAT_QUICK_ACCOUNT=<uin>`
- 当前本地默认：
  - 覆盖文件已落地为：
    - `3956020260`
  - 因此手动 logged 启动与 CLI 启动将默认朝同一个账号收敛
- 设计目标：
  - 不把本地测试 QQ 号硬写进受版本控制的 NapCat 配置文件
  - 同时避免继续被 `webui.json` 中的历史 `autoLoginAccount` 污染

### [2026-03-20][019] 2000 条群导出现场基线：导出成功，剩余噪声集中在单个 deep-forward 包

- 现场命令：
  - `/export group 蕾米二次元萌萌群 data_count=2000 asJSONL`
- 现场结果：
  - `records=2000`
  - `elapsed=32.734s`
  - `pages=11`
  - `assets copied=225 reused=100 missing=245`
- 本轮关键解释：
  - `245 missing` 看起来大，但主成分并不是新回归
  - manifest 分解为：
    - `qq_not_downloaded_local_placeholder = 233`
    - `missing_after_napcat = 7`
    - `qq_expired_after_napcat = 5`
  - 也就是说，这次真正和当前导出链残余问题直接相关的，只是：
    - `7` 个 `missing_after_napcat`
    - `5` 个 `qq_expired_after_napcat`
- deep-forward 现场细节：
  - 只剩 `1` 次真实：
    - `forward_context_metadata status=timeout`
  - 该 timeout 对应单个 forward 父消息：
    - `message_id_raw = 7617760641125573795`
  - 同一个 forward 包里有 `7` 张图：
    - `2C167901425EF469C0B1F0BF859E4B2C.jpg`
    - `49D109C31C9FADA0A156408B75DC1620.png`
    - `5AFEB7CD692F6C908EEA82E9DF26986B.jpg`
    - `4D5CD0D6C6CE08CB5ABC8FF7479ABE30.png`
    - `09C868CB47C64A1ED520F7A4190F4C5B.png`
    - `1C824B386DAB0CBBCC41DB7F77188D1C.png`
    - `F9140E7ADB6458C3F9958E79CEDF5EA4.jpg`
- 当前判断：
  - 导出本身是成功的，不属于“又炸了”
  - 先前的同父级 timeout 放大问题已经被压住
  - 现在的剩余怪相更准确地说是：
    - 单个 deep-forward 包里的 forward 元数据水合超时

### [2026-03-20][020] runtime 自动启动链改走 project logged launcher helper

- 新现场结论：
  - `app.py /login --refresh` 若直接打 `launcher-win10.bat`，会落到管理员限制 / quick-login 注入链和手动 logged 启动不一致的问题
- 本轮修正：
  - runtime wrapper 现在优先走：
    - `start_napcat_logged.bat`
  - 并通过：
    - `NAPCAT_LAUNCHER_OVERRIDE`
    - `NAPCAT_QUICK_ACCOUNT`
    - `-q 3956020260`
    把显式 quick-login 账号和真实 NapCat launcher 继续传下去
- 同轮还修正了一个真实 batch bug：
  - `start_napcat_logged.bat` 的管理员 relaunch 分支原先在括号块内提前展开 `%NAPCAT_ELEVATED_WRAPPER%`
  - 现场等价于执行：
    - `Start-Process '' -Verb RunAs`
  - 现在已改为 delayed expansion，不再把提权 wrapper 的 `FilePath` 吃空
- 当前判断：
  - 后续 Python 侧 runtime 自动启动、手动 logged 启动、quick-login 固定账号三条链现在已经基本对齐

### [2026-03-20][021] live 验证矩阵固定，并补上静默 0 条导出的 operator 提示

- 新约束：
  - 后续本地 live/export 验证只使用：
    - `group 922065597` `蕾米二次元萌萌群`
    - `private 1507833383`
- 现场补充验证：
  - `private 1507833383 --limit 300 asJSONL`
    - `records=53`
    - `missing=0`
  - `group 922065597 --limit 200 asTXT`
    - `records=200`
    - `missing=0`
- 同轮发现：
  - `group 751365230 --limit 300` 返回 `records=0`
  - 进一步核实后确认：当前在线账号 `3956020260` 的 `get_group_list` 视角下并没有这个群
  - 因此它不是 exporter 静默坏掉，而是目标在当前账号视角下不可解析
- 本轮修正：
  - CLI 现在会在 `records=0` 时补一个 `zero_result_hint`
  - 明确区分：
    - 当前账号视角里根本解析不到目标
    - 目标可解析，但本次切片本来就没有消息
    - 再叠加旧时间窗的大量 placeholder 资产
- NapCat 控制台里这类报错当前可视为已知噪声而不是整次导出失败：
  - `Protocol FetchForwardMsg fallback failed`
  - `protocolFallbackLogic: 找不到相关的聊天记录`
  - 在该次现场里，它们没有阻止：
    - `records=2000` 完整写出
    - forward 文本细节进入 `content` / `segments[*].extra.forward_messages`

### [2026-03-20][020] deep-forward 远程 URL 回收路径真正打通，2000 条导出缺失显著下降

- 二次现场核查发现：
  - `NapCatMediaDownloader` 的远程媒体缓存目录准备函数：
    - `_prepare_remote_cache_dir()`
  - 之前只有定义，没有在实际远程 URL 下载前被调用
  - 这会让：
    - `forward_remote_url`
    - `forward_remote_url_prefetched`
    - `sticker remote_url`
    这些路径在逻辑上存在、但运行时始终拿不到可写缓存目录
- 直接影响：
  - `2026-03-16T13:12:57+08:00`
  - `message_id_raw=7617760641125573795`
  - 那个 deep-forward 图串里的 `7` 张图在第一次 2000 条导出中全部落成：
    - `missing_after_napcat`
- 本轮修复：
  - 在真正执行远程 URL 下载前主动准备 remote cache dir
  - 同时为：
    - 远程媒体下载
    - sticker 远程下载
    增加回归测试
- 定点复测结果：
  - 窄窗仅含该 forward 消息时：
    - `7/7` 图全部恢复成功
    - 解析器返回：
      - `napcat_forward_remote_url`
      - `napcat_forward_remote_url_prefetched`
- 全量 `2000` 条重跑结果：
  - 旧结果：
    - `copied=225 reused=100 missing=245`
    - `missing_breakdown = {qq_not_downloaded_local_placeholder:233, missing_after_napcat:7, qq_expired_after_napcat:5}`
  - 新结果：
    - `copied=341 reused=100 missing=129`
    - `missing_breakdown = {qq_not_downloaded_local_placeholder:124, qq_expired_after_napcat:5}`
- 当前解释：
  - deep-forward 这条残余导出链问题已被明显压下去
  - 现在大盘缺失已基本回到：
    - 老 placeholder 图
    - 少量已过期图
  - 不再是“当前导出链还在持续丢当期 forward 图”

### [2026-03-20][021] operator-facing export summary 改成分离 actionable/background missing，并完成异源 smoke

- 现场再次确认：
  - 导出成功时最容易误导操作者的，不再是主链崩溃
  - 而是摘要把：
    - `missing_after_napcat`
    - `qq_not_downloaded_local_placeholder`
    - `qq_expired_after_napcat`
    混在一起报，导致看起来像“仍有大量新故障”
- 本轮调整：
  - export summary 现在会同时显示：
    - `final_missing_reason`
    - `actionable_missing_reason`
    - `background_missing_reason`
  - 并且 retry hints 只针对 actionable missing 生成
- 当前口径：
  - background missing:
    - `qq_not_downloaded_local_placeholder`
    - `qq_expired_after_napcat`
  - actionable missing:
    - 其余当前链路仍值得立即重试/排查的缺失
- 现场复跑验证：
  - `group 922065597 limit=2000 asJSONL`
    - `missing=129`
    - `actionable_missing_reason=[-]`
    - `background_missing_reason=[qq_expired_after_napcat:5, qq_not_downloaded_local_placeholder:124]`
  - `private 1507833383 limit=50 asJSONL`
    - `missing=0`
  - `group 922065597 limit=50 asTXT`
    - `missing=0`
- 当前解释：
  - 大群 JSONL
  - 私聊 JSONL
  - 小窗 TXT
  这三条主路径都已通过现场 smoke
  - 若朋友环境仍报异常，应优先怀疑：
    - 本地 NapCat/QQ 状态
    - 旧发布线残留
    - 环境配置漂移
  - 而不是默认怀疑当前 exporter 主链

### [2026-03-20][022] reviewer 继续加压后补上的 runtime/login guardrail

- 本轮第三者 reviewer 继续从：
  - login/bootstrap/runtime 启动链
  - quick-login 账号漂移
  - REPL/CLI 行为不一致
  - WebUI “ready 但其实不可认证/不可用”
  这几条线继续咬代码。
- 新确认的高风险点：
  - `QQ already logged in.` 之前会把“错误账号已在线”也当成成功返回
  - REPL 的 quick-login 候选获取异常时，之前比 CLI 更容易直接命令失败，而不是优雅回退二维码
  - bootstrap 之前对：
    - WebUI ready
    - “看起来已登录”
    的判定都偏乐观，容易把 ghost session / 旧 runtime 误当成可用状态
  - `start_napcat_logged.bat` 在管理员提权重启路径上，计算出来的 quick-login 账号有丢失风险
- 本轮已补的 guardrail：
  - `/login` 在请求账号与当前在线账号不一致时，明确报：
    - `QQ session mismatch`
    而不是继续把错误账号当成成功
  - CLI / REPL 都对 quick-login lookup 异常做了保守回退
  - bootstrap 的：
    - `webui`
    - `onebot_http/ws`
    相关路径现在会再多核一层认证/可用会话信息，减少 ghost-ready
  - `start_napcat_logged.bat` 的提权路径现在显式保留 quick-login 注入信息
- 当前解释：
  - 这轮修的不是“现有现场已炸点”
  - 而是多账号、多运行时、多机器环境下最容易在朋友环境里继续复现的漂移型问题

### [2026-03-20][023] placeholder-heavy public-token 图像链继续降噪，错误账号导出 guard 正式接入

- reviewer 新抓到的高频噪声：
  - 在 `group 922065597 limit=2000` 的上一轮 trace 里，普通顶层图像存在：
    - `public_token_get_image_remote_url cached_error = 124`
    - `public_token_get_image_classification classified_missing = 124`
  - 这说明代码先走了：
    - `public token -> remote_url`
  - 然后才承认它其实只是：
    - `qq_not_downloaded_local_placeholder`
- 本轮修正：
  - 对 image public-token payload：
    - 先做 placeholder / expired 分类
    - 再决定是否需要 remote URL 尝试
  - 对 operator summary：
    - 若 `missing` 全部只是 background missing，则显式输出：
      - `missing_note: 当前剩余 missing 全是背景缺失`
  - 对运行时账号：
    - `app.py export-history`
    - REPL `/export`
    现在都会在固定 quick-login 账号配置存在时，再核一次当前在线会话
    - 若检测到当前在线 `uin` 与请求/固定账号不一致，会直接报：
      - `QQ session mismatch`
- 回归：
  - `33 passed`
- live 结果：
  - `group 922065597 limit=2000 asJSONL`
    - 仍成功完成
    - `missing=129`
    - `actionable_missing_reason=[-]`
    - `background_missing_reason=[qq_expired_after_napcat:5, qq_not_downloaded_local_placeholder:124]`
  - 关键 trace 变化：
    - 旧：
      - `public_token_get_image_remote_url cached_error = 124`
    - 新：
      - `public_token_get_image_remote_url cached_error = 0`
    - `public_token_get_image_classification classified_missing = 124`
      仍保留，表示这些资产被直接判为背景缺失，而不再先做一轮无意义远程尝试
- 当前解释：
  - 这轮不是把更多旧资产“神奇救活”
  - 而是把：
    - 不必要的远程重试
    - 容易误导 operator 的错误噪音
    - 错账号会话下看起来像成功的风险
    一起压下去了

### [2026-03-20][024] remote prefetch 热路径改成“短 peek + 真正需要时再等”，2000 条群导出继续提速

- reviewer 新抓到的硬点：
  - `remote prefetch` 在热路径上仍可能调用：
    - `future.result(timeout=...)`
  - 这会把“正在后台下载”的状态重新带回主导出循环里阻塞等待
- 本轮修正：
  - `remote prefetch` 消费改成：
    - 先做短 `peek`
    - 真正需要该资产时，才在最终下载路径里等待完整结果
  - `prepare_for_export(...)` 里：
    - 不再先对所有请求一股脑做 eager remote prefetch
    - 先过：
      - forward-parent skip
      - stale-local
      - hinted-local
      - old placeholder 跳过 eager prefetch
- live 结果（`group 922065597 limit=2000 asJSONL`）：
  - 正确性保持：
    - `copied=341 reused=100 missing=129`
  - 总耗时继续下降：
    - 旧：`42.48s`
    - 新：`36.914s`
  - 平均单步 materialize：
    - 旧：`0.0206s`
    - 新：`0.0128s`
- 当前解释：
  - 最折磨人的“主循环被 prefetch 反向拖住”已经继续被压了一刀
  - 现在 remaining missing 仍然主要是：
    - `qq_not_downloaded_local_placeholder`
    - `qq_expired_after_napcat`
  - 不再像前几轮那样主要体现为 exporter 主链阻塞

### [2026-03-20][025] operator 首屏提示继续降噪：显式会话、显式 verdict、REPL/CLI 对齐

- 本轮补的 operator-facing 改动：
  - `app.py export-history` 现在会显式打印：
    - `export_session: uin=3956020260 nick=wiki online=True`
  - 首屏增加统一 verdict：
    - `export_verdict: success`
    - 或 `success_with_background_missing`
    - 或 `success_with_actionable_missing`
  - REPL `/export` 也补上了：
    - `export_session`
    - `zero_result_hint`
    - `export_verdict`
  - compact retry hint 现在会带：
    - `kinds=[...]`
- 当前解释：
  - 这轮没改核心导出逻辑
  - 主要是把“看起来很吓人但其实没炸”的现场体验再压一层
  - 方便朋友机器和大群导出现场更快判断：
    - 到底是背景缺失
    - 还是新的可行动故障

### [2026-03-20][026] remote prefetch runtime 启动失败改为受控降级，不再把 downloader 构造直接炸掉

- reviewer 继续往死里刁时，发现当前还有一个“看着像偶发、实则很伤”的点：
  - `NapCatMediaDownloader` 构造阶段如果远程预取 async runtime `5s` 内没 ready
  - 会直接抛：
    - `remote media async runtime failed to start`
  - 这会把本来只是“远程预取优化不可用”的情况，放大成整个导出器初始化失败
- 本轮修正：
  - `remote prefetch runtime` 启动失败时：
    - 记录禁用状态
    - 保留 `public token` 预取线程池
    - 正式导出链继续可用
  - 也就是说现在语义变成：
    - “少一个优化子系统”
    - 而不是：
    - “整个 exporter 构造炸掉”
- focused regression：
  - `tests/test_media_downloader_progress_and_forward_timeout.py`
  - `tests/test_export_selection_summary.py`
  - `23 passed`
- live sanity：
  - `group 922065597 --limit 300 --format jsonl`
  - 结果：
    - `records=300`
    - `copied=79 reused=16 missing=13`
    - `actionable_missing=0`
    - `background_missing=13`
  - 当前解释：
    - 这轮没有改动导出结果语义
    - 只是把一个高风险初始化炸点降成了可控退化

### [2026-03-20][027] 修复发布线 `start_cli` 自动更新后的 REPL 启动崩溃

- 现场故障：
  - `main` 分支本地 `start_cli.bat` 自动更新后，CLI 进入 REPL 即崩：
    - `TypeError: SlashCommandCompleter.__init__() got an unexpected keyword argument 'quick_login_lookup'`
- 根因：
  - 发布线里：
    - `repl.py` 已经接了 `quick_login_lookup=...`
  - 但：
    - `completion.py`
    - `tests/test_cli_login_completion.py`
    没有同步进发布线
  - 导致发布包处于“REPL 已升级、completer 仍是旧签名”的半新半旧状态
- 修正方向：
  - 把 login quick-completion 的 `completion.py` 变更和对应测试成套补进 `main/runtime`
- 价值：
  - 避免 `main` 自动更新后直接把 CLI 启动链炸掉
  - 也提醒后续发布线同步要覆盖：
    - REPL 调用侧
    - completer 实现侧
    - 对应回归测试

### [2026-03-20][028] `/login --quick-uin` 补全再做一层兜底，并正式建立分支同步事故记录

- 现场反馈：
  - 用户在 `main` 本地更新后测试：
    - `/login --quick-uin`
  - 仍然认为 QQ 候选补全不可用
- 当前处理方向：
  - 不再依赖“必须先敲空格”这一种交互路径
  - 只要进入：
    - `/login --quick-uin`
    上下文，就允许直接给出：
    - `--quick-uin 3956020260`
    这类完整候选
- 同时新增：
  - [branch-sync-incidents.md](/d:/Coding_Project/IsThisShit/dev/documents/branch-sync-incidents.md)
  - 用来持续记录：
    - `main/runtime` 半新半旧
    - release bundle skew
    - auto-update 拉到坏包
    这类事故
- 主 [AGENTS.md](/d:/Coding_Project/IsThisShit/AGENTS.md) 也已补充：
  - release sync 必须按 feature family 成套同步

### [2026-03-20][029] quick-login 补全改成“先本地 cache，后后台预热”，不再在补全热路径同步碰 WebUI

- 新现场反馈：
  - `/login`
  - `/login --quick-uin`
  的补全会：
    - 先硬控约 `1-2s`
    - 然后还可能什么都不弹
- 当前判断：
  - 补全热路径里同步触发 quick-login 候选查询，本身就不是一个稳妥设计
  - 即便逻辑上最后能拿到候选，也会把 prompt_toolkit 的交互体验拖坏
- 本轮修正：
  - REPL 启动后后台预热 quick-login 候选缓存
  - 补全时只读本地 cache
  - 若 cache 还没热好，也至少立即返回 pinned 账号：
    - `3956020260`
  - 也就是说现在补全策略变成：
    - first return local-known candidate
    - then refresh in background
- startup 提示：
  - `startup_cache: 正在后台预加载 quick-login QQ 号补全，/login 会优先走本地缓存。`
- 当前价值：
  - 不再让 `/login` / `/login --quick-uin` 因 WebUI 查询而把输入体验卡坏

### [2026-03-20][030] quick-login 补全候选必须以 NapCat 返回为主来源，空预热不能被缓存成 fresh

- 新现场反馈：
  - 发布线 `main` 上：
    - `/login`
    - `/login --quick-uin`
    虽然已经不再硬控热路径，但仍然只弹参数选项，不弹 QQ 号
- 根因判断：
  - 之前的后台预热逻辑里：
    - 如果当时从 NapCat 拉到的是空 quick-login 列表
  - 系统仍会把“空列表”记成 fresh cache
  - 于是后续几分钟里补全一直只有参数，没有 QQ 候选
  - 同时，当前在线账号没有作为 NapCat 侧 fallback 候选并进缓存
- 修正方向：
  - quick-login 候选以 NapCat 为主来源：
    - `GetQuickLoginList*`
    - 当前在线 `login_info.uin`
  - 空结果不再记 fresh cache，而是记成 retryable failure
  - REPL 启动时给 quick-login 预热线一个很短的抢跑窗口，尽量在 `Slash REPL ready` 前把候选装入缓存
  - 预热结果写入 info 日志，明确区分：
    - `cache_ready`
    - `cache_empty`
    - `prime_failed`
- 当前价值：
  - 避免“后台查过一次空结果，然后 /login 长时间只有参数没有 QQ”这一类假死体验

### [2026-03-20][031] REPL 启动阶段预热 NapCat WebUI，并把 quick-login 补全来源顺序改成 NapCat 优先

- 新现场反馈：
  - `main` 上：
    - `/login`
  - 仍然可能先看到参数补全，没有 QQ 候选
  - 用户同时提出：
    - 打开程序时就应先加载 NapCat service
    - 加载完成后再开放输入
- 本轮修正：
  - REPL 启动时先执行一轮：
    - `startup_napcat`
    - 预热 `webui`
  - 然后才开始 quick-login 候选预热和放出交互提示
  - `/login` 候选顺序调整为：
    - NapCat 候选缓存优先
    - 本地 pinned `quick_login_uin` 仅作兜底
- 关联风险：
  - 这轮现场又暴露出新的 release skew：
    - `repl.py` 已经开始给 `ensure_endpoint(...)` 传 `quick_login_uin`
    - 但发布线 `bootstrap.py` 仍是旧签名
  - 这条已单独记录进：
    - `branch-sync-incidents.md`

### [2026-03-20][032] 启动链再向下一层收口：`runtime.py` 也必须进入 quick-login/startup 同步包

- 新现场反馈：
  - `main` 更新到上一轮后：
    - `startup_napcat`
  - 不再炸在 `bootstrap.py`
  - 但继续炸在：
    - `NapCatRuntimeStarter.ensure_endpoint(... quick_login_uin=...)`
- 当前判断：
  - 这说明 quick-login/startup 功能包仍然没有完整下沉到 runtime starter 层
  - 只同步：
    - `repl.py`
    - `bootstrap.py`
  - 不同步：
    - `runtime.py`
  - 会继续形成逐层冒泡式故障
- 修正方向：
  - 将 `runtime.py` 和对应的 launch/diagnostic 测试也纳入 release bundle
  - 不再允许“上层签名升级、底层 runtime 还停留旧版”这种半套状态

### [2026-03-20][034] `/login` 补全交互继续收口：默认优先 QQ 号，不把参数和 QQ 混在一起，经典控制台导航不再污染输入行

- 新现场反馈：
  - `main` 更新后：
    - `/login`
  - 已经能看到 QQ 候选，但仍会：
    - 默认把第一个 QQ 塞进输入框
    - `Up/Down` 导航时把多个 QQ 号拼进同一行
    - QQ 候选和 `--refresh/--timeout/...` 混在同一菜单里
- 当前判断：
  - 这不是候选源问题，而是：
    - prompt_toolkit 默认 completion 导航会重写 buffer
    - `/login` 在“用户还没输入 `--`”时仍同时吐出参数和 QQ 候选
- 本轮修正方向：
  - 经典 Windows 控制台下，`/login` completion 菜单导航只切换菜单索引，不再改写 buffer
  - `/login` 在尚未显式输入 `--` 之前，默认只展示 QQ 号候选
  - 只有用户显式输入 `--` 或 `--quick-uin` 上下文时，才展示 login 选项
- 目标效果：
  - `/login`
    - 默认就是“按 QQ 号作为输入”
  - `/watch` / `/export`
    - 行为保持不变

### [2026-03-20][035] Git branch governance 从事故笔记升级为独立 handbook

- 背景：
  - 近几轮现场问题里，多次出现：
    - 程序症状看起来像运行时 bug
    - 实际根因却是 `main/runtime` bundle skew
    - 或 release worktree 同步半套
- 本轮处理：
  - 新增独立分支治理手册：
    - [GitBranch_AGENTs.md](../agents/GitBranch_AGENTs.md)
  - 同时补齐：
    - [dev/agents/INDEX.md](../agents/INDEX.md)
    - [TODOs.git-branch-governance.md](../todos/TODOs.git-branch-governance.md)
  - 顶层 [AGENTS.md](../../AGENTS.md) 也新增路由，明确：
    - branch governance
    - release sync discipline
    - staging hygiene
    - branch incident response
- 目标：
  - 后续先判断：
    - 是真实程序问题
    - 还是 release sync 问题
  - 减少“查半天代码，最后发现是分支问题”的时间浪费

### [2026-03-20][036] `/login` 自动补全继续向“真实操作手感”对齐

- 新现场反馈：
  - `/` 会自动弹命令
  - 但 `/l` 不会自动继续弹 `/login`
  - `/login 3` 不会自动及时收敛到 `3956020260`
  - 同时 quick-login 候选之前按“包含匹配”过滤，导致输入 `3` 时还会把不以 `3` 开头的 QQ 一起带出来
  - 空白昵称候选也需要明确显示成：
    - `<空白ID>`
- 本轮修正：
  - `/login` quick-login 候选改成：
    - 数字输入按 QQ 号前缀过滤
    - 非纯数字仍允许昵称包含匹配
  - 空白 quick-login 昵称现在显示为：
    - `<空白ID>`
  - REPL 增加了文本变更后的轻量 completion auto-refresh：
    - `/l`
    - `/login `
    - `/login 3`
    - `/login --quick-uin`
    这些场景不再只等手动 `Tab`
- 目标：
  - `/login` 这条补全链更像真实命令行输入，而不是“先开菜单再手动逼它刷新”

### [2026-03-20][037] `start_cli` 更新后 handoff 再收口：去掉内部 CLI 哨兵参数

- 新现场反馈：
  - 用户本地 `main` clone 在自动更新后出现：
    - `Restarting start_cli to apply updated launcher logic...`
  - 紧接着 `app.py` 直接收到：
    - `--post-update-handoff`
  - 然后报：
    - `No such option: --post-update-handoff`
- 这轮核查结论：
  - 不是新的 release skew
  - `start_cli.bat` 在：
    - 根仓
    - release worktree
    - 用户更新后的 `main` clone
  - 内容一致
  - 真问题是 launcher 自己的 handoff 方案过于脆弱：
    - 用内部 CLI 参数做“二次启动标记”
- 本轮修正：
  - 去掉：
    - `--post-update-handoff`
  - handoff 状态只放在环境变量里：
    - `CLI_POST_UPDATE_HANDOFF=1`
  - 更新后重新调用 launcher 时，只传原始 operator 参数
  - 并改成新 `cmd /c` 进程重启新的 launcher，旧批处理不再继续跑后续 label
- 当前价值：
  - 避免内部标记再漏进 `app.py`
  - 也避免后续把这类 launcher 设计问题误判成“又一次 branch sync 故障”

### [2026-03-20][038] 经典控制台下的补全菜单改成真正的菜单样式，并增加底部预留空间

- 新现场反馈：
  - 当命令行已经贴近窗口底部时：
    - `/login`
  - 的补全菜单会被挤到窗口外，看起来像“候选消失”
- 当前判断：
  - 兼容模式此前使用：
    - `CompleteStyle.READLINE_LIKE`
  - 这种显示方式在经典 Windows 控制台里对底部空间的约束不够稳定
  - 同时固定：
    - `reserve_space_for_menu=8`
  - 在 `30` 行窗口里也偏紧
- 本轮修正：
  - 兼容模式改用真正受 `reserve_space_for_menu` 约束的：
    - `CompleteStyle.COLUMN`
  - 经典控制台下的菜单预留行数改为按窗口高度动态计算
    - `30` 行窗口当前默认预留：
      - `10` 行
- 当前价值：
  - `/login`、`/login --quick-uin` 等菜单在窗口底部不再更容易被挤没

### [2026-03-20][039] 导出完成后的结果展示改成分块结果卡片，并显式输出 `export_status`

- 新现场反馈：
  - 导出完成后原来的：
    - `export_verdict`
    - `written: ...`
    - `export_summary: ...`
  - 虽然信息全，但形式又长又乱
  - `content_export=`、`final_asset_result=` 这种机器向行不适合人眼扫读
- 本轮修正：
  - CLI / REPL 共用一套新的 `export_result` 结果块
  - 按区块输出：
    - `export_status`
    - `export_verdict`
    - `files`
    - `summary`
    - `assets`
    - `note`
  - `export_status=success|failed` 进入显式状态着色范围
  - 原先冗长的 `content_export=` / `final_asset_result=` 结果块不再默认直接刷屏
- 当前价值：
  - 大群导出结束后，一眼就能看到：
    - 成功还是失败
    - 文件写到了哪里
    - 时间窗和历史源
    - 资产恢复总体结果
    - missing 是否只是背景缺失

### [2026-03-21][040] `10000` 条导出的 bounded diagnosis 已收口到两条明确结论

- 新现场诉求：
  - 当 `data_count` 拉到 `10000` 或者直接导出超长历史窗口时：
    - 不能再靠“等很久看它会不会 finally failed”
  - 需要尽早拿到：
    - 当前到底卡在哪个阶段
    - 是真的阻塞，还是只是大窗正常运行中
- 本轮针对 `group 922065597` 的 live probe 结论：
  - `prefetch_media_chunk` 现在已经有稳定心跳和耗时速率显示
  - 但如果把所有 old-bucket context 资产都重新纳入 batch prefetch：
    - metadata-only 预热仍会把 `10000` 条导出的 prefetch 阶段拖爆预算
  - 因此当前保留：
    - 大窗 old-bucket batch prefetch 跳过
  - 只对较新的 context 资产做 batch prefetch
- 同时收紧了一个误报：
  - `2025-09-08` 那条旧 `file` 资产：
    - context hydration 可达
    - public token `get_file` 也返回
    - 但本地 path/url 为空
    - direct `file_id` 再返回 `file not found`
  - 这类 case 现在从：
    - `missing_after_napcat`
  - 改为：
    - `qq_expired_after_napcat`
- 当前 maintainer 侧 live baseline：
  - `export-history group 922065597 --limit 10000 --format jsonl`
  - 约 `122.1s` 完成
  - `actionable_missing=0`
  - `background_missing=900`
  - `prefetch_chunks=3`
  - `prefetch_degraded=no`
- 当前价值：
  - `10000` 量级现在已经能在可接受时间里拿到完整 verdict
  - 不再需要盲等很久才知道是不是 exporter 主链真的炸了

### [2026-03-21][041] `prefetch` 准备阶段现已显式出心跳，导出结果不再把“已完成但有可行动 missing”误标成 failed

- 新现场反馈：
  - 大窗 root export 在：
    - `status=in progress export_progress: prefetching media context requests=3150`
  - 这一步仍然会静止几十秒，operator 不知道它到底是在卡住还是在正常扫描待预热资产
  - 同时导出完成后还出现了语义冲突：
    - `export_status=failed export_verdict=success_with_actionable_missing`
- 根因复核：
  - downloader 已经发出了：
    - `phase=prefetch_media_prepare`
  - 但 REPL / CLI / watch 的进度路由仍然只接：
    - `prefetch_media`
    - `prefetch_media_chunk`
  - 所以这段“正在枚举 / 分类 / 跳过 old bucket / 复用本地 path”的准备工作没有被显示出来
  - 另外 `export_status` 之前仍被 `actionable_missing_count > 0` 直接映射成：
    - `failed`
  - 这不适合“数据文件已经成功写出，但仍有部分可行动 missing”的场景
- 本轮修正：
  - `prefetch_media_prepare` 已接入：
    - CLI
    - REPL
    - watch view
  - 现在 large export 会显式显示：
    - `planning media prefetch scanned=... context=... local=... skip_old=...`
  - `export_status` 统一改成表达“导出流程是否完成”：
    - 成功写出 bundle 时为：
      - `success`
  - 细分结果继续留在：
    - `export_verdict`
  - 同时新增 note：
    - 若存在 actionable missing，会明确提示优先查看 `actionable_missing_reason` 和 trace
- maintainer 侧 live 验证：
  - `export-history group 922065597 --limit 2000 --format jsonl`
  - 现在在 prefetch 阶段可见连续心跳：
    - `planning media prefetch scanned=105/570 context=41 local=64 skip_old=0 ...`
    - `planning media prefetch scanned=500/570 context=248 local=247 skip_old=0 ...`
    - `planned media prefetch scanned=570/570 context=254 local=304 skip_old=0 ...`
  - 最终结果块也已变成：
    - `export_status=success export_verdict=success_with_background_missing`
- 当前价值：
  - operator 终于能区分：
    - 真卡死
    - 还是正在做 prefetch 规划
  - 导出完成后的 `status` / `verdict` 语义也更直观，不再互相打架

### [2026-03-21][042] maintainer 侧 `10000` live smoke 已验证新心跳；朋友现场 trace 还单独暴露了一条视频恢复缺口

- maintainer 侧 live smoke：
  - `export-history group 922065597 --limit 10000 --format jsonl`
  - 当前已能稳定显示：
    - `planning media prefetch scanned=... context=... local=... skip_old=... rate=... elapsed=...`
  - 最终结果：
    - `export_status=success`
    - `export_verdict=success_with_background_missing`
    - `actionable_missing=0`
- 朋友提供的复制现场：
  - [state - 副本](C:/Users/Peter/Downloads/state%20-%20副本/state%20-%20副本) 里的 root export trace 仍显示另一条独立问题线：
    - group `763328502`
    - `message_count=10000`
    - `elapsed_s≈856.4`
    - `missing_after_napcat=18`
    - 资产类型全部落在：
      - `video`
  - trace 里当前最慢一步：
    - `resolver=missing_after_napcat`
    - `asset_type=video`
    - `slowest_materialize_step_s≈44.1`
- 当前判断：
  - `prefetch` 面板“像卡死”这一层已经和真正的 exporter 主链分离开了
  - 朋友那份超慢失败现场更像是：
    - 另一条尚未收完的 `video/public_token_get_file` 恢复链问题
  - 后续修复要单独盯：
    - 大窗视频 missing cluster 的 bounded probe
    - 不再把它和 prefetch 可视化问题混在一起

### [2026-03-21][043] `10000` tail export 的 overshoot 与老视频 actionable 误报已收口

- 新发现并修复的两处问题：
  - `tail boundary bridge` 在重复 anchor 边界补桥时可能追加超过请求上限，导致 `--limit 10000` 实际导出 `10047` 条
  - 老 `video` 资产的 `public_token -> get_file` 可能返回：
    - `file=""`
    - `url=<已失效本地路径字符串>`
    - 旧逻辑会把它漏成 `missing_after_napcat`
- 当前处理：
  - bridge 追加已经显式卡住 `data_count`
  - 旧 `video/file` 的 blank-payload / stale-local-url `get_file` 返回现在会归到：
    - `qq_expired_after_napcat`
- maintainer live re-run：
  - `export-history group 922065597 --limit 10000 --format jsonl`
  - 当前结果：
    - `records=10000`
    - `export_status=success`
    - `export_verdict=success_with_background_missing`
    - `actionable_missing=0`
    - `background_missing=900`

### [2026-03-22][044] `forward video` timeout storm 已增加旧资产断路器，避免整窗被大量不同 parent 的 12s 超时拖死

- 朋友新现场截图暴露的真实问题不是“导出 failed 后又复活”，而是两层叠加：
  - UI 把单个 asset 子步骤超时渲染成了 `status=failed`
  - 实际主导出循环仍在继续，因此后面又回到 `status=in progress`
- maintainer 侧新增了本地模拟器，用来专门复现：
  - 同一 `forward_parent` 下兄弟 `video/file/speech`
  - 大量不同 `forward_parent` 的老 `video`
  - `forward_context_metadata`
  - `forward_context_materialize`
  - `public_token_get_file / get_record`
  - `direct_file_id_get_file`
- 当前新增的导出器硬化：
  - old forward `video/file/speech` 一旦在某条恢复路线上累计达到 timeout storm 阈值，就对同月同路由同 asset-role 的后续资产直接短路
  - 当前覆盖的 storm route：
    - `forward_context_metadata`
    - `forward_context_materialize`
    - `public_token_get_file`
    - `public_token_get_record`
    - `direct_file_id_get_file`
  - 仅对：
    - 有 `forward_parent` hint
    - 且时间足够老的资产
    生效，避免误伤近期懒加载媒体
- UI 侧修正：
  - asset 子步骤 `timeout / unavailable / storm_skip` 现在统一显示为：
    - `status=in progress ... continuing=1`
  - 避免把“单个 asset 恢复失败”误读成“整次导出终止”
- 新诊断信号：
  - `diag=... forward_timeout_breaker=<n>`
  - 便于从现场直接判断是不是 old-forward timeout storm 被断路器接管
