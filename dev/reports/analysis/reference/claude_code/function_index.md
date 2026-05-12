# Claude Code Function Index

## Context assembly

- `getUserContext()`
  - file: `src/context.ts`
  - role: builds and memoizes user-facing persistent context such as `CLAUDE.md`

- `getSystemContext()`
  - file: `src/context.ts`
  - role: builds and memoizes system-side context such as git snapshot

- `fetchSystemPromptParts(...)`
  - file: `src/utils/queryContext.ts`
  - role: canonical cache-safe prefix assembly

- `buildSideQuestionFallbackParams(...)`
  - file: `src/utils/queryContext.ts`
  - role: reconstructs the same cache-safe prefix for alternate query flows

- `analyzeContext(...)`
  - file: `src/utils/contextAnalysis.ts`
  - role: token-cost accounting by source class

## Compaction

- `stripImagesFromMessages(...)`
  - file: `src/services/compact/compact.ts`
  - role: remove expensive image/document payloads before compaction

- `stripReinjectedAttachments(...)`
  - file: `src/services/compact/compact.ts`
  - role: remove attachment classes that will be reintroduced later

- `truncateHeadForPTLRetry(...)`
  - file: `src/services/compact/compact.ts`
  - role: last-resort head truncation when compaction itself hits prompt-too-long

- `buildPostCompactMessages(...)`
  - file: `src/services/compact/compact.ts`
  - role: reconstruct post-compact transcript from boundary, summary, kept suffix, attachments

- `compactConversation(...)`
  - file: `src/services/compact/compact.ts`
  - role: full compaction pipeline over a transcript

- `getEffectiveContextWindowSize(...)`
  - file: `src/services/compact/autoCompact.ts`
  - role: reserve output budget before computing available input budget

- `getAutoCompactThreshold(...)`
  - file: `src/services/compact/autoCompact.ts`
  - role: derive compaction trigger from effective window

- `calculateTokenWarningState(...)`
  - file: `src/services/compact/autoCompact.ts`
  - role: warning/error/compact/blocking thresholds

- `shouldAutoCompact(...)`
  - file: `src/services/compact/autoCompact.ts`
  - role: decide whether proactive compaction should fire

- `autoCompactIfNeeded(...)`
  - file: `src/services/compact/autoCompact.ts`
  - role: run compaction flow with guards and failure tracking

## Session memory

- `trySessionMemoryCompaction(...)`
  - file: `src/services/compact/sessionMemoryCompact.ts`
  - role: reuse session memory before legacy compaction

- `waitForSessionMemoryExtraction(...)`
  - file: `src/services/SessionMemory/sessionMemoryUtils.ts`
  - role: bounded wait for in-progress memory extraction

- `startSessionMemoryExtraction(...)`
  - file: `src/services/SessionMemory/sessionMemory.ts`
  - role: launch background memory extraction

## Planning and coordination

- `call(...)` in `commands/plan/plan.tsx`
  - role: thin command wrapper for plan-mode transition and plan display/edit

- `getCoordinatorUserContext(...)`
  - file: `src/coordinator/coordinatorMode.ts`
  - role: inject worker-capability context for coordinator sessions

- `getCoordinatorSystemPrompt()`
  - file: `src/coordinator/coordinatorMode.ts`
  - role: define synthesis-oriented coordinator behavior

- `isCoordinatorMode()`
  - file: `src/coordinator/coordinatorMode.ts`
  - role: runtime mode check

- `matchSessionMode(...)`
  - file: `src/coordinator/coordinatorMode.ts`
  - role: align resumed session mode with environment/runtime state

## Permissions and safety

- `createPermissionRequestMessage(...)`
  - file: `src/utils/permissions/permissions.ts`
  - role: human-facing explanation for permission asks

- `getAllowRules(...)`, `getDenyRules(...)`, `getAskRules(...)`
  - file: `src/utils/permissions/permissions.ts`
  - role: normalize rules into decision inputs

- `prepareContextForPlanMode(...)`
  - file: `src/utils/permissions/permissionSetup.ts`
  - role: transform tool-permission context for plan mode

- `stripDangerousRulesForAutoMode(...)`
  - file: `src/utils/permissions/permissionSetup.ts`
  - role: remove rules that would make auto mode unsafe

## Subagents

- `resolveTeammateModel(...)`
  - file: `src/tools/shared/spawnMultiAgent.ts`
  - role: inherit or select worker model

- `buildInheritedCliFlags(...)`
  - file: `src/tools/shared/spawnMultiAgent.ts`
  - role: propagate mode/settings into subagents

## Why This Index Exists

This file is meant to accelerate later reading and migration work.

It is not a full API catalog.
It highlights functions that express:

- architecture
- context policy
- compaction policy
- orchestration policy
- safety policy
