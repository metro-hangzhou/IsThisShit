# ORCH Observer Event Contract

Date: 2026-04-26

This document defines the semantic event layer used by `LLM Sessions`.

## Principle

The session log keeps both:

- Raw event: exact backend/orchestrator payload.
- Semantic snapshot: human-readable observer data derived at event time.

Frontend should render semantic snapshots first. It may expose raw payloads
through Inspect/Raw, but must not guess main UI from arbitrary raw JSON.

## Human-Oriented Output Direction

The preferred contract is not "backend emits UI components". The preferred
contract is "ORCH/model emits a human-oriented semantic payload that the
frontend can render with stable components".

Bad current/legacy shape:

```json
{
  "evidence_basis": [
    ["asset_count=1", "direct_visual_surface", "missing_media_penalty"]
  ],
  "bearingness": "social_echo_only",
  "carrier_score": 0
}
```

This shape is compact for machines but poor for the observer. It forces the UI
to guess which keys matter and often creates unreadable rows such as
`117 功能字段`.

Preferred shape:

```json
{
  "review_results": [
    {
      "result_id": "r1",
      "rank": 1,
      "result_kind": "shi",
      "role": "primary",
      "verdict": {
        "label": "弱史 / 可能成立",
        "confidence": "medium",
        "summary": "文本本体能支撑错位史，但缺图和大量 routine topic 降低确定性。"
      },
      "core_object": {
        "label": "吹高通但不买高通机器",
        "why_it_matters": "荒诞点来自立场输出和实际消费选择的错位。"
      },
      "evidence": [
        {
          "title": "核心文本锚点",
          "quote": "就感觉很抽象，吹高通的不买高通机器",
          "source": "qq_message",
          "message_uid": "msg_xxx"
        }
      ],
      "boundaries": [
        {
          "title": "媒体边界",
          "severity": "info",
          "summary": "6 个历史图片资源未本地化，不能当作图像内容证据。"
        }
      ],
      "audit_risks": [
        "优先核对核心文本锚点和群体接球，不要把缺失图片补脑成证据。"
      ]
    },
    {
      "result_id": "r2",
      "rank": 2,
      "result_kind": "background",
      "role": "secondary",
      "verdict": {
        "label": "背景争论",
        "confidence": "medium",
        "summary": "同窗口还有性能争论背景，但不是主审阅对象。"
      },
      "core_object": {
        "label": "性能争论背景"
      },
      "evidence": [
        {
          "source": "qq_message",
          "message_uid": "msg_yyy",
          "quote": "A18 Pro 12瓦的水平"
        }
      ],
      "boundaries": [],
      "audit_risks": []
    }
  ],
  "primary_result_id": "r1",
  "debug": {
    "raw_schema_version": "benshi_master_v1",
    "inspect_only": {}
  }
}
```

Legacy single-result payloads are still readable through adapters:

```json
{
  "final_review": {
    "verdict": {
      "label": "弱史 / 可能成立",
      "confidence": "medium",
      "summary": "文本本体能支撑错位史，但缺图和大量 routine topic 降低确定性。"
    },
    "core_object": {
      "label": "吹高通但不买高通机器",
      "why_it_matters": "荒诞点来自立场输出和实际消费选择的错位。"
    },
    "evidence": [
      {
        "title": "核心文本锚点",
        "quote": "就感觉很抽象，吹高通的不买高通机器",
        "source": "qq_message",
        "message_uid": "msg_xxx"
      }
    ],
    "boundaries": [
      {
        "title": "媒体边界",
        "severity": "info",
        "summary": "6 个历史图片资源未本地化，不能当作图像内容证据。"
      }
    ],
    "audit_guidance": [
      "优先核对核心文本锚点和群体接球，不要把缺失图片补脑成证据。"
    ]
  },
  "debug": {
    "raw_schema_version": "benshi_master_v1",
    "inspect_only": {}
  }
}
```

The frontend should still tolerate unknown future fields. Unknown fields are
not errors; they belong in Inspect/Raw unless they arrive with an explicit
semantic summary.

## Schema

Every event may carry:

```json
{
  "semantic": {
    "schemaVersion": "orch_observer_event_v1",
    "eventId": 12,
    "eventType": "chat_packet.built",
    "createdAtIso": "2026-04-26T12:00:00+08:00",
    "source": "orch",
    "stage": "prepared_input",
    "kind": "prepared_packet",
    "visibility": "main_collapsed",
    "severity": "info",
    "title": "Prepared input",
    "summary": "223 messages, 16 senders, 8 assets, 6 missing.",
    "badges": [
      {"label": "QQ Source", "tone": "source"},
      {"label": "8 assets", "tone": "info"}
    ],
    "items": [
      {
        "label": "Messages",
        "value": "223"
      }
    ],
    "actions": [
      {
        "kind": "open_qq_record",
        "label": "Open PCQQ view",
        "target": "inputPacket"
      }
    ],
    "inspect": {
      "rawEventRef": "event_000012",
      "rawPayloadKeys": ["working_set", "evidence_gap_count"]
    },
    "legacyDerived": false
  }
}
```

