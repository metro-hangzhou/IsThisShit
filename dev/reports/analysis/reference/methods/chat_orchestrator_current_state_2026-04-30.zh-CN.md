# Chat Orchestrator Current State - 2026-04-30

## 结论

ORCH 本体已经从设计文档阶段进入可运行的 `shi_analysis_v1` runtime 阶段。当前代码具备 lifecycle engine、mission profile、context packet、budget stop、read-only tool runtime、deterministic/LLM worker 包装、observer event boundary、artifact persistence，以及 review-editor LLM Session 观察入口。

本轮主线变更重点是把 ORCH 的“证据关系图”从浅层 reply/local-context 扩成 v1.5，并让 worker 的 evidence-gap / tool-planning 先看关系图，再决定是否补工具；同时补上 review-editor LLM Session 的关系图观察入口，让人能直接看到 ORCH 为什么认为几条 QQ 原文互相关联。

## 当前代码基线

主要入口：

- `src/qq_data_analysis/orch/engine.py`
  - `ChatOrchestratorEngine`
  - 生命周期：prepare -> packet -> tool loop -> judge -> artifacts
  - 负责公开 observer event boundary，避免 worker 私有事件直接泄露成 UI 语义。
- `src/qq_data_analysis/orch/workers/shi_analysis.py`
  - `ShiAnalysisMissionWorker`
  - 包装 `build_benshi_analysis_pack(...)`
  - 负责 evidence gap 推导、tool request 规划、deterministic / LLM judge 对接、review surface guidance。
- `src/qq_data_analysis/orch/tool_runtime.py`
  - 当前工具都是 read-only local evidence tools：
    - `expand_window`
    - `fetch_reply_chain`
    - `fetch_sender_history_slice`
    - `fetch_topic_cluster_slice`
    - `fetch_related_assets`
    - `fetch_shared_object_context`
    - `fetch_forward_tree`
- `src/qq_data_analysis/benshi_message_first.py`
  - message-first probes
  - relation-bound message packet
  - relation graph v1.5
- `scripts/run_chat_orchestrator.py`
  - 从 review run / materialized packet 触发 ORCH headless run。

## Relation Graph v1.5

已实现 edge families：

- `reply`
  - 从 `reply_to.referenced_message_id` 绑定源消息与被回复消息。
- `at_binding`
  - 从结构化 `at` segment 或文本 `@xxx` 抽取 @ 目标，并按 sender id / name / card 映射到消息。
- `shared_asset_continuation`
  - 同一图片、文件、语音、视频、贴纸等 asset key 重复出现时绑定上下文。
- `nested_forward_parent_child`
  - forward segment 内已保留 child payload 时，标记该 forward carrier 已有可见子结构。
- `same_sender_continuation`
  - 同发送者连续发言且存在局部 topic/object 连续性时绑定。
- `explicit_uptake`
  - 邻近消息出现明确接话、反应、复述、吐槽等 uptake 信号时绑定。
- `local_context`
  - 低置信兜底，只表示相邻 stronger anchor 与 social echo 可能相关。

当前关系图仍是启发式 v1.5，不是最终判定器。它的职责是降低明显冗余的 tool call，并让 ORCH 更接近“先理解已有证据结构，再补缺口”的 agentic 工作流。

## Tool Planning 策略变化

旧行为倾向：

- 只要出现 sender/topic/forward 迹象，就容易发工具。
- 已经在 packet / relation graph 中存在的局部关系，也可能重复请求。

新行为：

- `missing_relation_binding` 先检查是否已有 reply / @ / explicit uptake / shared asset / local context。
- sender history 只在 anchor 缺少 `same_sender_continuation` 且窗口内确实存在同发送者上下文时请求。
- topic cluster 只在 anchor 缺少 reply / @ / uptake / shared asset / local context，且窗口内确实存在同 topic 支持时请求。
- forward tree 只在 forward carrier 存在但没有 `nested_forward_parent_child` 结构时请求。
- asset missing 仍只作为 info / boundary，不应自动升级成 warning；但会保留 `fetch_related_assets` 入口用于验证媒体边界。

## 本轮验证

聚焦回归：

```text
./.venv/Scripts/python.exe -m pytest tests/test_benshi_message_first.py tests/test_chat_orchestrator_runtime.py -q
24 passed
```

新增/更新覆盖：

