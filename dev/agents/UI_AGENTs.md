# UI_AGENTs.md

> Last updated: 2026-04-01  
> Scope: human-computer interaction design, UI visual design, layout density, visual hierarchy, preview-driven iteration, and GUI delivery for repository-local tools.

## Purpose

This handbook defines a dedicated UI agent workflow for repository work that involves:

- interaction design
- layout restructuring
- information density tuning
- visual hierarchy
- UI readability and affordance design
- visual fidelity against reference products
- preview-first iteration before or alongside implementation

It exists because GUI work in this repository should not be treated as:

- random CSS tweaking
- isolated "make it prettier" requests
- purely subjective visual taste
- implementation-only frontend work without a design loop

The UI agent exists to make interface work:

- evidence-based
- preview-driven
- iteration-friendly
- reviewer-auditable
- compatible with the common-track workflow

## When To Use This Handbook

Use this handbook when the task involves any of the following:

- review-editor UI redesign
- QQ-like visual fidelity work
- bottom composer / right drawer / forward window / chat surface re-layout
- readability and density problems
- "looks wrong", "feels inefficient", "too empty", "too dense", "too big", "too small"
- reference-image-driven design matching
- rapid preview generation for human review
- GUI work where visual verification matters as much as code correctness

Do not use this handbook for:

- NapCat protocol fidelity
- exporter schema design
- backend-only bugfixes
- pure data/contract work with no user-facing interface impact

## Core Principles

### 1. Optimize for interaction efficiency, not raw compactness

Higher information density does **not** mean:

- smaller fonts
- tighter everything
- compressing all controls into one corner

Higher information density means:

- fewer wasted regions
- clearer task grouping
- less visual travel for common actions
- readable text at normal desktop distance
- stronger prioritization of the currently important information

### 2. Structure first, styling second

If a UI feels wrong, assume the first root cause is:

- grouping
- hierarchy
- screen real-estate allocation
- action placement

Only after that should you spend energy on:

- color
- border radius
- shadows
- icon style

### 3. Never claim UI work is finished without a visual validation loop

A UI change is not complete just because:

- the code compiles
- the layout technically renders
- tests pass

Completion requires:

- preview inspection
- structured critique
- at least one self-review pass against the stated reference or target

Mandatory self-review gate:

- Do not hand UI work to the user before the agent has inspected the rendered result itself.
- For data-driven UI, first confirm the expected data exists in the current artifact/API response, then confirm the component actually renders that data.
- Use at least one of these checks before handoff: local rendered text inspection, component mount test that asserts the visible text/class, browser/Tauri screenshot, or a Playwright-style DOM capture.
- If the UI depends on a fresh session or fresh backend artifact, state whether the current visible session is old data or newly generated data.
- Do not rely on the user screenshot as the first validation pass when the agent can read the rendered DOM, run the component test, or capture the app itself.

### 4. Readability outranks theoretical density

Avoid the failure mode where:

- the UI becomes smaller
- but still wastes space structurally
- while text becomes harder to read

That is negative optimization.

### 5. Human review is part of the design loop

The UI agent may iterate autonomously, but must preserve an explicit handoff point for:

- user screenshot feedback
- manual approval
- targeted correction requests

## Truth Source Priority

For UI work, the truth-source order is:

1. explicit user goals
2. user-provided screenshots or reference images
3. current running UI state
4. current source code in the relevant frontend files
5. product/platform constraints documented in repository AGENT docs
6. preview artifacts generated during the current UI round

Important rule:

- reference screenshots outrank vague memory
- current code outranks assumptions about what "must already be implemented"
- visual evidence outranks verbal optimism

## Required Read Order

Before major UI work or UI-focused subagent dispatch, read:

1. `AGENTS.md`
2. `dev/agents/major_AGENTs.md`
3. `dev/agents/CodeStrict_AGENTs.md`
4. `dev/agents/subagents/CONTRACT.md`
5. `dev/agents/subagents/SHARED_CONTEXT.md`
6. this file
7. the relevant program handbook under `dev/agents/programs/`
8. the relevant current source files under `apps/`
9. any user-provided screenshots for the current round

If the task explicitly references QQ or another product:

- treat the screenshots as the primary visual comparison source
- do not rely on memory of that product

## UI-Specific Common-Track Workflow

UI work must use the same common-track discipline as other major repository work.

### Mandatory loop

1. `reviewer` critique current UI
2. `explorer` maps concrete layout/interaction causes in source
3. `preview` lane generates one or more visual candidate directions
4. `worker` lane implements the selected structural direction
5. `reviewer` re-checks the result
6. repeat until only non-blocking polish remains

The reviewer is **not** a one-time gate.

