# ORCH analyzer token budget / compact contract - 2026-05-02

## 结论

本轮把 ORCH model-led analyzer 的输入预算与 compact 契约从隐含约定改成了显式运行时契约。

2026-05-02 追加修正：

- compact 不再被视为普通前置步骤。
- 参考 Claude Code / Codex 的策略，只有上下文逼近模型极限、或系统已经实际丢弃上下文 section 时，才允许 compact。
- 几百条 QQ 原文的常规 live run 不应因为固定小 packet budget 被提前裁剪。
- `compact_contract` 只是“如果未来必须 compact 时应该保留什么”的契约，不代表本轮已经 compact。
- `context_organization` 成为新的主语义：明确本轮是 `pass_through`、`organized` 还是 `compact_applied`。
- 当前 V1 不额外调用整理模型；先用显式契约和阈值把错误 compact 挡住，后续再把 prompt-based organizer 接成独立同模型阶段。

目标不是节省 token 本身，而是保证后续 GPT / Claude / 便宜小模型都能按同一套边界理解输入：

- QQ 原文仍是第一证据层。
- 关系、补证、边界、缺失媒体必须作为结构化辅助信息进入模型。
- 超预算裁剪必须可见，不能静默丢证据。
- compact 摘要必须保留 `shi_core`、`relation_skeleton`、`uncertainty`、`dropped_noise_statement` 四个稳定面。
- 如果没有真实上下文丢弃，不生成 `CompactSnapshot`；tool call 或 evidence gap 本身不等于 compact。
- raw/debug 字段只能作为 Inspect/Raw，不应成为主审阅语义。

## 代码落点

- `src/qq_data_analysis/orch/source_packet.py`
  - 新增 `SourcePacketBudgetContract`。
  - 新增 `AnalyzerCompactContract`。
  - 新增 `ContextOrganizationResult` / `ContextOrganizationSection`。
  - `build_source_transcript_packet(...)` 接受 `ContextBudget`，按 `packet_budget` 裁剪消息包。
  - `SourceTranscriptPacket` 现在携带 `budget_contract`、`compact_contract` 与 `context_organization`。
  - `summarize_source_packet(...)` 改为显示 `输入包纳入 N/M 条 QQ 原文`，避免把原始窗口总数误读成实际输入包全量。
  - 如果确实有消息因预算被省略，`context_organization.status=compact_applied`，并生成可审计的低保真 `sections`。

- `src/qq_data_analysis/orch/engine.py`
  - model-led path 先加载 LLM client，解析模型上下文窗口，再调用 `build_source_transcript_packet(..., context_budget=profile.context_budget, context_window_tokens=...)`。
  - 当前 profile 的 `ContextBudget` 成为 analyzer packet 的预算来源。
  - 新增 `context.organization.completed` 事件，Observer 可直接读取本轮输入组织状态。

- `src/qq_data_analysis/orch/context_window.py`
  - 新增模型上下文窗口解析：
    - config 显式 `context_window_tokens` 优先。
    - 其次使用内置模型前缀表。
    - 最后 fallback 到 profile 默认窗口。

- `src/qq_data_analysis/llm_agent.py`
  - `DeepSeekRuntimeConfig` / `OpenAICompatibleRuntimeConfig` 增加可选 `context_window_tokens`。

- `src/qq_data_analysis/llm_session_service.py`
  - `sourcePacketContract` 现在会带出 `context_organization`，供前端 Observer 展示。

- `src/qq_data_analysis/orch/compact_runtime.py`
  - compact snapshot 现在额外生成：
    - `shi_core`
    - `relation_skeleton`
    - `uncertainty`
    - `dropped_noise_statement`
  - `summary_text` 也按这四类组织，避免 compact 退化成泛泛的 established facts。

- `src/qq_data_analysis/orch/state.py`
  - `CompactSnapshot` 增加上述四个稳定字段。

## 当前默认预算

