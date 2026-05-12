# ORCH Observer 对齐记忆

Date: 2026-04-26

本文件用于防止 Codex / Claude Code 在后续迭代中丢失本轮需求分布对齐。
它不是新增需求池，而是当前 `LLM Sessions / ORCH Observer` 的工作记忆。

## 一句话定义

ORCH Observer 是一个面向人的 ORCH 调试观察器。它要让人看懂：

- ORCH 收到了什么请求。
- ORCH 选择了哪些 QQ 源证据。
- ORCH 依什么顺序准备上下文、调用工具、构造 prompt、等待模型、形成审阅结论。
- 模型实时流式输出了什么。
- 最终审阅结论、证据、边界和人工复核重点是什么。
- 必要时如何进入 Inspect/Raw 深挖。

它不是 raw JSON viewer，不是 prompt dump，也不是把所有内部字段摊开的报表。

## 已确认的产品选择

- 默认体验采用用户友好模式。主线必须能扫读，但仍保留审计入口。
- 时间顺序不可打乱。可以在单个事件块内部摘要，但不能把主线重排成脱离流程的 dashboard。
- 主线用中文友好标签。内部字段名原文只放 Inspect/Raw 或极弱 metadata。
- QQ 原文必须用 PCQQ/forward 风格显示，帮助用户确认这些内容来自 QQ 数据源。
- Tool、ORCH、Model、QQ Source、System 都需要明确来源标记。
- JSON 流式输出要增量解析。主线不显示未闭合 raw JSON。
- asset missing 默认是 info/boundary，不是 warning。
- `117 功能字段` 这种主线大字段列表是失败模式。
- final report 必须优先呈现人类审阅结论，不得把 prompt/instruction 当报告描述。
- V1 不做自动 repair call。
- 当前模型可能很强，但未来弱模型也必须可降级展示。

## Mainline 与 Inspect/Raw

Mainline 应该包含：

- 用户请求摘要。
- QQ 源输入包的紧凑卡片。
- 可打开 PCQQ 记录窗口的 source/evidence 卡。
- ORCH 阶段进展和边界信息。
- Tool call 的目的、参数摘要、结果摘要。
- Prompt/packet ready 的简要状态。
- 模型文本或结构化 JSON 的实时流。
- final review 人类报告卡。

Inspect/Raw 应该包含：

- raw event payload。
- raw model JSON。
- 全量字段名、调试字段、长列表。
- 大型 packet 的完整或 capped raw 结构。
- 未识别的新事件和未来字段。

## QQ 原文规则

所有人类可见 QQ 原文都必须尽量复用：

- `apps/review-editor/src/components/ForwardRecordViewer.vue`
- `apps/review-editor/src/forwardRecord.ts`
- `apps/review-editor/src/forwardWindow.ts`
- Review 页面已有的 PCQQ/forward 渲染经验。

紧凑态只显示 1-2 条预览和统计。打开后必须看到消息文本、发送者、时间和媒体 token/缩略图。
如果弹窗只有头像和 user id，没有消息文本，就是 blocker。

## Final Review 规则

final review 的默认层应回答：

- 判定是什么。
- 置信度或可审程度如何。
- 核心对象是什么。
- 为什么成立或为什么弱。
- 直接证据有哪些。
- 边界/限制是什么。
- 人工应该怎么复核。

过长内容可以折叠，但必须有显式展开入口。不能只用省略号隐藏。

## 与 Claude Code 的协作规则

Codex 负责契约、后端语义、测试验收和 diff 审查。
Claude Code 负责 Vue UI/UX 实现。

Claude Code 在改代码前必须读：

- `dev/llm_session_orch_observer_product_contract.md`
- `dev/llm_session_orch_observer_event_contract.md`
- `dev/llm_session_cc_ui_workflow.md`
- `dev/reports/handoffs/claude_code_orch_observer_alignment_task_2026-04-26.zh-CN.md`

然后必须用自己的话复述：

