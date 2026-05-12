# Claude Code `LLM Sessions` 改动盘点

> 日期：2026-04-23  
> 分支：`full-dev`  
> 目的：盘清 Claude Code 这轮到底改了什么、主要推进的是哪一层。

## 1. 证据范围
本盘点基于以下对象：

- 当前代码：
  - `apps/review-editor/src/App.vue`
  - `apps/review-editor/src/components/LlmSessionPage.vue`
  - `apps/review-editor/src/composables/useTranscript.ts`
  - `apps/review-editor/src/api.ts`
  - `apps/review-editor/src/types.ts`
- 旧版本对照：
  - `apps/review-editor/src/components/LlmSessionPage.vue.bak-codex`
- 本轮新增文档 / 产物：
  - `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round3_findings.zh-CN.md`
  - `state/ui_reference/review_editor_sessions/2026-04-23T08-54-25.105Z`
  - `state/ui_reference/diff_reports/2026-04-23T08-57-31.513Z_ui_reference_diff.md`

## 2. 总结结论
Claude Code 这轮主要推进的是：

- **前端 UI 结构收敛**
- **基于 capture/diff 的 UI 调整**
- **transcript 呈现方式重排**

它**不是**一次 session backend 扩面，也不是 orch runtime 功能扩面。

更准确地说，这轮工作的主轴是：
- 把 `LLM Sessions` 从“packet/inspector 风格页面”拉向“transcript-first 页面”
- 同时继续沿用 capture -> diff -> findings 的 UI 方法链

## 3. 明确新增 / 改动了什么

### A. `LlmSessionPage.vue` 被重构成 transcript-first
相对 `LlmSessionPage.vue.bak-codex`，当前版本有这些明显变化：

- rail 顶部 header 被收薄
- 中间主区从 `session-stage / session-bubble / session-packet / session-operation` 大块结构
  改成更单列的：
  - user
  - assistant
  - thinking
  - tool
  - context
- transcript 前 chrome 被压缩
- composer 从较厚的 `session-composer` 壳体收成更薄的底部输入栏

这说明它做的是：
- 页面阅读结构的重排
- 元素层级的弱化
- 更接近 ChatGPT conversation-state 的骨架

### B. 新增 `useTranscript.ts`
当前有新的：
- `apps/review-editor/src/composables/useTranscript.ts`

它的作用不是 backend 改造，而是前端阅读层归并：
- `user` 独立 turn
- `assistant reasoning + content` 合并成 assistant entry
- 连续 `tool_call/tool_result` 归成 tool group
- `prompt/chat_packet/system` 归成 context group
- stream chunk 做 dedupe

这是一种典型的“显示层重组”，不是 wire protocol 改造。

### C. `App.vue` 的 session 主链仍是既有链，但做了更完整的 active merge
从当前 `App.vue` 看，session 行为主链已经比较完整：

- `refreshLlmSessions`
- `selectLlmSession`
- `attachLlmSessionStream`
- `startLlmSessionRegistryStream`
- `startLiveLlmSession`

这轮没有看到新的 session backend 语义接入，但有比较清晰的 active merge：
- `sessionPatch` 合并到 active summary/detail
- `packet` 追加
- `message` 按 `messageId` upsert
- `chunk` 追加

这说明 CC 接手后没有重建 session 模型，而是沿用了既有 runtime/stream 体系。

### D. 新增 round3 findings 与新的 capture/diff
当前 repo 已经有：
- `review_editor_llm_sessions_ui_round3_findings.zh-CN.md`
- 2026-04-23 新的 ChatGPT conversation-state capture
- 2026-04-23 新的 review-editor capture
- 新的 diff report

这说明 CC 至少按交接要求继续沿用了“真实参考采样 -> findings -> UI 修改”的方法链，而不是完全脱离 capture 继续手调。

## 4. 这轮没有明显推进什么

### A. 没有看到新的 backend session API 面
当前 `scripts/run_review_editor_server.py` 仍主要提供：
- list
- detail
- session stream
- registry stream
- start
- mock-start
- stop
- retry

没有看到新的：
- `/session/:id/input`
- `/session/:id/control` 的更丰富动作
- `/materialize-review`
- `/live-review-runs`

### B. 没有看到 orch runtime 侧的新能力扩面
当前真实 live session 仍依赖既有：
- `context.prepared`
- `chat_packet.built`
- `tool.requested/completed`
- `prompt.built`
- `session.stream_chunk`
- `session.materialized_review_run`

这轮看不到新的 orch event family，也看不到新的 control plane。

### C. 没有看到 review bridge 的前端入口扩展
虽然 backend 有 `materialized_review_run_id/label`，但当前前端并没有把这条桥显式暴露成：
- live runs source
- review jump
- materialized run CTA

## 5. 这轮改动的实际效果

### 正向效果
- 页面第一眼更像聊天产品而不是控制台
- transcript 阅读流比旧版更干净
- user / assistant / thinking / tool / context 的结构更清晰
- 继续维持了 registry 自动切换与 SSE 主链

### 副作用 / 风险
- prompt / packet / tool detail 被压缩得更弱
- orch 工程痕迹的可观察性下降
- context 被泛化成一类折叠块，弱化了 prompt / packet / system 的语义区别
- UI 更像聊天页了，但不一定更符合 orch session 的观察目标

## 6. 盘点结论
可以把 Claude Code 这轮工作定性为：

### 主要是
- `LLM Sessions` 前端显示层重构
- ChatGPT conversation-state 对齐
- transcript-first 结构收敛

### 不是
- session backend 扩面
- orch runtime 扩面
- review bridge 扩面
- live control plane 扩面

因此后续 review 不应问“它有没有把 session 全做完”，而应问：

1. 它把 UI 收到了哪一步  
2. 它是否在 UI 收敛过程中牺牲了 orch observability  
3. 哪些原本该有的 session 功能仍然没被 UI 暴露出来

## 7. 一个额外信号
当前 repo 里仍保留：
- `apps/review-editor/src/components/LlmSessionPage.vue.bak-codex`

这说明本轮改动是一次较大的前端页面重写/替换。  
它在研究层面很有价值，因为可以直接对照“改前 / 改后”，但后续进入正式收尾阶段时应考虑清理或转移到更合适的比较产物目录，避免把临时备份长期留在源码树中。
