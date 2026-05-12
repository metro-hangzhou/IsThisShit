# ORCH Observer 功能性 UX 审查与修复记录（2026-04-26）

## 背景

这轮问题不是单纯视觉样式，而是 ORCH Observer 主线把内部事件结构直接暴露给人看，导致用户虽然能看到 session 流，但无法判断“发生了什么、为什么要看、下一步该审哪里”。

ORCH Observer 的主线目标不是 JSON viewer，也不是后端日志浏览器。它应该按时间顺序展示 ORCH 如何整理 QQ 原文、如何补证、如何调用工具、如何把 prompt 交给模型、模型如何流式输出，以及最终报告如何从结构化输出转成人类可审阅结论。

## 已确认的问题

- `tool.requested` 直接显示 `fetch_topic_cluster_slice`、`fetch_sender_history_slice` 等内部工具名，用户无法从名字判断动作目的。
- 工具调用正文直接显示英文 `why_needed`，例如 `The current anchor still depends...`，这属于内部计划语，不应出现在主线。
- 工具结果正文直接显示 `sender_history:msg_xxx` / `topic_cluster:msg_xxx` / `assets:msg_xxx`，这是内部 source key，不是审阅结论。
- `judge.started` 显示 `loop_count=3, stop_reason=completed`，这是生命周期 debug 字段，不告诉用户此处发生了什么。
- `Prompt ready` 容易被理解成“一个可直接审的内容块”，但它真实含义是“已经组装好发给模型的 system/user prompt”。主线应说明用途和规模，完整 prompt 只放 Raw/Inspect。
- `Model response` / `Assistant reply` 英文标题在中文审阅界面中语义不清，且完成事件不应重复贴 raw JSON。
- 旧 session 事件里已经持久化了旧 semantic 字段。如果详情页直接信旧 semantic，历史 session 即使后端升级也会继续显示旧英文语义。

## 本轮修复

- 后端新增工具展示翻译层：
  - `fetch_sender_history_slice` -> `补充同发送者上下文`
  - `fetch_topic_cluster_slice` -> `补充相关话题证据`
  - `fetch_related_assets` -> `检查相关媒体资源`
  - `inspect_asset_manifest` -> `检查媒体清单`
  - `hydrate_missing_asset` -> `尝试恢复缺失媒体`
- 工具调用主线正文改为中文功能说明，原始 `tool_name` 和 `why_needed` 只保留在 Raw/Inspect。
- 工具结果主线正文改为“已返回 N 条聊天记录 / N 个资源 / N 个实体”，不再显示内部 source key。
- `judge.started` 主线改为 `模型审阅开始`，正文解释 ORCH 已把证据包交给模型。
- prompt 事件改为 `组装模型提示词`，正文解释完整 prompt 默认只在 Raw/Inspect 中查看。
- stream 标题改为 `模型思考` / `模型输出` / `模型响应开始` / `模型输出完成`。
- `llm.response_completed` 不再在主线重复 raw JSON，只显示“模型流式输出已结束，报告会转成人类可审阅结论”。
- 详情页派生 semantic 时忽略旧事件里已持久化的旧 semantic，确保历史 session 刷新后使用最新产品契约。
- 前端工具行支持 live running 状态 spinner；已完成历史工具调用不会保持转圈。

## 主线展示原则

每个主线块必须回答三个问题：

- 发生了什么：例如“补充相关话题证据”，而不是 `fetch_topic_cluster_slice`。
- 为什么有用：例如“查看同话题接球、回应和延续，确认群体是否真的围绕这条消费。”
- 细节去哪看：参数、原始 tool name、完整 prompt、raw payload 放到 Raw/Inspect。

## 仍需后续 UX 审查的区域

- Packet 展开后的 Raw 摘要仍偏工程化，后续应把“前端安全摘要 / 完整 payload 在 events.jsonl”做成更清晰的 Inspect block。
- 如果后续启用 `semanticTimeline` 直接驱动主线，需要把 QQ packet card/PCQQ modal 嵌入 semantic timeline，否则会丢掉当前 transcript 中较好的 QQ 原文可视化能力。
- `Assistant reply` 的结构化 JSON 流当前由 `LlmStructuredStreamBlock` 渲染，但命名和折叠策略还需要在真实 live run 中继续验证。
- `loop.tool_requests_planned` 等 inspect-only 事件仍保留较工程化 summary；只要不进主线即可接受，后续可继续翻译。

## 2026-04-26 晚间补丁

人工验收又发现一组功能性 UX 问题：这些不是单纯视觉问题，而是“用户看不懂这行是什么意思”。

本轮已处理：

