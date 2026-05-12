# `LLM Sessions` 并行协作边界

> 日期：2026-04-23  
> 目的：把 Claude Code 与 Codex 的并行工作边界钉死，避免同时编辑同一批文件。

## 1. 总原则
本轮并行推进拆成两条线：

- **A+B：前端 / UI / 既有能力接线**
  - 负责人：Claude Code
- **C：真实 backend / runtime gap**
  - 负责人：Codex

分工目标是：
- CC 不碰 backend/runtime
- Codex 不碰 sessions 前端主显示层
- 双方通过文档和稳定协议对接，不抢同一文件

## 2. A / B / C 的正式定义

### A：纯 UI / 显示层问题
不需要 backend 新能力，只改前端表达。

包括：
- prompt / packet / tool / system / context 的显示层级重做
- phase / evidence / tool observation 的弱暴露
- tool payload / details 的可展开阅读面
- composer 的误导文案修正
- materialized 状态的视觉提示

### B：前端接已有 backend 能力
backend 已有数据或接口，但前端没接上。

包括：
- 把 detail 里的 `overlayManifest` / `result` / materialized 结果接入前端类型与显示
- 把已有 stop / retry 接到前端 UI
- 把 session 完成后的 review materialization 结果上屏

### C：真实 backend / runtime gap
这类问题不是纯前端能补出来的。

包括：
- 真实 `continue current session`
- 正式 replay / resume control plane
- `live review runs` 作为正式 review 数据源
- 如果需要让 registry / summary 直接感知 materialized 状态，则补 summary/patch wire shape

## 3. Claude Code 允许改动的文件
CC 这轮**只允许**改下面这些路径：

- `apps/review-editor/src/App.vue`
- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/api.ts`
- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/App.test.ts`
- `apps/review-editor/scripts/ui_reference/*`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_*`
- 本轮新增的 handoff / findings / capture / diff 文档

CC **不允许**改：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `src/qq_data_analysis/review_service.py`
- 任何 session backend / runtime / review discovery 代码

如果 CC 发现某个 UI 需求必须依赖 backend 新字段或新接口：
- 只能在 findings 文档中标注为 `backend gap`
- 不允许自行补 backend

## 4. Codex 允许改动的文件
Codex 这轮只负责 C，所以**只碰 backend/runtime 侧**。

当前锁定的 Codex 写集：
- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `src/qq_data_analysis/review_service.py`
- 相关 backend tests / 文档

Codex 这轮**不碰**：
- `apps/review-editor/src/App.vue`
- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- 其他 sessions UI 主文件

如果 C 实现需要前端后续配合：
- 由 Codex 先补 backend / wire shape
- 再通过文档通知 CC 接线
- 不在同一轮里同时改前端显示层

## 5. 当前优先级

### CC 优先级
1. 完成 A  
2. 完成 B  
3. 发现 backend gap 时停在文档，不越权

### Codex 优先级
1. 真实 continue API / runtime 设计与实现
2. replay / resume control plane 设计与实现
3. live review runs 正式 discoverability
4. 如有必要，再补 summary/patch 中 materialized 状态

## 6. 冲突防护规则

### Rule 1
CC 不改 backend 文件，Codex 不改 sessions 前端主文件。

### Rule 2
`apps/review-editor/src/api.ts` 与 `apps/review-editor/src/types.ts` 暂时归 CC。
如果 Codex 后续在 C 中新增 backend wire shape：
- 先写 backend
- 再通过文档把需要的字段列给 CC
- 不直接并发改前端适配层

### Rule 3
`review_service.py` 只归 Codex。
因为 `live review runs` / session materialization discoverability 会直接碰 review source 发现逻辑，不适合让 CC 顺手改。

### Rule 4
任何“这个点到底是 UI 问题还是 backend gap”不再靠口头说明，统一写进 findings / handoff 文档。

## 7. 这轮执行结果应该长什么样

### CC 交付
- 新的 findings
- 新的 capture / diff
- `LLM Sessions` UI 继续收敛
- stop / retry / materialized 状态等已有 backend 能力的前端接线

### Codex 交付
- continue / replay / live-review-runs 的 backend 方案和实现
- 对应 tests / 文档
- 明确列出给前端补接的新增字段或接口

## 8. 当前判断
这套拆法的核心价值是：

- CC 可以继续专注 `LLM Sessions` 的 UI 与前端产品感
- Codex 可以专注 session 作为 orch runtime surface 的本底能力
- 双方不会再在 `LlmSessionPage.vue` / `App.vue` / backend service 上交叉改同一层
