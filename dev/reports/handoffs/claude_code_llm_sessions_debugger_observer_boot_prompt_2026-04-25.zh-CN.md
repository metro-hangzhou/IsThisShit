# 给 Claude Code 的启动 Prompt：`LLM Sessions` ORCH Debugger / Observer UI 重构

把下面整段复制给 Claude Code。

```text
你接手 review-editor 的 `LLM Sessions` UI 重构。先不要直接写代码，必须先读这些文档并按文档边界执行：

1. dev/reports/handoffs/claude_code_llm_sessions_debugger_observer_replan_2026-04-25.zh-CN.md
2. dev/reports/handoffs/claude_code_llm_sessions_pcqq_chat_record_ui_assignment_2026-04-25.zh-CN.md
3. dev/reports/handoffs/review_editor_technical_index_2026-04-23.zh-CN.md
4. dev/reports/handoffs/claude_code_llm_sessions_final_report_ui_acceptance_fail_2026-04-25.zh-CN.md

目标不是再做一个普通 JSON viewer，而是把 `LLM Sessions` 收敛成 ORCH session debugger / observer：

- 像 ChatGPT Web / Claude Code 一样，以对话流为主线。
- 能实时看 session request、prompt、packet、tool call/result、token streaming、final structured output。
- 主 transcript 默认展示人能读懂的进展，不允许大段裸 JSON / Python repr 铺满页面。
- 长聊天记录、长 prompt、长 packet、长功能字段都要默认折叠。
- 原始 JSON / raw report 可以保留，但必须默认折叠并按需展开。
- emoji 可以使用，但只能做辅助状态/类型标识，不能替代文字标签、分组和层级。

Codex 刚补了后端/类型契约，你必须优先使用这些字段，不要继续只从 `human_report` 文本里猜结构：

- `activeSession.finalReportPayload`
- `activeSession.reviewSurfaceGuidance`
- `activeSession.inputPacket`
- `activeSession.sourceRunDir`
- `activeSession.resultSummary`

注意：`/api/review/llm/session/:id` 已不再返回完整 `result` 字段，这是为了避免大响应导致 Tauri WebView 崩溃。不要恢复完整 result。如果 UI 缺字段，先报告后端 gap。

本轮你只负责前端/UI，除非我明确批准，不要改：

- src/qq_data_analysis/llm_session_service.py
- src/qq_data_analysis/review_service.py
- scripts/run_review_editor_server.py
- apps/review-editor/src/App.vue 的 session registry / SSE 主逻辑

优先允许修改：

- apps/review-editor/src/components/LlmSessionPage.vue
- apps/review-editor/src/components/LlmFinalReportBlock.vue
- apps/review-editor/src/components/LlmFunctionalFieldBlock.vue
- apps/review-editor/src/components/LlmSessionChatPacketCard.vue
- apps/review-editor/src/lib/llmFinalReportParser.ts
- apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts
- 相关测试

必须解决的具体问题：

1. `finalReportPayload` / `reviewSurfaceGuidance` 要成为 final report 的主数据源。
2. `human_report` 只能作为人类摘要和 raw fallback，不能默认裸 `<pre>` 铺开。
3. “117 功能字段”这类长数组必须分组折叠，默认只显示 group summary 和少量代表条目。
4. `bearingness`、`baseline_role`、`shi_delta`、`priority`、`deprioritized`、`口吻层输出` 等都要标记为模型派生/编排/证据边界字段，不准伪装成原始聊天。
5. 聊天记录卡片要复用或贴近 review 页 PCQQ forward UI；优先看 `MessageBubble.vue`、`ForwardRecordViewer.vue`、`forwardWindow.ts`。
6. 如果数据只有 `user_xxx` alias，不要把它显示成真实 QQ 昵称；标记为“模型输入别名/匿名 sender”。不要猜真实名。
7. 如果某个数据源只是 `message_probes` 或模型摘要，标题必须写清“模型输入摘要 / 非原文”，不要伪装成完整原始聊天记录。

测试流程必须自己完成：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run
npm run tauri:build
```

如果需要启动 review server：

```powershell
cd D:\Coding_Project\IsThisShit
.\.venv\Scripts\python.exe scripts\run_review_editor_server.py --host 127.0.0.1 --port 43127
```

手动验收要求：

- 打开 Tauri review-editor。
- 进入 `LLM Sessions`。
- 选择最新真实 session。
- 检查主 transcript 不再有大段裸 JSON / Python repr。
- 检查 final structured output 是分组折叠的 debugger 视图。
- 检查点击聊天记录/模型输入摘要卡片时，窗口标题、身份标签、数据来源标签都准确。
- 检查 streaming mock/full spectrum session 仍能实时更新。

交付时请报告：

- 改了哪些文件。
- 哪些字段来自 Codex 新增契约。
- 哪些 UI 状态完成了。
- 真实 session 和 mock session 的验收结果。
- 如果仍有后端 gap，明确列出来，不要用前端猜测绕过去。
```
