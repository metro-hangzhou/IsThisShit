# Review Editor 当前功能与风格说明

> 日期：2026-04-23  
> 用途：让 Claude Code 快速理解 `review-editor` 现在是什么样，不用自己重新扫一遍组件树

## 1. 当前产品分成两个页面
### A. `Review`
这是当前旧主界面。

功能：
- run 选择
- candidate 选择
- card 选择
- message list / quoted jump / evidence jump
- model reasoning 展示
- composer save
- window review
- profile drawer
- forward viewer

视觉风格：
- QQ-like
- dense workbench
- 信息密度较高
- 工具台感强

### B. `LLM Sessions`
这是 live session 可视化页。

功能：
- session 列表
- 选中 active session
- transcript 显示
- thinking 折叠块
- tool call / tool result
- prompt / packet / report / warnings
- source bubble + picker
- 创建 / 继续 session

目标风格：
- 更像 ChatGPT Web / Claude Code

当前风格状态：
- 已经从最初控制台版收过两轮
- 但仍未真正收成聊天产品

## 2. `Review` 页现有风格由哪些地方决定
如果 Claude Code 想知道“为什么整个 app 有强烈的本地工具感”，先看：

- `App.vue`
  - 顶层壳
- `ReviewWorkspacePage.vue`
  - 整体布局与工作区分配
- `ChatHeader.vue`
  - 顶部操作条
- `ComposerDock.vue`
  - 底部审核区
- `ProfileDrawer.vue`
  - 右侧资料 / 模型 / 审阅区

这套结构定义了：
- QQ-like
- reviewer workbench
- 高密度审核界面

## 3. `LLM Sessions` 当前已有的功能
### 已实现行为
- session 列表加载
- active session detail 加载
- 新建 session
- 自动发现外部新 session
- 自动切入 running session
- 流式 token / message 更新
- mock session 与 live session 共用同一页
- 离线回看已完成 session

### 已实现显示块
- user turn
- assistant final
- assistant reasoning / thinking
- tool call / tool result
- prompt / chat packet
- final report
- warnings

### 相关代码
- `LlmSessionPage.vue`
- `App.vue`
- `api.ts`
- `types.ts`

## 4. `LLM Sessions` 当前视觉风格现状
### 已改善
- 不再是最初那种强 inspector / card wall
- 已经有：
  - 左 rail
  - 中间 transcript
  - 底部 composer
- source 选择已挪进 composer 功能气泡

### 仍然不对
- 仍明显不像 ChatGPT Web / Claude Code
- app shell 还残留本地桌面工具味道
- tool / packet / system 仍偏“块”
- transcript 还不够像真正的会话阅读流
- composer 还不够自然

## 5. 现有 style 的根源
### `review` 页
根源是：
- QQ-like workbench 的历史目标
- 多面板、多信息区、多操作区

### `sessions` 页
根源是：
- 在已有 workbench 壳内叠加了一个聊天式界面
- 结果造成：
  - app shell 还像本地工具
  - 内部 transcript 又试图像聊天产品

这个混合状态正是当前 UI 不自然的原因。

## 6. Claude Code 接手时应如何理解
你不是在“美化一个页面”，而是在解决一个结构冲突：

- 外层 app 继承的是本地审核工具工作台风格
- 内层 `LLM Sessions` 目标却是会话产品风格

所以接手重点不是微调颜色，而是：
- 重新定义 `sessions` 页面在 app shell 中的视觉独立性
- 重新定义 rail / transcript / composer 的关系
- 把工程痕迹层级压到对话正文之下

## 7. 可以参考的实现方向
### 主要参考
- ChatGPT Web

### 辅助参考
- Claude Code / Codex
- OpenWebUI

其中：
- ChatGPT Web 用于骨架
- Claude/Codex 用于工程块语义
- OpenWebUI 用于找开源可执行的聊天 UI 组织方式
