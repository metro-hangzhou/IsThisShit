# 给 Claude Code 的二次修复 Prompt

请直接复制下面这段给 Claude Code。

```text
上一轮 LLM Sessions chat packet / forward card UI 修复验收未通过。请先读新的失败说明和二次修复规格：

D:\Coding_Project\IsThisShit\dev\reports\handoffs\claude_code_llm_sessions_final_report_ui_acceptance_fail_2026-04-25.zh-CN.md

关键结论：你上一轮主要修了 entry.type === "prompt" / "packet"，但用户截图里仍裸显示的大段 `bearingness=[{...}]`、`baseline_role=[...]`、`shi_delta=[...]`、`口吻层输出` 来自 `activeSession.finalReport`。当前 LlmSessionPage.vue 的 final report 分支仍然是：

<LlmStructuredStreamBlock v-if="finalReportIsJson(activeSession.finalReport)" ... />
<pre v-else class="report-block__body">{{ activeSession.finalReport }}</pre>

真实 finalReport 是 backend 暴露的 `analysis_output.human_report`，开头是 Markdown `## Benshi Master LLM`，不是 JSON，所以 finalReportIsJson() 返回 false，最终仍落入裸 `<pre>`。这就是验收失败原因。

本轮只改 apps/review-editor 前端。不要改 Python backend、orchestrator、模型配置。

目标：

1. 新增 LlmFinalReportBlock.vue 和 llmFinalReportParser.ts（命名可调整），替换 LlmSessionPage.vue 中 final report 的裸 `<pre>` fallback。
2. parser 要处理 Markdown + Python repr / key-value 混合的 human_report，不要只用 JSON.parse。
3. 把 `baseline_role=`、`shi_delta=`、`bearingness=`、`priority=`、`deprioritized=`、`boundary=` 转成 LlmFunctionalFieldBlock 可显示的功能字段。
4. `口吻层输出:` 后续内容显示成独立 voice/口吻 section。
5. final report 的普通自然语言总结仍直接可读；结构化/派生字段不要裸文本摊开。
6. Raw report 入口保留，但默认折叠，关闭时不要渲染大 `<pre>`。
7. 不要回滚上一轮 LlmSessionChatPacketCard、ForwardRecordViewer/openForwardWindow、asset thumbnail/lightbox、raw 懒渲染等改动。
8. 如果 LlmStructuredStreamBlock 完整 JSON parse 成功且包含 domain keys，也尽量复用同一套 functional field renderer，不要只显示 generic key preview。

验收重点：

- 用户截图对应场景里，不再出现整屏 `bearingness=[{'message_uid': ...}]` 裸文本。
- 不再出现整屏 `baseline_role=[...]` / `shi_delta=[...]` 裸文本。
- `口吻层输出` 是独立 section。
- `priority` / `deprioritized` / `boundary` 是功能字段 badge/card。
- raw 默认折叠并懒渲染。

完成后运行：

cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run

交付时请说明：

- 改了哪些文件。
- final report 分支如何替换裸 `<pre>`。
- parser 如何处理 baseline_role / shi_delta / bearingness / 口吻层输出。
- raw 是否默认折叠并懒渲染。
- 是否保留上一轮 packet/forward card 行为。
- vue-tsc / vitest 结果。
- 是否仍需要 Codex 做 backend 结构化字段补充。
```

