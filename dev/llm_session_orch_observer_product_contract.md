# ORCH Observer Product Contract

Date: 2026-04-26

This document is the product contract for `review-editor` -> `LLM Sessions`.
It exists because the old implementation mixed raw packets, model JSON,
frontend guesses, and review output into one transcript. That made the page
look busy while hiding the actual ORCH behavior.

## Goal

`LLM Sessions` is an ORCH observer/debugger, not just a transcript viewer.
It must let a human answer these questions in one pass:

1. What did the user ask ORCH to do?
2. What QQ source evidence was sent to ORCH/model?
3. What did ORCH decide to do, and in what order?
4. What tools were called, with what purpose and result?
5. What prompt/model packet was sent?
6. What did the model stream back, including structured JSON before it fully closes?
7. What final review result should the human inspect?
8. What raw/debug material exists if the human needs to drill down?

## Alignment Decisions From 2026-04-25/26

These decisions came from the latest human/Codex alignment pass and override
older UI attempts.

- The primary mode is user-friendly by default, with enough audit detail to
  inspect ORCH behavior. This means "human-readable first, Inspect/Raw second",
  not "hide everything".
- Event order is part of the ORCH design surface. The UI may summarize within
  a block, but must not reorder the main timeline into unrelated dashboards.
- The mainline should use friendly Chinese labels. Raw field names are allowed
  only as secondary detail in Inspect/Raw or tiny metadata, never as the main
  reading experience.
- All visible QQ source messages must use PCQQ/forward style. This is a source
  provenance rule, not only a visual preference.
- Tool calls need an explicit tool mark and purpose/result. ORCH decisions need
  an agent/process mark. Model output needs a model mark. QQ source evidence
  needs a QQ/export/source mark.
- Partial JSON streams must become structured previews as soon as fields can be
  parsed. Incomplete raw JSON text must not appear in the mainline.
- Missing historical assets are usually information boundaries, not warnings.
  Promote them only when the model/ORCH says they materially affect conclusion.
- The long-term direction is that ORCH/model emits human-oriented structured
  `review_results[]` directly, with `primary_result_id` selecting the default
  result. Frontend adapters can support legacy `final_review` payloads, but
  should not make arbitrary raw JSON look like a report.
- No automatic repair model call is part of V1. Bad or weak model output must
  degrade gracefully into Inspect/Raw and visible boundary notes.
- Current validation may use GPT-5.5-class models, but the product must tolerate
  cheaper/weaker models after release.

## Primary UX Rule

The main timeline is human-readable.

Do not show raw JSON, Python dict repr, internal field names, or 100-item
field dumps in the main timeline. Raw data belongs under `Inspect` / `Raw`.

The page has two layers:

- Mainline: user-friendly chronological transcript.
- Inspect: local raw payload, semantic event payload, and raw event log.

## Timeline Stages

The main timeline must preserve event order. Do not regroup events in a way
that hides sequencing.

Required stages:

1. User request
2. Prepared input
3. Evidence gaps / boundaries
4. Tool calls and tool results
5. Prompt sent
6. Model stream
7. Final review
8. Warnings / errors

## Source Labels

Every visible block must make source clear:

- User: direct operator request.
- QQ Source: original chat messages from exporter data.
- ORCH: orchestration decisions, evidence boundaries, stage planning.
- Tool: tool call and observation.
- Model: streamed and final model output.
- System: transport/session lifecycle.

Emoji are allowed, but labels must not rely on emoji alone.

Suggested visual marks:

- QQ Source: small `QQ Export` badge or chat-bubble/export icon.
- ORCH: agent/node/network mark.
- Tool: hammer/wrench mark.
- Model: spark/brain mark.
- System: gear/status mark.

## QQ Original Text Rule

Any QQ original chat text shown to humans must use the PCQQ-style renderer
already used in the Review page / forward viewer.

Reason: humans must immediately know "this is source evidence from QQ", not
"this is model-written prose".

Allowed:

- A compact card: "223 messages, 16 senders, 8 assets".
- A PCQQ-style modal/window for full chat message viewing.
- ORCH annotation cards that quote one or two PCQQ snippets.

Not allowed:

- Plain JSON arrays of messages.
- Raw `user_xxx content` lists as the primary display.
- Using message probes as if they were complete original chat records.

## Prepared Input

Prepared input is a compact source card, not a dump.

Default collapsed summary should show:

- chat/window identity
- message count and sender count
- time range
- asset count and missing count
- 1-2 human-readable preview lines

Expanded view should open the PCQQ-style chat viewer.

Prompt packet and prepared input are distinct:

- Prepared input = selected QQ evidence/context.
- Prompt sent = actual model prompt/packet.

Implementation detail:

- The UI may receive a capped preview of a large packet, but it must still
  contain enough message rows for PCQQ-style rendering.
- Do not solve payload size by replacing the whole packet with `omitted`; that
  breaks the source-evidence viewer and makes the compact card misleading.
- If a message itself is very long, truncate that message and mark it as
  truncated. Do not drop the sender/time/message row.

## Functional / Debug Fields

Functional fields are ORCH/model annotations, not source evidence.

They must be translated into human terms. Raw field keys may appear only in
Inspect/Raw.

Examples:

- `local_anchor_bearingness` -> `锚点承载度`
- `missing_media_gap` -> `媒体边界`
- `evidence_gap` -> `证据边界`
- `tool_observation_count` -> `工具观察`