预算来自 `ContextBudget`。当前 `shi_analysis_v1` live 默认面向大上下文模型：

- `max_input_tokens`: 128000
- `reserved_output_tokens`: 12000
- `prefix_budget`: 8000
- `packet_budget`: 96000
- `tool_observation_budget`: 8000
- `relation_summary_budget`: 6000
- `recap_budget`: 6000
- `output_budget`: 12000

model-led `SourceTranscriptPacket` 目前主要使用 `packet_budget` 裁剪 QQ 消息包，并把其他预算项写进 `budget_contract`，供模型、Observer、后续 compact/replay 使用。

`ContextBudget()` 类型自身仍可被测试或小模型 profile 显式改小；不要把默认 profile 的大窗口预算硬套给未来小模型。

## 裁剪策略

当前 V1 策略：

- 每条 QQ 消息先转为 `SourceMessageRef`。
- 单条消息的正文、text-only 字段、asset 数量有上限。
- 从窗口前部按顺序纳入消息，直到估算 token 超过 `message_packet_budget`。
- 至少保留 1 条消息，避免空 packet。
- 被裁剪数量写入：
  - `budget_contract.omitted_message_count`
  - `budget_contract.omitted_by_budget_count`
  - `omitted.message_count`
  - `omitted.reason`

这不是最终的智能抽样算法，只是第一版硬边界。修正后的默认预算足够容纳常规几百条 QQ 消息；只有接近上下文极限时才会触发裁剪。后续可升级为 relation-bound selection：优先保留核心锚点、锚点邻域、tool-needed anchors、关系骨架，而不是单纯按窗口顺序截断。

## Context Organization 契约

`context_organization` 是本轮实际输入组织状态，不是未来契约。

状态：

- `pass_through`
  - 所有被选中的 QQ 原文都直接进入 `messages`。
  - 普通几百条消息应走这个状态。
  - 模型可以在内部理解上整理讨论，但不能把原文证据替换成不可追溯摘要。
  - 如果没有原文被裁剪、但总压力已接近阈值，仍保持 `pass_through`，同时 `activation_reason=context_pressure_threshold_reached_without_drop`，供 Observer 提醒后续可能需要更强整理策略。
- `organized`
  - 预留给后续“同主模型 prompt-based organizer”。
  - 用于高频长讨论的可读整理，但仍必须标出 raw-pass 高风险消息。
- `compact_applied`
  - 只有实际发生消息省略或上下文压力达到阈值时出现。
  - `sections` 是低保真背景，不得替代 `messages` 中的 QQ 原文证据。

当前默认 compact 阈值：

- `compact_threshold_ratio = 0.9`
- 阈值 token = `context_window_tokens * 0.9`
- 压力估算包含 `reserved_output_tokens`。原因是模型真实上下文窗口不仅容纳输入，也要给输出留空间；只看输入材料会低估是否接近极限。

上下文窗口来源：

- 优先读取 `state/config/llm.local.json` 里的 `openai_compatible.context_window_tokens` 或 `deepseek.context_window_tokens`。
- 未配置时，根据模型名前缀解析，例如 `gpt-5.5* -> 128000`。
- 仍无法识别时，回退到 mission profile 的 `ContextBudget.max_input_tokens`。

后续 prompt-based organizer 的方向：

- 仍使用同一个主模型，不引入 RAG/clustering 作为主路径。
- 让模型输出分段审计结构：
  - 时间范围
  - 参与人数 / 关键发送者
  - 话题摘要
  - 组织后的输入文本
  - 必须 raw-pass 的消息
  - 失真风险
- 不能把独立 shi/topic 淹没在大段 compact 摘要里。

## Compact 契约

`AnalyzerCompactContract` 固定要求保留：

- `shi_core`
  - 核心对象、核心原文、已经确认的人类可读判断。
- `relation_skeleton`
  - 关键消息之间的关系骨架、工具补证摘要、关系图摘要。
