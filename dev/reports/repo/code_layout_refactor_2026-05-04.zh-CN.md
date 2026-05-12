# 2026-05-04 代码结构重构记录

## 本轮目标

本轮落实“多文件、低行数、强命名、文件头说明”的维护规则，但不碰 QQ 数据导出器、NapCat、CLI 发布族等高回归风险区域。

核心边界：

- 允许重构 `src/qq_data_analysis` 与 `apps/review-editor/src` 中的 ORCH / LLM Session / 审阅展示相关代码。
- 不重构 `src/qq_data_core`、`src/qq_data_integrations/napcat`、`src/qq_data_cli`、`NapCat/`。
- 新增或明显重构的程序文件必须有文件头说明：负责什么、不负责什么、关键输入/输出。
- 新增模块保持单一职责，优先低于 800 行，必须低于 1000 行。

## 新增规则文档

- `dev/agents/CodeLayout_AGENTs.md`
  - 记录文件命名、模块拆分、文件头说明、行数阈值和当前排除区。
  - 已吸收本地参考 `D:\360极速浏览器X下载\chatgpt_personal_backup_selected_2026-05-03\代码文件组织方式_cb7fd8b321a3.json` 的结论：中大型 / agentic coding 项目优先模块化、多文件、单一职责、清晰命名，但不能拆到失去内聚。
- `dev/agents/INDEX.md`
  - 增加 CodeLayout 手册入口。

## 后端拆分

### ORCH engine

- `src/qq_data_analysis/orch/model_prompt_contract.py`
  - 拆出模型主审 system prompt 与 JSON 输出契约。
  - 避免 `engine.py` 混入长 prompt 文本。
- `src/qq_data_analysis/orch/model_result_contract.py`
  - 拆出模型输出的归一化、校验、证据案卷补全、人类报告投影。
  - `engine.py` 继续 re-export 旧私有函数名，减少测试和调用方震荡。
- `src/qq_data_analysis/orch/worker_event_boundary.py`
  - 拆出 worker 私有事件到 ORCH Observer 公共事件的边界转换。
- `src/qq_data_analysis/orch/source_packet.py`
  - 补文件头说明。
  - `summarize_source_packet()` 在 pass-through 情况下明确输出“QQ 原文完整保留”。
- `src/qq_data_analysis/orch/group_insights.py`
  - 补文件头说明。

结果：

- `src/qq_data_analysis/orch/engine.py`: 约 `1715 -> 938` 行。
- `src/qq_data_analysis/orch/model_result_contract.py`: `730` 行。
- `src/qq_data_analysis/orch/worker_event_boundary.py`: `79` 行。
- `src/qq_data_analysis/orch/model_prompt_contract.py`: `102` 行。
- `src/qq_data_analysis/orch/source_packet.py`: `998` 行，贴近上限，后续不要继续塞新逻辑。

### LLM Session service

- `src/qq_data_analysis/llm_sessions/frontend_contract.py`
  - 拆出前端事件/schema/payload budget/display label 常量。
- `src/qq_data_analysis/llm_sessions/view_model_helpers.py`
  - 拆出通用 ViewModel 纯函数、截断、安全 payload、tool summary helper。
- `src/qq_data_analysis/llm_sessions/final_report_view.py`
  - 拆出 final report、group insights、evidence package 的前端 ViewModel。
- `src/qq_data_analysis/llm_sessions/frontend_previews.py`
  - 拆出 packet/message/asset/prompt/source packet 预览投影。
- `src/qq_data_analysis/llm_sessions/relation_graph_projection.py`
  - 拆出 relation graph hydration、summary、asset enrichment。

结果：

- `src/qq_data_analysis/llm_session_service.py`: 第一轮从约 `6050 -> 3929` 行。
- 新拆出的 `llm_sessions/*.py` 均低于 1000 行。
- `llm_session_service.py` 仍是最大遗留债务，后续应继续拆 storage / runtime thread / stream detail builder。

### LLM Session service 第二轮

- `src/qq_data_analysis/llm_sessions/event_semantics.py`
  - 拆出 raw session event 到前端 canonical / semantic event 的投影逻辑。
  - 负责 phase、badge、semantic item、frontend snapshot，不负责 session 生命周期。
- `src/qq_data_analysis/llm_sessions/input_packet_assets.py`
  - 拆出输入消息、asset、review asset URL 的前端 payload 构造逻辑。
  - 负责让 packet / prompt 能显示 QQ 原文和 asset 状态，不负责实际媒体解析。
- `src/qq_data_analysis/llm_sessions/review_run_materials.py`
  - 拆出 review run / candidate / seed / materialized review packet 的解析与写回。
  - 负责把 ORCH session 产物落回 review-editor 可读的 review run，不负责 stream 事件组装。
