# Claude Code `LLM Sessions` A+B 任务单

> 日期：2026-04-23  
> 范围：只做 `LLM Sessions` 的前端 / UI / 既有能力接线  
> 不允许改 backend/runtime

## 1. 这轮目标
你这轮不是继续抽象地“让页面更像 ChatGPT”，而是：

在现有 session backend 主链不动的前提下，把 `LLM Sessions` 的**可观察性**和**前端可用性**补上。

这轮工作只包含：
- A：纯 UI / 显示层问题
- B：前端接已有 backend 能力

## 2. A：你必须解决的 UI 暴露问题

### A1. prompt 不能再被吞成泛 context
当前 backend 已经有：
- `llm.prompt_built`
- `prompt.built`

但当前 UI 基本把它吞成了 `context` 折叠块。  
这轮必须让用户明确看见：
- 这是 prompt
- 它和 chat packet/system 不是一回事

要求：
- 默认仍可折叠
- 但语义必须清晰
- 不允许重新做成控制台卡片墙

### A2. chat packet 要恢复明确语义
当前 packet 已经真实存在，但 UI 不够清晰。

要求：
- packet 需要有自己的摘要形态
- 长消息列表默认折叠
- 短 packet 可直接展开
- 用户能一眼区分 packet 与普通系统上下文

### A3. tool call/result 需要可追进去
当前 tool 摘要过轻。

要求：
- 保留 tool name / summary
- 保留展开后的 details / payload
- 继续维持 transcript-first，不回退成调试卡片墙

### A4. phase / evidence / tool observation 需要弱暴露
detail 里已经有：
- `phase`
- `evidenceGapCount`
- `toolObservationCount`

要求：
- 用极轻方式上屏
- 不抢 transcript 主体
- 但不能继续完全隐形

### A5. 修掉“继续输入”的假语义
当前页面会暗示“继续输入当前 session”，但实际上是新建 session。

这轮在 backend 没有正式 continue API 之前：
- 不要假装 continue 已存在
- 先改成不会误导用户的 UI 文案与状态语义

## 3. B：你可以直接接上的已有 backend 能力

### B1. stop / retry 前端接线
backend 已有：
- `POST /api/review/llm/session/:id/stop`
- `POST /api/review/llm/session/:id/retry`

你这轮可以直接把它们做成 UI controls。

### B2. materialized review run 上屏
backend 侧已具备：
- `session.materialized_review_run` event
- `review_packets_overlay_manifest.json`
- detail 里的 `overlayManifest`

这轮要把“这个 session 已经变成 review run”变成用户可见状态。

可接受形式：
- transcript 末尾结果块
- rail / active item 状态提示
- 结果 CTA

### B3. detail 中已有产物接线
当前后端 `get_session_detail()` 已会返回：
- `result`
- `events`
- `overlayManifest`

如果前端当前没 normalize 这些字段：
- 你可以在 `api.ts` / `types.ts` 补上
- 但只接已有字段，不发明新 backend 协议

## 4. 你不能做的事

### 不允许
- 改 `src/qq_data_analysis/llm_session_service.py`
- 改 `scripts/run_review_editor_server.py`
- 改 `src/qq_data_analysis/review_service.py`
- 新增 continue / replay backend API
- 新增 live review runs backend discovery

### 如果遇到 backend gap
只能：
- 在 findings 文档中明确列为 `backend gap`
- 指出缺什么字段 / 接口 / 行为

不能：
- 自己顺手补 backend

## 5. 当前建议读物
先读这些，不要跳：

- `dev/reports/analysis/reference/methods/orch_session_baseline_reconstruction_2026-04-23.zh-CN.md`
- `dev/reports/analysis/reference/methods/cc_llm_sessions_delta_inventory_2026-04-23.zh-CN.md`
- `dev/reports/analysis/reference/methods/cc_llm_sessions_functioning_review_2026-04-23.zh-CN.md`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_reference_method.zh-CN.md`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round3_findings.zh-CN.md`

## 6. 允许改动的文件

- `apps/review-editor/src/App.vue`
- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/api.ts`
- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/App.test.ts`
- `apps/review-editor/scripts/ui_reference/*`
- 本轮 findings / capture / diff 文档

## 7. 允许参考
- ChatGPT Web：主骨架
- Claude Code / Codex：tool / reasoning / engineering trace
- OpenWebUI：transcript / composer / collapsible engineering blocks 的开源实现参考

注意：
- OpenWebUI 只能作为实现参考
- 不要让它盖过 ChatGPT Web 的主骨架

## 8. 本轮交付要求
你这轮至少要交：

1. 新的 findings 文档  
2. 新的 capture / diff  
3. `LLM Sessions` 的前端重构  
4. stop / retry / materialized 状态等已有 backend 能力的 UI 接线  
5. 如果有 backend gap，明确列出，不要自己补 backend
