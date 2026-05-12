# Chat Orchestrator Model-Led Native Tool Loop - 2026-05-01

## 背景

ORCH 前一阶段的实现把“预整理”和“关系图”做得过重：

- `message_first_context`、机械 `relation_edges`、`message_probes` 会在模型审阅前先形成一套启发式结论。
- `fetch_topic_cluster_slice` 等工具会由 worker 预规划，而不是由模型在阅读 QQ 原文后按需调用。
- Observer 上容易出现“看似 agentic，实际是预整理后的机械补证流程”的错觉。

这和最新对齐后的目标不一致。ORCH Observer 的核心价值不是展示一坨内部字段，而是让人类看到：

1. 模型实际读到了哪些 QQ 原文和资源边界。
2. 模型为什么认为需要补证。
3. 模型调用了什么工具、拿回了什么证据。
4. 模型最终如何判定 QQ 原文之间的关系、哪些关系确认、哪些只是边界。

## 新主线结论

新的默认 LLM 审阅路径改为 model-led：

```text
source transcript packet
  -> native tool-call model loop
  -> model-adjudicated review_results[]
  -> model-adjudicated relation graph
  -> Observer 展示人类可审阅结论，Raw/Inspect 保留底层细节
```

程序只负责提供客观输入和本地只读工具，不再提前替模型做语义关系判定。

## 关键代码

- `src/qq_data_analysis/orch/source_packet.py`
  - 新增 `SourceTranscriptPacket`。
  - 只包含 QQ 原文、发送者、时间、reply/forward/asset facts、seed objective facts 和边界提示。
  - 不包含 `message_first_context`、机械 `relation_edges`、机械 topic graph。
- `src/qq_data_analysis/orch/native_tools.py`
  - 新增 provider-agnostic tool-call 内部契约。
  - 目前实现 OpenAI-compatible payload 适配。
- `src/qq_data_analysis/llm_agent.py`
  - `OpenAICompatibleAnalysisClient.create_chat_tool_turn(...)` 是 thin adapter。
  - OpenAI-compatible Chat Completions streaming 会聚合 content / reasoning / tool-call delta，返回准最终 `choices[0].message.tool_calls`，供 ORCH 复用同一 provider-agnostic extractor。
  - `benshi_orch_*` prompt family 现在和 `benshi_master_*` 一样默认 `temperature=0.0`、`reasoning_effort=medium`，除非本地配置显式覆盖。
  - ORCH loop 不写死在 OpenAI client 内。
- `src/qq_data_analysis/orch/engine.py`
  - `allow_llm_judge=True` 时进入 `_run_model_led(...)`。
  - 旧 deterministic worker path 仍保留为 non-LLM / legacy fallback。
- `src/qq_data_analysis/orch/tool_runtime.py`
  - `fetch_shared_object_context` 现在必须由模型提供 `object_cues`。
  - ORCH 不再机械推断 same-object。
- `src/qq_data_analysis/llm_session_service.py`
  - `orchestrator.completed` 现在可把 `adjudicated_relation_graph` 转成前端 `semantic.relationGraph`。
  - 旧 `relation_graph_summary` 仍只作为旧 packet / historical session 兼容。

## Native Tool Loop 契约

V1 默认工具：

- `expand_window`
- `fetch_reply_chain`
- `fetch_related_assets`
- `fetch_shared_object_context`
- `fetch_sender_history_slice`
- `fetch_forward_tree`

默认禁用：

- `fetch_topic_cluster_slice`
- `web_search`
- `entity_disambiguation_search`

预算：

- 最大模型轮次：`4`
- 最大总工具调用：`8`
- 同一工具最大重复：`2`

失败策略：

- provider 不支持 native tool-call：fail closed。
- 模型给出非法 tool args：fail closed。
- 模型未输出 `review_results`、`primary_result_id` 或 `adjudicated_relation_graph`：fail closed。
- `final_review` / `final_reviews` 只允许作为历史 session 或下游 materializer 兼容字段；model-led ORCH 的模型输出不能只给 legacy 单结果字段。
- 不静默回落到机械工具规划，避免 Observer 误以为模型完成了 agentic 审阅。

流式策略：

- 模型自然语言 / JSON content delta 实时进入 `session.stream_chunk`。
- reasoning delta 若 provider 返回，也以 `kind=reasoning` 进入同一流。
- content/reasoning delta 按 provider 原样拼接，不对每个 chunk 做 `.strip()`，避免流式 JSON 字符串里的空格/换行被静默改写。
- tool-call arguments delta 只在 provider adapter 内部聚合，不直接逐字显示给用户；一旦 tool call 完整闭合，由 ORCH 发出 `tool.requested` / `tool.completed` 事件。
- 如果 provider 或 fake client 不走 streaming，ORCH 仍会把最终 content 作为 fallback chunk 发出，但不会在 streaming 成功时重复发送完整 JSON。

## Same-Object Rule

`fetch_shared_object_context` 不再自己用关键词重叠猜同对象。

模型必须显式给：

```json
{
  "anchor_message_uid": "msg_xxx",
  "object_cues": ["吹高通但不买高通机器", "不买高通机器"],
  "limit": 8
}
```

原因：

- “同对象”是语义判断，不能由 worker 靠字符串重叠偷做。
- Worker 可以检索，不能替模型判定关系。
- 没有 `object_cues` 时返回 `missing_object_cues`。

## Final JSON Contract

模型最终必须输出 JSON object，并至少包含：