- `src/qq_data_analysis/llm_sessions/runtime_state.py`
  - 拆出 session runtime dataclass、stream assembly state、JSON/JSONL 持久化小工具和 session 根目录常量。
  - 负责状态结构与文件读写 helper，不负责事件语义、前端 ViewModel、ORCH 执行或 SSE 订阅。

结果：

- `src/qq_data_analysis/llm_session_service.py`: 第二轮降到 `2803` 行。
- `event_semantics.py`: `686` 行。
- `input_packet_assets.py`: `242` 行。
- `review_run_materials.py`: `249` 行。
- `runtime_state.py`: `73` 行。
- `llm_session_service.py` 仍超过 1000 行，但已从“投影 + asset + materialize + runtime 混杂”收窄到 session manager / stream / mock runtime 主体。下一轮应拆 runtime thread、session storage、SSE detail builder。

## 前端拆分

- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
  - 从约 `1467` 行降到 `849` 行。
- `apps/review-editor/src/components/final-report/FinalReportHeader.vue`
  - 审阅报告标题和分页控件。
- `apps/review-editor/src/components/final-report/HeroCardPanel.vue`
  - verdict hero 区域。
- `apps/review-editor/src/components/final-report/GroupInsightsPanel.vue`
  - 群画像 / shi 成分面板。
- `apps/review-editor/src/components/final-report/groupInsightsModel.ts`
  - 群画像 ViewModel 归一化。

结果：

- 本轮触及的前端 final-report 文件均低于 1000 行。
- `ComposerDock.vue`、`ReviewWorkspacePage.vue` 仍超过 1000 行，属于后续 UI 拆分债务。

### LLM Session Page 第二轮

- `apps/review-editor/src/lib/llmSessionContractView.ts`
  - 拆出 session contract / context budget / relation graph 是否有内容的 ViewModel 逻辑。
- `apps/review-editor/src/lib/llmSessionTranscriptView.ts`
  - 拆出 transcript 行为判断、tool preview、状态文案、截断和 semantic source 文案。
- `apps/review-editor/src/lib/llmSessionPacketAssets.ts`
  - 拆出 packet/prompt asset 解析、missing asset 折叠、prompt preview、raw JSON preview。
- `apps/review-editor/src/components/LlmSessionRail.vue`
  - 拆出左侧 session 列表、刷新按钮、状态显示。
- `apps/review-editor/src/components/LlmSessionComposer.vue`
  - 拆出底部输入栏、run/candidate selector、提交按钮。
- `apps/review-editor/src/components/LlmSessionContractPanel.vue`
  - 拆出上下文预算、压缩契约、输入压力等 contract 面板。
- `apps/review-editor/src/components/LlmSessionTranscriptEntry.vue`
  - 拆出单条 session transcript entry 的渲染、raw/asset 折叠、packet/tool/report/stream 分支。

结果：

- `LlmSessionPage.vue`: `756` 行。
- `LlmSessionTranscriptEntry.vue`: `614` 行。
- `LlmSessionRail.vue`: `129` 行。
- `LlmSessionComposer.vue`: `174` 行。
- `LlmSessionContractPanel.vue`: `178` 行。
- LLM Session 页面主体已低于 1000 行，后续 UI 修改应优先进入上述细分组件或 `src/lib/llmSession*.ts`，不要再把新逻辑堆回 `LlmSessionPage.vue`。

### Group insights / shi 成分雷达

- `apps/review-editor/src/components/final-report/GroupInsightsPanel.vue`
  - 从“横向条形列表”升级为 `shi` 成分雷达，但雷达不是固定六轴。
  - 雷达只读取模型按当前窗口生成、且已绑定 QQ 原文证据的用户向 `shi` 类型轴。
  - 不足 `3` 个有效轴时宁可少显示或不显示，不允许用“硬件/技术 shi”“管人/八卦 shi”等通用分类补轴。
  - 继续保留右侧 / 下方轴列表，方便用户看分数和一句解释。
  - 新增窗口统计与说话风格样本区，补齐群画像 / 群友画像的主线可读层。
  - 群友画像主线不再显示 `QQ <uid>`，默认显示昵称或 alias，避免 raw 身份泄露。
- `apps/review-editor/src/components/final-report/groupInsightsModel.ts`
  - 增加 `display_policy` 防线。
  - 当 payload 明确声明非用户向来源 / provenance 轴时，前端不展示雷达，避免把内部诊断维度误画成用户向 `shi` 类型。
  - 归一化 `group_portrait` 的消息数、发送者数、资源数、缺失资源数，并把 `style_sample_pack` 投影为短样本列表。
- `src/qq_data_analysis/orch/engine.py`
  - model-led 路径和 deterministic/headless 路径统一补上 `group_insights`。
  - deterministic 路径不再只返回主审结论，后续无模型 smoke / 测试路径也能检验群画像契约。
- `src/qq_data_analysis/orch/group_insights.py`
  - `reply_count` 改为兼容 `has_reply` 与 `reply_to`。
  - 没有昵称时使用 `成员 <alias>`，不在主线裸露 raw sender id。
  - 2026-05-06 起移除 deterministic `shi` 类型兜底轴；该模块只保留群画像 / 群友行为画像的 deterministic 层。