Do not show a 117-field vertical list in the mainline. Group into a few
semantic categories, each with a summary and a small number of representative
items.

## Relation Graph

The relation graph is a core ORCH Observer audit surface. It is not a decorative
summary list.

Purpose:

- Let the human see which QQ source messages ORCH believes are related.
- Let the human verify whether the core anchor is actually connected to useful
  supporting evidence.
- Let the human distinguish strong direct evidence from weak contextual edges.
- Let the human catch ORCH mistakes such as "all edges are loose and none touch
  the core anchor".

The relation graph must answer these questions without opening Raw:

1. What is the core anchor message?
2. Which source message points to which target message?
3. What relationship type connects them?
4. Is the relation direct/strong, contextual/weak, or only a boundary?
5. Why did ORCH create that edge?
6. Does the edge connect to the core anchor, or is it only a loose side relation?

Required mainline presentation:

- Render graph semantics as `source QQ message -> relation edge -> target QQ
  message`, not as a flat list of relation labels.
- Show source and target as compact QQ-message nodes. They do not need the full
  PCQQ forward-window layout, but they must visually read as QQ source evidence
  and must show sender label plus message preview.
- The relation edge must be visually between the two nodes, with relation label,
  confidence/strength, and a short human explanation.
- Anchor-connected edges should be visually primary.
- Loose edges must be explicitly labeled as "未连接核心锚点" / "旁支关系"; do
  not hide them under a generic "其他关系" label.
- If an anchor has no connected edge, show this as an audit finding:
  "当前核心锚点没有直接关系边，主要依赖原文和边界说明复核。"
- Raw edge ids, raw relation type names, and internal message ids belong in
  Inspect/Raw only.

Bad relation graph UI:

- A card that only says "已围绕 1 个锚点整理 5 条关系".
- Repeated rows that only say "同发送者延续" or "邻近上下文".
- A flat list where source/target messages and edge direction are not visible.
- A graph that does not tell the human whether any edge touches the core anchor.

Good relation graph UI:

```text
核心锚点
  user_a: 就感觉很抽象，吹高通的不买高通机器

旁支关系：未连接核心锚点
  user_d: [image:...]  --同发送者延续 / 低-->  user_d: [image:...]
  why: 同一发送者连续发送两个图像壳，但缺少图像内容，只能作为边界。

上下文弱边：需要人工复核
  user_d: [image:...]  --邻近上下文 / 低-->  user_b: vision pro 砸进去不少吧
  why: 相邻上下文只能说明时间邻近，不能单独证明核心对象。
```

## Final Review

Final review has a double layer:

- Default layer: human review card with conclusion, core object, evidence,
  boundaries, and audit risks.
- Inspect layer: raw model answer, full structured payload, and internal
  trace.

The default layer must not show the prompt/instruction as if it were a report
description.

## JSON Streaming

Streaming JSON must be parsed incrementally.

While JSON is incomplete:

- Show parsed fields that are already complete.
- Show currently generating field as a structured placeholder if possible.
- Do not show raw JSON text in the main timeline.

If the completed JSON is invalid:

- Show a degraded structured block.
- Keep raw text under Inspect/Raw.

## Mainline Event Labels

Mainline event labels must describe the user-facing action, not the internal
event or function name.

Examples:

- `fetch_sender_history_slice` -> `补充同发送者上下文`
- `fetch_topic_cluster_slice` -> `补充相关话题证据`
- `fetch_related_assets` -> `检查相关媒体资源`
- `judge.started` -> `模型审阅开始`
- `llm.prompt_built` -> `准备模型审阅指令`
- `llm.response_completed` -> `模型输出完成`

The mainline must not show raw `tool_name`, English internal `why_needed`, or
source keys such as `sender_history:msg_xxx`. Those belong in Raw/Inspect.

Legacy/internal aliases such as `prompt.built`, `loop.tool_observation`, and
`loop.tool_failure` are not product-facing concepts. If they exist in an old
session, the read layer may use them only as compatibility input and must not
render them as separate mainline rows when the canonical event is present.

## Warnings

Severity policy:

- Blocking: session/model/tool failed; user action required.
- Warning: evidence boundary may change conclusion.
- Info: expected limitations or normal missing media.

Asset missing is usually info, not warning. Most historical QQ media can be
missing and still be legitimate; only promote it when the model/ORCH says it
materially affects the conclusion.

## Model Robustness

Development validation currently uses GPT-5.5-class models, but open-source
users may run cheaper/weaker models.

The observer must therefore:

- show model name/provider/tier when available
- tolerate missing semantic fields
- degrade unknown event kinds to Inspect/Raw, not broken main UI
- avoid depending on a repair call in V1

No automatic repair model call is part of V1.

## Detail Payload Budget

`GET /api/review/llm/session/<id>` is a frontend detail endpoint. It must stay
small enough for Tauri/WebView reloads.

Current policy:

- `semanticTimeline` excludes stream chunks.
- stream chunks are retained as a bounded tail for UI continuity.
- large assistant aggregate text is capped in `chatMessages`.
- raw model/event data remains in session files for offline inspection.
- packet previews preserve QQ message rows with per-message caps.

If the frontend needs a full raw export later, add a separate raw/download
endpoint instead of expanding the default detail payload.
