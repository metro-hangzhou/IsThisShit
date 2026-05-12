# CodeLayout_AGENTs.md

> Last updated: 2026-05-04
> Scope: repository file layout, module splitting, file naming, and AI/human maintainability rules.

## Purpose

This handbook turns the project-level "多文件少代码行数" rule into an enforceable engineering default.

It exists because agentic coding degrades quickly when large files become mixed-purpose buckets. Files must be easy for both humans and agents to locate, read, edit, test, and hand off.

## Default Rule

Prefer focused modules over large mixed files.

Every new or substantially refactored program file must follow these rules:

- The file name must make the file's responsibility understandable without opening it.
- The file must begin with a concise module/file comment explaining:
  - what the file owns
  - what it does not own
  - the key inputs/outputs or public integration surface
- A program file should stay under `800` lines when practical.
- A program file must not exceed `1000` lines unless the exception is documented near the file or in the relevant subsystem TODO/report.
- New functionality must not be added to an already oversized mixed-purpose file when a focused module can be created instead.

## Naming Guidance

Use names that describe the domain behavior, not vague implementation shape.

Good examples:

- `final_report_view.py`
- `session_event_projection.py`
- `source_packet_budget.py`
- `GroupInsightsPanel.vue`
- `relationGraphViewModel.ts`

Avoid:

- `utils.py` for domain behavior
- `helpers.ts` for UI state
- `misc.py`
- `new_logic.py`
- adding unrelated code to `service.py` / `Page.vue` / `Block.vue` because it is convenient

## Split Boundaries

Split by responsibility, not by arbitrary line count.

Preferred boundaries:

- public contract / schema constants
- runtime orchestration
- event projection
- view-model construction
- UI rendering components
- test fixtures and factories
- validation and normalization
- storage / persistence

Do not split so finely that one behavior requires opening ten files. A file should be small enough to understand, but large enough to own a coherent idea.

## Agentic Coding Rationale

The local reference note at `D:\360极速浏览器X下载\chatgpt_personal_backup_selected_2026-05-03\代码文件组织方式_cb7fd8b321a3.json` reinforces the same direction:

- For medium or large projects, modular files improve maintainability, parallel work, review, and debugging.
- Agentic coding is especially sensitive to mixed-purpose large files because agents lose the local purpose boundary and start adding unrelated behavior to convenient buckets.
- The goal is not "many tiny files"; the goal is single-responsibility modules with clear names, stable interfaces, and enough cohesion that a future human or agent can edit one concern without re-reading the whole project.
- File splitting must be paired with tests and stable public entrypoints; otherwise it creates navigation overhead without improving safety.

## Current Refactor Policy

The QQ exporter family is temporarily excluded from broad layout refactors because its regression surface is large:

- `src/qq_data_core`
- `src/qq_data_integrations/napcat`
- `src/qq_data_cli`
- `NapCat/`
- exporter-heavy tests

The active refactor target is the analysis and observer stack:

- `src/qq_data_analysis`
- `apps/review-editor/src`
- ORCH observer/session projection
- ORCH group insights / shi composition
- review-editor LLM Sessions UI

## Review Checklist

Before considering a refactor complete:

- No newly touched program file exceeds `1000` lines without an explicit recorded exception.
- New files have a top comment/docstring.
- File names match responsibilities.
- External imports still use stable public entrypoints where possible.
- Tests cover behavior, not the old file layout.
- Raw/internal fields do not leak into user-facing ORCH observer UI.
