# Claude Code 启动 Prompt

下面这段可以直接复制给 Claude Code：

---

你现在接手的是 `/mnt/d/Coding_Project/IsThisShit` 仓库里 `apps/review-editor` 的 `LLM Sessions` UI 重构工作。

## 你的目标
不要重写 backend，不要从头理解整个仓库。  
你的目标是：在现有已打通的 LLM session backend / SSE / persistence 基础上，把 `LLM Sessions` 页面重构成一个更像 **ChatGPT Web + Claude Code/Codex** 的会话式 UI。

## 你不需要重新做的事情
- 不重写 session backend
- 不重做 session types / SSE 契约
- 不拆 mock/live 两套链路
- 不回退自动发现 / 自动切换 / 自动流式显示
- 不把 source 选择再塞回左侧厚表单
- 不把页面做回 inspector-first / console-first

## 你必须先读的文档
先按这个顺序读：

1. `dev/reports/handoffs/claude_code_project_handoff_2026-04-23.zh-CN.md`
2. `dev/reports/handoffs/claude_code_llm_sessions_ui_handoff_2026-04-23.zh-CN.md`
3. `dev/reports/handoffs/review_editor_technical_index_2026-04-23.zh-CN.md`
4. `dev/reports/handoffs/review_editor_current_features_and_style_2026-04-23.zh-CN.md`
5. `dev/reports/handoffs/llm_sessions_backend_frontend_map_2026-04-23.zh-CN.md`
6. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_reference_method.zh-CN.md`
7. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round1_findings.zh-CN.md`
8. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round2_findings.zh-CN.md`

## 你必须先读的代码
按这个顺序：

1. `apps/review-editor/src/App.vue`
2. `apps/review-editor/src/components/LlmSessionPage.vue`
3. `apps/review-editor/src/App.test.ts`
4. `apps/review-editor/src/api.ts`
5. `apps/review-editor/src/types.ts`
6. `src/qq_data_analysis/llm_session_service.py`
7. `scripts/run_review_editor_server.py`

## 当前已通能力
- session list / detail / stream / registry 已通
- `chatMessages / packets / tokenChunks / conversationSummary` 已有稳定前后端契约
- mock session 与 live session 共用同一前端链
- 外部创建新 session 会自动出现在 sessions 页并自动切入
- 底部 composer、source bubble、thinking/tool/packet/report/warnings 都已有基础 UI

## 当前主要问题
不是功能没通，而是 UI 没收对：
- 整体骨架还不够像 ChatGPT Web
- tool / packet / system 的视觉层级还不够像 Claude Code / Codex 的工程轨迹
- app shell 仍残留本地桌面工具味道
- transcript 仍不够像正常聊天产品
- composer 还不够像真正的主输入栏

## 允许参考的对象
- **ChatGPT Web**
  - 主骨架真值
- **Claude Code / Codex**
  - tool / reasoning / engineering traces 的表达方式
- **OpenWebUI**
  - 开源聊天式 transcript / composer / tool block 的实现参考

注意：
- OpenWebUI 只是实现参考，不要反过来覆盖 ChatGPT Web 的主骨架

## 你必须继续使用的工作方法
不要只靠截图和主观感觉调 UI。  
继续沿用仓库现有的参考采样闭环：

- `apps/review-editor/scripts/ui_reference/capture_chatgpt_reference.mjs`
- `apps/review-editor/scripts/ui_reference/capture_review_editor_sessions.mjs`
- `apps/review-editor/scripts/ui_reference/compare_ui_references.mjs`

你需要先：
1. 补一份 ChatGPT Web conversation-state capture
2. 跑最新 review-editor sessions capture
3. 生成新的 diff
4. 写 `round3_findings`
5. 再开始改 UI

## 你接手后的第一轮工作顺序
1. 读上面列出的文档与代码
2. 跑真实 capture / diff
3. 写一份 round3 findings 文档
4. 重构 `LLM Sessions`
5. 回归：
   - `npm test`
   - `npm run build`
   - `npm run tauri:build`
6. 产出新的 capture / diff / findings

## 你这轮应该交付什么
- 一份新的 `round3_findings` 文档
- 一轮新的 `LLM Sessions` UI 重构
- 新的真实 review-editor capture
- 新的真实 diff 报告
- 前端测试与 build / tauri build 通过结果

你的重点不是补 backend，而是把 `LLM Sessions` 真正收成一个像 ChatGPT Web / Claude Code 的会话产品界面。

---
