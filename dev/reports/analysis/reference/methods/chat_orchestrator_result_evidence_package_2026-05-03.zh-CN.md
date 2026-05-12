# ORCH result evidence package contract

日期：2026-05-03

## 目标

每个 `review_results[]` 结果都必须成为一个可人工复核的“证据案卷”，而不是只给模型结论。

用户需要在 review-editor LLM Sessions 中回答三件事：

- 这个结论引用了哪些 QQ 原文？
- 这个结论依赖哪些关系边？
- 这个结论是否使用了 ORCH 工具补证，工具返回了什么方向的信息？

## 新约束

`review_results[]` 中每个非 `boundary/rejected` 结果必须至少引用一条 QQ 原文 `message_uid`。

允许的引用来源：

- `evidence[*].message_uid`
- `relation_edge_ids[]` 指向的 `adjudicated_relation_graph.confirmed_edges[*].evidence_message_uids`
- 工具返回的 QQ 消息仍然必须使用工具 payload 里的 `message_uid`

不允许：

- 只写自然语言 quote 但没有 `message_uid`
- 把 `tool_name`、`coverage_scope`、`derived_hints` 当成人类报告正文
- 把缺失图片/语音/文件默认升级成 warning

## 关系图要求

`adjudicated_relation_graph.confirmed_edges[]` 现在要求：

```json
{
  "edge_id": "edge_1",
  "source": "msg_a",
  "target": "msg_b",
  "relation": "same_sender_continuation",
  "summary": "后一条延续前一条对象。",
  "evidence_message_uids": ["msg_a", "msg_b"]
}
```

如果模型省略 `edge_id`，运行时会自动补稳定 ID，但后续 prompt 会要求模型原生输出。

## 运行时生成内容

ORCH 在验证后会给每个 result 注入：

```json
{
  "evidence_package": {
    "schema_version": "orch_result_evidence_package_v1",
    "result_id": "r1",
    "direct_message_uids": ["msg_a"],
    "relation_edge_ids": ["edge_1"],
    "tool_observation_ids": ["obs_x"],
    "missing_message_uids": [],
    "direct_evidence": [],
    "relation_edges": [],
    "tool_observations": [],
    "summary": "1 条直接证据，1 条关系依据，1 个补证来源。"
  }
}
```

这不是模型要填写的新主报告，而是后端根据模型 JSON、source packet 和 tool observations 派生出的观察器案卷。

## 前端承接

`llm_session_service.py` 会把 `evidence_package` 映射成 final report view model 的三个 section：

- `证据案卷`
- `关系依据`
- `补证来源`

前端应该继续把它当作人类可读审查辅助信息展示，不要直接展示 raw JSON。

## 验收标准

- 非 boundary/rejected 结果没有 QQ `message_uid` 时，后端拒绝 model output。
- result 的 evidence/message_uid 不存在于 source packet 或 tool observations 时，后端拒绝。
- session 详情中的每个 result page 能看到证据案卷、关系依据和补证来源。
- 旧 `final_review` 兼容字段仍保留，但模型 prompt 不再允许 final_review-only 输出。
