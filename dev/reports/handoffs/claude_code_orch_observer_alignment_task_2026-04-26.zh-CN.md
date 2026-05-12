# Claude Code ORCH Observer 对齐任务书

Date: 2026-04-26

本文件是给 Claude Code 的当前唯一任务入口。先读完，再做阅读理解；阅读理解通过后才允许改 UI。

## 身份与协作关系

Codex 是本项目 `LLM Sessions / ORCH Observer` 方向的产品契约、后端语义、测试验收负责人。Claude Code 是前端 UI/UX 实现工程师，负责在既有 Vue/Tauri 代码中实现更好的观察器界面。

Claude Code 不要重新发明产品目标，也不要按截图碎片猜需求。你必须按本文和下列契约实现：

- `dev/llm_session_orch_observer_product_contract.md`
- `dev/llm_session_orch_observer_event_contract.md`
- `dev/llm_session_cc_ui_workflow.md`

如果你发现字段含义、展示层级、验收标准不明确，先问 Codex；不要自己补一个看似合理但实际不对的 UI。

## 当前问题背景

此前 LLM Sessions 多轮 UI 迭代出现了系统性偏差：

- 把调试字段、模型 JSON、QQ 原文、final report 混在同一个主时间线里。
- 把 100+ 个功能字段直接纵向展开，导致人类无法判断哪些信息重要。
- 把 QQ 原始聊天记录渲染成 `user_xxx content` 或空白列表，而不是 Review 页已经存在的 PCQQ/forward 风格。
- 把模型 prompt / packet / final report 的不同语义混在一起，有时把 prompt 当成报告描述显示。
- 过度依赖 raw JSON 或字段名原文，而不是给人类可审阅的中文标签、摘要、可展开 Inspect。
- 修改后没有按真实 session 和 mock stress session 做完整验收，导致同一类问题反复出现。

目标不是“让页面看起来有内容”，而是让人类能观察 ORCH 的行为链路。

## 最新对齐结论

这些结论来自用户和 Codex 的最新深度对齐，必须优先于旧截图驱动的修修补补：

- 默认走用户友好模式，但不能牺牲 ORCH 审计能力。主线负责扫读和判断，Inspect/Raw 负责深挖。
- 主时间线必须保留事件顺序。ORCH 的行为顺序本身就是需要观察的对象。
- 主线用中文友好标签，不用原始字段名堆 UI。原始字段名只在 Inspect/Raw 或次要 metadata 出现。
- 所有 QQ 原文必须走 PCQQ/forward 风格，这是为了证明“这是 QQ 来源证据”，不是模型脑补文本。
- tool call 要有工具标记、用途和结果；ORCH 决策要有 agent/流程标记；model 输出要有模型标记；QQ 来源要有 QQ/export 标记。
- JSON streaming 不能在主线显示未闭合 raw JSON。能解析出字段就立刻结构化显示，不能解析的 raw 放 Inspect。
- asset missing 默认是信息边界，不是 warning。只有当它实质影响结论时才提升严重度。
- 长期方向是 ORCH/model 直接输出更适合人读的 `final_review` 结构。前端兼容 legacy，但不要把任意 raw JSON 包装成报告。
- 当前测试模型可能是 GPT-5.5，但开源后可能换成弱模型。UI 必须容忍字段缺失、弱结构和未知事件。
- V1 不启用自动 repair call。坏输出只能降级展示，不要偷偷再调模型修复。

## 产品定义

ORCH Observer 是一个调试观察器，用于回答：

1. 用户发起了什么 session。
2. ORCH 选择了哪些 QQ 源证据。
3. 证据边界、缺失媒体、上下文限制是什么。
4. ORCH 按什么顺序做了哪些步骤。
5. 调用了哪些 tool，目的是什么，结果是什么。
6. 发给模型的 prompt / packet 是什么。
7. 模型正在流式输出什么，结构化 JSON 是否能增量可读。
8. 最终 review 结论是什么，人类应优先看哪里。
9. 如果需要深挖，Inspect/Raw 里有什么。

主时间线必须保留事件顺序，但不能把所有原始字段都扔给用户。

## 主时间线 vs Inspect/Raw

主时间线只展示人类可读的、与审阅/调试直接相关的信息。

主时间线允许：

- 用户请求摘要。
- 准备好的 QQ 输入包摘要。
- 可点击打开 PCQQ 风格窗口的 QQ 原文卡片。
- 工具调用的名称、目的、结果、关键观察。
- prompt ready / packet ready 的紧凑摘要。
- 模型流式文本或结构化流式预览。
- final review 的人类报告卡。
- 证据边界、缺失媒体等 info/degraded 提示。

主时间线禁止：

- 原始 JSON 字符串。
- Python dict repr。
- 内部字段名长列表。
- 100+ 个功能字段纵向铺开。
- 把 prompt/instruction 当作 final report 描述。
- 把 QQ 原文显示成裸 `user_xxx: text` 列表。

Inspect/Raw 才放：

- raw event payload。
- raw model JSON。
- 完整字段表。
- capped raw transcript。
- 调试字段原名。

## QQ 原文显示规则

所有人类可见的 QQ 原始聊天消息，都必须使用 Review 页已有的 PCQQ/forward 风格。

必须复用或对齐这些文件：

- `apps/review-editor/src/components/ForwardRecordViewer.vue`
- `apps/review-editor/src/forwardRecord.ts`
- `apps/review-editor/src/forwardWindow.ts`
- `apps/review-editor/src/components/MessageBubble.vue`
- `apps/review-editor/src/components/AvatarImage.vue`

