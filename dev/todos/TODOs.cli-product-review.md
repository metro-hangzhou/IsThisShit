# CLI Product Review TODOs

Spec baseline: 2026-03-15

This file tracks CLI follow-up work discovered under the expanded CodeStrict lens:

- strict production reviewer
- product manager
- first-time non-developer user
- remote tester support

See also:

- [CodeStrict_AGENTs.md](../agents/CodeStrict_AGENTs.md)
- [TODOs.production-review.md](TODOs.production-review.md)
- [TODOs.cli-ux.md](TODOs.cli-ux.md)
- [TODOs.export-cli.md](TODOs.export-cli.md)

## Review Baseline

The CLI is not considered "good enough" just because:

- commands work on the maintainer machine
- developers can recover from raw errors
- advanced users can infer intent from logs

The CLI should also feel:

- understandable on first use
- forgiving when the user mistypes
- emotionally safe when something goes wrong
- visually clear even with strange QQ names
- diagnosable by remote users without maintainer intuition

## P0. Input Safety And Fear Reduction

- [x] Catch unmatched quotes and malformed `shlex` input in both root REPL and watch-mode command handlers, and convert them into calm recovery hints instead of bubbling parser exceptions.
- [x] Audit every top-level command path for parser exceptions that currently occur before the main `try/except` blocks.
- [x] Replace the most frightening generic error surfaces with recovery-oriented wording:
  - what went wrong
  - whether the program is still usable
  - what to try next
  - where the log/trace is, if relevant

Why:

- current command tokenization uses `shlex.split(...)`
- a single missing quote can currently escape before the normal command error handler
- for ordinary users, this feels like "the program broke because of me"

## P0. Target Identity Must Be Visually Reliable

- [x] Add a shared CLI-facing target-label formatter for:
  - `/friends` and `/groups` tables
  - completion popup display
  - watch header
  - export progress target labels
- [x] Detect blank-like or nearly invisible names and render them with an explicit recognizable label.
- [ ] Make sure visually normalized labels still preserve the real QQ ID and raw display name somewhere cheap to inspect.
- [ ] Review duplicate-name and blank-like-name flows together so the operator can still tell "which blank-like target" was picked when several visually similar rows exist.

Why:

- technically valid QQ nicknames can be visually blank or nearly blank
- correct lookup is not enough if the operator cannot tell who was selected

## P0. Command Outcome Messaging

- [x] Review all current `error: ...` outputs in root REPL and watch mode.
- [ ] Decide which classes should include:
  - log path
  - trace path
  - suggestion to retry
  - suggestion to use `/friends` or `/groups`
  - suggestion to refresh metadata
- [ ] Ensure watch-mode failures use wording that clarifies whether:
  - watch stayed alive
  - only export failed
  - the whole view closed

Why:

- developers tolerate terse raw exception text
- ordinary users interpret terse errors as instability

## P1. Consistency Of Product Semantics

- [x] Resolve the default-format inconsistency:
  - repository spec says JSONL is primary
  - `app.py export-history` defaults to `jsonl`
  - root `/export` parsing currently defaults to `txt`
- [x] Review whether root REPL and packaged CLI should share the same default export format and the same wording.
- [x] Review whether watch export should inherit the same default or remain intentionally human-readable by default.

Why:

- inconsistent defaults feel random to users
- "same export, different surface, different default file type" is product debt

## P1. Target Resolution Policy Review

- [x] Review numeric-ID direct shortcuts in:
  - root REPL
  - packaged `export-history`
- [x] Decide whether numeric ID should:
  - still resolve via metadata first when possible
  - warn when the ID is unknown to current metadata
  - preserve the current raw fallback only after lookup misses
- [ ] Review ambiguous-target flows and make sure the "closest matches" UI remains understandable with blank-like names.

Why:

- current numeric shortcut is convenient but bypasses friendlier metadata-backed identity
- product trust is better when the CLI confirms who it thinks the target is

## P1. Completion And Discovery Behavior

- [x] Stop swallowing target-completion lookup failures silently; emit at least one compact log or operator-visible clue.
- [ ] Review completion behavior for weird Unicode, leading/trailing blanks, and quoted names.
- [ ] Make sure the completion popup can distinguish:
  - no matches
  - metadata not loaded
  - lookup failure
- [ ] Review whether top-6 target completion is enough when duplicate names are common.

Why:

- "no suggestions" currently hides several distinct states
- remote users cannot tell whether they typed the wrong thing or the tool failed

## P1. First-Time User Guidance

- [x] Review `/help` output as product copy, not just syntax dump.
- [x] Add at least one concrete example for:
  - `/watch friend ...`
  - `/export group ...`
  - date interval export
  - `data_count=...`
- [x] Make quote requirements for names with spaces explicit.
- [ ] Review whether the root prompt should surface one short "common actions" hint instead of relying on `/help` alone.

Why:

- current help is dense and developer-shaped
- first-time users benefit more from examples than from option lists

## P1. Remote Tester Supportability

- [x] Batch export errors should include stronger per-target context:
  - resolved chat id when available
  - query text
  - log or trace pointer where relevant
- [ ] Review whether non-watch root REPL failures should print the current CLI log path when the error looks operational rather than syntactic.
- [ ] Ensure packaged paths are never less diagnosable than maintainer paths.
- [ ] Split the highest-frequency failures into product-shaped classes (`login`, `watch`, `export`) and give each a calmer "what to try next" recovery hint instead of falling back to one generic operational error voice.

Why:

- external testers do not know where to look next
- sparse error lines increase support back-and-forth

## P2. Startup And Interaction Cost

- [ ] Review whether root REPL should eagerly run `discover_qq_media_roots()` at startup even when the user only wants `/friends`, `/watch`, or `/status`.
- [ ] Review whether non-TTY/basic-loop mode should announce that interactive completion is unavailable, instead of silently dropping features.
- [ ] Review whether the product should expose a clearer "ready / connected / metadata loaded" state before the user starts typing commands.
- [ ] Review whether startup should surface the current operating assumption explicitly, for example:
  - NapCat-connected or not
  - compatibility mode or full mode
  - metadata freshness
  without dumping developer-only instrumentation.

Why:

- product responsiveness matters to trust even before the first export starts
- hidden mode shifts create confusion

## P2. Watch Product Shape

- [ ] Review whether watch-mode command affordances are discoverable enough from inside the view.
- [ ] Review whether the status/help/footer text feels like developer instrumentation or user guidance.
- [ ] Review whether watch export progress and notices explain:
  - what is happening
  - whether the UI is still interactive
  - where the output went
- [ ] Review whether compatibility mode should materially simplify watch rendering beyond mode messaging, so risky Windows hosts actually see a calmer/safer surface rather than mostly the same behavior under a new label.

Why:

- watch mode is one of the most "product-like" surfaces in the repo
- if it feels fragile, users will avoid it even when it works

## Proven Findings Behind This TODO

- Root REPL currently calls `shlex.split(raw)` before entering its main command `try/except`, so malformed quoted input can escape the friendly command handler.
- Watch-mode command parsing uses the same pattern and deserves the same review.
- CLI target identity is currently correct but not always visually recognizable, especially for blank-like QQ names.
- Root REPL and packaged CLI currently disagree on default export format.
- Completion lookup failures are currently easy to hide from the operator.