## UI Agent Roles

### 1. Strict UI Reviewer

Purpose:

- challenge hierarchy
- identify wasted space
- identify weak readability
- identify inefficient action placement
- reject "smaller but still bad" pseudo-fixes

Questions:

- what is the user trying to do in the next 3 seconds
- what information must be visible without searching
- what region is wasting area without carrying interaction weight
- where is text readable vs technically present but unusable

Output shape:

- `blocking findings`
- `non-blocking visual issues`
- `layout root causes`

### 2. Interaction Architect

Purpose:

- decide where actions belong
- decide what must stay visible
- decide which controls should become popovers, overlays, drawers, or inline chips

Questions:

- what are the most frequent actions
- which actions deserve first-class visibility
- which inputs should be collapsed by default
- which content belongs in sidebars vs the bottom input area

### 3. Visual Designer

Purpose:

- generate or refine visual direction
- translate structure into usable composition
- ensure spacing, weight, rhythm, and contrast are coherent

Questions:

- does the interface scan cleanly
- is the visual hierarchy obvious
- are related controls visually grouped
- does the screen feel like one product rather than stitched panels

### 4. UI Worker

Purpose:

- implement the agreed design in code
- preserve behavior while changing structure/visuals
- update tests when structure changes invalidate old selectors

### 5. UI Validator

Purpose:

- compare the result against screenshots and task goals
- check interactive affordances
- check layout stability across the likely desktop size range

## Preview-Driven Workflow

When the task benefits from visual exploration before implementation, the UI agent should use a preview lane.

### Allowed preview methods

1. code-native preview
   - modify the real frontend and inspect screenshots
2. synthetic mock preview
   - use image generation to produce rough UI directions
3. design reference transformation
   - if reference screenshots exist, use them as layout comparison anchors

### Preferred tool/skill routing

When available in the current Codex environment:

- use `frontend-skill` for actual frontend implementation quality
- use `imagegen` when exploring UI visual directions or generating rough mock previews
- use `figma` if the task is Figma-based

### Preview loop

For each UI round:

1. define the interaction problem precisely
2. define the target visual/interaction outcome
3. create one or more preview candidates
4. critique them structurally
5. choose one direction
6. implement the direction
7. inspect the result again visually

## Artifact Contract

For a UI-focused round, keep artifacts under the active program round directory.

Minimum recommended artifacts:

- `ui_review_input.md`
- `ui_findings.md`
- `ui_todos.md`
- `ui_preview_plan.md`
- `ui_preview_feedback.md`
- `ui_resolution.md`

If image/mock preview generation is used, also keep:

- `ui_preview_round_<n>.md`
- `ui_preview_round_<n>_notes.json`
- preview image files or paths recorded in the round ledger

## Review Questions For UI Work

Reviewer questions should include categories such as:

- `information_architecture`
- `aesthetic_quality`
- `decision_quality`
- `latency_waste_risk`
- `goal_fidelity`
- `first_principles_fidelity`
- `main_agent_scope_integrity`
- `subagent_coverage`

Useful UI-specific reviewer prompts:

- what is visually occupying space without carrying proportional value
- what action takes too many eye movements or cursor movements
- what should be directly visible but is hidden
- what is visible but should be collapsed
- what is readable in code but unreadable to a human
- what is styled but still structurally wrong

## Hard Rules For UI Delegation

When dispatching UI subagents:

- never send vague prompts like `make it better`
- always include:
  - the current problem
  - the target interaction goal
  - the relevant source files
  - the visual reference source
  - the explicit role of the subagent
- reviewer subagents should critique, not implement
- worker subagents should implement a bounded slice
- preview subagents should generate alternatives, not generic moodboards

## Minimum Prompt Contract For UI Subagents

Each UI subagent prompt should specify:

1. role
2. scope
3. required files to inspect
4. visual references to honor
5. what counts as success
6. what not to do

Example:

- role: strict UI reviewer
- scope: bottom composer only
- files: `ComposerDock.vue`, `App.vue`
- reference: provided QQ screenshots
- success: identify exact layout root causes and concrete structural corrections
- forbidden: cosmetic-only critique without structure

## UI Completion Criteria

A UI round is not complete until:

- the current dominant blocker is resolved in code
- the updated UI is visually re-checked
- the reviewer no longer has blocking objections
- the latest result is reflected in the round TODO/resolution artifacts

## Next-Stage Guidance

Once a UI surface is stable enough:

- stop doing random fidelity tweaking
- move to:
  - workflow simplification
  - interaction throughput
  - state clarity
  - trust and recovery messaging

That is the point where the UI stops being "styled" and becomes genuinely usable.
