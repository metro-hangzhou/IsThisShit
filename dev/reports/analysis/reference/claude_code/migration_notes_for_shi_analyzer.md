# Migration Notes For The Shi Analyzer

## Goal

Translate Claude Code reference patterns into a concrete redesign direction for the local `shi_analyzer`.

The user has already identified the core problem:

- the current analyzer remains too `window-first`
- it still overweights `forward` and other carrier/provenance features
- it is not yet a true `message-first` `shi` analyzer

This document focuses on how Claude Code’s architecture should influence that redesign.

## What To Reuse

### 1. Stable context prefix

We should introduce one canonical analyzer prefix builder that assembles:

- stable ontology and rubric
- stable corpus role info
- stable group-profile prior
- stable reviewed-policy recap

This prefix should be cached and reused across worker calls.

Only the message packet and local relation graph should vary heavily.

### 2. Prompt-based structured compact

We should not make RAG the main compact path.

Instead, compact should summarize:

- confirmed `shi` objects
- confirmed relation edges
- unresolved ambiguity
- dropped-noise classes
- stable group-profile updates

This summary should be a structured continuation packet, not a generic semantic search result.

### 3. Execution modes as real runtime regimes

We should stop treating the analyzer as one giant prompt.

Recommended mode split:

- `message_probe_mode`
  - per-message `shi` candidacy and bearingness
- `relation_assembly_mode`
  - bind replies/forwards/@/shared-object continuations into a graph
- `cross_window_aggregation_mode`
  - update group profile and component/object distributions
- `review_scheduling_mode`
  - map analyzed evidence to:
    - positive review
    - boundary review
    - negative audit
- `retro_review_mode`
  - architecture and method critique, no live inference

### 4. Coordinator/worker split

The future analyzer should separate:

- coordinator
  - picks packets
  - manages budgets
  - synthesizes outputs
  - decides when to continue vs respawn workers
- workers
  - message-level `shi` judgments
  - relation extraction
  - uncertainty checks
  - review scheduling

This should reduce the current strong coupling between:

- selection
- interpretation
- review-point generation
- group-level claims

### 5. Evidence trust pipeline

Borrow the permission-pipeline design pattern and apply it to evidence:

1. direct core-bearing message evidence
2. relation-bound supporting evidence
3. weak proximity context
4. carrier/provenance metadata
5. fallback uncertainty

Do not flatten these into one raw confidence signal.

## What Not To Reuse Blindly

### 1. Transcript semantics

Claude Code manages a human/assistant/tool transcript.
We manage a QQ message graph.

So “recent suffix” in our case should mean:

- recent unresolved anchors
- current direct edges
- current object-level ambiguity

not raw recent chronological chat.

### 2. Tool-centric reasoning

Claude Code’s compact and budgets care heavily about tool results and file reads.

Our system instead needs to care about:

- message-level `shi` core
- image/video/text assets
- relation graph edges
- repeated carriers and shells

### 3. Permission implementation details

We should reuse the pipeline pattern, not copy shell/file permission logic verbatim.

## Proposed Message-First Redesign Skeleton

### Layer A. Message-level analyzer

Per message:

- `is_shi_candidate`
- `shi_object_type`
- `shi_core_reason`
- `carrier_type`
- `local_anchor_bearingness`

Output classes should include:

- `core_bearing`
- `carrier_only`
- `social_echo_only`
- `boundary_only`
- `off_target`

### Layer B. Relation graph

Bind only true or high-value relations:

- reply
- @ mention and target uptake
- forward-child / nested-forward
- same-object asset continuation
- lexical/semantic uptake
- clear group reaction chains

Do not treat generic temporal adjacency as strong relation.

### Layer C. Window construction

Windows should be constructed after message-level analysis and relation binding.

They should emerge from:

- connected `shi` objects
- connected consumption fragments

not from general “this part of the chat looks weird”.

### Layer D. Group aggregation

Across windows, aggregate:

- `group_profile_prior`
- `shi_object_distribution`
- `carrier_distribution`
- `interaction_feature_distribution`

### Layer E. Review scheduling

Schedule from analyzed message/object structures, not from surface heuristics.

## Context Budget Proposal

We should explicitly reserve:

- system/rubric budget
- message packet budget
- relation-summary budget
- cross-window recap budget
- output budget

Suggested trimming order:

1. off-target routine chatter
2. weak social echo
3. repeated carrier-only shells
4. older low-value boundary context

Never trim:

- strongest core-bearing anchors
- direct edge-defining evidence

## Why This Matters

This is the central reason the user pushed for first-principles redesign:

- a system that guesses from `forward` form is not a true `shi` analyzer
- a system that reasons from `shi core` and then understands carrier/consumption is

Claude Code gives us reusable context/orchestration patterns that make that redesign more practical under constrained context windows.
