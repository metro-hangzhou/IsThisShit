Your reading check is accepted.

Now implement the relation graph UI pass.

Task:

Refactor `LlmRelationGraphBlock.vue` so it becomes an audit graph, not a
summary/list card.

Implementation requirements:

1. Header
   - Keep `证据关系图`.
   - Show count summary.
   - If all relations are loose / no relation touches any anchor uid, show an
     explicit audit note such as `当前关系边未连接核心锚点`.

2. Core anchor section
   - Render each anchor as a compact QQ-source node: role, sender, message
     preview.
   - If an anchor has zero connected edges, show:
     `当前核心锚点没有直接关系边，人工复核时应主要看原文和边界说明。`

3. Relation edges
   - Render every visible relation as:
     source QQ node -> relation edge pill/confidence -> target QQ node.
   - Direction must be visually clear.
   - Show `relation.why || relation.summary`.
   - Include source and target sender/message previews.
   - Do not put raw edge ids, raw relation types, or inspect fields in mainline.

4. Anchor-connected vs loose
   - Anchor-connected means source or target `messageUid` is in
     `graph.anchorMessageUids`.
   - Anchor-connected edges should be visually primary.
   - Loose edges must be labeled as `旁支关系` / `未连接核心锚点`.
   - Do not hide loose edges under a generic `其他关系` without showing endpoints.

5. Tests
   - Add/adjust tests so the old bad UI fails:
     - loose relation source and target previews are visible
     - relation label and why are visible
     - loose relations are marked as not connected to core anchor
     - anchor with no connected edges shows an explicit audit note
     - raw relation type / raw edge id do not appear in mainline
   - Existing LLM Session tests must still pass.

Allowed files:

- `apps/review-editor/src/components/LlmRelationGraphBlock.vue`
- `apps/review-editor/src/components/LlmSessionPage.test.ts`
- optionally one small frontend helper under `apps/review-editor/src/lib/`

Do not edit:

- backend Python
- NapCat runtime
- relation graph TypeScript data contract unless absolutely necessary
- unrelated LLM Session UI

Validation:

From `apps/review-editor`, run:

- `npx vue-tsc --noEmit`
- `npx vitest run`

Report:

- exact files changed
- what changed in each file
- test commands and results
- any uncertainty or follow-up needed