- 工具事件按调用配对显示。若事件顺序是 `call A, call B, result A, result B`，前端现在会显示为 `call A -> result A`、`call B -> result B`，避免“同发送者上下文已返回”视觉上挂到“相关话题证据”下面。
- `生成模型输入包` 改为 `准备给模型的审阅材料`，`整理候选聊天记录` 改为 `整理 QQ 聊天证据`，`组装模型提示词` 改为 `准备模型审阅指令`。
- 工具行字体和层级做了轻量收敛：调用行和结果行通过缩进和左侧连接线绑定，避免像散落日志。
- Final Report 的 `直接证据` 记录如果来自 QQ 原文，前端用 QQ 来源样式渲染，不再只是普通灰卡。
- Final Report 常见内部计数字段会翻译为人话，例如：
  - `forward_message_count=0` -> `无转发消息`
  - `nested_forward_count=0` -> `无嵌套转发消息`
  - `reply_message_count=15` -> `15 条回复消息`
  - `core_bearing` -> `核心承载`
  - `text_native_shi_object` -> `原生文本对象`

仍然需要后续重点盯：

- 不要再把新增 ORCH 字段直接扔进主线。任何新字段必须先判断：是“人类复审需要看的信息”，还是“Inspect/Raw 里的调试信息”。
- QQ 原文引用必须强化来源感，优先使用 PCQQ/QQ 风格；模型解释和 ORCH 摘要不能伪装成 QQ 原文。
- `Packet` / `Prompt` / `Tool` 这些块的标题必须描述用户动作或系统动作，不允许直接显示内部函数名或后端字段名。

## 验证记录

- 后端回归：`tests/test_llm_session_service.py` 已新增 `test_orch_observer_mainline_uses_human_readable_event_labels`。
- 前端回归：现有 Vitest 保持通过。
- 人工抽样：`live_2d45c4818f7cb5` 刷新详情后，主线前 18 条已不再显示 raw tool id、英文 why_needed、内部 source key、`loop_count/stop_reason`。

## 2026-04-26 夜间补丁 2

人工复核继续暴露了三个问题：`Packet`/`Prompt` 展开后仍像 JSON viewer，tool result 展开后只显示内部参数，空的 `模型响应开始` 占位没有信息价值。

本轮已处理：

- `chat_packet` 的前端 `jsonPreview` 改为可审阅摘要：保留 QQ 消息预览、资源状态、缺失资源和工作集计数摘要，不再把完整 `working_set` 塞给前端。
- 重复的 `chat_packet.built` 不再因为同名同类而被整体省略。每轮 packet 都应保留自己的可审阅消息预览；如果消息过多则按 300/160/80/40/16 逐级降级，而不是回退成 `omitted raw JSON`。
- `prompt` 的 `jsonPreview` 改为 prompt 摘要：`systemPrompt.preview`、`userPrompt.preview`、字符数、message-first 计数。前端展开后显示 `System 指令预览` 和 `User 指令预览`，不再展示转义后的大 JSON 字符串。
- `tool_result` 若返回 QQ `messages`，前端会复用 `LlmSessionChatPacketCard`，显示为“工具返回的 QQ 原文”卡片，点击后仍走已有 PCQQ forward 窗口。
- `tool_result.details` 只保留人类可读提示。`message_count=8`、`sender_history_loaded`、`overlap_match=true` 等内部 hint 被过滤；asset hint 会翻译成“可显示图片”“缺失媒体仅作边界”等。
- `assistant.response_started` 这种空的 `模型响应开始` 占位在 transcript 分组阶段过滤，不再显示一个展开后只有横杠的系统块。
- Tool / Packet / Prompt 的标题行做了小幅排版修正：标题字号、行高、label 对齐和展开按钮位置收敛，避免标题和按钮在一行内错位。

仍需后续重点盯：

- Tool call 请求侧仍只能显示锚点 UID 和补充范围，尚未把“锚点消息本体 + 周边几条上下文”注入 request 侧。当前 result 侧已能显示返回的 QQ 原文，但 request 侧要做到完全符合 agentic tool UX，还需要 ORCH 在 `tool.requested` 事件里附带 anchor preview。
- 媒体资源类 tool result 目前会显示资源数量和可读 asset hint，但还没有像 QQ 消息一样做成图片/文件资源卡。后续如果该类工具变多，应补一个 `ToolAssetObservationCard`。
- 若未来重新启用 `semanticTimeline` 作为主线，必须同步嵌入 QQ packet card 和 tool result card，否则会退化成摘要列表，丢失本轮修复的可审阅内容。

验证记录：

- 后端：`powershell.exe -Command "& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_llm_session_service.py -q"`，17/17 通过。
- 前端：`powershell.exe -Command "npx vitest run"`，45/45 通过。
- 类型检查：`powershell.exe -Command "& .\\node_modules\\.bin\\vue-tsc.cmd --noEmit"` 通过。
- 本地 detail 抽样：`live_2d45c4818f7cb5` 的 4 个 `chat_packet` 均 `omitted=false`，prompt 均有 `systemPrompt/userPrompt` 预览，两个有消息的 tool result 分别保留 8 条和 5 条 QQ 消息预览。