```json
{
  "review_results": [
    {
      "result_id": "r1",
      "rank": 1,
      "result_kind": "shi",
      "role": "primary",
      "verdict": {
        "label": "可成立 / 可能成立 / 不成立 / 不确定",
        "confidence": "high / medium / low",
        "summary": "人类可读短结论"
      },
      "core_object": {
        "label": "被审阅对象",
        "summary": "这个对象为什么值得审"
      },
      "evidence": [],
      "boundaries": [],
      "audit_risks": []
    }
  ],
  "primary_result_id": "r1",
  "adjudicated_relation_graph": {
    "summary": "模型如何整理关系的总述",
    "nodes": [],
    "confirmed_edges": [],
    "boundary_edges": [],
    "rejected_edges": [],
    "open_questions": []
  },
  "evidence_acquisition_summary": {
    "tool_calls_made": [],
    "why_enough": "为什么当前证据足够或为什么仍需保留边界",
    "remaining_limits": []
  }
}
```

多对象规则：

- 如果窗口内有多个独立可审阅对象，必须输出多条 `review_results`，不要压成一个混合结论。
- 如果只有一个对象，也输出长度为 `1` 的 `review_results`。
- 缺失图片、普通背景话题、资产状态和无命题闲聊不要硬塞成结果；它们应进入 `boundaries`、`audit_risks` 或 `evidence_acquisition_summary.remaining_limits`。
- 模型输出只给 `final_review` / `final_reviews` 时，model-led 验证器必须拒绝，避免重新退回单结果契约。

关系图语义：

- `confirmed_edges`: 模型认为已由 QQ 原文或工具返回证据确认的关系。
- `boundary_edges`: 有提示价值但证据不足，不能当作确认关系。
- `rejected_edges`: 模型主动驳回的候选关系。
- `open_questions`: 仍需要人工或更多数据判断的问题。

确认关系必须带可复核 QQ 证据引用，例如 `evidence_refs[*].message_uid`。

## Observer Contract

主线展示：

- QQ 原文证据。
- 工具调用原因和工具返回的人类摘要。
- 模型最终审阅报告。
- 模型判定后的关系图。

Raw/Inspect 展示：

- provider 原始响应。
- legacy prepared payload。
- old `message_first_context`。
- tool args / coverage scope / derived hints。
- 过大的 prompt/packet preview。

`llm_session_service.py` 现在把新 `adjudicated_relation_graph` 适配为：

```json
{
  "schemaVersion": "orch_adjudicated_relation_graph_v1",
  "modelAdjudicated": true,
  "summary": "...",
  "groups": [
    {
      "title": "模型确认关系",
      "relations": []
    },
    {
      "title": "边界关系",
      "relations": []
    }
  ]
}
```

这只是后端契约适配，不代表当前前端关系图 UI 已经达到最终可用质量。

## 与旧路径的关系

仍保留：

- deterministic worker judge。
- old relation graph summary。
- `fetch_topic_cluster_slice` runtime implementation。

但它们现在是：

- legacy / non-LLM fallback。
- historical session compatibility。
- Raw/Inspect 诊断材料。

不再是 LLM 主线判断路径。

## 当前限制

- OpenAI-compatible native tool-call adapter 已有，但其他 provider 还没有独立 adapter。
- `_run_model_led(...)` 已支持 OpenAI-compatible native tool-call turn 的 content/reasoning token streaming；tool-call delta 在 adapter 内聚合后交给 ORCH 执行。
- 其他 provider 的 streaming/tool-call adapter 尚未实现；接入时必须实现同一 turn contract，不能把 provider 原始 wire shape 透传给 engine。
- 前端关系图仍需要 CC 做高质量 UI/UX 重构：目前先保证拿到的是 model-adjudicated graph，而不是旧机械 graph。
- 旧 prepared payload 仍会在运行时为兼容而构造，但不应进入主线 prompt 和主线 Observer。

## 验证

已运行：

```powershell
.\.venv\Scripts\python.exe -m py_compile src\qq_data_analysis\llm_session_service.py src\qq_data_analysis\orch\tool_runtime.py tests\test_llm_session_service.py
```

结果：通过。

已运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_orchestrator_runtime.py tests\test_llm_session_service.py -q
```

结果：`47 passed`。

本轮补充验证：

```powershell
.\.venv\Scripts\python.exe -m py_compile src\qq_data_analysis\llm_agent.py src\qq_data_analysis\orch\engine.py tests\test_llm_window_analysis.py tests\test_chat_orchestrator_runtime.py
```

结果：通过。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_orchestrator_runtime.py tests\test_llm_session_service.py tests\test_llm_window_analysis.py -q
```

结果：`70 passed`。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_orchestrator_runtime.py tests\test_llm_session_service.py tests\test_benshi_message_first.py tests\test_benshi_master_agent.py -q
```

结果：`81 passed`。

真实数据命令行 live verify：

```powershell
.\.venv\Scripts\python.exe scripts\run_chat_orchestrator.py state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641 --window-index 1 --output-root .tmp\chat_orchestrator_model_led_live_verify --session-id codex_model_led_live_verify_20260501 --allow-llm-judge
```

结果：

- `status=completed`
- `agent=shi_orchestrator_model_led v1`
- `model=gpt-5.5` from local OpenAI-compatible config
- `review_results[0].verdict.label=not_established`
- `adjudicated_relation_graph`: `confirmed_edges=6`, `boundary_edges=2`, `rejected_edges=3`, `open_questions=3`
- `tool_calls_made=[]`

解释：

- 这轮模型认为 source packet 已足够判定核心对象是高通 / Nuvia / Oryon / ARM / 苹果芯片与跑分功耗争论，不需要额外工具。
- 这符合 model-led 设计：工具不是预整理阶段强制调用，而是模型在证据不足时按需调用。
