# `LLM Sessions` 前后端接口与代码地图

> 日期：2026-04-23  
> 用途：防止 Claude Code 为了做 UI 又重新逆向 session 体系

## 1. 后端主服务
### `src/qq_data_analysis/llm_session_service.py`
职责：
- session root：`state/llm_sessions/`
- session 生命周期
- event log / packets / messages / chunks 持久化
- orchestrator -> session 事件映射
- mock session / materialization / review packet 相关桥接

接手 UI 时要知道：
- 这层已经存在
- session 数据不是临时前端状态
- 前端现在消费的是“结构化 session 结果”，不是原始 CLI stdout

## 2. review server
### `scripts/run_review_editor_server.py`
职责：
- review editor API server
- review 相关接口
- llm session 相关接口
- mock session 启动

你做 UI 时最相关的是这里提供的 session API 与 stream。

## 3. 前端 API 适配层
### `apps/review-editor/src/api.ts`
LLM 相关接口：
- `fetchLlmSessions()`
- `fetchLlmSession(sessionId)`
- `startLlmSession(payload)`
- `subscribeToLlmSession(sessionId, handlers)`
- `subscribeToLlmSessionRegistry(handlers)`

重要 normalize：
- `normalizeSessionSummary`
- `normalizeSessionDetail`
- `normalizeChatMessage`
- `normalizePacket`
- `normalizeTokenChunk`
- `normalizeSessionStreamEvent`
- `normalizeSessionRegistryEvent`

## 4. 前端核心类型
### `apps/review-editor/src/types.ts`
最重要的类型：
- `LlmSessionSummary`
- `LlmSessionDetail`
- `LlmSessionChatMessage`
- `LlmSessionPacket`
- `LlmSessionTokenChunk`
- `LlmSessionStreamEvent`
- `LlmSessionRegistryEvent`

当前 UI 重构优先原则：
- 优先改显示层
- 尽量不要先打破这些类型契约

## 5. `App.vue` 里的 session 生命周期
### 状态
- `llmSessions`
- `activeLlmSessionId`
- `activeLlmSession`
- `llmSessionComposer`
- `llmSessionLoading`
- `llmSessionCreating`
- `llmSessionStreamConnected`

### 关键行为函数
- `refreshLlmSessions`
  - 拉 session 列表并决定自动选择逻辑
- `attachLlmSessionStream`
  - 连当前 active session 的 SSE
- `startLlmSessionRegistryStream`
  - 连 registry，感知新 session
- `selectLlmSession`
  - 主动切 session
- `reloadActiveLlmSession`
  - 重载当前 active session
- `startLiveLlmSession`
  - 从 composer 发起新 session

## 6. `LlmSessionPage.vue` 的显示结构
这不是数据契约层，而是显示层。

当前主要区块：
- `session-rail`
- `session-stage`
- `session-transcript`
- `session-composer`

当前主要 turn 类型判定函数：
- `isToolMessage`
- `isPacketMessage`
- `isReasoningMessage`
- `roleLabel`
- `packetRoleLabel`
- `showPacketInline`

## 7. 当前行为上不要回退的东西
UI 重构时不要破坏：
- session list 正常加载
- active session detail 正常加载
- 外部新 session 自动出现
- registry 新 session 自动切入
- stream 中 assistant 内容原位更新
- mock 与 live 共用同一页

## 8. 当前建议
Claude Code 接手 `LLM Sessions` 时：
- 先把它当成“显示层重构”问题
- 不要先从 backend 开刀
- 不要先改 types / wire shape
- 如果真需要改接口，应先写 findings 文档说明为什么旧契约不够
