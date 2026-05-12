# CC ORCH Observer UI 密度与语义层级修复任务

Date: 2026-04-26 22:34 +08:00

本文件是给 Claude Code 的当前前端任务入口。请先读完：

- `dev/reports/handoffs/claude_code_orch_observer_alignment_task_2026-04-26.zh-CN.md`
- `dev/reports/handoffs/orch_observer_functional_ux_audit_2026-04-26.zh-CN.md`
- 本文件

然后再改代码。不要重新定义产品目标。

## 分工

Codex 负责：

- ORCH Observer 产品契约、后端语义、数据契约和验收。
- 判断哪些内容应进主线、哪些进 Raw/Inspect。
- 最终跑测试和 build。

Claude Code 负责：

- `apps/review-editor` 前端 UI/UX 实现。
- 重点改 LLM Sessions / ORCH Observer 的 Vue 组件和样式。
- 不改 Python 后端，除非 Codex 明确要求。

## 当前人工验收问题

### 1. Tool result 的 QQ 原文卡太大

现在工具返回的 QQ 原文直接复用了接近 forward 大窗的视觉语言，结果在主时间线里占太多空间。

正确方向：

- Tool result 是 agentic tool output preview，不是正式审阅 packet。
- 默认应高密度、横向一行宽、低高度展示。
- 展示最多 1-2 条预览消息。
- 保留“这是 QQ 原文”的来源感，但不要把完整 PCQQ forward 卡套进主线。
- 点开或按钮进入详情时，才打开已有 PCQQ/forward 独立窗口。

建议实现：

- 给 `LlmSessionChatPacketCard.vue` 增加 `density` 或 `variant` prop，例如：
  - `variant="packet"`：用于审阅材料/模型输入包，保持当前较完整卡片。
  - `variant="tool-result"`：用于 tool result，紧凑显示，约束高度和内边距。
- `tool-result` 变体不要显示大块背景/大边框/多行元信息。
- 预览行建议形态：
  - 标题行：`同发送者上下文已返回`
  - 副标题：`工具返回的 QQ 原文 · 8 条 · 1 人`
  - 消息预览：`user_xxx：文本...`，最多 2 行。
  - 操作：`查看 8 条原文`

### 2. “审阅材料”的层级放错了

现在“审阅材料”是卡片里的小字，用户看起来像 forward 窗内部标签。

正确方向：

- `审阅材料` / `模型输入包` 是这个 section 的外部语义标题。
- 标题应在卡片外层或卡片顶部明显位置，下面才挂 QQ 原文卡。
- 主次顺序应是：
  - `审阅材料`
  - `整理 QQ 聊天证据`
  - 紧凑 QQ preview 卡

不要把“审阅材料”塞在卡片内的小 eyebrow 里。

### 3. Prompt 块不能只显示不可点的标题

现在 `准备模型审阅指令` 看起来像按钮/卡片，但无法点击进去看，不知道里面到底发给模型了什么。

正确方向：

- Prompt 主线可默认紧凑，但必须可展开。
- 展开后至少显示：
  - System 指令预览。
  - User 指令预览。
  - 字符数/是否截断。
  - Raw/Inspect 入口。
- 如果当前已有 `promptPreviewSections()`，请把展开交互接到 UI 上，而不是只显示标题。

### 4. “模型审阅开始”节点没有必要

现在有一个 `模型审阅开始` 节点，展开后只是说明“ORCH 已把证据包交给模型”。它信息量太低，且干扰主线。

正确方向：

- 默认隐藏或弱化为 timeline divider。
- 不要渲染成可展开详情块。
- 如果必须保留，只作为细灰色阶段分隔：`模型开始输出`，无可展开内容。

### 5. Final report 的 QQ 原文证据过冗余

现在 `直接证据` 中每条记录都重复显示 `QQ 原文` 和 `来源 QQ 原文`，造成一条消息视觉上占两行甚至更多。

正确方向：

- 一个证据组只需要在组标题处显示一次 `QQ 原文` 来源标记。
- 每条消息不要重复显示 `QQ 原文` / `来源 QQ 原文`。
- 每条记录用 PCQQ 气泡/轻量消息条表达“这是 QQ 原文”即可。
- 目标是“来源感明显，但信息密度高”。

建议：

- 在 `LlmFinalReportBlock.vue` 的直接证据组上显示一个小 badge：`QQ 原文`。
- 子项只显示标题/摘要/引用文本，不重复 source chip。

### 6. 字体与对齐

最新截图仍有一些标题和中文文本视觉不齐：

- `PROMPT 准备模型审阅指令` 中 `PROMPT` 与中文标题的字号/基线不协调。
- Tool call/result 的折叠按钮有时错位。
- Packet/Prompt header 的标题垂直居中要统一。

正确方向：

- 保持中文标题 `font-size` 与审阅报告区域一致。
- 英文小标签使用小号、半粗、固定行高，不要影响主标题基线。
- 折叠按钮靠近它控制的内容，不要飞到太远或垂直错位。

## 必须保持的产品原则

- ORCH Observer 是 agentic 调试观察器，不是 JSON viewer。
- 主线保留事件顺序，但每个块必须能让人理解“发生了什么、为什么看它、细节在哪”。
- QQ 原文必须有来源感，但不同场景使用不同密度：
  - 正式审阅材料：可以较完整。
  - Tool result preview：必须紧凑。
  - Final report 引用：更紧凑，只做证据引用。
- Raw/Inspect 保留完整技术细节，但默认不污染主线。

## 允许修改范围

优先：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
- 必要时新增小组件，例如 `LlmInlineQqEvidencePreview.vue`
- 对应前端测试

不要改：

- Python 后端
- NapCat/exporter 逻辑
- 与 Review 主页面无关的组件

## 验收要求

改完后请自己运行：

- `cd apps/review-editor && npx vitest run`
- `cd apps/review-editor && npx vue-tsc --noEmit`

并人工检查最新 live session：

- `live_2d45c4818f7cb5`

重点看：

- Tool result QQ 原文是否高密度，不再像大 forward 卡。
- Prompt 是否可展开看 system/user 预览。
- `模型审阅开始` 是否不再作为无意义展开块干扰主线。
- Final report 直接证据是否只在组级显示一次 QQ 来源，不再每条重复。
- 字体、基线、折叠按钮是否对齐。

完成后请输出：

- 读了哪些文档。
- 改了哪些文件。
- 每个问题怎么修。
- 测试结果。
- 仍可能需要 Codex/用户验收的风险点。
