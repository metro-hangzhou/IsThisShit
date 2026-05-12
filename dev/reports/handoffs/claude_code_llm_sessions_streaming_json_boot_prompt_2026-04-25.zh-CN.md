# 给 Claude Code 的复制 Prompt

请接手 `review-editor` 的 `LLM Sessions` 前端 UI-only 修复。

先读这份任务文档：

- `dev/reports/handoffs/claude_code_llm_sessions_streaming_json_ui_assignment_2026-04-25.zh-CN.md`

重点目标：

- 修复模型流式输出 JSON 时的中间态展示。
- 不能等 JSON 完整闭合后才一口气显示；必须对已经到达的字段/片段做增量可读展示。
- 未闭合 JSON 不能作为普通 assistant prose 大段摊开占屏。
- 暂不可 parse 的尾部片段应默认折叠/降噪，但 raw stream 仍可手动展开。
- 完整 JSON parse 成功后切回稳定结构化/最终展示。
- 完成后仍 parse 失败时显示明确 invalid/incomplete 状态，raw 默认折叠。

分工边界：

- 只改前端/UI。
- 优先改 `apps/review-editor/src/components/LlmSessionPage.vue`、`apps/review-editor/src/composables/useTranscript.ts`。
- 可新增 `LlmStructuredStreamBlock.vue` 或 `structuredStreamPreview.ts`。
- 不要改 backend、orchestrator、模型配置、prompt、`state/config/llm.local.json`。

验收：

- 普通自然语言 streaming 仍即时显示。
- 未闭合 JSON streaming 不撑爆页面，并能增量看到已出现内容。
- 完整 JSON streaming parse 后稳定展示。
- 损坏 JSON 完成态显示 invalid/incomplete，raw 默认折叠。
- 运行 `npx vue-tsc --noEmit` 和 `npx vitest run`。

完成后报告改动文件、展示策略和测试结果。
