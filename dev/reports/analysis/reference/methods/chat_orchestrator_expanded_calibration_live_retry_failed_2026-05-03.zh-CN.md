# ORCH expanded calibration run

- generated_at: 2026-05-03T01:10:40
- allow_llm_judge: True
- case_count: 4

## Summary

| case | status | stop | messages | context | compact | tools | verdict | confidence | relations | leaks |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| x3c_specific_candidate_002 | completed | completed | 447 | pass_through | available_not_applied | - | 成立，但应判为硬件平台取舍的粗口比喻，不是实际“吃屎”事件 | 高 | c4/b1/r2/q2 | - |
| x3c_specific_candidate_003 | completed | completed | 183 | pass_through | available_not_applied | - | 成立 | 中高 | c8/b1/r3/q3 | - |
| phase2_763_candidate_001 | completed | completed | 24 | pass_through | available_not_applied | - | 不成立 | 中高 | c0/b1/r3/q2 | - |
| small_712_candidate_001 | completed | completed | 15 | pass_through | available_not_applied | fetch_reply_chain | 未成立 | 中高 | c3/b4/r3/q3 | - |

## Case details

### x3c_specific_candidate_002

- tags: large, tool-likely, budget-pass-through
- expected: 447-message X3C case; useful for checking pass-through budget and natural tool-call behavior.
- session_id: `orch_cal_x3c_specific_candidate_002_20260503_010606`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_002`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 447/447 条 QQ 原文；15 名发送者；seed burst=1.00；输入包≈53171/96000 tokens；16 个信息边界。
- source_packet: `{"included_message_count": 447, "omitted_message_count": 0, "estimated_message_packet_tokens": 53171, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.6654}`
- final_review: `{"label": "成立，但应判为硬件平台取舍的粗口比喻，不是实际“吃屎”事件", "confidence": "高", "summary": "本轮窗口中明确出现“屎味巧克力和巧克力味屎”的 shi 锚点，语境是在 Intel/AMD CPU、主板、扩展性、价格、升级路径、稳定性之间争论。它成立为对两边方案各有缺陷的比喻性评价。", "core_object": "Intel/AMD 平台选择中的两难取舍", "evidence_count": 9, "boundary_count": 3, "audit_risk_count": 4}`
- relation_counts: `{"nodes": 6, "confirmed_edges": 4, "boundary_edges": 1, "rejected_edges": 2, "open_questions": 2}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": "本轮没有消息被省略，且 QQ 原文中已经包含直接 shi 锚点、前后连续硬件平台争论、发言人对个人需求的明确说明，以及双方对 AMD/Intel 缺点的文本证据；无需额外补证即可判断对象成立及其边界。", "remaining_limits": ["多张图片资源缺失，不能复核图片里的配置、跑分或截图细节。", "未展开回复链，因此不对每条 @ 消息的精确被回复对象作强断言。"]}`
- tool_names: `[]`
- model_error: `{}`
- internal_leak_terms: `[]`

### x3c_specific_candidate_003

- tags: medium, relation-graph
- expected: Medium X3C case; checks model-adjudicated relation graph stability.
- session_id: `orch_cal_x3c_specific_candidate_003_20260503_010715`
- source: `state\group_analysis_runs_message_first_phase4_specific_case\x3c_group_757773326\run_20260417_210641` / `group_757773326_candidate_003`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 183/183 条 QQ 原文；18 名发送者；seed burst=0.43；输入包≈21648/96000 tokens；8 个信息边界。
- source_packet: `{"included_message_count": 183, "omitted_message_count": 0, "estimated_message_packet_tokens": 21648, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.4191}`
- final_review: `{"label": "成立", "confidence": "中高", "summary": "本轮可以确认存在一个清晰的“搬史/吃史”对象：围绕小米自研芯片、Xring、ARM/台积电依赖、制裁风险、是否算自研等话题，群内有人连续搬出成组的外部化、口号化负面说法。", "core_object": "关于小米自研芯片/Xring是否算自研及其制裁风险的成组负面话术", "evidence_count": 8, "boundary_count": 4, "audit_risk_count": 4}`
- relation_counts: `{"nodes": 10, "confirmed_edges": 8, "boundary_edges": 1, "rejected_edges": 3, "open_questions": 3}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": "本轮没有消息因预算省略，且核心判断所需的直接文本锚点已经完整可见：23:26 连续三条消息清楚列出围绕小米自研芯片/Xring的成组负面话术，前后也有可见文本建立 Xring、ARM、TSMC、制裁和自研语境。因此足以判断“话术对象成立”，同时把事实真伪和图片内容列为边界即可。", "remaining_limits": ["未读取缺失图片内容，不能判断图片中是否有额外来源或反驳。", "未展开所有回复链，个别 @ 回复的精确对象可能仍有不确定性，但不影响核心三条文本的成立。", "聊天中没有给出外部来源，不能验证被搬出话术本身的真假。"]}`
- tool_names: `[]`
- model_error: `{}`
- internal_leak_terms: `[]`

