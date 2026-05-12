# Claude Code `LLM Sessions` ORCH Debugger / Observer 重构总计划

> 日期：2026-04-25  
> 目标受众：Claude Code  
> 状态：Codex 已补后端 detail 结构化契约；CC 下一轮主做 UI 和交互收敛。  
> 重要补充：emoji 可以使用，但只能作为辅助标识，不能替代信息架构、分组、层级和可访问文本。

## 1. 产品目标

`LLM Sessions` 不是普通报告页，也不是把 JSON 美化一下的页面。它的目标是做成 ORCH session debugger / observer：

- 实时看到用户/脚本投递给 ORCH 的任务和聊天记录输入。
- 实时看到 prompt / packet / tool call / tool result / token stream。
- 看清模型当前状态、下行 token、结构化输出、失败/缺口/边界。
- 事后离线打开 session，能复盘“发了什么、模型怎么想、ORCH 调了什么工具、最终怎么 materialize 到 review packets”。
- UI 要像 ChatGPT Web / Claude Code 的对话流：主线信息先可读，调试细节按需展开。

设计原则：

- 主 transcript 默认展示“人能读懂的进展”，不是把所有 debug payload 展开。
- 长聊天记录、长 prompt、长 packet、长功能字段必须折叠。
- 原始 JSON 必须保留入口，但默认折叠并懒渲染。
- 功能字段要明确标记为“模型派生/编排/证据边界”，不能伪装成原始聊天文本。
- emoji 允许使用，但必须克制，用于状态或类型区分，例如 ✅ / ⚠️ / 🧰 / 🧠。不要用 emoji 堆砌替代组件设计。

## 2. 当前失败点

### 2.1 聊天记录身份显示不可靠

真实 session 里，`message_probes` / `inputPacket.messages` 目前常见的是：

```text
sender_id: user_d83a571bba
sender_name: user_d83a571bba
```

这不是 CC 的纯 UI bug。当前 session payload 里很多地方只有去敏 alias，没有 raw QQ 昵称。真实 raw 身份存在于 source analysis DB / review candidate enrichment 里，例如：

- `src/qq_data_analysis/review_service.py`
- `_load_raw_sender_lookup`
- `_apply_raw_sender_to_message`
- `_apply_raw_sender_to_card`

UI 处理要求：

- 如果数据只有 `user_xxx`，不要显示得像真实 QQ 昵称。
- 应标记为“模型输入别名”或“匿名 sender”。
- 不要自行猜真实用户名。
- 如果用户后续要求真实名显示，需要后端增加 source run identity lookup 给 LLM session detail；这属于 Codex/backend 任务，不是 UI 任务。

### 2.2 `message_probes` 不是原始聊天记录

模型报告中的 `message_probes` / `bearingness` 等字段是模型输出的摘要/证据索引，不是完整原始聊天记录。

UI 处理要求：

- 不要把这些字段直接用 PCQQ forward viewer 当成“原文聊天”。
- 可以做成“模型输入摘要”或“证据索引”卡片。
- 只有真正来自 `inputPacket.messages` 或 review candidate context 的消息，才适合 PCQQ-like 聊天记录窗口。

### 2.3 功能字段展开过度

当前截图里出现了 “117 功能字段”，并且一条条展开成大量浅蓝卡片。这不符合 debugger 目标。

正确方向：

- 默认只展示 group summary。
- 每组最多显示 3-8 个最关键条目。
- 长数组只显示数量、前几个代表条目、风险摘要。
- 详细字段进 inspector / details / raw JSON。
- 不能在主 transcript 中铺满 117 个 field cards。

### 2.4 `human_report` 解析不应继续作为主数据源

上一轮 CC 已经做了 `LlmFinalReportBlock` 和 `llmFinalReportParser`，但它仍然在从 markdown-ish `human_report` 文本里猜结构。

现在 Codex 已补了结构化后端字段：

- `activeSession.finalReportPayload`
- `activeSession.reviewSurfaceGuidance`
- `activeSession.inputPacket`
- `activeSession.resultSummary`

下一轮 UI 应优先消费这些结构化字段，只把 `finalReport` 当作人类可读摘要和 raw fallback。

## 3. Codex 已完成的后端/类型契约

本轮 Codex 改动文件：

- `src/qq_data_analysis/llm_session_service.py`
- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/api.ts`
- `tests/test_llm_session_service.py`

新增 `LlmSessionDetail` 字段：

```ts
finalReportPayload?: Record<string, unknown> | null;
reviewSurfaceGuidance?: Record<string, unknown> | null;
inputPacket?: Record<string, unknown> | null;
sourceRunDir?: string | null;
resultSummary?: Record<string, unknown> | null;
```

字段语义：

- `finalReportPayload`：优先来自 `analysis_output.compact_payload`，其次尝试 `structured_payload` / `payload` / `raw_payload`，已移除已知 heavy raw 字段。
- `reviewSurfaceGuidance`：优先来自 `finalReportPayload.review_surface_guidance`，其次来自 result 顶层 `review_surface_guidance`。
- `inputPacket`：来自 session request 的 `inputPacket`，保留前端可展示的模型输入消息，默认最多 300 条，超出时带 `messagesTruncated`。
- `sourceRunDir`：真实 source run 目录字符串，供 UI 显示来源，不要拿它直接做文件读取。
- `resultSummary`：替代原来 detail 里完整 `result.json` 的轻量摘要。

重要行为变更：

- `/api/review/llm/session/:id` 不再返回完整 `result` 字段。
- 这是故意的。完整 result 原样返回曾导致 Tauri WebView 大响应和 `STATUS_BREAKPOINT` 崩溃风险。
- 如果 UI 需要更多字段，应在 backend detail 增加明确的小字段，不要恢复完整 `result`。

## 4. CC 分工边界

CC 本轮只改前端 UI / 解析 / 测试。

优先允许修改：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
- `apps/review-editor/src/lib/llmFinalReportParser.ts`
- `apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts`
- 相关 `.test.ts`

除非用户明确批准，不要修改：

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/review_service.py`
- `scripts/run_review_editor_server.py`
- `apps/review-editor/src/App.vue` 的 session registry / SSE 自动切换主逻辑

