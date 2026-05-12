# ORCH expanded calibration run

- generated_at: 2026-05-03T00:46:11
- allow_llm_judge: True
- case_count: 6

## Summary

| case | status | stop | messages | context | compact | tools | verdict | confidence | relations | leaks |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| x3c_specific_candidate_001 | completed | completed | 223 | pass_through | available_not_applied | - | 成立 | 中高 | c10/b3/r3/q3 | - |
| x3c_specific_candidate_002 | failed | model_error | 447 | pass_through | available_not_applied | - | failed | low | c0/b0/r0/q1 | - |
| x3c_specific_candidate_003 | failed | model_error | 183 | pass_through | available_not_applied | - | failed | low | c0/b0/r0/q1 | - |
| phase2_763_candidate_001 | failed | model_error | 24 | pass_through | available_not_applied | - | failed | low | c0/b0/r0/q1 | - |
| small_712_candidate_001 | failed | model_error | 15 | pass_through | available_not_applied | - | failed | low | c0/b0/r0/q1 | - |
| small_712_candidate_004 | completed | completed | 48 | pass_through | available_not_applied | fetch_forward_tree, fetch_reply_chain | 部分成立 | 中 | c5/b3/r1/q3 | - |

## Case details

### x3c_specific_candidate_001

- tags: large-ish, asset-boundary, direct-text
- expected: 223-message X3C case; should avoid premature compact and keep asset missing as info boundary.
- session_id: `orch_cal_x3c_specific_candidate_001_20260503_004129`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_001`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 223/223 条 QQ 原文；16 名发送者；seed burst=0.61；输入包≈26716/96000 tokens；6 个信息边界。
- source_packet: `{"included_message_count": 223, "omitted_message_count": 0, "estimated_message_packet_tokens": 26716, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.4587}`
- final_review: `{"label": "成立", "confidence": "中高", "summary": "本轮窗口存在清晰、持续的“shi/搬史/吃史”对象：群聊围绕高通、Oryon/Nuvia、8E/8750/8850、GB6/SPEC、苹果与ARM公版展开高强度争论，并反复出现“抄袭、作弊、超频、功耗、跑分、打苹果、Nuvia做不了几代”等可追溯说法。", "core_object": "高通/Oryon/Nuvia 及其跑分、功耗、商业前景争议", "evidence_count": 10, "boundary_count": 4, "audit_risk_count": 4}`
- relation_counts: `{"nodes": 15, "confirmed_edges": 10, "boundary_edges": 3, "rejected_edges": 3, "open_questions": 3}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": "本轮输入显示 223 条 QQ 原文全部纳入，省略消息数为 0；核心争议由多条可见文本直接支撑，且跨越多个发送者和多个时间段反复出现。缺失图片会影响具体截图内容和技术事实核验，但不影响确认本轮存在围绕高通/Oryon/Nuvia/跑分功耗争议的“shi”对象，因此无需额外补证即可作出成立判断。", "remaining_limits": ["部分图片缺失，不能确认图片内容。", "未展开回复链，不能精确确认每条回复的被引用原句。", "未验证群聊技术说法的外部真实性。"]}`
- tool_names: `[]`
- internal_leak_terms: `[]`

### x3c_specific_candidate_002

- tags: large, tool-likely, budget-pass-through
- expected: 447-message X3C case; useful for checking pass-through budget and natural tool-call behavior.
- session_id: `orch_cal_x3c_specific_candidate_002_20260503_004254`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_002`
- status: `failed` / `model_error`
- prepared_summary: 输入包纳入 447/447 条 QQ 原文；15 名发送者；seed burst=1.00；输入包≈53171/96000 tokens；16 个信息边界。
- source_packet: `{"included_message_count": 447, "omitted_message_count": 0, "estimated_message_packet_tokens": 53171, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.6654}`
- final_review: `{"label": "failed", "confidence": "low", "summary": "模型主导 ORCH 未能产出有效审阅结果。", "core_object": "", "evidence_count": 0, "boundary_count": 1, "audit_risk_count": 1}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 1}`
- evidence_acquisition: `{}`
- tool_names: `[]`
- internal_leak_terms: `[]`

### x3c_specific_candidate_003

- tags: medium, relation-graph
- expected: Medium X3C case; checks model-adjudicated relation graph stability.
- session_id: `orch_cal_x3c_specific_candidate_003_20260503_004315`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_003`
- status: `failed` / `model_error`
- prepared_summary: 输入包纳入 183/183 条 QQ 原文；18 名发送者；seed burst=0.43；输入包≈21648/96000 tokens；8 个信息边界。
- source_packet: `{"included_message_count": 183, "omitted_message_count": 0, "estimated_message_packet_tokens": 21648, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.4191}`
- final_review: `{"label": "failed", "confidence": "low", "summary": "模型主导 ORCH 未能产出有效审阅结果。", "core_object": "", "evidence_count": 0, "boundary_count": 1, "audit_risk_count": 1}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 1}`
- evidence_acquisition: `{}`
- tool_names: `[]`
- internal_leak_terms: `[]`

