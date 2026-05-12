# Review Editor 技术索引

> 日期：2026-04-23  
> 目的：让 Claude Code 快速定位 `review-editor` 现有功能、风格和代码入口

## 1. 顶层壳与页面切换
### `apps/review-editor/src/App.vue`
职责：
- Tauri/浏览器双运行态壳层
- `review` / `sessions` 两页切换
- sessions 页 active error 选择
- LLM session registry / polling / stream 自动管理

重点函数：
- `refreshLlmSessions`
- `attachLlmSessionStream`
- `startLlmSessionRegistryStream`
- `selectLlmSession`
- `startLiveLlmSession`

如果要改 `LLM Sessions` 的自动发现、自动切换、stream 行为，先看这里。

## 2. `Review` 页主工作区
### `apps/review-editor/src/components/ReviewWorkspacePage.vue`
职责：
- run / candidate / card 三层审核工作流
- message list、composer、drawer、model panel
- save / reparse / next unresolved

这块不是当前 UI 主目标，但会影响：
- `review` 页现有视觉风格
- 整个 app shell 的历史包袱

## 3. `LLM Sessions` 页
### `apps/review-editor/src/components/LlmSessionPage.vue`
职责：
- session rail
- active transcript
- tool / packet / thinking / report / warnings 显示
- source bubble + picker
- composer

重点计算与函数：
- `activeContextLabel`
- `activeConversationStatsLabel`
- `streamStateLabel`
- `sourceBubbleLabel`
- `composerPlaceholder`
- `isToolMessage`
- `isPacketMessage`
- `isReasoningMessage`
- `roleLabel`
- `packetRoleLabel`
- `messageText`
- `showPacketInline`

如果要重构 `LLM Sessions` UI，主战场就是这里。

## 4. 前端 API 适配
### `apps/review-editor/src/api.ts`
职责：
- review API 适配
- llm session list/detail/start/SSE 适配
- JSON -> 前端类型 normalize

LLM 相关入口：
- `fetchLlmSessions`
- `fetchLlmSession`
- `startLlmSession`
- `subscribeToLlmSession`
- `subscribeToLlmSessionRegistry`

关键 normalize：
- `normalizeSessionSummary`
- `normalizeSessionDetail`
- `normalizeChatMessage`
- `normalizePacket`
- `normalizeTokenChunk`

## 5. 类型定义
### `apps/review-editor/src/types.ts`
LLM Session 相关必须优先读的类型：
- `LlmSessionSummary`
- `LlmSessionDetail`
- `LlmSessionConversationSummary`
- `LlmSessionChatMessage`
- `LlmSessionPacket`
- `LlmSessionTokenChunk`
- `LlmSessionStreamEvent`
- `LlmSessionRegistryEvent`

UI 重构时尽量不要先改这些契约；优先改显示层。

## 6. 现有 `Review` 页主要组件
这些文件帮助理解当前 app 的工作台风格来自哪里：

### 聊天主界面
- `ChatHeader.vue`
- `ConversationPane.vue`
- `MessageList.vue`
- `MessageBubble.vue`
- `ConversationItem.vue`

### 右侧 / 下方审核与模型区
- `ComposerDock.vue`
- `ReviewPanel.vue`
- `ReviewFormTab.vue`
- `ModelPanel.vue`
- `ModelTab.vue`
- `ProfileDrawer.vue`
- `WindowPanel.vue`
- `WindowSummaryTab.vue`

### 其他
- `SidebarRail.vue`
- `CardAnchorRail.vue`
- `ForwardRecordViewer.vue`

这些组件定义了当前 `review` 页的 QQ-like / dense workbench 风格。  
`LLM Sessions` 不应该简单继承这套视觉。

## 7. 本地桌面壳相关
### `apps/review-editor/src/useWindowChrome.ts`
负责：
- 窗口拖动
- 最大化 / 最小化 / 关闭

### `apps/review-editor/src/components/DesktopWindowControls.vue`
负责：
- 窗口按钮

如果要继续收 `sessions` 页的壳层视觉，需要同时理解 `App.vue` 和这两个文件的关系。

## 8. 后端支撑代码
### `src/qq_data_analysis/llm_session_service.py`
职责：
- live/mock session 生命周期
- events / packets / messages / chunks 持久化
- orchestrator session 适配

### `scripts/run_review_editor_server.py`
职责：
- review API
- llm session API
- stream / registry 路由
- mock session 启动

UI 工作通常不需要改后端，但必须知道这层已经存在。

## 9. 现有测试入口
### `apps/review-editor/src/App.test.ts`
最重要：
- review 页面回归
- sessions 页面进入
- start session
- registry 新 session 自动切换

### 其他
- `apps/review-editor/src/components/MessageList.test.ts`
- `apps/review-editor/src/ui-reference-diff.test.ts`
- `apps/review-editor/src/forwardRecord.test.ts`

如果重构 `LLM Sessions`，先维护 `App.test.ts` 的 sessions 相关行为，再考虑视觉层测试。