- ORCH Observer 是什么。
- Mainline 与 Inspect/Raw 的边界。
- QQ 原文为什么必须 PCQQ 风格。
- 为什么不能再显示 117 功能字段。
- final report 如何显示。
- 自测流程。

如果复述不对，Codex 必须先纠正，不能让它直接开工。

## 当前高风险回归点

- 旧 live session 中仍可能显示 `117 功能字段`。
- packet 弹窗可能出现只有头像/user id 但没有消息文本。
- final report 可能省略关键字段且无法展开。
- prompt/packet 可能被误放到 report 描述位。
- raw JSON 或 Python dict repr 可能重新进入主线。
- session detail payload 过大可能导致 Tauri WebView 崩溃。

## 2026-04-26 落地记录

本轮 Codex 已先行落地一组低风险边界修复：

- 后端 `src/qq_data_analysis/llm_session_service.py`
  - `finalReportPayload` 不再把完整结构化结果塞进详情接口，只返回可索引摘要。
  - `finalReport` 文本增加前端预览上限，完整报告仍保留在 session/run artifact。
  - prompt raw payload 默认摘要化；重复 packet raw 只保留首份大预览，后续重复事件转为摘要。
  - `packets` 列表改为轻量索引，避免和 `chatMessages` 双份携带同一个大 `jsonPreview`。
  - stream detail message 去掉详情页不需要的 `delta` 大字段副本。
  - 最新真实 live session `live_2d45c4818f7cb5` 详情响应从约 1.68 MB 降到约 0.49 MB。
- 前端 `apps/review-editor/src/api.ts`
  - 映射 `events/eventsTruncated` 到 `LlmSessionDetail`，使 Raw event log/Inspect 数据能进入页面。
  - 暂不启用 `semanticTimeline` 自动接管主线，因为当前页面的 semantic timeline 与“按发生顺序展示”的产品选择仍有设计差距。
- 前端 packet/chat adapter
  - 当 message 同时有媒体 segment 和 `contentPreview/textContent` 时，PCQQ 弹窗会补回文本 segment，避免只显示头像和 user id。
- UI 主线约束
  - packet 卡片里的 media missing 作为 boundary/info，不再默认显示成 warning。
  - packet 卡片不再把 `functionalFields` 直接展开成 `117 功能字段`。
  - final report 的截断 section/record 增加显式展开入口。

本轮未使用 Claude Code hook。原因：当前修复集中在后端 payload budget、API normalize 和可测试的 Vue 组件边界，本地回归测试覆盖更直接。后续如果启用 CC hook，只允许用于：

- PreToolUse：强制确认 CC 已阅读指定产品/事件/UI 工作流文档。
- PostToolUse：要求 CC 输出本次修改文件、修改意图、测试结果。
- Stop：提醒 CC 在完成前跑 `vue-tsc` / `vitest` 并给出 UI 验收截图或 DOM 检查摘要。

不得用 hook 自动提交、自动删除文件、自动启动真实模型调用或绕过 Codex 审查。

## 验收最低线

- `live_2d45c4818f7cb5` 或最新真实 live session 可读。
- 最新 `FULL SPECTRUM ...` mock session 可读。
- 新 session 出现后能自动打开和实时流式更新。
- `npx vue-tsc --noEmit` 通过。
- `npx vitest run` 通过。
- Tauri build 在人工验收前尽量通过，但 dev server 视觉验收优先。

## 2026-04-26 功能性 UX 修正追加

详见：

- `dev/reports/handoffs/orch_observer_functional_ux_audit_2026-04-26.zh-CN.md`

追加约束：

- ORCH Observer 主线不得直接显示 raw tool id、英文内部 `why_needed`、`sender_history:msg...` / `topic_cluster:msg...` 这类内部 source key。
- `Prompt ready` / `Judge started` / `Model response` 这类内部生命周期标题必须翻译成可审阅动作语义。
- 旧 session 里持久化的旧 semantic 不能作为详情页最终展示真相；详情页应按最新产品契约重新派生展示语义。
