# Claude Code `LLM Sessions` A+B 启动 Prompt

把下面整段直接发给 Claude Code：

```text
你现在继续接手 `/mnt/d/Coding_Project/IsThisShit` 里的 `apps/review-editor`，但这轮只处理 `LLM Sessions` 的前端 / UI / 既有能力接线，不允许改 backend/runtime。

先读这些文档：
1. `/mnt/d/Coding_Project/IsThisShit/dev/reports/handoffs/llm_sessions_parallel_work_boundary_2026-04-23.zh-CN.md`
2. `/mnt/d/Coding_Project/IsThisShit/dev/reports/handoffs/claude_code_llm_sessions_ab_ui_assignment_2026-04-23.zh-CN.md`
3. `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/methods/orch_session_baseline_reconstruction_2026-04-23.zh-CN.md`
4. `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/methods/cc_llm_sessions_delta_inventory_2026-04-23.zh-CN.md`
5. `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/methods/cc_llm_sessions_functioning_review_2026-04-23.zh-CN.md`
6. `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_reference_method.zh-CN.md`
7. `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round3_findings.zh-CN.md`

然后读这些代码：
1. `/mnt/d/Coding_Project/IsThisShit/apps/review-editor/src/App.vue`
2. `/mnt/d/Coding_Project/IsThisShit/apps/review-editor/src/components/LlmSessionPage.vue`
3. `/mnt/d/Coding_Project/IsThisShit/apps/review-editor/src/composables/useTranscript.ts`
4. `/mnt/d/Coding_Project/IsThisShit/apps/review-editor/src/api.ts`
5. `/mnt/d/Coding_Project/IsThisShit/apps/review-editor/src/types.ts`
6. `/mnt/d/Coding_Project/IsThisShit/apps/review-editor/src/App.test.ts`

你这轮只做 A+B：
- A：纯 UI / 显示层问题
- B：前端接已有 backend 能力

不要做这些：
- 不改 `src/qq_data_analysis/llm_session_service.py`
- 不改 `scripts/run_review_editor_server.py`
- 不改 `src/qq_data_analysis/review_service.py`
- 不新增 continue/replay/backend API
- 不自己补 live review runs backend discovery

这轮的重点不是抽象地“更像 ChatGPT”，而是：
1. 恢复 orch observability
2. 把已有 backend 能力上屏
3. 同时保持聊天产品骨架

你必须解决这些点：
- prompt 要有清晰可读面，不能再完全吞进泛 context
- chat packet 要恢复明确语义
- tool call/result 要能展开 details / payload
- phase / evidenceGapCount / toolObservationCount 要有弱暴露
- 修掉 composer 当前“继续输入”的假语义
- stop / retry 要接到 UI
- materialized review run 要变成用户可见状态

允许参考：
- ChatGPT Web：主骨架
- Claude Code / Codex：tool / reasoning / engineering trace
- OpenWebUI：transcript / composer / collapsible engineering blocks 的实现参考

注意：
- OpenWebUI 只能作为实现参考，不能覆盖 ChatGPT Web 主骨架
- 如果你发现某个需求需要 backend 新字段或新接口，只能在 findings 里标成 `backend gap`，不要自行补 backend

允许改动的文件只有：
- `apps/review-editor/src/App.vue`
- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/api.ts`
- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/App.test.ts`
- `apps/review-editor/scripts/ui_reference/*`
- 本轮 findings / capture / diff 文档

本轮交付必须包括：
1. 新的 findings 文档
2. 新的 capture / diff
3. `LLM Sessions` 前端重构
4. stop / retry / materialized 状态等已有 backend 能力的 UI 接线
5. 如果有 backend gap，单列写清楚
```