## Relation Graph Summary V1

`chat_packet.prepared` and `chat_packet.built` may carry a public relation graph
summary at `payload.relation_graph_summary`. `llm_session_service` exposes the
same object as `semantic.relationGraph` and `jsonPreview.relationGraph`.

This is a public observer contract. It must not be a direct dump of
`message_first_context.relation_edges`.

Shape:

```json
{
  "schemaVersion": "orch_relation_graph_summary_v1",
  "summary": "已围绕 1 个锚点整理 3 条消息关系：回复绑定、同发送者延续。",
  "messageCount": 16,
  "edgeCount": 3,
  "anchorMessageUids": ["msg_anchor"],
  "relationTypes": ["reply", "same_sender_continuation"],
  "groups": [
    {
      "anchorMessageUid": "msg_anchor",
      "anchor": {
        "messageUid": "msg_anchor",
        "senderLabel": "user_a",
        "contentPreview": "就感觉很抽象，吹高通的不买高通机器",
        "roleLabel": "核心线索"
      },
      "title": "核心线索周边关系",
      "summary": "围绕该锚点找到 3 条关系：回复绑定、同发送者延续。",
      "relations": [
        {
          "relationId": "reply:msg_reply->msg_anchor",
          "relationType": "reply",
          "label": "回复绑定",
          "summary": "一条 QQ 原文明确回复另一条消息，关系来源可复核。",
          "confidenceLabel": "高",
          "source": {"messageUid": "msg_reply", "contentPreview": "这也太逆天了"},
          "target": {"messageUid": "msg_anchor", "contentPreview": "就感觉很抽象..."},
          "why": "QQ 回复链把两条消息直接连起来，适合作为强绑定证据。",
          "inspect": {
            "edgeId": "reply:msg_reply->msg_anchor",
            "rawRelationType": "reply"
          }
        }
      ]
    }
  ],
  "looseRelations": [],
  "warnings": []
}
```

Frontend rules:

- Main UI renders `summary`, anchor previews, relation labels, relation reason,
  and compact source/target previews.
- Main UI must make the graph structure visible: source message, relation edge,
  target message, direction, confidence, and why.
- A relation row is not acceptable if it only repeats the relation label without
  showing both endpoints.
- Anchor-connected relations are primary. Loose relations are allowed, but they
  must be labeled as loose / not connected to the core anchor.
- If all relations are loose and the anchor has zero connected edges, the UI must
  explicitly say that the current anchor has no direct relation edge. This is an
  audit signal, not a harmless layout detail.
- Raw edge ids and raw relation types stay under Inspect/Raw only.
- Missing relation graph is not an error; zero relation edges is an `info`
  boundary, not a warning.
- The UI should group by anchor first. It should not show a flat table of raw
  relation rows by default.

The relation graph is a relation-audit component, not a summary-card component.
It should help the reviewer catch whether ORCH's evidence binding is strong,
weak, absent, or off-anchor.

## Enum Values

`source`:

- `user`
- `qq_source`
- `orch`
- `tool`
- `model`
- `system`

`stage`:

- `request`
- `prepared_input`
- `evidence`
- `tool`
- `prompt`
- `model`
- `review_results`
- `session`
- `error`

`visibility`:

- `main_required`: always show in mainline.
- `main_collapsed`: show compactly, expandable.
- `inspect_only`: do not show in mainline by default.
- `raw_only`: only raw event log.

Unknown new events default to `inspect_only` unless backend provides explicit
visibility and a human-readable summary.

`severity`:

- `info`
- `degraded`
- `warning`
- `blocking`

Asset missing defaults to `info`.

## Event Mapping V1

Required mappings:

| raw event | source | stage | visibility | title |
| --- | --- | --- | --- | --- |
| `session.request_created` | `user` | `request` | `main_required` | `Session request` |
| `session.started` | `system` | `session` | `inspect_only` | `Session started` |
| `context.prepared` | `orch` | `prepared_input` | `main_collapsed` | `Context prepared` |
| `chat_packet.prepared` | `orch` | `prepared_input` | `main_collapsed` | `Prepared input` |
| `loop.context_built` | `orch` | `evidence` | `inspect_only` | `Evidence context built` |
| `chat_packet.built` | `orch` | `prepared_input` | `main_collapsed` | `Effective prompt packet` |
| `loop.tool_requests_planned` | `orch` | `tool` | `inspect_only` | `Tool plan` |
| `tool.requested` | `tool` | `tool` | `main_required` | tool name |
| `tool.completed` | `tool` | `tool` | `main_collapsed` | tool source/result |
| `tool.failed` | `tool` | `error` | `main_required` | `Tool failed` |
| `judge.started` | `orch` | `prompt` | `main_collapsed` | `Judge started` |
| `llm.prompt_built` | `model` | `prompt` | `main_collapsed` | `Prompt sent` |
| `session.stream_chunk` | `model` | `model` | handled by stream block | `Model stream` |
| `llm.response_completed` | `model` | `model` | `main_collapsed` | `Model response completed` |
| `orchestrator.completed` | `orch` | `review_results` | `main_collapsed` | `ORCH completed` |
| `session.completed` | `system` | `session` | `inspect_only` | `Session completed` |
| `session.failed` | `system` | `error` | `main_required` | `Session failed` |

