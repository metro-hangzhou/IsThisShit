# Chat Orchestrator source candidate contract - 2026-05-03

## 背景

ORCH live session 已支持多结果输出和每个结果的证据案卷，但仍缺少一层 ORCH 自己负责的“候选对象索引”。

没有这层时，人类只能从模型最终报告里反推：模型到底看到了哪些可能对象、漏掉哪些对象、哪个结果是它自己发现的，哪个结果是基于 ORCH 输入包中的候选锚点。

## 目标

`source_packet.object_candidates` 是 ORCH 在把 QQ 原文交给模型之前，基于消息顺序、锚点、回复/转发、资源缺口和文本信号整理出的低保真候选对象索引。

它不是结论，也不替代模型审阅。它只解决两个问题：

- 防漏：提醒模型不要只审一个对象。
- 可追溯：最终 `review_results[]` 可以绑定到候选对象，方便 Observer 判断模型覆盖了哪些候选、跳过了哪些候选。

## 后端契约

`SourceTranscriptPacket` 新增：

```json
{
  "object_candidates": [
    {
      "candidate_id": "source_candidate_xxx",
      "rank": 1,
      "candidate_kind": "message_anchor",
      "role_hint": "candidate",
      "label_hint": "候选对象摘要",
      "object_cues": ["候选原文或关键词"],
      "anchor_message_uids": ["msg_anchor"],
      "evidence_message_uids": ["msg_before", "msg_anchor", "msg_after"],
      "boundary_message_uids": ["msg_asset_only"],
      "source": "source_packet_heuristic_v1",
      "why": "为什么把它列为候选"
    }
  ]
}
```

模型输出 `review_results[]` 时：

- 如果结果使用了候选对象，写 `source_candidate_ids`。
- 如果结果是模型自己从聊天中发现的新对象，写 `candidate_origin="model_discovered"`，不要伪造 candidate id。
- `source_candidate_ids` 必须来自 `source_packet.object_candidates[*].candidate_id`。

运行时验证：

- 未知 `source_candidate_ids` 会被拒绝。
- 如果模型没写 `source_candidate_ids`，ORCH 会尝试根据结果引用的 `message_uid` 与候选的 anchor/evidence/boundary 消息做保守绑定。
- 每个成功绑定的结果会注入 `candidate_package`，并在顶层写入 `result_candidate_packages`，供 Observer 和后续审查使用。

## 证据案卷修复

本轮同时修复了 `evidence_package` 展开后只显示摘要、不显示证据原文的问题。

修复规则：

- `llm_session_service.py` 不再在后端提前截断 final report section 的 `records`。
- `evidence_package.direct_evidence[]` 会映射成 `证据案卷` section 的 QQ 原文 records。
- 前端 `LlmFinalReportBlock.vue` 负责默认显示前 4 条，并通过“展开 N 条记录”展示剩余记录。

## Live 验证记录

时间：2026-05-03 23:27-23:29 +08:00

session：`state/llm_sessions/live_07aa7ded6335f2`

输入：

- review run：`x3c_group_757773326_run_20260417_210641_orch`
- candidate：`group_757773326_candidate_001`

验证结果：

- `chat_packet.prepared.payload.source_packet.object_candidates.length = 6`
- `analysis_output.compact_payload.review_results.length = 3`
- 3 个结果均带 `source_candidate_ids`
- 3 个结果均带 `candidate_package`
- `analysis_output.compact_payload.result_candidate_packages.length = 3`
- API detail 中 `finalReportViewModel.sections[id=evidence_package].recordCount = 6`
- `证据案卷` 第一条记录带 `badgeText = "QQ 原文"`，并含可读 quote

## 当前边界

- 候选对象索引是低保真启发式，不代表 ORCH 已经判断这些对象成立。
- 关系图 UI 仍是后续大改项；本合同只保证关系/候选数据进入可审查数据层。
- 模型可以发现候选之外的新对象，但必须显式标注来源，不能把新对象伪装成 ORCH 候选。