### phase2_763_candidate_001

- tags: negative-or-uncertain, no-core-object
- expected: Known weak/uncertain style sample; ORCH should not force a confident positive verdict.
- session_id: `orch_cal_phase2_763_candidate_001_20260503_010833`
- source: `state\group_analysis_runs_message_first_phase2\amd_guanren_group_763328502\run_20260417_003634` / `group_763328502_candidate_001`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 24/24 条 QQ 原文；4 名发送者；seed burst=0.18；输入包≈2952/96000 tokens。
- source_packet: `{"included_message_count": 24, "omitted_message_count": 0, "estimated_message_packet_tokens": 2952, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.2731}`
- final_review: `{"label": "不成立", "confidence": "中高", "summary": "本轮纳入的 24 条 QQ 原文中，没有出现可识别的“shi”“搬史”“吃史”相关表述，也没有出现可指向具体被搬运/食用/讨论对象的文本或媒体。", "core_object": "未识别到成立的 shi/搬史/吃史对象", "evidence_count": 4, "boundary_count": 3, "audit_risk_count": 3}`
- relation_counts: `{"nodes": 5, "confirmed_edges": 0, "boundary_edges": 1, "rejected_edges": 3, "open_questions": 2}`
- evidence_acquisition: `{"tool_calls_made": [], "why_enough": "本轮输入明确包含 24 条消息且没有预算省略；每条消息均为系统类内容，无回复、转发、媒体或缺失媒体。目标是判断本轮窗口内对象是否成立，而当前完整窗口没有任何可识别对象线索，因此足以作出“不成立”的保守结论。", "remaining_limits": ["结论仅覆盖当前窗口，不覆盖群聊其他时间段。", "若上游用“[system message]”替换了真实聊天文本，则当前材料不足以审查被替换内容，需要重新提供原文。"]}`
- tool_names: `[]`
- model_error: `{}`
- internal_leak_terms: `[]`

### small_712_candidate_001

- tags: small, reply-or-local-context
- expected: Small 712 sample; checks local relation and tool behavior on short windows.
- session_id: `orch_cal_small_712_candidate_001_20260503_010928`
- source: `state\group_analysis_runs_message_first_small_one_fixed\amd_guanren_group_712742342\run_20260417_001344` / `group_712742342_candidate_001`
- status: `completed` / `completed`
- prepared_summary: 输入包纳入 15/15 条 QQ 原文；13 名发送者；seed burst=0.13；输入包≈2100/96000 tokens；2 个信息边界。
- source_packet: `{"included_message_count": 15, "omitted_message_count": 0, "estimated_message_packet_tokens": 2100, "message_packet_budget": 96000, "compact_status": "available_not_applied", "context_status": "pass_through", "context_activation_reason": "below_threshold_raw_messages_retained", "context_pressure_ratio": 0.2664}`
- final_review: `{"label": "未成立", "confidence": "中高", "summary": "本轮 15 条 QQ 原文中，没有出现明确的“shi/史/搬史/吃史”表达，也没有足够证据显示群友在围绕某个对象进行“吃史”式指认或搬运。", "core_object": "未确认的 shi 对象", "evidence_count": 6, "boundary_count": 4, "audit_risk_count": 4}`
- relation_counts: `{"nodes": 9, "confirmed_edges": 3, "boundary_edges": 4, "rejected_edges": 3, "open_questions": 3}`
- evidence_acquisition: `{"tool_calls_made": ["查询 msg_9dec62efe19e5676 的回复链，以确认“这啥”指向的对象；结果没有返回可补充的被引用消息。"], "why_enough": "本轮没有省略 QQ 文本消息；关键文本中没有出现 shi/史/搬史/吃史锚点。已对唯一显式回复链消息进行补查，但仍无法确认被引用对象。现有原文足以作出保守结论：窗口内未成立可确认的 shi 对象；缺失媒体和未解析回复链作为信息边界保留。", "remaining_limits": ["两处图片资源缺失，不能审阅其视觉内容。", "“这啥”的回复链未能补出被引用消息。", "已复制图片的视觉内容未在输入中转写，不能据其画面细节作结论。"]}`
- tool_names: `["fetch_reply_chain"]`
- model_error: `{}`
- internal_leak_terms: `[]`