如果发现后端缺字段：

- 先在交付报告里明确说明缺什么、为什么 UI 无法可靠实现。
- 不要在前端用字符串猜测或伪造真相。

## 5. 目标信息架构

主 transcript 只保留这些层级：

```text
Session header
├─ status / model / source / review run
├─ replay / reload / continue

Transcript
├─ User request
├─ Prepared context
│  ├─ input chat packet summary card
│  ├─ prompt packet summary card
│  └─ raw details collapsed
├─ Tool operations
│  ├─ requested / result / failed
│  └─ compact operation rows
├─ Model response
│  ├─ streaming text or structured stream preview
│  ├─ final structured report block
│  └─ raw collapsed
└─ Materialized review output
```

具体 UI 约束：

- 聊天记录卡片默认像 PCQQ forward card：标题、消息数、发送者数、2-3 行预览、asset/missing 摘要。
- 点击聊天记录卡片后，优先复用 `openForwardWindow` 和 `ForwardRecordViewer`。
- 如果数据是模型摘要而不是原始聊天记录，标题必须写“模型输入摘要 / 非原文”。
- `finalReportPayload` 按 top-level domain 分组，不要把每个叶子字段变成主流里的一个卡片。
- `reviewSurfaceGuidance` 应单独成组，适合显示“证据边界 / 承载度 / 复审提示”。
- `human_report` 作为最后的“Raw human report”默认折叠。

## 6. 功能字段显示规则

建议分组：

```text
模型结论
├─ judgment_verdicts
├─ shi_presence_verdict
├─ transport_pattern_verdict

证据与边界
├─ direct_evidence_layer
├─ evidence_gaps
├─ unknown_boundaries
├─ missing media / asset gap

推理与承载度
├─ structured_inference_layer
├─ bearingness
├─ local_anchor_bearingness
├─ shi_delta
├─ baseline_role

编排与调试
├─ evidence_acquisition_summary
├─ orchestrator_trace_summary
├─ tool observations
├─ priority / deprioritized
```

展示规则：

- 每组默认 collapsed 或半展开 summary。
- 每组显示数量、最重要 3-8 条、风险/边界摘要。
- 长数组不要逐条铺满主 transcript。
- 字段值是对象/数组时，用 compact key-value preview，不要直接 `JSON.stringify` 全量显示。
- Raw JSON 入口保留，但默认折叠。

## 7. PCQQ 聊天记录复用要求

已有实现文档：

- `dev/reports/handoffs/claude_code_llm_sessions_pcqq_chat_record_ui_assignment_2026-04-25.zh-CN.md`
- `dev/reports/handoffs/review_editor_technical_index_2026-04-23.zh-CN.md`

必须优先复用：

- `apps/review-editor/src/components/MessageBubble.vue`
- `apps/review-editor/src/components/MessageList.vue`
- `apps/review-editor/src/components/ForwardRecordViewer.vue`
- `apps/review-editor/src/forwardWindow.ts`
- `apps/review-editor/src/ForwardRecordWindowApp.vue`

不要再新造一个不一致的聊天记录窗口。

如果 `inputPacket.messages` 字段不够生成 `ForwardDetail`：

- 做一个明确的“模型输入摘要”卡片。
- 卡片可打开 inspector 显示输入消息列表。
- 不要谎称它是完整 QQ 原文。

## 8. 自测流程

CC 需要自己跑测试和手动验收，不要只写代码不看效果。

基础命令：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run
npm run tauri:build
```

如果需要后端：

```powershell
cd D:\Coding_Project\IsThisShit
.\.venv\Scripts\python.exe scripts\run_review_editor_server.py --host 127.0.0.1 --port 43127
```

手动验收：

- 打开 Tauri review-editor。
- 进入 `LLM Sessions`。
- 选择最新真实 session。
- 检查主 transcript 是否还有大段裸 JSON / Python repr。
- 检查 “117 功能字段” 是否被分组折叠，而不是全量铺开。
- 点击模型输入聊天卡片，确认窗口标题和数据来源标签正确。
- 若只有 alias 身份，应明确显示 alias，不伪装成真实 QQ 昵称。
- 运行一个 mock/full spectrum session，确认 streaming 时仍逐 token 更新。

## 9. 验收标准

本轮 UI 通过条件：

- 主 transcript 不再出现大段裸 `bearingness=[{...}]`、`baseline_role=[...]`、`shi_delta=[...]`。
- `finalReportPayload` 被用于结构化显示，`human_report` 不再是唯一主数据源。
- 长功能字段默认分组折叠，展开也不能撑爆页面。
- 模型输入摘要和真实聊天记录在标签上明确区分。
- PCQQ-like 聊天窗口复用 review 页实现或视觉一致。
- emoji 可以出现，但页面不能依赖 emoji 才能理解含义。
- `vue-tsc`、`vitest`、`tauri:build` 通过。
