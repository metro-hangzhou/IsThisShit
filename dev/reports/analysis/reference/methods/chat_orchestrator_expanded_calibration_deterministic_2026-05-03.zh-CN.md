# ORCH expanded calibration run

- generated_at: 2026-05-03T00:39:58
- allow_llm_judge: False
- case_count: 3

## Summary

| case | status | stop | messages | context | compact | tools | verdict | confidence | relations | leaks |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| x3c_specific_candidate_001 | completed | completed | 223 | - | - | fetch_sender_history_slice, fetch_related_assets | possible_shi | medium | c0/b0/r0/q0 | - |
| x3c_specific_candidate_002 | uncertain | insufficient_evidence | 447 | - | - | expand_window, fetch_reply_chain, fetch_related_assets, fetch_forward_tree | uncertain | medium | c0/b0/r0/q0 | - |
| x3c_specific_candidate_003 | completed | completed | 183 | - | - | fetch_related_assets | possible_shi | medium | c0/b0/r0/q0 | - |

## Case details

### x3c_specific_candidate_001

- tags: large-ish, asset-boundary, direct-text
- expected: 223-message X3C case; should avoid premature compact and keep asset missing as info boundary.
- session_id: `orch_cal_x3c_specific_candidate_001_20260503_003947`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_001`
- status: `completed` / `completed`
- prepared_summary: 窗口内共有 223 条已选消息，发送者 16 人。 forward 消息 0 条，reply 消息 15 条。 群友吃史反应约 137 条，主模式=整齐反馈/嫌弃/排斥/围观/惊诧。 当前 pack 仍有 6 个媒体缺口待解释。；已选 223 条聊天记录；1 个核心候选锚点；16 条消息探针；6 个媒体缺口仅作为信息边界。
- source_packet: `{"included_message_count": null, "omitted_message_count": null, "estimated_message_packet_tokens": null, "message_packet_budget": null, "compact_status": null, "context_status": null, "context_activation_reason": null, "context_pressure_ratio": null}`
- final_review: `{"label": "possible_shi", "confidence": "medium", "summary": "窗口内共有 223 条已选消息，发送者 16 人。 forward 消息 0 条，reply 消息 15 条。 群友吃史反应约 137 条，主模式=整齐反馈/嫌弃/排斥/围观/惊诧。 当前 pack 仍有 6 个媒体缺口待解释。", "core_object": "窗口内共有 223 条已选消息，发送者 16 人。 forward 消息 0 条，reply 消息 15 条。 群友吃史反应约 137 条，主模式=整齐反馈/嫌弃/排斥/围观/惊诧。 当前 pack 仍有 6 个媒体缺口待解释。", "evidence_count": 3, "boundary_count": 6, "audit_risk_count": 3}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 0}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": null, "remaining_limits": []}`
- tool_names: `["fetch_sender_history_slice", "fetch_related_assets"]`
- internal_leak_terms: `[]`

### x3c_specific_candidate_002

- tags: large, tool-likely, budget-pass-through
- expected: 447-message X3C case; useful for checking pass-through budget and natural tool-call behavior.
- session_id: `orch_cal_x3c_specific_candidate_002_20260503_003952`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_002`
- status: `uncertain` / `insufficient_evidence`
- prepared_summary: 窗口内共有 447 条已选消息，发送者 15 人。 forward 消息 1 条，reply 消息 61 条。 预处理层整理出 1 个 forward 摘要。 群友吃史反应约 240 条，主模式=嫌弃/排斥/围观/惊诧/整齐反馈。 当前 pack 仍有 23 个媒体缺口待解释。 deep forward 里还有 1 个只能靠 preview 保守判断的退化媒体位点。；已选 447 条聊天记录；16 条消息探针；23 个媒体缺口仅作为信息边界。
- source_packet: `{"included_message_count": null, "omitted_message_count": null, "estimated_message_packet_tokens": null, "message_packet_budget": null, "compact_status": null, "context_status": null, "context_activation_reason": null, "context_pressure_ratio": null}`
- final_review: `{"label": "uncertain", "confidence": "medium", "summary": "窗口内共有 447 条已选消息，发送者 15 人。 forward 消息 1 条，reply 消息 61 条。 预处理层整理出 1 个 forward 摘要。 群友吃史反应约 240 条，主模式=嫌弃/排斥/围观/惊诧/整齐反馈。 当前 pack 仍有 23 个媒体缺口待解释。 deep forward 里还有 1 个只能靠 preview 保守判断的退化媒体位点。", "core_object": "窗口内共有 447 条已选消息，发送者 15 人。 forward 消息 1 条，reply 消息 61 条。 预处理层整理出 1 个 forward 摘要。 群友吃史反应约 240 条，主模式=嫌弃/排斥/围观/惊诧/整齐反馈。 当前 pack 仍有 23 个媒体缺口待解释。 deep forward 里还有 1 个只能靠 preview 保守判断的退化媒体位点。", "evidence_count": 3, "boundary_count": 6, "audit_risk_count": 4}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 0}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": null, "remaining_limits": []}`
- tool_names: `["expand_window", "fetch_reply_chain", "fetch_related_assets", "fetch_forward_tree"]`
- internal_leak_terms: `[]`

### x3c_specific_candidate_003

- tags: medium, relation-graph
- expected: Medium X3C case; checks model-adjudicated relation graph stability.
- session_id: `orch_cal_x3c_specific_candidate_003_20260503_003957`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_003`
- status: `completed` / `completed`
- prepared_summary: 窗口内共有 183 条已选消息，发送者 18 人。 forward 消息 0 条，reply 消息 40 条。 群友吃史反应约 85 条，主模式=嫌弃/排斥/复读/回声/围观/惊诧。 当前 pack 仍有 8 个媒体缺口待解释。；已选 183 条聊天记录；1 个核心候选锚点；16 条消息探针；8 个媒体缺口仅作为信息边界。
- source_packet: `{"included_message_count": null, "omitted_message_count": null, "estimated_message_packet_tokens": null, "message_packet_budget": null, "compact_status": null, "context_status": null, "context_activation_reason": null, "context_pressure_ratio": null}`
- final_review: `{"label": "possible_shi", "confidence": "medium", "summary": "窗口内共有 183 条已选消息，发送者 18 人。 forward 消息 0 条，reply 消息 40 条。 群友吃史反应约 85 条，主模式=嫌弃/排斥/复读/回声/围观/惊诧。 当前 pack 仍有 8 个媒体缺口待解释。", "core_object": "窗口内共有 183 条已选消息，发送者 18 人。 forward 消息 0 条，reply 消息 40 条。 群友吃史反应约 85 条，主模式=嫌弃/排斥/复读/回声/围观/惊诧。 当前 pack 仍有 8 个媒体缺口待解释。", "evidence_count": 3, "boundary_count": 6, "audit_risk_count": 3}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 0}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": null, "remaining_limits": []}`
- tool_names: `["fetch_related_assets"]`
- internal_leak_terms: `[]`