- `src/qq_data_analysis/llm_sessions/final_report_view.py`
  - final report ViewModel 增加 `display_policy` 校验和 `axisId` 投影。
  - 不匹配用户向动态 `shi` 成分契约的 group insights 不进入主线 UI。

结果：

- `GroupInsightsPanel.vue`: `511` 行。
- `groupInsightsModel.ts`: `621` 行。
- `engine.py`: `970` 行，仍低于 1000 行上限。
- `group_insights.py`: `423` 行。
- `final_report_view.py`: `934` 行。

### Preprocess package export 修复

- `src/qq_data_process/__init__.py`
  - 补出 `RagService`、local corpus resolver、detect helpers 的 package-level 导出。
  - 原因：全量 pytest 收集阶段暴露 `tests/test_rag_retrieval.py` 仍从 `qq_data_process` 包根导入 `RagService`，包根未导出会直接 ImportError。

## 测试结果

已通过：

- `powershell.exe -Command "& .\\.venv\\Scripts\\python.exe -m py_compile src\\qq_data_analysis\\llm_session_service.py src\\qq_data_analysis\\llm_sessions\\event_semantics.py src\\qq_data_analysis\\llm_sessions\\input_packet_assets.py src\\qq_data_analysis\\llm_sessions\\review_run_materials.py src\\qq_data_process\\__init__.py"`
- `powershell.exe -Command "& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_llm_session_service.py tests\\test_llm_session_candidate_resolution.py tests\\test_chat_orchestrator_runtime.py tests\\test_rag_retrieval.py -q"`
  - `71 passed`
- `powershell.exe -Command "& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_final_report_view.py tests\\test_chat_orchestrator_runtime.py -q"`
  - `40 passed`
- `powershell.exe -Command "& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_llm_session_service.py tests\\test_llm_session_candidate_resolution.py tests\\test_chat_orchestrator_runtime.py tests\\test_final_report_view.py -q"`
  - `70 passed`
- `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "& .\\node_modules\\.bin\\vue-tsc.cmd --noEmit"`
- `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "npm run test"`，工作目录 `apps/review-editor`
  - `12 passed`, `63 tests passed`
- `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "npm run tauri:build"`，工作目录 `apps/review-editor`
  - 已按授权 `taskkill /IM review-editor.exe /F` 后重跑。
  - 输出：`apps/review-editor/src-tauri/target/release/review-editor.exe`

全量 pytest 状态：

- 命令：`powershell.exe -Command "& .\\.venv\\Scripts\\python.exe -m pytest tests -q --tb=short --disable-warnings --maxfail=40"`
- 结果：`35 failed, 371 passed, 1 skipped, 5 errors`，到 `--maxfail=40` 后停止。
- 失败分布不集中在本轮重构文件，主要包括：
  - Windows temp 目录权限导致 `tmp_path` fixture 创建失败。
  - CLI / REPL 入口公开符号漂移。
  - NapCat bootstrap fake client 与实现接口不一致。
  - media bundle / exporter 旧断言与当前 NapCat-only 媒体策略不一致。
  - 旧 analysis fixture 断言与当前 Benshi/ORCH 分析输出漂移。
- 结论：全量 suite 目前不是绿色基线，本轮以触达面的定向 suite + 前端完整 suite + Tauri build 作为验收准入；全量 suite 需要单独的测试基线清理任务。

## 剩余债务

这些文件仍超过 1000 行，本轮没有强行拆完：

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/review_service.py`
- `src/qq_data_analysis/benshi_pack.py`
- `src/qq_data_analysis/benshi_llm_agent.py`
- `src/qq_data_analysis/benshi_prompting.py`
- `src/qq_data_analysis/benshi_agent.py`
- `src/qq_data_analysis/llm_agent.py`
- `src/qq_data_analysis/substrate.py`
- `src/qq_data_analysis/llm_window.py`
- `apps/review-editor/src/components/ComposerDock.vue`
- `apps/review-editor/src/components/ReviewWorkspacePage.vue`

后续建议顺序：

1. 继续拆 `llm_session_service.py` 的 runtime/storage/stream 三块，减少前后端联动调试成本。
2. 拆 `benshi_pack.py` 与 `benshi_prompting.py`，为群画像、群友画像、shi 成分分析扩展留空间。
3. 拆 `ComposerDock.vue` / `ReviewWorkspacePage.vue`，但优先级低于 ORCH 主线。
4. 单独开“全量测试基线清理”任务，先把 temp 权限、CLI fixture、media bundle fixture 分层处理。
5. 暂不碰 QQ 导出器族，直到单独规划回归测试。
6. 关系图 UI 仍只是临时可用状态，后续需要按 ORCH Observer 的审查目标重做真正的关系图，而不是继续堆列表式关系卡。
