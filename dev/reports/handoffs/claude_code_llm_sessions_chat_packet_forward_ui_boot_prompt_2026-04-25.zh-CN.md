# 给 Claude Code 的启动 Prompt

请直接复制下面这段给 Claude Code。

```text
你现在接手 review-editor 的 LLM Sessions 前端 UI 继续开发。先不要从头读项目，先读这份任务规格：

D:\Coding_Project\IsThisShit\dev\reports\handoffs\claude_code_llm_sessions_chat_packet_forward_ui_assignment_2026-04-25.zh-CN.md

目标：修复 LLM Sessions 页面里聊天记录 / prompt packet / model context 被直接摊成大段 JSON 或 Python repr 的问题。聊天记录默认折叠成 Review 页现有 PCQQ forward card 风格；点击后复用 Review 页现成的 ForwardRecordViewer 和 openForwardWindow，在独立 Tauri 子窗口显示完整聊天记录，失败则 fallback 到页面内 modal。不要自己再造一套聊天记录 UI。

关键要求：

1. 只改 apps/review-editor 前端/UI。不要改 Python backend、orchestrator、模型配置、review server。
2. 必须复用这些现有代码：
   - apps/review-editor/src/components/MessageBubble.vue 里的 forward card 视觉
   - apps/review-editor/src/components/ForwardRecordViewer.vue
   - apps/review-editor/src/forwardWindow.ts 的 openForwardWindow(detail)
   - apps/review-editor/src/forwardRecord.ts / types.ts 中的 ForwardDetail / ForwardMessageEntry 类型
3. 建议新增 apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts，把 LLM session jsonPreview / prompt payload / message_probes 转成 ForwardDetail + functionalFields。
4. `jsonPreview.messages` / `selected_messages` / `inputPacket.messages` 是完整聊天记录时，按原文聊天记录处理。
5. `message_first_context.message_probes` 只是模型输入摘要，不是完整原文。可以用 ForwardRecordViewer 展示预览，但 UI 必须标记“模型输入摘要 / 非完整原文”。
6. `baseline_role`、`shi_delta`、`bearingness`、`口吻层输出` 等模型/编排派生字段不能再裸文本显示成普通聊天原文。新增或扩展 functional field UI，用 badge/callout/table 明确标记为“模型推断”“编排字段”“证据边界”等。
7. Raw JSON 必须保留入口，但默认折叠；关闭时不要渲染大 `<pre>`，参考 LlmStructuredStreamBlock.vue 的 rawOpen 懒渲染。
8. 不要破坏已有 streaming token、asset thumbnail/lightbox、structured JSON streaming block。

完成后请运行：

cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run

交付时请说明：

- 改了哪些文件。
- 哪些地方复用了 ForwardRecordViewer / openForwardWindow。
- 完整 messages 和 message_probes 分别怎么显示。
- functional fields 怎么分类显示。
- raw JSON 是否默认折叠并懒渲染。
- vue-tsc / vitest 结果。
- 是否发现需要 Codex 处理的 backend/schema gap。
```

