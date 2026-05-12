# LLM Session / ORCH Observer backend budget handoff - 2026-04-26

## 背景

本轮目标不是继续局部美化 UI，而是把 ORCH Observer 的产品语义、后端事件契约、前端详情预算和验证方式收束到可验收状态。

用户侧核心诉求：

- ORCH Observer 是给人类审阅 Agent/ORCH 行为的调试观察器，不是把模型 JSON 或内部字段原样摊开。
- 主线必须按真实发生顺序展示，但展示内容要用户亲和，不能让人从一堆 raw key 里猜含义。
- QQ 原文必须用 PCQQ / forward 式样展示，方便一眼确认“这是 QQ 数据源原文，不是模型脑补”。
- 模型最终报告默认展示 `final_review` 这类人类可读结构；其他功能字段默认进入 Inspect / Raw。
- JSON 流式输出允许增量解析，但主线不应显示未闭合 JSON 原文。
- 普通 asset missing 是信息边界，不是错误 warning。
- 未来弱模型可能不稳定，因此前端与后端都要容忍字段缺失，但 V1 不做额外 repair call。

## 本轮后端修复

### 1. 详情响应预算

问题：

- 真实 session 详情曾达到约 7.54 MB。
- 其中 `semanticTimeline` 被旧事件污染到 13,657 行，约 6.46 MB。
- 原因是旧 persisted session 同时包含 `llm.stream_chunk` 和 `session.stream_chunk`；旧 `llm.stream_chunk` 的 payload 里又带了 semantic 快照，读详情时被误当成人类观察事件。

处理：

- 新代码只把 `session.stream_chunk` 作为 canonical stream event。
- `llm.stream_chunk` 被定义为 legacy duplicate，新写入路径不再发出。
- 详情读取时遇到旧 `llm.stream_chunk` / `session.stream_chunk` 不再进入 `semanticTimeline`。
- token chunk 详情只保留前端需要的最近 80 个 chunk；完整文本仍由运行态用于拼接，但前端详情响应会截断。
- 单个 stream chunk、累计 stream text、event payload value、packet JSON 都加了上限。

当前关键预算值：

- `MAX_FRONTEND_DETAIL_TOKEN_CHUNKS = 80`
- `MAX_FRONTEND_DETAIL_EVENTS = 120`
- `MAX_FRONTEND_EVENT_VALUE_CHARS = 800`
- `MAX_FRONTEND_STREAM_CHUNK_CHARS = 800`
- `MAX_FRONTEND_STREAM_TEXT_CHARS = 30000`
- `MAX_FRONTEND_PACKET_JSON_CHARS = 180000`
- `MAX_FRONTEND_PACKET_PREVIEW_MESSAGES = 300`
- `MAX_FRONTEND_PACKET_MESSAGE_TEXT_CHARS = 1000`

### 2. 保留聊天包可读性

问题：

- 只做粗暴 budget 时，chat packet 可能退化成一个 `omitted` 摘要，导致 PCQQ / forward viewer 无法打开真实消息行。

处理：

- 对 packet 内 `messages` 做 message-level preview，而不是整体丢弃。
- 默认保留最多 300 条消息，每条消息保留 sender、time、content preview、text content、segments、asset refs 等前端 viewer 需要的字段。
- 单条消息文本和 segment 文本独立截断，保留 truncation metadata。

当前真实 session `live_a4722917c6f5f6` 验证结果：

- detail size: 约 1.98 MB。
- `semanticTimeline`: 29 行。
- `conversationSummary.tokenChunkCount`: 13,628。
- `tokenChunks` retained: 80。
- Prepared packet / Effective prompt packet 保留 223 条 message 行。
- warning list 为空，asset missing 不进入 warning。

这个大小比 7.54 MB 明显下降，同时保留了 PCQQ viewer 所需的消息行。V1 暂不做跨 packet message array 去重；如果后续详情响应仍偏大，可以升级为 packet message cache / lazy packet endpoint。

### 3. final_review 翻译与人类预览

问题：

- `weak_shi`、`possible`、`qq_message`、`orch_observation` 等 enum 原文直接显示，会让 UI 看起来像 raw debug。

处理：

- 后端加入 `FRONTEND_ENUM_LABELS`，把常见 enum 转为中文人类可读标签。
- final report hero / section item / evidence record 使用 `_human_preview()`。
- `weak_shi` 当前显示为 `弱史 / 可能成立`。

### 4. 模型输出契约

处理：

- prompt 要求模型必须输出 `final_review`。
- `final_review` 是 ORCH Observer 默认主报告。
- 旧模型或弱模型缺字段时，后端 fallback 生成最小可读 `final_review`，并把完整模型字段留给 Inspect。
- 真实 GPT-5.5 session 已产出 `finalReviewViewModel.schemaVersion = llm_final_report_view_v2`。

## 本轮前端/契约修复

### 1. 前端 token retained 对齐

- `apps/review-editor/src/App.vue` 中 retained token chunks 调整为 80。
- 避免前端重新累积大量 chunk 导致页面和 Tauri WebView 压力过大。

### 2. 事件契约文档

文档已明确：

- canonical stream event 是 `session.stream_chunk`。
- `llm.stream_chunk` 是 legacy duplicate。
- 新代码不得再 emit `llm.stream_chunk`。
- 读旧 session 时必须忽略 persisted stream semantic 快照。

