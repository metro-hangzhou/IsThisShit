# LLM Session UI Collaboration Workflow

Date: 2026-04-26

This document is for Claude Code or any UI-focused agent working on
`review-editor` -> `LLM Sessions`.

## Roles

Codex owns:

- product/contract clarity
- backend event semantics
- test strategy
- reviewing diffs for unintended scope changes

Claude Code owns:

- Vue component structure and visual/interaction polish
- PCQQ-style chat rendering reuse
- frontend acceptance checks

Codex is the supervising agent for this project lane. In this lane, Codex is
not a passive reviewer: it owns the product contract, backend semantics,
acceptance gates, and final integration judgment. Claude Code should treat
Codex as the direct technical lead for UI implementation questions.

Claude Code must not invent a new product model. It must implement the
contracts in:

- `dev/llm_session_orch_observer_product_contract.md`
- `dev/llm_session_orch_observer_event_contract.md`
- this workflow document

## Required Reading Check

Before editing, Claude Code must reply with a short reading-comprehension
summary covering:

1. What ORCH Observer is for.
2. What belongs in mainline vs Inspect/Raw.
3. How QQ source messages must be displayed.
4. How functional/debug fields must be grouped.
5. How final review should be shown.
6. What files it intends to edit.

If that summary is materially wrong, stop and ask Codex/user for correction.

Claude Code must explicitly confirm the following latest alignment decisions:

- Mainline is user-friendly and chronological; Inspect/Raw is where raw payloads
  and long fields live.
- QQ source messages are always rendered with PCQQ/forward style when visible.
- `117 功能字段` style dumps are a failure mode, not an acceptable detail view.
- Asset missing is usually info/boundary, not warning.
- Partial JSON stream should become structured UI as fields become parseable;
  raw incomplete JSON stays out of mainline.
- The product must tolerate weaker future models and missing fields without a
  repair call.

If Claude Code skips this reading check or produces a generic answer, Codex
must send a correction prompt before implementation. If this happens repeatedly,
pause and report to the user instead of letting UI drift continue.

## Persistent Claude Code Session Rule

Use one maintained Claude Code session for this project lane whenever possible.
Do not fork a fresh Claude Code session for every UI issue. The goal is to keep
the accumulated ORCH Observer context, prior mistakes, product rationale, and
acceptance criteria in memory.

Current maintained session for this lane:

- `07ecedd6-81cc-4f63-bdc6-d3050bfd9e56`

Use `claude -r 07ecedd6-81cc-4f63-bdc6-d3050bfd9e56 -p <prompt>` and do not add
`--fork-session` unless Codex explicitly decides the old session is unusable.

If a new Claude Code session must be started, it must first read this workflow
document and the two ORCH Observer contracts, then produce the required reading
check before making edits.

## Supervision Loop

After each implementation pass, Claude Code must report:

- exact files changed
- what each file change does
- which acceptance checklist items were exercised
- commands run and their results
- any uncertainty or product-contract mismatch

Codex must review the diff before considering the pass accepted. If Claude Code
is unsure whether a field belongs in mainline or Inspect/Raw, it must ask Codex
instead of guessing.

Claude Code should not self-declare completion based only on typecheck/build.
It must inspect at least one real live session and one full-spectrum mock
session, then state what it saw in those sessions.

## File Boundaries

Frontend UI files usually allowed:

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`
- `apps/review-editor/src/components/ForwardRecordViewer.vue`
- `apps/review-editor/src/lib/*`
- `apps/review-editor/src/types.ts`
- frontend tests under `apps/review-editor/src/**/*.test.ts`

Backend/session contract files require Codex review before large changes:

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/orch/**`
- `tests/test_llm_session_service.py`

Do not edit NapCat runtime files for LLM Session UI work.

## PCQQ Reuse

Do not build a second QQ message viewer from scratch.

Reuse existing Review/forward components and helpers:

- `apps/review-editor/src/components/ForwardRecordViewer.vue`
- `apps/review-editor/src/forwardRecord.ts`
- `ForwardDetail`
- `ForwardMessageEntry`
- `TranscriptSegment`

