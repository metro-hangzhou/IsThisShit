You are Claude Code working as the UI implementation engineer for
`review-editor` -> `LLM Sessions`.

Codex is the product/contract/backend owner and will review your diffs.

Do not edit files yet.

First, read these files:

- `dev/llm_session_orch_observer_product_contract.md`
- `dev/llm_session_orch_observer_event_contract.md`
- `dev/llm_session_cc_ui_workflow.md`
- `dev/llm_session_relation_graph_ui_handoff.md`
- `apps/review-editor/src/components/LlmRelationGraphBlock.vue`
- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/types.ts`

Context:

The current relation graph UI is not acceptable. It is only a summary/list card.
It does not let the human audit ORCH's evidence binding behavior because it
does not clearly show source message -> relation edge -> target message,
direction, confidence, why, or whether the edge connects to the core anchor.

Before editing, reply only with a reading-comprehension summary covering:

1. Why ORCH Observer needs a relation graph.
2. Why the current relation summary/list UI fails.
3. How you will map payload fields to graph nodes, edges, direction,
   confidence, and why.
4. How you will distinguish anchor-connected edges from loose side relations.
5. Which files you intend to edit.
6. Which files you will not touch.
7. What acceptance tests you will add or adjust before claiming completion.

Constraints:

- Do not edit backend Python.
- Do not edit NapCat runtime.
- Do not change the relation graph data contract unless Codex explicitly
  approves.
- Do not create a decorative graph. The output must be an audit graph that helps
  a human judge whether ORCH bound evidence correctly.
- Do not start implementation until this reading check is complete.