紧凑态建议：

- 标题：`模型输入包` / `Prepared input` / `Effective prompt packet`
- 摘要：`223 条 · 16 人 · 8 assets · 6 missing`
- 预览：最多 1-2 条真实 QQ 消息，显示发送者名/卡片/去敏 ID 与内容。
- 点击：打开 PCQQ 风格独立窗口。

展开/弹窗态：

- 必须有消息文本或媒体 token，不允许只有头像和 user id。
- 发送者优先显示 `sender_card` / `sender_name` / alias；没有时才显示去敏 id。
- 图片、sticker、文件按既有 review/forward 显示规则处理；不可用资源显示边界信息，但不要把 asset missing 当 warning。

## 功能字段显示规则

功能字段不是 QQ 原文，也不是 final review 主报告。它们是 ORCH/模型的调试解释层。

不要再显示 `117 功能字段` 这种大块主线内容。

V1 规则：

- 如果 packet 是 probe-only / model-input-debug 类结构，主线只显示一条弱提示：`模型输入调试字段已隐藏，可在 Inspect/Raw 查看`。
- 如果字段已被 backend 适配成 `finalReviewViewModel` 或 semantic event，则按语义分组显示。
- 每组最多显示少量代表项；其余进入 Inspect。
- 字段名要翻译成中文人类标签，保留原始字段名只放 Inspect。

示例翻译：

- `evidence_basis` -> `证据依据`
- `boundary` / `evidence_gap` -> `证据边界`
- `bearingness` -> `承载度`
- `core_reason` -> `核心原因`
- `carrier` -> `载体信号`
- `debug` -> `调试信息`

## Final report 显示规则

final report 是最终审阅报告，应优先显示，不是 raw model output。

默认卡片必须包含：

- 判定结论。
- 置信度或可审程度。
- 核心对象。
- 核心机制/为什么成立。
- 直接证据。
- 边界/限制。
- 人工复审导航或注意点。

默认不应折叠掉关键信息。如果文本过长，可以用“展开全部”交互，但必须有显式入口，不允许只有省略号。

禁止：

- 把用户 prompt / instruction 放在 final report 说明位置。
- 把 `compact_payload` / legacy raw JSON 直接作为报告主体。
- 把所有结论一行一行垂直堆成没有重点的列表。

## Streaming JSON

流式 JSON 不能等完整闭合后才显示，也不能在主线直接显示未闭合 JSON 原文。

要求：

- 已经完整解析出来的 top-level 字段要立刻以结构化 UI 出现。
- 正在生成的字段可显示 `生成中` 或 skeleton。
- Raw JSON 默认折叠。
- 完成后如果 parse 成功，显示 structured report。
- 完成后如果 parse 失败，显示降级错误块，并把 raw 放 Inspect。

## Tool / ORCH / Model / QQ 标记

每个可见块必须明确来源：

- QQ 原文：QQ Export / 群聊来源标记。
- ORCH：agent/节点/流程标记。
- Tool：锤子或工具标记。
- Model：模型输出/思考标记。
- System：会话生命周期标记。

Emoji 可以使用，但不能替代文字标签和信息架构。

## 需要你先做的阅读理解

你第一条回复必须只包含阅读理解，不要改文件。

阅读理解必须回答：

1. ORCH Observer 到底是做什么的。
2. 主时间线和 Inspect/Raw 的边界是什么。
3. QQ 原文应该如何显示，具体复用哪些文件。
4. `117 功能字段` 这类内容为什么不能直接显示在主线，应该怎么处理。
5. final report 应该怎么显示，哪些内容不能出现在报告描述位。
6. 你计划检查和可能修改哪些前端文件。
7. 你会如何自测，包括至少一个真实 live session 和一个 full-spectrum mock session。
8. 上面的“最新对齐结论”分别意味着你不能再做哪些旧实现。

如果你的阅读理解没有覆盖这些点，Codex 会要求你重读。

## 允许编辑范围

优先允许：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`
- `apps/review-editor/src/components/ForwardRecordViewer.vue`
- `apps/review-editor/src/forwardRecord.ts`
- `apps/review-editor/src/forwardWindow.ts`
- `apps/review-editor/src/lib/*`
- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/**/*.test.ts`

禁止无批准编辑：

- `src/qq_data_analysis/**`
- `NapCat/**`
- `scripts/run_review_editor_server.py`
- release/runtime/Git 分支治理文件

如果你认为必须改后端，先在回复中说明原因，不要直接改。

## 验收流程

你完成实现后必须报告：

- 改了哪些文件。
- 每个文件为什么改。
- 哪些旧问题被修复。
- 哪些问题仍需 Codex/backend 处理。
- 运行了哪些命令及结果。

必须至少运行：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run
```

只在 dev server 视觉验收基本可用后，才需要 Tauri build。Tauri build 可由 Codex 最后执行。

## 当前需要重点验证的 sessions

真实 live：

- `live_2d45c4818f7cb5`
- 标题：`x3c_group_757773326_run_20260417_210641_orch`
- 目标：确认 final report、QQ 输入摘要、tool、stream、materialized review 都可读。

full-spectrum mock：

- 查最新 session 列表中 `FULL SPECTRUM ...` 开头的 mock sessions。
- 目标：覆盖 prompt、packet、tool success/failure、reasoning stream、content stream、assets、missing assets、final review。

## 注意

不要追求一次性塞更多内容。主线必须“可扫读”，深挖靠 Inspect/Raw。

如果你不知道某个字段是否应该显示，默认放 Inspect，主线只显示一条人类摘要。
