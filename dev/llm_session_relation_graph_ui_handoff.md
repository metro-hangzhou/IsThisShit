# LLM Session Relation Graph UI Handoff

Date: 2026-04-30

This handoff is for Claude Code in the maintained review-editor UI lane.

Do not implement before completing the reading check at the bottom.

## Roles

Codex owns product contract, data semantics, backend/session boundaries, and
final acceptance.

Claude Code owns Vue UI implementation and visual/interaction polish inside the
allowed frontend files.

## Why This Feature Exists

`LLM Sessions` is an ORCH Observer. The relation graph is not decorative. It is
the human audit surface for ORCH evidence binding.

The reviewer needs to know:

- Which QQ source message is the core anchor.
- Which QQ source messages ORCH thinks are related.
- Which direction the relation points: source -> relation -> target.
- Whether a relation is strong direct evidence or weak contextual evidence.
- Whether any relation actually connects to the core anchor.
- Whether ORCH is relying on loose side relations that do not support the core
  claim.

If the UI only says "5 条关系：邻近上下文、同发送者延续", it fails. The human still
cannot see what is related to what.

## Current Failure

The current `LlmRelationGraphBlock.vue` behaves like a summary/list card:

- It shows `证据关系图` and a summary.
- It shows the anchor message.
- If the anchor has no connected relations, it prints a generic empty message.
- It hides all loose relations behind `其他关系`.
- Loose rows repeat labels such as `同发送者延续` / `邻近上下文` without a visible
  source node, target node, direction, or anchor connection status.

This is not a usable relation graph. It does not let the human audit ORCH's
behavior.

## Real Payload Example

Latest real session observed:

- session id: `live_f8d706cfb4ef27`
- graph summary: `已围绕 1 个锚点整理 5 条消息关系：邻近上下文, 同发送者延续。`
- anchor: `msg_d25bd8516bebc220`
- anchor text: `就感觉很抽象，吹高通的不买高通机器`
- anchor has `0` connected relations
- all 5 relations are currently in `looseRelations`

Example loose relation:

```json
{
  "relationType": "same_sender_continuation",
  "label": "同发送者延续",
  "confidenceLabel": "低",
  "strength": 0.54,
  "source": {
    "messageUid": "msg_4ef0d30c503346e4",
    "senderLabel": "user_284569ae45",
    "contentPreview": "@LITTLETREE88 o1和9400隔多久",
    "roleLabel": "群体反应"
  },
  "target": {
    "messageUid": "msg_d5e29ccbcba65f66",
    "senderLabel": "user_284569ae45",
    "contentPreview": "@LITTLETREE88 所以o1比9400有断层式差距吗，反正8750甩xelite老远是真",
    "roleLabel": "群体反应"
  },
  "why": "同一发送者前后连续表达相近对象，适合判断是否延续同一立场。"
}
```

This must render as an edge, not as a text row:

```text
旁支关系 · 未连接核心锚点 · 低置信

[QQ node: user_284569ae45]
@LITTLETREE88 o1和9400隔多久
        -- 同发送者延续 / 低 -->
[QQ node: user_284569ae45]
@LITTLETREE88 所以o1比9400有断层式差距吗...

why: 同一发送者前后连续表达相近对象，适合判断是否延续同一立场。
```

## Required UX Model

The relation graph block should be an audit panel with these sections:

1. Header
   - Title: `证据关系图`
   - Compact summary: edge count, anchor count, relation categories.
   - If all edges are loose, explicitly say: `当前关系边未连接核心锚点` or similar.

2. Core anchor
   - Show the anchor as a QQ-source node.
   - Include sender label and content preview.
   - If no edge connects to it, show an audit note:
     `当前核心锚点没有直接关系边，人工复核时应主要看原文和边界说明。`

3. Anchor-connected evidence paths
   - For each anchor-connected relation, render:
     `source node -> edge label/confidence -> target node`.
   - Make direction visually clear.
   - Show `why` in a short secondary line.

4. Loose / side relations
   - Do not hide under a generic `其他关系`.
   - Label them as `旁支关系` / `未连接核心锚点`.
   - Render them with the same source -> edge -> target structure.
   - They can be collapsed after a small visible count, but the first few must
     show concrete endpoints.

5. Inspect/Raw
   - Raw edge ids, raw relation types, message ids, and raw payload stay under
     Inspect/Raw only.

## Visual Direction

Use a compact audit-diagram style, not a huge modal and not a generic card list.

Acceptable structure:

- left/right or vertical two-node lane
- small QQ source node cards
- central relation pill/connector
- confidence badge
- subtle line/arrow indicating direction
- separate tone for direct/strong vs contextual/weak vs loose side relation

Do not use:

- a flat list of labels
- repeated rows that do not show source and target
- raw ids in mainline
- a large blank graph canvas with no readable evidence
- a pure SVG graph that makes Chinese text hard to read

## Data Mapping

Use `LlmRelationGraphSummary` from `apps/review-editor/src/types.ts`.

- `graph.summary`: header summary.
- `graph.edgeCount`: count badge.
- `graph.anchorMessageUids`: anchor identifiers for connection checks.
- `graph.groups[*].anchor`: core anchor node.
- `graph.groups[*].relations`: anchor-connected relation edges.
- `graph.looseRelations`: side relations not grouped under an anchor.
- `relation.source`: source QQ node.
- `relation.target`: target QQ node.
- `relation.label`: human relation label.
- `relation.confidenceLabel` and `relation.strength`: relation strength.
- `relation.why || relation.summary`: human reason.
- `relation.inspect`: Inspect/Raw only.

Connection rule:

- A relation is anchor-connected if source or target `messageUid` is in
  `graph.anchorMessageUids`.
- Otherwise it is a loose / side relation.

## Allowed Files

Likely allowed:

- `apps/review-editor/src/components/LlmRelationGraphBlock.vue`
- `apps/review-editor/src/components/LlmSessionPage.test.ts`
- optionally a small frontend helper under `apps/review-editor/src/lib/`

Do not edit backend Python for this UI pass.
Do not edit NapCat runtime.
Do not change the relation graph data contract unless Codex explicitly approves.

## Required Acceptance Tests

Add/adjust frontend tests so they fail on the current bad UI and pass only when:

- Relation graph renders concrete source and target message previews.
- Relation graph renders relation label and `why`.
- Relation graph marks loose relations as not connected to the core anchor.
- If an anchor has no connected edges, UI says that explicitly.
- Raw relation type / raw edge id do not appear in mainline.
- Existing tests for relation graph and legacy semantic timeline still pass.

## Required Commands

From `apps/review-editor`:

```powershell
npx vue-tsc --noEmit
npx vitest run
```

Do not claim completion without reporting exact files changed and which
acceptance cases were exercised.

## Reading Check Required Before Editing

Before editing, reply with:

1. Why ORCH Observer needs a relation graph.
2. Why the current relation summary/list UI fails.
3. How you will map payload fields to graph nodes, edges, direction,
   confidence, and why.
4. How you will distinguish anchor-connected edges from loose side relations.
5. Which files you intend to edit.
6. Which files you will not touch.

Do not edit until this reading check is complete.