If a packet contains original QQ messages:

- compact card in timeline
- open full PCQQ-style viewer on click
- preserve sender name/card/avatar when available
- fallback to sender id only when no better display name exists

## UI Acceptance Checklist

Claude Code must validate against a real or mock session before claiming done:

1. The session list still loads.
2. A new running session appears immediately and opens automatically.
3. Streaming model text appears before completion.
4. Partial JSON stream does not show raw JSON in mainline.
5. Prepared input appears as a compact source card.
6. Opening prepared input shows PCQQ-style chat messages with text.
7. Image assets show thumbnails and open a lightbox.
8. Missing assets are compact and not warning-colored by default.
9. Tool calls show tool mark, purpose, and result.
10. Final review shows a human conclusion card first.
11. Inspect/Raw remains available but collapsed.
12. No giant raw field list appears in mainline.
13. Packet cards that show QQ message summaries can also open a PCQQ-style
    viewer with visible message text.
14. Detail reload does not require multi-megabyte semantic timelines; stream
    chunks must not appear as thousands of semantic rows.
15. Relation graph is rendered as an audit graph, not a summary list: source QQ
    node -> relation edge -> target QQ node, with direction, confidence, why,
    and whether the edge is connected to the core anchor.
16. If relation edges exist but none connect to the core anchor, the UI says so
    explicitly instead of hiding them under "other relations".

## Relation Graph UI Work Rule

Do not ask Claude Code to "make a relation graph" without first giving product
context. Claude Code must understand:

- The graph exists so a human can audit ORCH's evidence binding behavior.
- The graph must show concrete source/target QQ message nodes and relation
  edges, not just a list of relation labels.
- The graph must help the human detect whether ORCH has strong direct evidence,
  weak contextual evidence, loose side relations, or no anchor-connected edge.
- Raw edge ids and internal relation type names are Inspect/Raw-only.

Before implementing relation graph UI changes, Claude Code must explain in its
own words:

1. Why ORCH Observer needs the relation graph.
2. What a good relation graph lets the reviewer verify.
3. Why the current "summary/list" version is insufficient.
4. Which data fields map to node/edge/direction/confidence/why.
5. What it will change and which files it will not touch.

If this explanation is generic or wrong, Codex must correct it before allowing
implementation.

## Required Commands

Use the project-local environment.

For Python/backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_llm_session_service.py -q
```

For frontend from `apps/review-editor`:

```powershell
npx vue-tsc --noEmit
npx vitest run
```

Use dev server for local visual checks first. Build Tauri only after the dev
server version is acceptable.

## Handoff Prompt

Use this prompt when delegating the next UI pass:

```text
You are Claude Code working as the UI implementation engineer for review-editor.
Codex is the contract/backend owner and will review your diffs.

Before editing, read these files and reply with a reading-comprehension summary:
- dev/llm_session_orch_observer_product_contract.md
- dev/llm_session_orch_observer_event_contract.md
- dev/llm_session_cc_ui_workflow.md
- apps/review-editor/src/components/LlmSessionPage.vue
- apps/review-editor/src/components/ForwardRecordViewer.vue
- apps/review-editor/src/forwardRecord.ts
- apps/review-editor/src/components/LlmFinalReportBlock.vue
- apps/review-editor/src/types.ts

Your task:
Refactor LLM Sessions UI so the main timeline renders ORCH semantic events and
human-readable final review first. Raw JSON, raw model payloads, and long
functional field dumps must stay collapsed under Inspect/Raw. All QQ original
messages must use the existing PCQQ/ForwardRecordViewer style, not a custom raw
list.

Constraints:
- Do not edit backend/session Python without explicit approval.
- Do not touch NapCat runtime files.
- Do not create a second QQ chat viewer; reuse ForwardRecordViewer/forwardRecord helpers.
- Preserve streaming behavior and session auto-open.
- Do not turn a large chat packet into a single `omitted` payload if it still
  contains QQ messages. Keep capped message rows so ForwardRecordViewer can
  render them.
- After edits, report exact files changed, what each change does, and run
  `npx vue-tsc --noEmit` plus `npx vitest run`.
```