- `uncertainty`
  - 仍未确认的证据缺口、需要补证或保守判断的边界。
- `dropped_noise_statement`
  - 哪些低优先级内容因为预算被丢弃，以及这会如何影响判断。

这四项是后续跨窗口 recap、小模型 fallback、Observer 主视图的共同契约。

触发规则：

- 普通几百条消息：不 compact。
- tool call 返回了补证：不因此 compact，只把补证放进当前上下文。
- evidence gap 存在：不因此 compact，只显示待补证点。
- 只有当预算管理确实丢弃了上下文 section，或后续会话逼近模型上下文窗口时，才生成 `CompactSnapshot`。

验收要求：

- compact 发生时，Observer 必须能显示 compact 后实际输入摘要。
- compact 后输入必须可读，能看出保留了哪些 QQ 原文、关系骨架、边界和被丢弃内容说明。
- 不能只显示一个契约名或 raw JSON，让人类无法判断 compact 是否有效。

## 验证

已跑：

```text
powershell.exe -Command "& .\.venv\Scripts\python.exe -m pytest tests\test_chat_orchestrator_runtime.py -q"
30 passed

powershell.exe -Command "& .\.venv\Scripts\python.exe -m pytest tests\test_llm_session_service.py tests\test_run_chat_orchestrator_script.py tests\test_llm_session_candidate_resolution.py -q"
29 passed

powershell.exe -Command "& .\.venv\Scripts\python.exe -m py_compile src\qq_data_analysis\orch\source_packet.py src\qq_data_analysis\orch\engine.py src\qq_data_analysis\orch\context_window.py src\qq_data_analysis\llm_agent.py src\qq_data_analysis\llm_session_service.py"
```

额外 headless probe：

```text
session_id = codex_budget_contract_probe_20260502
status = uncertain
stop_reason = insufficient_evidence
tool_observation_count = 4
compact_snapshot fields = shi_core, relation_skeleton, uncertainty, dropped_noise_statement
```

该 probe 没开 live LLM，只用于确认 deterministic ORCH runtime 与 artifact 写入未被契约变更破坏。

真实 review-editor live session 验收：

```text
session_id = live_6b3ef79ac9e071
status = completed
event_count = 4011
stream_chunk_count = 3999
prompt_tokens = 107249
completion_tokens = 4500
total_tokens = 111749
included_message_count = 447
omitted_message_count = 0
estimated_message_packet_tokens = 53171
message_packet_budget = 96000
context_window_tokens = 128000
context_window_source = known_model:gpt-5.5
estimated_pressure_ratio = 0.6654
context_organization.status = pass_through
context_organization.activation_reason = below_threshold_raw_messages_retained
compact_contract.status = available_not_applied
tool_observation_count = 0
final_json_valid = true
final_json_top_keys = review_results, primary_result_id, adjudicated_relation_graph, evidence_acquisition_summary
```

结论：

- 这轮真实 QQ 群 live session 没有触发 compact，符合“几百条、未裁剪、未逼近上限时不 compact”的最新约定。
- 模型实际 prompt token 比估算更高，但总量仍低于 128k 上下文窗口，并低于 90% compact 阈值。
- `context.organization.completed` 已补为人类可读 semantic 事件，不再在 session API 中显示成 `unknown_event`；需要重启 review server 后前端才能看到该修正。
- 本轮没有 tool call，符合这次 objective 要求“证据足够时不要主动补证”。

## 后续注意

- 下一轮 live LLM 测试应重点看 `chat_packet.prepared/source_packet.budget_contract` 是否在 Observer Raw/Inspect 中可查。
- 同时看 `context_organization.status`：几百条常规 QQ 消息必须是 `pass_through`，不能显示成 compact。
- 若真实窗口中预算裁剪导致模型漏掉明显关键证据，下一步应升级 packet selection，而不是放弃预算契约。
- 关系图 UI 暂时可用但不达最终标准，后续需要单独大改；本轮没有继续改关系图 UI。