### phase2_763_candidate_001

- tags: negative-or-uncertain, no-core-object
- expected: Known weak/uncertain style sample; ORCH should not force a confident positive verdict.
- session_id: `orch_cal_phase2_763_candidate_001_20260503_004345`
- source: `state\group_analysis_runs_message_first_phase2\amd_guanren_group_763328502\run_20260417_003634` / `group_763328502_candidate_001`
- status: `failed` / `model_error`
- prepared_summary: 输入包纳入 24/24 条 QQ 原文；4 名发送者；seed burst=0.18；输入包≈2952/96000 tokens。
- source_packet: `{"included_message_count": 24, "omitted_message_count": 0, "estimated_message_packet_tokens": 2952, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.2731}`
- final_review: `{"label": "failed", "confidence": "low", "summary": "模型主导 ORCH 未能产出有效审阅结果。", "core_object": "", "evidence_count": 0, "boundary_count": 1, "audit_risk_count": 1}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 1}`
- evidence_acquisition: `{}`
- tool_names: `[]`
- internal_leak_terms: `[]`

### small_712_candidate_001

- tags: small, reply-or-local-context
- expected: Small 712 sample; checks local relation and tool behavior on short windows.
- session_id: `orch_cal_small_712_candidate_001_20260503_004403`
- source: `state\group_analysis_runs_message_first_small_one_fixed\amd_guanren_group_712742342\run_20260417_001344` / `group_712742342_candidate_001`
- status: `failed` / `model_error`
- prepared_summary: 输入包纳入 15/15 条 QQ 原文；13 名发送者；seed burst=0.13；输入包≈2100/96000 tokens；2 个信息边界。
- source_packet: `{"included_message_count": 15, "omitted_message_count": 0, "estimated_message_packet_tokens": 2100, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.2664}`
- final_review: `{"label": "failed", "confidence": "low", "summary": "模型主导 ORCH 未能产出有效审阅结果。", "core_object": "", "evidence_count": 0, "boundary_count": 1, "audit_risk_count": 1}`
- relation_counts: `{"nodes": 0, "confirmed_edges": 0, "boundary_edges": 0, "rejected_edges": 0, "open_questions": 1}`
- evidence_acquisition: `{}`
- tool_names: `[]`
- internal_leak_terms: `[]`

### small_712_candidate_004

- tags: small-medium, mixed-context
- expected: 48-message 712 sample; broadens relation/tool calibration beyond the first small case.
- session_id: `orch_cal_small_712_candidate_004_20260503_004420`
- source: `state\group_analysis_runs_message_first_small_one_fixed\amd_guanren_group_712742342\run_20260417_001344` / `group_712742342_candidate_004`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 48/48 条 QQ 原文；13 名发送者；seed burst=0.36；输入包≈5927/96000 tokens。
- source_packet: `{"included_message_count": 48, "omitted_message_count": 0, "estimated_message_packet_tokens": 5927, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.2963}`
- final_review: `{"label": "部分成立", "confidence": "中", "summary": "本窗口中可以确认存在一次“搬运/分享”型对象：首条多层转发把“霍金、萝莉岛、克林顿”等猎奇段子或聊天记录带入群内，并引发短暂反应与追问。但不能确认群内明确使用了“史”“搬史”“吃史”等说法，也不能确认转发内图片和嵌套聊天记录的完整内容。", "core_object": "霍金、萝莉岛、克林顿相关的多层转发内容", "evidence_count": 7, "boundary_count": 4, "audit_risk_count": 4}`
- relation_counts: `{"nodes": 11, "confirmed_edges": 5, "boundary_edges": 3, "rejected_edges": 1, "open_questions": 3}`
- evidence_acquisition: `{"tool_calls_made": ["查询首条多层转发的结构和可补正文", "核对紧随其后的“？”是否有明确回复链"], "why_enough": "本轮输入没有省略消息，且首条转发、后续反应、霍金追问、克林顿画面评论都已在 QQ 原文中可追溯；补证确认未获得更多首条转发正文，也未能补到“？”的回复链。因此已经足够做保守判断：对象作为被搬运并被短暂消费的霍金/萝莉岛相关转发成立，但不足以确认完整嵌套内容或明确‘史’标签。", "remaining_limits": ["首条转发的深层聊天记录和图片没有完整展开。", "图片资源虽无缺失，但当前证据层没有图像内容解读。", "部分短回复的具体指向无法确认。"]}`
- tool_names: `["fetch_forward_tree", "fetch_reply_chain"]`
- internal_leak_terms: `[]`
