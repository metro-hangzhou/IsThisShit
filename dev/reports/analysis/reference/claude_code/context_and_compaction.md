# Claude Code Context And Compaction

## Why This Topic Matters

The user explicitly pointed out that our future `shi_analyzer` must be:

- message-first
- token-budget aware
- careful about not sending too much or too little context

Claude Code is valuable here because it offers a production example of:

- prompt-based compaction
- stable context prefixing
- layered budget controls
- session memory

## Stable Context Prefix

### `context.ts`

The local source shows two memoized context layers:

- `getUserContext()`
- `getSystemContext()`

These gather:

- CLAUDE.md / memory file content
- current date
- git status
- optional cache-breaker injection

The important pattern is:

- context is cached as a stable prefix
- changes to the system-prompt injection clear both caches immediately

This is a better design than reconstructing the full analytical scaffold on every turn.

### `queryContext.ts`

`fetchSystemPromptParts(...)` centralizes the cache-key prefix pieces:

- default/custom system prompt
- user context
- system context

`buildSideQuestionFallbackParams(...)` rebuilds the same prefix for alternate query flows.

Architecture lesson:

- if a system has multiple query paths, all of them must reconstruct the same stable context prefix
- otherwise prompt cache identity and reasoning continuity drift apart

For us this suggests:

- one canonical analyzer context builder
- not one builder for live analysis and another for side probes/review generation

## Prompt-Based Compaction

### What the local source shows

The compaction path is not retrieval-first.

`src/services/compact/prompt.ts` defines an explicit compaction prompt structure that asks for:

- `<analysis>`
- `<summary>`

The summary is a structured working-state output, not arbitrary semantic retrieval.

### What is stripped before compaction

`compact.ts` strips several payload classes before sending the transcript to the summarizer:

- user images
- user documents
- nested images/documents inside tool results
- reinjected skill-discovery/listing attachments

The system is saying:

- these payloads are expensive
- they are often continuation-poor
- keep their existence, not their full weight

For us, the direct analog is:

- weak image/video shells
- repeated carrier-only forward shells
- routine reaction noise

These should not dominate the compact packet.

## Compaction Preserves A Boundary And A Kept Suffix

`buildPostCompactMessages(...)` does not replace everything with one summary blob.

It returns:

- compact boundary message
- summary messages
- messages to keep
- attachments
- hook results

This is important because it preserves:

- some recency
- some structural continuity
- a clean summary boundary

For our analyzer, the analog should be:

- compact summary of older established evidence
- plus a kept suffix of:
  - current anchor candidates
  - current direct relation edges
  - the most recent unresolved ambiguity

## PTL Retry Strategy

Claude Code also handles a second-order problem:

- compaction itself can exceed prompt limits

When that happens, the runtime truncates oldest API-round groups and retries.

This is not ideal for fidelity, but it is operationally sane:

- do something graceful
- do not dead-end the session

For our analyzer, this means:

- compact should have a fallback trimming ladder
- not just “send giant compact prompt and hope”

## Token Budgeting

### Effective context window

`autoCompact.ts` computes:

- effective window = model context window - reserved summary output budget

Then it sets:

- warning thresholds
- error thresholds
- auto-compact trigger
- manual blocking limit

This is a much better pattern than:

- blindly filling to model max tokens

### What this implies for the message-first analyzer

We should explicitly reserve:

- system/contract budget
- message evidence budget
- relation-summary budget
- cross-window recap budget
- output budget

And budget trimming should happen in a fixed order:

1. off-target weak nearby chatter
2. social-echo-only noise
3. repeated carrier-only evidence
4. older low-value boundary context

Not:

- trimming core-bearing anchors first

## Session Memory

### What session memory does

Claude Code’s session memory is not just another transcript summary.

It is:

- background extracted
- threshold gated
- stored separately
- reused before legacy compaction where possible

Threshold logic in `sessionMemoryUtils.ts` and `sessionMemory.ts` is tied to:

- initial context size
- context growth since last update
- tool call count

### Why this is relevant

For our analyzer, long-horizon memory should store:

- stable `shi` object hypotheses
- verified false-positive patterns
- stable group profile updates
- cross-window recurring motifs

It should not try to store:

- full QQ transcript history

## Context Analysis Instrumentation

`contextAnalysis.ts` gives a practical lesson:

- token cost should be measured by source class

Claude Code tracks:

- human message tokens
- assistant message tokens
- tool request tokens
- tool result tokens
- local command output tokens
- attachments
- duplicate file-read waste

Our future analyzer should track at least:

- tokens spent on direct core-bearing evidence
- tokens spent on carrier-only evidence
- tokens spent on relation-bound supporting context
- tokens spent on weak proximity context
- tokens spent on repeated shells and duplicate wrappers

Without this, “context is too big” remains intuition instead of engineering.

## Migration Guidance

The direct migration lesson is:

- do not send chronological windows as the main analytical unit

Instead, build a compact message packet containing:

- candidate anchors
- direct relation edges
- minimal local context
- stable group-prior recap
- stable cross-window recap

That packet is what should hit the model.