- relation graph v1.5 能产生 `at_binding`、`shared_asset_continuation`、`same_sender_continuation`、`nested_forward_parent_child`。
- relation graph 不再把两端都是 `off_target` 的 same-sender 系统/噪声消息误连成证据关系。
- worker 在 relation graph 已覆盖 sender/topic/forward 时不再请求冗余工具。
- worker 在 relation graph 缺少 anchor coverage 时仍会请求 sender/topic 工具。
- ORCH engine 现在在 `chat_packet.prepared` / `chat_packet.built` 事件上输出 `relation_graph_summary`。
- `llm_session_service` 会把该摘要转换为 `semantic.relationGraph` 和 packet `jsonPreview.relationGraph`。
- review-editor 新增关系图块，默认显示人类可读的锚点、关系类型、关系原因和 source/target 预览；raw edge id / raw relation type 只保留在 Inspect/Raw。
- worker 在所有本地补证工具耗尽后仍没有 core probe 时，会停在 `insufficient_evidence`，不会伪装成完成。
- `fetch_shared_object_context` 的 observation hints 已修复，不再引用不存在的 `keywords` 变量。
- engine 仍能记录 canonical tool observations，且不会泄露旧的 worker-private event aliases。

小样本 headless 验证已扩展到 4 个真实窗口：

```text
.tmp/orch_small_sample_calibration_20260430/
```

结果：

- `sample_x3c_specific_w1`
  - status: `completed`
  - stop_reason: `completed`
  - relation_edge_count: `6`
  - tools: `fetch_sender_history_slice`, `fetch_topic_cluster_slice`, `fetch_related_assets`
- `sample_763_phase2_w1`
  - status: `uncertain`
  - stop_reason: `insufficient_evidence`
  - relation_edge_count: `0`
  - evidence gap: `missing_core_object`
  - 这是本轮关键负例：无核心对象时不再误完成，也不再生成 off-target same-sender 假关系。
- `sample_712_small_fixed_w1`
  - status: `completed`
  - stop_reason: `completed`
  - relation_edge_count: `1`
  - tools: `fetch_reply_chain`, `fetch_shared_object_context`, `fetch_related_assets`
- `sample_712_batch_w1`
  - status: `completed`
  - stop_reason: `completed`
  - relation_edge_count: `6`
  - tools: `fetch_topic_cluster_slice`, `fetch_shared_object_context`, `fetch_related_assets`, `fetch_forward_tree`

Observed caveat:

- deterministic fallback `final_review` is still only a safe fallback contract, not the final product-level human report. Product-quality final report should come from the LLM worker once the public output contract is fully converged.
- relation graph v1.5 仍是启发式；same-sender 已收窄，但 `shared_asset_continuation` / `local_context` 还需要更多真实窗口校准。

详细报告：

- `dev/reports/analysis/reference/methods/chat_orchestrator_small_sample_calibration_2026-04-30.zh-CN.md`

## 仍然没有完成的主线

P0:

- 真实窗口校准 relation graph v1.5 的误判 / 漏判。
- 正式收束 ORCH public contract 与 worker-private internal payload 的边界。
- 小样本 qualitative validation：确认 direct text / image / video shi 不再被 forward bias 压过。

P1:

- token budget / compact contract formal化已落第一版：
  - `SourceTranscriptPacket` 携带 `budget_contract` / `compact_contract`
  - model-led 输入包按 `ContextBudget.packet_budget` 裁剪 QQ 消息
  - `CompactSnapshot` 保留 `shi_core` / `relation_skeleton` / `uncertainty` / `dropped_noise_statement`
  - 详细记录见 `dev/reports/analysis/reference/methods/chat_orchestrator_budget_compact_contract_2026-05-02.zh-CN.md`
- selected-message compatibility layer 逐步降级，最终让 raw message probing 成为唯一主路径。
- tool runtime 增强：每个 tool observation 应提供人类可读 summary + raw inspect，而不是只给内部字段。
- ORCH Observer relation graph UI 的 V1 已可显示主线关系摘要；但 2026-05-02 验收结论是：当前 UI 只能临时使用，后续需要大改，不应作为最终可用关系图形态。
- 关系图后续大改目标：source/target 接到 PCQQ 风格原文证据卡或跳转能力，关系方向、关系类型、确认/边界状态、模型理由必须一眼可见；raw debug 继续留在 Raw/Inspect。
- BenshiMaster worker registry / multi-worker contract 继续落地。

P2:

- 大样本定量跑分。
- 更强的 relation score calibration。
- 跨窗口 recap / memory budget。

## 下一步建议

1. 先用一到两个真实 review run 做 small-sample ORCH validation，不开大规模量化。
2. 审查 relation edges 是否与人类直觉一致，尤其是 @、shared asset、same-sender、explicit uptake。
3. 如果 relation graph 方向正确，继续把 source/target message node 接到 PCQQ 风格原文证据卡；raw debug 继续留在 Raw/Inspect。
4. 之后再推进 BenshiMaster agent worker registry 和 compact/budget formalization。
