# Claude Code File Index

This is a functional file index for the local `claude-code/` source snapshot.

## Core lifecycle

- `claude-code/src/QueryEngine.ts`
  - main orchestration spine for query lifecycle, tool loop, compaction integration, persistence

## Context assembly

- `claude-code/src/context.ts`
  - memoized `userContext` and `systemContext`
- `claude-code/src/utils/queryContext.ts`
  - cache-safe prompt prefix assembly and fallback parameter reconstruction
- `claude-code/src/utils/contextAnalysis.ts`
  - token accounting and duplicate/waste analysis

## Compaction

- `claude-code/src/services/compact/compact.ts`
  - main compaction engine
- `claude-code/src/services/compact/autoCompact.ts`
  - threshold logic, effective window, circuit breaker
- `claude-code/src/services/compact/prompt.ts`
  - prompt template and output contract for compaction
- `claude-code/src/services/compact/sessionMemoryCompact.ts`
  - reuse session memory before legacy compaction
- `claude-code/src/services/compact/microCompact.ts`
  - smaller-scale compaction/cleanup path
- `claude-code/src/services/compact/grouping.ts`
  - API-round grouping used for compaction logic
- `claude-code/src/services/compact/postCompactCleanup.ts`
  - post-compact cleanup and rehydration support

## Session memory

- `claude-code/src/services/SessionMemory/sessionMemory.ts`
  - background extraction and memory update service
- `claude-code/src/services/SessionMemory/sessionMemoryUtils.ts`
  - thresholds, waiting logic, summarized-boundary tracking
- `claude-code/src/services/SessionMemory/prompts.ts`
  - prompt text for memory extraction

## Planning and modes

- `claude-code/src/commands/plan/plan.tsx`
  - plan-mode command
- `claude-code/src/commands/plan/index.ts`
  - command entry surface
- `claude-code/src/utils/planModeV2.ts`
  - plan-mode policy and experimental tuning
- `claude-code/src/coordinator/coordinatorMode.ts`
  - coordinator-mode matching, user context, system prompt

## Permissions and safety

- `claude-code/src/utils/permissions/permissions.ts`
  - central permission decision engine
- `claude-code/src/utils/permissions/permissionSetup.ts`
  - mode setup and dangerous-rule stripping
- `claude-code/src/utils/permissions/filesystem.ts`
  - filesystem safety, protected paths, normalization
- `claude-code/src/utils/permissions/pathValidation.ts`
  - path validation details and dangerous path handling
- `claude-code/src/utils/permissions/PermissionMode.ts`
  - mode definitions
- `claude-code/src/utils/permissions/PermissionRule.ts`
  - rule model
- `claude-code/src/utils/permissions/permissionsLoader.ts`
  - persisted rule loading
- `claude-code/src/utils/permissions/classifierDecision.ts`
  - classifier-based approval logic
- `claude-code/src/utils/permissions/autoModeState.ts`
  - auto-mode state management
- `claude-code/src/utils/permissions/permissionExplainer.ts`
  - user-facing explanations

## Subagents and teammate orchestration

- `claude-code/src/tools/shared/spawnMultiAgent.ts`
  - shared subagent/teammate spawn infrastructure

## Related docs-facing commands

- `claude-code/src/commands/context/context.tsx`
  - interactive context visualization
- `claude-code/src/commands/context/context-noninteractive.ts`
  - noninteractive context inspection

## Notes

This file index is intentionally selective.

It only lists files that are materially relevant to:

- context management
- compaction
- planning/execution separation
- permissions/safety
- subagent orchestration
- migration into our analyzer redesign
