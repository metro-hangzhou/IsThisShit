# Windows Terminal Compatibility TODOs

Spec baseline: 2026-03-15

This file tracks CLI rendering and interaction issues that appear on some Windows terminal hosts, especially older Win10 `cmd.exe` / `powershell.exe` environments whose behavior differs from the maintainer's Win11 setup.

This is a product issue, not just a code issue:

- the CLI may be logically correct
- but if the terminal UI looks broken, crowded, or misaligned
- ordinary users will still lose trust and avoid the tool

See also:

- [CodeStrict_AGENTs.md](../agents/CodeStrict_AGENTs.md)
- [TODOs.cli-product-review.md](TODOs.cli-product-review.md)
- [TODOs.production-review.md](TODOs.production-review.md)

## Current Problem Statement

Observed from external tester feedback:

- Win10 terminal rendering can look visually messy or misaligned
- some characters appear offset or occupy unexpected width
- the interaction experience feels worse than on the maintainer's Win11 machine
- the maintainer cannot directly inspect the tester terminal host, font, or console mode today

Current likely causes include a mix of:

- old Windows console host differences
- `prompt_toolkit` full-screen rendering quirks
- wide-character width mismatches
- Unicode/blank-like QQ names
- `Rich` table/panel rendering differences
- terminal font/codepage/ANSI mode differences

## Product Goal

The CLI should degrade gracefully across Windows terminal environments:

- on modern terminals, keep the richer UI
- on risky/older terminals, prefer a simpler but stable compatibility mode
- never make the user feel that the program is visually broken because their terminal is "wrong"

## P0. Evidence And Reproduction Surface

- [ ] Define the minimum tester feedback bundle for terminal-compat reports:
  - Windows version
  - terminal host (`cmd`, `powershell`, Windows Terminal, etc.)
  - screenshot of startup
  - screenshot of `/watch`
  - screenshot of a completion popup if broken
  - current terminal font if known
- [ ] Add a lightweight terminal probe surface or command, for example `/terminal-doctor`, to report:
- [x] Add a lightweight terminal probe surface or command, for example `/terminal-doctor`, to report:
  - TTY or not
  - terminal width/height
  - Windows version where available
  - relevant environment clues
  - ANSI/VT capability hints where detectable
- [ ] Record a checklist of current high-risk rendering features used by the CLI:
  - full-screen `prompt_toolkit` app
  - completion float menu
  - custom scrollbar margin
  - `Rich` tables/panels
  - QR block rendering
  - Unicode placeholder text
  - custom width wrapping via `get_cwidth`

Why:

- we cannot harden what we cannot describe
- tester screenshots alone are useful, but repeatable probes are better

Current note:

- [x] Root REPL now exposes `/terminal-doctor`
- [x] Packaged CLI now exposes `terminal-doctor`
- [x] Current probe output already includes platform, Windows build, terminal host guess, shell, TTY status, encoding, size, ANSI/VT hint, and recommended UI mode

## P0. Compatibility Mode Design

- [x] Define a `compat` UI mode for Windows terminals that are likely to render poorly.
- [x] Decide which features are disabled or simplified in compatibility mode:
  - no full-screen watch
  - no floating completion menu
  - no custom scrollbar
  - simpler header/footer blocks
  - more conservative wrapping
  - reduced Unicode-heavy visuals
- [x] Decide how compatibility mode is selected:
  - auto-detect
  - manual override
  - both
- [x] Define user-visible wording so compatibility mode feels intentional, not degraded:
  - "已切换为兼容显示模式"
  - explain that behavior is deliberate for stability

Why:

- not every Windows terminal can be made to render the same advanced UI reliably
- a smaller stable UI is better than a richer broken one

Current note:

- [x] CLI 兼容模式决策已解耦到 [terminal_compat.py](../../src/qq_data_cli/terminal_compat.py)
- [x] root REPL 与 watch 现在都会消费同一份 `CliUiProfile`
- [x] 兼容模式当前会关闭：
  - full-screen watch
  - floating completion menu
  - custom thumb scrollbar
  - highlight-heavy prompt styling
  - complete-while-typing
