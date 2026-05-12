# ORCH expanded calibration run

- generated_at: 2026-05-04T02:28:38
- allow_llm_judge: True
- case_count: 1

## Summary

| case | status | contract | issues | stop | messages | context | compact | tools | verdict | confidence | relations | leaks |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| small_712_candidate_004 | completed | pass | 0 | completed | 48 | pass_through | available_not_applied | fetch_forward_tree, fetch_forward_tree | 可能成立的吃史对象 | 中等 | c7/b3/r2/q3 | - |

## Case details

### small_712_candidate_004

- tags: small-medium, mixed-context
- expected: 48-message 712 sample; broadens relation/tool calibration beyond the first small case.
- session_id: `orch_cal_small_712_candidate_004_20260504_022635`
- source: `state\group_analysis_runs_message_first_small_one_fixed\amd_guanren_group_712742342\run_20260417_001344` / `group_712742342_candidate_004`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 48/48 条 QQ 原文；13 名发送者；seed burst=0.36；输入包≈5927/96000 tokens。
- source_packet: `{"included_message_count": 48, "omitted_message_count": 0, "estimated_message_packet_tokens": 5927, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.2963, "object_candidate_count": 6}`
- payload_contract: `{"top_level_keys": ["adjudicated_relation_graph", "evidence_acquisition_summary", "final_review", "final_reviews", "orchestrator_trace_summary", "primary_result_id", "provider_protocol", "result_candidate_packages", "result_evidence_packages", "review_results", "tool_observation_count"], "has_native_review_results": true, "review_result_ids": ["topic_1", "topic_2", "topic_3"], "primary_result_id": "topic_1", "primary_result_id_known": true, "has_legacy_final_review": true, "has_legacy_final_reviews": true, "legacy_only": false, "has_adjudicated_relation_graph": true, "has_evidence_acquisition_summary": true, "missing_top_keys": [], "result_evidence_package_count": 3, "result_candidate_package_count": 3}`
- review_results: `{"count": 3, "primary_result_id": "topic_1", "primary": {"result_id": "topic_1", "rank": 1, "role": "primary", "result_kind": "shi", "label": "可能成立的吃史对象", "confidence": "中等", "summary": "窗口前半段围绕一条关于“霍金去萝莉岛”的转发段子及疑似 AI 生成内容展开，群友接着用“生草”“ai 太好用了”“霍金的渐冻症发展到什么程度了”“用手搂克林顿肩看懵了”等话语继续消费该对象。", "core_object": "关于霍金、萝莉岛与克林顿的转发段子或疑似 AI 内容", "evidence_count": 6, "boundary_count": 2, "audit_risk_count": 2, "source_candidate_ids": ["source_candidate_a026a84562", "source_candidate_d1932d05a1"], "has_candidate_package": true, "has_evidence_package": true, "evidence_package": {"direct_message_uid_count": 5, "relation_edge_id_count": 3, "tool_observation_id_count": 2, "direct_evidence_count": 6, "relation_edge_count": 3, "tool_observation_count": 2, "missing_message_uid_count": 0}}, "items": [{"result_id": "topic_1", "rank": 1, "role": "primary", "result_kind": "shi", "label": "可能成立的吃史对象", "confidence": "中等", "summary": "窗口前半段围绕一条关于“霍金去萝莉岛”的转发段子及疑似 AI 生成内容展开，群友接着用“生草”“ai 太好用了”“霍金的渐冻症发展到什么程度了”“用手搂克林顿肩看懵了”等话语继续消费该对象。", "core_object": "关于霍金、萝莉岛与克林顿的转发段子或疑似 AI 内容", "evidence_count": 6, "boundary_count": 2, "audit_risk_count": 2, "source_candidate_ids": ["source_candidate_a026a84562", "source_candidate_d1932d05a1"], "has_candidate_package": true, "has_evidence_package": true, "evidence_package": {"direct_message_uid_count": 5, "relation_edge_id_count": 3, "tool_observation_id_count": 2, "direct_evidence_count": 6, "relation_edge_count": 3, "tool_observation_count": 2, "missing_message_uid_count": 0}}, {"result_id": "topic_2", "rank": 2, "role": "secondary", "result_kind": "topic", "label": "技术背景话题成立，但不宜升级为主要吃史对象", "confidence": "中等偏高", "summary": "窗口后半段围绕 HyperOS/MIUI 漏洞、解锁、EL2、虚拟机性能和高通设备展开连续技术讨论。", "core_object": "HyperOS/MIUI 漏洞解锁与高通 EL2 虚拟化讨论", "evidence_count": 9, "boundary_count": 2, "audit_risk_count": 2, "source_candidate_ids": ["source_candidate_1f30a5ee8b", "source_candidate_a82b57166e", "source_candidate_da36d36d84"], "has_candidate_package": true, "has_evidence_package": true, "evidence_package": {"direct_message_uid_count": 8, "relation_edge_id_count": 4, "tool_observation_id_count": 2, "direct_evidence_count": 9, "relation_edge_count": 4, "tool_observation_count": 2, "missing_message_uid_count": 0}}, {"result_id": "topic_3", "rank": 3, "role": "boundary", "result_kind": "other", "label": "图片相关短评边界，不能独立成立为吃史对象", "confidence": "中等", "summary": "“今日高招”前后夹着多张图片和短反应，但当前文本没有图片内容，也未能取得回复链补证，因此不能确认它具体指向什么对象。", "core_object": "未能确认内容的图片与短评", "evidence_count": 4, "boundary_count": 2, "audit_risk_count": 2, "source_candidate_ids": ["source_candidate_7a3983d827"], "has_candidate_package": true, "has_evidence_package": true, "evidence_package": {"direct_message_uid_count": 4, "relation_edge_id_count": 0, "tool_observation_id_count": 0, "direct_evidence_count": 4, "relation_edge_count": 0, "tool_observation_count": 0, "missing_message_uid_count": 0}}]}`
- relation_counts: `{"nodes": 11, "confirmed_edges": 7, "boundary_edges": 3, "rejected_edges": 2, "open_questions": 3}`
- contract_status: `pass`
- contract_issues: `[]`
- evidence_acquisition: `{"tool_calls_made": ["查询 msg_adcea9705a8ba881 的转发结构，用于确认霍金相关转发的可见边界", "查询 msg_7d244b8d07de0eeb 的转发结构，用于确认技术讨论转发的可见边界", "尝试查询 msg_a406e382be7ba3ef 的回复指向，但本轮补证次数已用尽，未取得可用结果"], "why_enough": "本轮输入没有消息省略，核心文字证据已完整保留。前半段有明确转发锚点和多条围绕霍金、AI、克林顿的接续文字，足以判断主要吃史对象可能成立；后半段有明确技术转发和连续技术解释，足以判断为独立背景话题而非主要吃史。补证结果没有提供更多内部内容，但确认了两个转发锚点的结构边界，因此当前可以给出保守结论并明确未展开图片、回复链和转发内部内容的限制。", "remaining_limits": ["无法直接读取当前包中图片的实际画面内容，只能引用图片资源状态和周边文字。", "嵌套转发内部未完整展开，不能验证外部事实或转发内未显示的聊天细节。", "“今日高招”的回复链未取得可用结果，因此只能作为边界对象记录。", "所有技术真实性判断仅限群聊原文中的说法，未做外部验证。"]}`
- tool_names: `["fetch_forward_tree", "fetch_forward_tree"]`
- model_error: `{}`
- internal_leak_terms: `[]`