Worker boundary note:

- ORCH owns the public observer event stream.
- Mission workers and low-level agents may emit private implementation events,
  but ORCH must translate them through an event boundary before they reach
  `llm_session_service`.
- New ORCH runs must not directly persist worker-private aliases such as
  `prompt.built`, `loop.tool_observation`, or `loop.tool_failure`.
- `tool.completed` / `tool.failed` are the only public tool-result events.
- `llm.prompt_built` is the only public prompt-ready event.
- Readers must keep old `prompt.built`, `loop.tool_observation`, and
  `loop.tool_failure` sessions readable, but human-facing timelines must dedupe
  them when their canonical counterpart is present.
- Prompt compatibility must prefer `llm.prompt_built` whenever it exists in the
  same session. A legacy `prompt.built` that appears earlier in `events.jsonl`
  is still a legacy alias and must not win the main timeline.

Streaming note:

- `session.stream_chunk` is the canonical persisted stream event.
- `llm.stream_chunk` was an older duplicate compatibility event and must not be
  emitted by new code.
- Readers must ignore old persisted `llm.stream_chunk` semantic snapshots when
  building `semanticTimeline`; otherwise one long model response can create
  tens of thousands of useless semantic rows and crash WebView/Tauri.

## Mainline Payload Rules

Semantic `summary` must be short and human-readable.

Do:

```json
{
  "title": "Evidence boundary",
  "summary": "2 image-only messages are missing local media; conclusion should not depend on image content."
}
```

Do not:

```json
{
  "title": "evidence_basis",
  "summary": "[\"asset_count=1\", \"direct_visual_surface\", \"missing_media_penalty\"]"
}
```

## Review Results V2 Shape

ORCH/model output should prefer this model-friendly, multi-result shape:

```json
{
  "review_results": [
    {
      "result_id": "r1",
      "rank": 1,
      "result_kind": "shi",
      "role": "primary",
      "verdict": {
        "label": "可审但存在媒体边界",
        "confidence": "medium",
        "summary": "文本本体和群体接球足够，但缺图壳不能作为主要证据。"
      },
      "core_object": {
        "label": "吹高通但不买高通机器",
        "why_it_matters": "荒诞点来自立场输出和实际消费选择的错位。"
      },
      "evidence": [
        {
          "title": "文本直给",
          "quote": "就感觉很抽象，吹高通的不买高通机器",
          "message_uid": "msg_xxx",
          "role": "core"
        }
      ],
      "boundaries": [
        {
          "title": "媒体边界",
          "severity": "info",
          "summary": "6 个历史图片资源未本地化，不作为主要判断依据。"
        }
      ],
      "audit_risks": [
        "不要把缺图壳当作图像内容证据。"
      ]
    }
  ],
  "primary_result_id": "r1",
  "debug": {
    "raw_schema_version": "benshi_master_v1",
    "inspect_only": {}
  }
}
```

Legacy `compact_payload` remains supported through backend adapters, but new
ORCH/model code should prefer `review_results[]` plus `primary_result_id`.

## 2026-04-26 Implementation Note

Current backend behavior:

- `BenshiMasterLlmAgent` asks the model for native `review_results[]` and
  `primary_result_id`.
- If the model omits them, `BenshiMasterLlmAgent` builds a fallback
  `review_results[]` from judgment, direct evidence, review-surface guidance,
  boundaries, and selected QQ messages.
- `ShiAnalysisMissionWorker` applies a second fallback after ORCH merges trace
  and tool summaries, so every ORCH live session can expose a human-facing
  review result even when legacy judge output is used.
- `LlmSessionPage.vue` treats `semanticTimeline` as the main source of truth.
  When semantic events exist, old packet/prompt/tool/user/system transcript
  entries are suppressed from the mainline; only live assistant/model output is
  kept there. Raw events remain available through the collapsed Inspect log.

Payload-budget behavior:

- Detail responses are UI payloads, not raw archives.
- Full raw events remain in `state/llm_sessions/<session>/events.jsonl`.
- Default detail keeps only the tail of raw event previews and stream chunks.
- `chatMessages` stream text is capped and marked with `textTruncated` when
  needed; full output remains in the persisted event stream/result files.
- `semanticTimeline` excludes stream chunks entirely.
- Chat packet `jsonPreview` must not be replaced by a single `omitted` object
  when it contains QQ messages. Instead, backend must preserve renderable
  message previews with per-message text caps so the UI can still open the
  PCQQ-style viewer.
- Missing historical assets are information boundaries by default, not
  warning-level failures.

## Backward Compatibility

Legacy sessions without embedded semantic snapshots must be adapted at read
time and marked:

```json
{"legacyDerived": true}
```

Frontend can display these, but should keep raw/unknown fields under Inspect.