- [x] 当前已经同时支持：
  - 自动识别
  - `CLI_UI_MODE=compat|full|auto`
  - CLI 全局 `--ui compat|full|auto`
- [x] root REPL 在自动降级到 compat 时会打印显式说明文案
- [ ] Prove that `compat` mode is not only a mode decision plus notice; it should materially simplify the watch/render surface on risky hosts.

## P1. Windows Host Detection

- [ ] Research how reliably we can distinguish:
  - Win10 classic `conhost`
  - Win10 `powershell.exe`
  - Windows Terminal
  - VS Code integrated terminal
- [ ] Decide which environments should default to `compat` mode.
- [ ] Provide manual overrides, for example:
  - `--ui=full`
  - `--ui=compat`
  - env var override if useful

Why:

- the product should not require users to understand terminal internals just to get a clean UI

## P1. Width And Glyph Safety

- [ ] Audit all visually risky character classes in CLI rendering:
  - CJK
  - near-blank Unicode
  - block characters
  - emoji-like symbols
  - box-drawing characters
- [ ] Review `get_cwidth` assumptions against Windows console behavior.
- [ ] Review whether current manual wrapping logic in watch mode should switch to a safer fallback under `compat`.
- [ ] Prefer ASCII-safe or simpler fallback text where pretty glyphs are not worth the risk.

Why:

- most "misalignment" bugs in cross-terminal UIs come from width assumptions, not business logic

## P1. Rich And Prompt Toolkit Risk Audit

- [ ] Review every `Rich` surface for Windows-terminal sensitivity:
  - tables
  - panels
  - QR rendering
- [ ] Review every `prompt_toolkit` feature that may be too aggressive for Win10 hosts:
  - `full_screen=True`
  - floating completion menu
  - custom margins
  - cursor repositioning assumptions
- [ ] Decide which of these should be disabled in `compat`.

Why:

- advanced terminal features are where most environment-specific breakage hides

## P2. Packaging And Support

- [x] Add a short user-facing note to the share bundle about recommended Windows terminal environments.
- [ ] Recommend Windows Terminal where appropriate without making it mandatory.
- [ ] Document what users should do if the UI looks misaligned:
  - switch terminal host
  - force `compat` mode
  - send screenshots plus `/terminal-doctor`

Why:

- product quality includes recovery guidance, not only internal fixes

Current note:

- [x] Root [start_cli.bat](../../start_cli.bat) now prefers launching in Windows Terminal when:
  - it was double-clicked / launched without extra arguments
  - current host is not already a modern terminal
  - `wt.exe` is available
- [x] Windows Terminal discovery now also checks `%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe` instead of relying only on `where wt`
- [x] `start_cli.bat` now forwards CLI arguments through to `app.py`
- [x] users can disable automatic Windows Terminal handoff with `CLI_AUTO_WT=0`
- [x] [CLI_USAGE.md](../../CLI_USAGE.md) now explains:
  - automatic Windows Terminal preference
  - `CLI_AUTO_WT=0`
  - `python app.py --ui compat`
- [x] add [start_cli_compat.bat](../../start_cli_compat.bat) as a stable one-click fallback for risky Windows hosts
- [x] fix the Windows Terminal handoff quoting bug in [start_cli.bat](../../start_cli.bat) by switching the handoff to an internal helper [start_cli_modern_host.bat](../../start_cli_modern_host.bat)

## Acceptance Criteria

- [ ] On the maintainer Win11 environment, current good rendering remains available.
- [ ] On at least one stricter Windows console environment, the CLI stays visually stable in `compat` mode.
- [ ] Users can tell which UI mode they are in.
- [ ] Terminal-compat bug reports become actionable from screenshots plus one structured probe output.

## Non-Goals For The First Pass

- perfect pixel-equivalent rendering across every Windows terminal host
- keeping every advanced UI feature enabled everywhere
- solving unrelated export fidelity or NapCat transport issues under this TODO