### 3. 产品契约文档

文档已明确：

- 主线显示“对人类有判断价值”的 ORCH 过程。
- raw/function/debug 字段不默认摊开。
- 大 packet 不能整体变成 `omitted`，必须尽量保留 message row 让 PCQQ viewer 可用。
- missing asset 是 info/boundary，不是 warning。

### 4. subagent 模型策略

共轨/subagent 文档已统一：

- 默认 delegated model: `gpt-5.5`
- 默认 reasoning effort: `xhigh`
- 不允许因为习惯继续回落到 `gpt-5.4`

涉及文件：

- `dev/agents/subagents/CONTRACT.md`
- `dev/handbooks/workbench/CommonTrackWorkflow.md`
- `dev/handbooks/workbench/CommonTrackWorkflow.zh-CN.md`
- `dev/handbooks/workbench/SubagentExecutionPolicy.md`
- `dev/handbooks/workbench/SubagentExecutionPolicy.zh-CN.md`
- `dev/agents/programs/common_track_workflow/AGENTs.program.md`
- `dev/agents/programs/common_track_workflow/AGENTs.program.zh-CN.md`

## 验证记录

已完成的验证：

- `tests/test_llm_session_service.py`: 15 passed。
- `tests/test_llm_session_service.py tests/test_benshi_llm_agent.py tests/test_benshi_master_agent.py`: 54 passed。
- `apps/review-editor`: `vue-tsc --noEmit` 通过。
- `apps/review-editor`: `npx vitest run` 通过，37 passed。
- mock full-spectrum session `mock_960646334e3fa6`：
  - detail size 约 164 KB。
  - `semanticTimeline` 17 行。
  - `session.stream_chunk` 存在。
  - 无 `llm.stream_chunk`。
  - packet message row 可保留。
- real GPT-5.5 session `live_a4722917c6f5f6`：
  - model: `gpt-5.5`
  - status: completed
  - `finalReportViewModel.schemaVersion`: `llm_final_report_view_v2`
  - 详情降到约 1.98 MB。
  - `semanticTimeline` 降到 29 行。
  - 223 条 chat packet message row 保留。

最终收尾验证：

- `.\.venv\Scripts\python.exe -m pytest tests\test_llm_session_service.py tests\test_benshi_llm_agent.py tests\test_benshi_master_agent.py -q`: 54 passed。
- `apps/review-editor`: `.\node_modules\.bin\vue-tsc.cmd --noEmit`: passed。
- `apps/review-editor`: `npx vitest run`: 37 passed。
- `apps/review-editor`: `npm run tauri:build`: passed。
- Tauri release binary: `apps/review-editor/src-tauri/target/release/review-editor.exe`。

## 明早人工验收建议

打开 Tauri review-editor 后，重点验收以下内容：

- 进入真实 session `live_a4722917c6f5f6`，页面不再 STATUS_BREAKPOINT。
- Final report hero 显示 `弱史 / 可能成立`，而不是 `weak_shi`。
- Final report 主体不再把一百多个功能字段垂直摊开。
- `Prepared packet` 和 `Effective prompt packet` 卡片能打开 PCQQ / forward 风格 viewer，并且能看到真实消息文本。
- 普通 image missing 只作为边界/信息，不进入错误 warning。
- 主 transcript 不再出现大段未闭合 JSON 原文。
- Inspect / Raw 仍能追到完整调试信息。

## 已知 V1 限制

- 真实详情目前约 1.98 MB，因为同一个 223-message packet 可能在多个 packet block 中重复出现。V1 先保留可审阅性，后续可做 lazy packet endpoint 或 message-array de-dup。
- 如果原始 export/packet 只保留匿名 sender id，PCQQ viewer 只能显示 `user_xxx`，不能凭空恢复昵称。
- 本轮没有再烧一轮新的真实 GPT-5.5 调用；最新改动集中在事件写入、详情预算和前端可消费数据结构，已用旧真实 session + mock full-spectrum session + regression 覆盖。

## 2026-04-26 afternoon UI follow-up

用户验收真实 live session `live_2d45c4818f7cb5` 后反馈：

- `判定结论` / `史对象与核心机制` section 展开后仍然有省略，不能完整查看。
- probe-only packet 的 `117 功能字段` 仍然在主线里呈现旧式调试字段，违背“功能/debug 字段默认进 Inspect/Raw”的产品约束。

处理：

- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
  - `verdicts` / `core` section 不再应用 visible item/record limit。
  - 展开后的 item value、record preview、meta value 改为可换行，不再 `nowrap + ellipsis`。
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
  - 对 `isProbeOnly` 的 packet，不再主线展开 `功能字段` 详情。
  - 只显示弱提示：模型输入调试字段已隐藏，可在 Raw/Inspect 查看。
- `apps/review-editor/src/components/LlmFinalReportBlock.test.ts`
  - 增加 verdict/core 不应折叠到 Raw/Inspect 的回归测试。
- `apps/review-editor/src/components/LlmSessionChatPacketCard.test.ts`
  - 增加 probe-only functional fields 不进入主线 inspector 的回归测试。

验证：

- `.\node_modules\.bin\vue-tsc.cmd --noEmit`: passed。
- `npx vitest run`: 39 passed。
- `npm run tauri:build`: passed。
