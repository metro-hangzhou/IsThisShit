# Claude Code `LLM Sessions` UI 专项交接

> 日期：2026-04-23  
> 目标受众：Claude Code  
> 重点：直接接手 `apps/review-editor/src/components/LlmSessionPage.vue`

## 1. 目标 UI 语义
`LLM Sessions` 的目标不是“调试台”，而是：

- **整体骨架**向 ChatGPT Web 靠
- **tool / reasoning / packet** 的表达方式向 Claude Code / Codex 靠
- **实现与组织方式**可以参考 OpenWebUI

正确形态应该是：
- 左侧轻量 session rail
- 中间单列 transcript
- 底部固定主输入栏
- transcript 是主视觉
- tool / packet / system 默认弱化

错误形态是：
- inspector-first
- 控制台-first
- 卡片墙
- 左侧厚表单

## 2. 当前已经实现到哪
你不需要重做这些：

### 后端已通
- session 持久化：`state/llm_sessions/`
- session list / detail / stream / registry
- mock session 与 live session 同协议
- orchestrator 事件已经能落成前端 message / packet / chunk

### 前端已通
- `LLM Sessions` 页存在并可切换
- 会话列表可加载
- active session detail 可加载
- 新 session 可创建
- external / registry 新 session 自动出现并自动切入
- per-session SSE 流已接上

### 当前 UI 已有结构
- 左 rail
- 中间 transcript
- 底部 composer
- source bubble + picker
- thinking 折叠块
- tool / packet / report / warnings 块

## 3. 当前最大问题
这部分才是你真正要接手的。

### A. 仍不够像聊天产品
虽然已经从“控制台大卡片”收过两轮，但当前仍明显不像：
- ChatGPT Web
- Claude Code

### B. app shell 仍有工具产品残留
虽然 `sessions` 模式已经改成浅色壳，但整体仍残留强烈的本地桌面工具味道。

### C. transcript 层级仍不够对
当前仍有这些问题：
- user / assistant / context / tool / packet 的层级没有彻底拉开
- system/tool/packet 仍然偏“块”
- pre-transcript chrome 仍偏重
- transcript 节奏不够像正常会话阅读流

### D. composer 还不够像 ChatGPT 主输入
目前已比最初薄很多，但还不够：
- 输入壳体仍偏定制 workbench
- source bubble 还不够自然
- 与 transcript 的关系还不够强

## 4. 当前代码入口
你接手时最重要的文件就是这些：

### 前端 UI
- `apps/review-editor/src/App.vue`
  - 顶层壳
  - `review` / `sessions` page switch
  - session registry / auto-select / auto-refresh 行为
- `apps/review-editor/src/components/LlmSessionPage.vue`
  - 当前 UI 主战场
- `apps/review-editor/src/App.test.ts`
  - `sessions` 相关主要回归

### 前端契约
- `apps/review-editor/src/api.ts`
  - `fetchLlmSessions`
  - `fetchLlmSession`
  - `startLlmSession`
  - `subscribeToLlmSession`
  - `subscribeToLlmSessionRegistry`
- `apps/review-editor/src/types.ts`
  - `LlmSessionSummary`
  - `LlmSessionDetail`
  - `LlmSessionChatMessage`
  - `LlmSessionPacket`
  - `LlmSessionStreamEvent`

### 后端支撑
- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`

## 5. 真实参考与方法真值
必须优先使用这些，而不是凭印象：

### 真实 ChatGPT Web capture
- `state/ui_reference/chatgpt_web/2026-04-19T18-59-03.043Z`

注意：
- 当前抓到的是首页/空态
- 你接手后第一件高价值动作之一，是补一份 conversation-state capture

### 最新 review-editor capture
- `state/ui_reference/review_editor_sessions/2026-04-20T12-07-19.759Z`

### 现有 diff / findings
- `state/ui_reference/diff_reports/2026-04-19T19-24-18.397Z_ui_reference_diff.md`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round1_findings.zh-CN.md`
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round2_findings.zh-CN.md`

### 方法文档
- `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_reference_method.zh-CN.md`

## 6. 允许参考的产品 / 项目
### 主真值
- ChatGPT Web

### 工程表达参考
- Claude Code / Codex

### 开源实现参考
- OpenWebUI

对 OpenWebUI 的使用方式：
- 可以参考 transcript 结构
- 可以参考 composer 与 tool block 的开源组织
- 不要把它当成主骨架真值覆盖 ChatGPT Web

## 7. 不能回退或重做的东西
不要做这些：

- 不重写 session backend
- 不重设 LLM session 类型契约
- 不拆成 mock/live 两套前端链
- 不回退自动发现 / 自动切入 / SSE 行为
- 不把 source 选择再塞回左侧厚表单
- 不把 sessions 页面重新做成 inspector-first

## 8. 你接手后的推荐顺序
### Step 1
先读：
- `App.vue`
- `LlmSessionPage.vue`
- `App.test.ts`
- `api.ts`
- `types.ts`
- `review_editor_llm_sessions_ui_reference_method.zh-CN.md`
- `review_editor_llm_sessions_ui_round1_findings.zh-CN.md`
- `review_editor_llm_sessions_ui_round2_findings.zh-CN.md`

### Step 2
跑新的真实参考采样：
- ChatGPT Web conversation-state
- 最新 review-editor sessions

### Step 3
重新生成 diff

### Step 4
写 `round3_findings`

### Step 5
再做 UI 重构

### Step 6
回归验证：
- `npm test`
- `npm run build`
- `npm run tauri:build`

## 9. 当前交接判断
你接手时不需要重新把“功能做通”。  
你真正需要做的是：
- 在现有已打通的 session/runtime 基础上
- 把 `LLM Sessions` 真正收成一个像 ChatGPT Web / Claude Code 的会话产品 UI
