# Chat Orchestrator 公共契约加固记录

日期：2026-05-02

## 背景

ORCH 主线已经从“后端先机械预整理，再让 worker 判断”转向“模型主审按需调用本地 QQ 补证工具”。这要求 ORCH Observer 看到的是公共审阅契约，而不是 worker 内部字段、旧探针字段或工具实现细节。

本轮加固目标：

- 模型最终输出必须是可审计的 `final_review` + `adjudicated_relation_graph` + `evidence_acquisition_summary`。
- 工具返回必须说明“为什么查、围绕哪条 QQ 原文查、查回了什么”，而不是只暴露 `tool_name` / `coverage_scope` / `derived_hints`。
- 内部字段只能留在 Raw/Inspect，不进入主线人类审阅视图。

## 已落实

### 1. ToolObservation 公共字段

`ToolObservation` 增加：

- `request_reason`：模型为什么要求这次补证。
- `anchor_message`：触发补证的 QQ 原文摘要。
- `messages[*].role` / `messages[*].is_anchor`：返回消息与锚点的关系，例如 `anchor`、`same_sender`、`same_topic`、`context`。

这让前端后续可以直接渲染：

- 工具调用原因。
- 锚点原文。
- 返回的 QQ 原文列表。
- 哪条是锚点、哪些是补充证据。

### 2. Model-facing tool result 去内部化

发回模型的 tool message 现在只包含公共证据字段：

- `display_title`
- `display_summary`
- `request_reason`
- `anchor_message`
- `result_kind`
- `counts`
- `messages`
- `assets`
- `entities`

不再发送：

- `coverage_scope`
- `derived_hints`
- 内部 `tool_name`

模型仍能通过 native tool call 上下文知道自己调用了哪个工具，但不会把内部实现字段误写进最终报告。

### 3. 模型最终 JSON 契约校验

`_validate_model_led_payload(...)` 现在要求：

- 必须有非空 `final_review`。
- 必须有非空 `final_review.verdict` 和 `final_review.core_object`。
- `final_review.evidence` / `boundaries` / `audit_risks` 必须是数组。
- 必须有 `adjudicated_relation_graph`。
- `nodes` / `confirmed_edges` / `boundary_edges` / `rejected_edges` / `open_questions` 必须是数组。
- 每条 `confirmed_edges[]` 必须有 `source`、`target`、`relation`、`summary` 和非空 `evidence_message_uids`。
- 必须有 `evidence_acquisition_summary`。
- `tool_calls_made` / `remaining_limits` 必须是数组。
- `why_enough` 必须存在且非空。

不满足时 fail closed，避免 Observer 把半成品或格式不明的 JSON 包装成人类审阅报告。

### 4. 命令行实测入口补强

`scripts/run_chat_orchestrator.py` 现在支持：

- `--candidate-id <candidate_id>`

用途：

- 允许直接跑 `candidate_windows.json` 中未进入 `selected_windows.json` 的候选。
- 方便验证更暧昧、更容易触发工具补证的候选，而不必先生成 review-editor seed。
- CLI 摘要现在会显示新契约里的 `final_review.verdict`、`core_object`、关系图数量和 `evidence_acquisition_summary`。

## 实测记录

### 真实 review-editor live session

- session: `live_ebd1f754e974b8`
- source run: `group_analysis::group_analysis_runs_message_first_phase4_specific_case::x3c_group_757773326::run_20260417_210641`
- candidate: `group_757773326_candidate_001`
- status: `completed`
- result:
  - `final_review` 存在。
  - `adjudicated_relation_graph` 存在，包含 `10` 个节点、`6` 条确认边、`2` 条边界边、`2` 条驳回边、`3` 个开放问题。
  - `evidence_acquisition_summary` 存在。
  - `final_review` 正文未检测到 `coverage_scope`、`derived_hints`、`message_first_context`、旧 tool 函数字段泄露。
  - 本候选没有自然触发工具调用；模型判断当前输入已足够。

### candidate_002 命令行真实 LLM 路径

- session: `codex_orch_contract_tool_path_20260502`
- command path: `scripts/run_chat_orchestrator.py --candidate-id group_757773326_candidate_002 --allow-llm-judge`
- status: `completed`
- natural tool call:
  - `fetch_shared_object_context` x1
- tool observation:
  - `display_title`: `同对象上下文已返回`
  - `display_summary`: `未找到可补充的同对象上下文；该方向目前只提供边界信息。`
  - `request_reason`: 模型认为源包后段存在省略，需要确认“shi/屎/吃史/搬史”是否有同对象延续。
  - `anchor_message.message_uid`: `msg_9ca7efcb91fe1321`
  - `result_kind`: `empty`
- final contract:
  - `final_review` 存在。
  - `adjudicated_relation_graph` 存在，包含 `7` 个节点、`3` 条确认边、`2` 条边界边、`1` 条驳回边、`2` 个开放问题。
  - `evidence_acquisition_summary.tool_calls_made` 记录了本次补证动作。
  - `final_review` 正文未检测到内部字段泄露。

### candidate_002 review-editor live 路径

- session: `live_0c0846c0bf5ea8`
- source run: `group_analysis::group_analysis_runs_message_first_phase4_specific_case::x3c_group_757773326::run_20260417_210641`
- candidate: `group_757773326_candidate_002`
- status: `completed`
- implementation note:
  - review-editor live session 现在可以在没有 `review_packets/<candidate>/review_seed.json` 的情况下，从 `candidate_windows.json` 解析候选窗口并生成最小 seed。
  - 这使未入选 candidate 也能直接从 LLM Sessions 页面发起真实 ORCH live run。
- validation result:
  - 本轮 candidate fallback 生效，session 正常 materialize。
  - 本轮模型未自然触发 tool call，因此不能替代 session-page tool rendering 验收。
  - 后续仍需要一轮包含 `tool.requested` / `tool.completed` 的 review-editor live session，专门验收工具调用是否显示“调用原因 + 锚点 QQ 原文 + 返回证据”。

## 边界

本轮不解决关系图 UI 视觉质量问题。关系图 UI 已记录为后续大改项，目前只要求后端输出契约稳定、可审计、能被未来 UI 正确消费。

## 验收建议

下一轮人工验收重点：

1. 真实 live session 里是否仍出现 `derived_hints`、`coverage_scope`、旧 `message_first_context` 字段进入主报告。
2. 工具调用是否能看到“调用原因 + 锚点 QQ 原文 + 返回证据”。
3. `final_review` 是否始终是人类可读主报告。
4. 关系图是否至少有模型判定后的 `adjudicated_relation_graph`，旧机械关系图不得冒充最终结论。
