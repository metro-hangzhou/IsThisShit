# Claude Code 项目总交接

> 日期：2026-04-23  
> 交接重点：`apps/review-editor` 的 `LLM Sessions` UI 重构  
> 目标受众：Claude Code  

## 1. 项目一句话定位
这个仓库不是单一小工具，而是三条工作线并存的本地工程：

1. QQ / NapCat 数据导出与媒体恢复
2. `shi analyzer / chat orchestrator` 分析底座
3. `review-editor` 人工审核与 live session 可视化前端

你当前接手的重点只在第 3 条，尤其是：
- `apps/review-editor`
- 其中的 `LLM Sessions` 页面

## 2. 现在最重要的事实
你不需要重新怀疑这些前提：

- `LLM Sessions` 不是“后端没通”，而是“UI 没收对”
- session persistence、detail、SSE stream、registry stream 都已经通
- mock session 与 live session 共用同一条前端链
- 外部创建 session 自动出现在 sessions 页并自动切换，这条行为已经实现
- 当前最大的卡点是：
  - 页面骨架不像 ChatGPT Web / Claude Code
  - 对话层级与工程痕迹层级没有拉开
  - `sessions` 页仍残留过重的本地工具 / console 气质

## 3. 仓库结构只看这些
你不需要从头遍历整个 repo。先理解这些入口就够：

### A. `apps/review-editor/`
本地 Vue + Tauri 审核工作台。

最重要文件：
- `apps/review-editor/src/App.vue`
  - 顶层壳，`review` / `sessions` 页面切换
- `apps/review-editor/src/components/ReviewWorkspacePage.vue`
  - 旧人工审核主界面
- `apps/review-editor/src/components/LlmSessionPage.vue`
  - 当前 UI 重构主战场
- `apps/review-editor/src/api.ts`
  - review / llm session 前端 API 适配层
- `apps/review-editor/src/types.ts`
  - `LlmSessionSummary / Detail / StreamEvent` 等核心类型
- `apps/review-editor/src/App.test.ts`
  - sessions 页主要回归测试

### B. `src/qq_data_analysis/llm_session_service.py`
`LLM Sessions` 后端主服务。

你接手 UI 时需要知道：
- session 根目录：`state/llm_sessions/`
- session summary / detail / events / snapshots 都从这里来
- 它会驱动 orchestrator，并把前端需要的 message / packet / chunk 结构化出来

### C. `scripts/run_review_editor_server.py`
本地 Python review server。

职责：
- 暴露 review 相关 API
- 暴露 llm session 列表/detail/stream/registry
- 支持 mock session 启动

### D. `src/qq_data_analysis/orch/`
chat orchestrator runtime 骨架。

这次 UI 重构不需要你先重写它，但你需要知道：
- `LLM Sessions` 只是它的一个实时观察面
- 现在的 UI 应展示 orchestrator 的 prompt / tool / packet / stream 结果

### E. `dev/reports/analysis/reference/methods/`
当前已经写好的方法文档、round findings、orchestrator 文档都在这里。

### F. `state/ui_reference/`
真实 ChatGPT Web capture、真实 review-editor capture、真实 diff 报告都在这里。

## 4. 当前 `review-editor` 在项目中的角色
`review-editor` 不是产品站点，而是本地桌面审核/调试工作台。

它当前有两个页面：

### `Review`
偏 QQ-like / dense workbench。
用途：
- run / candidate / card 选择
- message list
- model panel
- composer / save / reparse
- profile drawer

### `LLM Sessions`
目标应该是聊天产品式 UI。
用途：
- 创建 / 继续一个 live session
- 流式看 prompt、tool、packet、reasoning、token content
- 离线回放已完成 session

当前问题：
- 它还没有真正收成“聊天产品”
- 只是比最初的控制台版好了不少

## 5. 你接手前必须知道的现状
### 已经通了的能力
- `fetchLlmSessions`
- `fetchLlmSession`
- `startLlmSession`
- `subscribeToLlmSession`
- `subscribeToLlmSessionRegistry`
- session 自动发现 / 自动切换
- mock session 自动启动并显示
- `chatMessages / packets / tokenChunks / conversationSummary` 前后端契约

### 当前最卡的能力
- 页面骨架
- transcript 阅读感
- tool / packet / system 的层级表达
- composer 关系
- `sessions` 页与 app shell 的视觉分离度

## 6. 已有方法与真值
你必须沿用，不要重造：

- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_reference_method.zh-CN.md`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round1_findings.zh-CN.md`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round2_findings.zh-CN.md`

真实 capture / diff：
- `state/ui_reference/chatgpt_web/2026-04-19T18-59-03.043Z`
- `state/ui_reference/review_editor_sessions/2026-04-20T12-07-19.759Z`
- `state/ui_reference/diff_reports/2026-04-19T19-24-18.397Z_ui_reference_diff.md`

规则：
- 继续使用 capture -> diff -> findings -> UI 改动 -> 再 capture 的闭环
- 不要回到“凭截图和记忆调 UI”

## 7. 可以参考什么
你可以参考这些东西来接手 `LLM Sessions`：

- **ChatGPT Web**
  - 页面骨架
  - rail / transcript / composer 关系
- **Claude Code / Codex**
  - tool call / tool result / reasoning 的工程表达方式
- **OpenWebUI**
  - 开源聊天式 transcript、tool block、composer 组织方式

注意优先级：
- ChatGPT Web 是整体骨架主真值
- Claude Code / Codex 是工程轨迹表达参考
- OpenWebUI 是开源实现参考，不要让它反过来覆盖主骨架

## 8. 你不需要先做什么
先不要：
- 重写 session backend
- 重设 session 数据模型
- 重做 orchestrator
- 重写 `Review` 页
- 重新理解整个 NapCat/Exporter 体系

## 9. 建议你接手时先读
按这个顺序：

1. `apps/review-editor/src/App.vue`
2. `apps/review-editor/src/components/LlmSessionPage.vue`
3. `apps/review-editor/src/App.test.ts`
4. `apps/review-editor/src/api.ts`
5. `apps/review-editor/src/types.ts`
6. `src/qq_data_analysis/llm_session_service.py`
7. `scripts/run_review_editor_server.py`
8. 上面那 3 篇 `review_editor_llm_sessions_ui_*` 文档

## 10. 当前交接结论
你接手的不是“修几个 bubble”，而是：
- 在不破坏现有 session 功能链的前提下
- 把 `LLM Sessions` 真正收成一个像 ChatGPT Web / Claude Code 的会话式 UI

这件事现在已经具备：
- 真实参考
- capture 方法
- diff 方法
- round1/round2 findings
- 已经打通的 session 后端与流式链

你不需要从 0 开始。
