# Release / Runtime Stability TODOs

Spec baseline: 2026-03-20

This file tracks release-branch (`main` / `runtime`) and local runtime integrity issues that are easy to miss when the main development focus is on exporter/analyzer features.

## Problem Statement

Recent field failures showed that the project has two separate but related stability risks:

1. release branches can regress on small compatibility entrypoints even when core logic is otherwise correct
2. `full-dev` can drift into a locally broken vendored NapCat runtime state even though the branch is not meant to auto-update

## Recorded Incidents

### [2026-03-20][001] CLI update policy must stay branch-specific

- Confirmed policy:
  - only `main/start_cli.bat` should auto-update from remote
  - `full-dev` must not auto-update
  - `runtime` must not auto-update
  - other branches must default to no auto-update
- Risk:
  - shared launcher edits can accidentally re-enable auto-update on local-only branches

### [2026-03-20][002] `full-dev` lost `start_napcat_logged.bat`

- Symptom:
  - local runtime helper batch file disappeared from `full-dev`
- Impact:
  - lower observability during local NapCat startup/debugging
- Guardrail:
  - keep the logged launcher present on `full-dev`

### [2026-03-20][003] Release exporter progress API regression

- Symptom on release lines:
  - `NapCatMediaDownloader` missing `begin_export_download_tracking(...)`
  - later field report also showed missing `settle_export_download_progress(...)`
- Impact:
  - `/export group ...` completion/export path can fail before real export work proceeds
- Required follow-up:
  - keep downloader progress helper API compatibility covered by release-branch regression tests

### [2026-03-20][004] `full-dev` vendored NapCat runtime missing dist artifacts

- Symptom:
  - `/login` failed before WebUI became ready
  - NapCat backend threw:
    - missing `path-to-regexp/dist/index.js`
- Confirmed missing runtime artifacts:
  - `path-to-regexp/dist/index.js`
  - `qs/dist/qs.js`
- Impact:
  - local NapCat runtime could not boot correctly on `full-dev`
- Guardrail:
  - vendored runtime completeness checks should cover required `node_modules/*/dist/*` artifacts

### [2026-03-20][005] Friend machine huge export still hits forward metadata timeout

- Symptom:
  - large group export can spend repeated `12s` timeouts on:
    - `media_resolution_substep substep=forward_context_metadata`
  - plugin route involved:
    - `/plugin/napcat-plugin-qq-data-fast/api`
    - `/hydrate-forward-media`
- Impact:
  - very large exports can look stalled or fail after repeated timeout chains
- Status:
  - still an active investigation/fix lane

### [2026-03-20][006] Large export can crash during final progress settlement

- Symptom:
  - export body already produced progress output
  - final crash:
    - `'NapCatMediaDownloader' object has no attribute 'settle_export_download_progress'`
- Impact:
  - large export can fail at the final materialization/progress-settlement stage even after doing real work
- Guardrail:
  - downloader progress helper methods must be treated as a compatibility contract:
    - `begin_export_download_tracking(...)`
    - `export_download_progress_snapshot(...)`
    - `settle_export_download_progress(...)`

### [2026-03-20][007] Need branch-safe quick login to reduce QR friction

- Symptom:
  - operator flow still falls back to QR too often even when local QQ authorization already exists
- Desired behavior:
  - `/login` should first attempt NapCat quick login through WebUI candidate accounts
  - QR should remain as fallback, not the only path
- Guardrail:
  - quick login must not remove QR fallback
  - quick login support should work without changing the branch auto-update policy

### [2026-03-20][008] `app.py login` and REPL `/login` must stay behavior-compatible

- Symptom:
  - quick login was initially wired in REPL first, while command-line `app.py login` still only did QR flow
- Impact:
  - operator behavior diverges depending on entrypoint
  - troubleshooting gets noisy because REPL and non-REPL screenshots no longer mean the same thing
- Guardrail:
  - `app.py login` and REPL `/login` must share:
    - quick login first
    - QR fallback second
    - same observable status prints where practical

### [2026-03-20][009] Large live export now completes, but still has genuine forward metadata slow spots

- Live validation:
  - `app.py export-history group "蕾米二次元萌萌群" --limit 2000 --format jsonl`
  - completed in about `40.2s`
  - no longer crashed on `settle_export_download_progress(...)`
- Residual signal:
  - one real `forward_context_metadata` timeout still occurred on a deep forward image context
  - final missing breakdown remained dominated by:
    - `qq_not_downloaded_local_placeholder`
- Interpretation:
  - crash regression is fixed
  - repeated sibling timeout amplification is reduced
  - deep forward metadata hydration still needs targeted performance/fidelity follow-up

### [2026-03-20][010] Local account policy for live runtime validation

- Policy:
  - local live runtime tests default to QQ account `3956020260`
  - do not attempt alternate quick-login candidates unless the user explicitly asks
- Why:
  - reduces account confusion on operator machines
  - avoids treating another persisted QQ session as an acceptable test target
  - keeps login/export validation reproducible across turns

### [2026-03-20][011] quick login must be hardened across both startup and WebUI paths

- Symptom:
  - field logs can still show:
    - `没有 -q 指令指定快速登录`
    - then NapCat auto-tries a stale historical account like `1507833383`
- Root-cause shape:
  - NapCat quick login is not one path; it splits into:
    1. startup arg path: `-q <uin>`
    2. WebUI/auto-login path:
       - `NAPCAT_QUICK_ACCOUNT`
       - `WebUiConfig.autoLoginAccount`
       - `SetQuickLoginQQ`
       - `SetQuickLogin`
- Guardrail:
  - when the operator explicitly requests a fixed quick-login account, runtime startup should drive both paths toward the same `uin`
  - the runtime wrapper should emit enough diagnostic context to prove which account it tried to launch with
- Current fix direction:
  - wrapper adds `-q <uin>`
  - wrapper also exports `NAPCAT_QUICK_ACCOUNT=<uin>`
  - login/UI side keeps preferring the explicitly requested `uin` over WebUI default candidates

### [2026-03-20][012] Local test-account override must beat stale `webui.json` auto-login state

- Field finding:
  - local `NapCat/napcat/config/webui.json` can retain stale:
    - `autoLoginAccount = 1507833383`
  - manual launcher runs without explicit `-q` can therefore still drift to the wrong QQ
- Current fix direction:
  - introduce a local-only override file:
    - `state/config/napcat_quick_login_uin.txt`
  - `NapCatSettings.from_env()` should read it when env is absent
  - `start_napcat_logged.bat` should read it too, so manual logged startup and CLI startup use the same pinned account
- Guardrail:
  - keep the local account pin outside tracked runtime config files
  - do not rely on `webui.json autoLoginAccount` as the authoritative local test-account source

### [2026-03-20][013] deep-forward remote URL recovery was wired but effectively dormant

- Field finding:
  - the residual `7 missing_after_napcat` case in:
    - `message_id_raw=7617760641125573795`
  - was not purely a plugin-side mystery
  - Python-side `NapCatMediaDownloader` had:
    - `_prepare_remote_cache_dir()`
    - but did not actually call it before first remote URL media download
- Impact:
  - forward remote URL recovery paths could remain effectively inert
  - especially for deep-forward image bundles that only survived through `hint_url`
- Fix direction:
  - prepare the remote cache dir on first real remote URL use
  - cover both:
    - `_download_remote_media_async(...)`
    - `_download_remote_sticker(...)`
- Validation target:
  - narrow window around `2026-03-16T13:12:57+08:00`
  - full `2000`-message rerun on group `922065597`

## Current Fix / Guardrail Tasks

- [ ] Keep CLI launcher policy explicit in regression review:
  - `main` may auto-update itself
  - `full-dev` / `runtime` may not
- [ ] Keep `start_napcat_logged.bat` present on `full-dev`
- [ ] Add or maintain release regression tests for downloader progress helper methods:
  - `begin_export_download_tracking(...)`
  - `settle_export_download_progress(...)`
- [ ] Add a runtime integrity checklist for vendored NapCat dependencies on `full-dev`
- [x] Investigate and reduce residual `forward_context_metadata` timeout cost on large exports
  - same-sibling timeout amplification is already fixed
  - the remaining `7 missing_after_napcat` case was further reduced by enabling actual forward remote URL recovery
- [x] Distinguish operator-facing “true actionable misses” from placeholder-heavy historical misses in export summary
  - summary now emits:
    - `final_missing_reason`
    - `actionable_missing_reason`
    - `background_missing_reason`
  - retry hints now ignore background-only missing clusters
  - current 2000-message baseline:
    - `missing=129`
    - `actionable_missing_reason=[-]`
    - `background_missing_reason=[qq_expired_after_napcat:5, qq_not_downloaded_local_placeholder:124]`
- [x] Decide whether deep-forward image hydration should get one more low-risk optimization pass
  - implemented low-risk pass by activating the already-designed forward remote URL recovery path
  - targeted forward `message_id_raw=7617760641125573795` now recovers `7/7` images in narrow-window retest
- [ ] Record friend-machine failures into perf/forensics docs when new logs arrive
- [ ] Keep quick-login path covered by regression tests so QR fallback remains intact
- [ ] Keep `app.py login` and REPL `/login` behavior-compatible in regression coverage
- [ ] Keep local live validation scripts/operator notes aligned with the fixed local account `3956020260`
- [ ] Keep local live/export validation matrix aligned with the fixed test targets:
  - `group 922065597` `蕾米二次元萌萌群`
  - `private 1507833383`
- [ ] Re-verify on a fresh NapCat restart that the operator console no longer falls through to stale auto-login account `1507833383` when `3956020260` is explicitly requested
- [ ] Re-verify that `start_napcat_logged.bat` without explicit args now auto-pins `3956020260` via `state/config/napcat_quick_login_uin.txt`
- [x] Guard against ghost logged-in sessions and wrong-account “already logged in” false success
  - `/login` now reports `QQ session mismatch` when current session `uin` differs from requested/pinned quick-login `uin`
  - bootstrap now rejects “logged in” states that do not return usable `QQ session info`
- [x] Align REPL quick-login lookup failure behavior with CLI fallback behavior
  - quick-login candidate lookup errors no longer hard-fail REPL `/login`
  - current fallback path is QR/normal login instead of command abort
- [x] Preserve quick-login injection across `start_napcat_logged.bat` admin relaunch path
  - elevated relaunch now carries the computed quick-login account instead of risking a drift back to stale local defaults
- [x] Route runtime auto-start through the project logged launcher helper instead of directly relying on `launcher-win10.bat`
  - `app.py /login --refresh` now enters the same admin-elevating / quick-login-preserving path as manual logged startup
- [x] Fix `start_napcat_logged.bat` admin relaunch parse-time variable expansion bug
  - the prior batch block effectively executed `Start-Process '' -Verb RunAs`
  - the helper now uses delayed expansion for the elevated wrapper path and no longer drops the FilePath argument
- [x] Reorder placeholder-heavy image missing classification ahead of public-token remote URL retry
  - latest `group 922065597 limit=2000` trace now shows:
    - `public_token_get_image_remote_url cached_error = 0`
    - instead of the prior `124`
  - background image misses now go straight to:
    - `public_token_get_image_classification classified_missing`
- [x] Add operator-facing note when remaining missing are background-only
  - current CLI/export summary now prints:
    - `missing_note: 当前剩余 missing 全是背景缺失（placeholder / expired 类）`
- [x] Guard non-login export flows against wrong-account runtime reuse when a fixed quick-login account is configured
  - `app.py export-history`
  - REPL `/export`
  now both reject:
    - `QQ session mismatch`
  when current online `uin` differs from the pinned/requested account
- [x] Remove hot-loop blocking waits when consuming remote media prefetch futures
  - hot-path prefetch consumption now uses a short peek instead of immediately full-waiting on `future.result(timeout=...)`
  - full waits now happen only in the final asset path that truly needs the remote download result
  - current `group 922065597 limit=2000` baseline improved from:
    - `42.48s`
- [x] Avoid export-cleanup hangs after the JSONL/manifest are already written
  - `cleanup_remote_cache()` now rebuilds prefetch runtime with `wait=False`
  - prevents stale remote-prefetch futures from keeping CLI alive after export work is already done
- [x] Reuse successful forward metadata payloads for sibling assets under the same forward parent
  - metadata-only `/hydrate-forward-media` success is now cached per outer forward bundle/type-role key
  - reduces repeated “load forward tree -> find sibling -> return metadata” work inside one export run
- [x] Prefer forward remote URL recovery before public-token action for matched forward assets
  - current order is:
    - local path
    - forward remote URL
    - public token
  - goal is to reduce needless `get_image/get_file` blocking on deep-forward assets whose remote URL is already good
- [x] Surface history source / partial fallback / forward-structure gap in operator-facing export summaries
  - detailed summary now prints:
    - `history_source`
    - `history_fallback=partial`
    - `forward_detail_count`
    - `forward_structure_unavailable`
  - compact app / REPL output now also includes:
    - `src=...`
    - `history_fallback=...`
    - `fwd_gap=...`
- [x] Split forward-route health from ordinary context-route health
  - `/hydrate-forward-media` unavailability no longer disables ordinary `/hydrate-media`
  - ordinary `/hydrate-media` unavailability no longer disables deep-forward hydration
  - reduces false whole-process downgrade after one route-specific wobble
- [x] Downgrade remote-prefetch async runtime startup failure from fatal constructor error to controlled optimization disable
  - if the async remote prefetch loop does not come up cleanly, exporter construction now continues
  - current behavior keeps:
    - formal export
    - public-token prefetch
  - and only disables:
    - remote media prefetch optimization
- [x] Repair release-line login completion bundle skew
  - `repl.py` already depended on `quick_login_lookup`
  - release `completion.py` was still on the old constructor signature
  - fixed by syncing:
    - `src/qq_data_cli/completion.py`
    - `tests/test_cli_login_completion.py`
- [x] Remove synchronous quick-login candidate lookup from the completion hot path
  - REPL startup now primes quick-login candidates in background
  - completion now returns:
    - pinned local account first
    - cache-backed candidates second
  - avoids the old `1-2s` interactive stall on `/login` and `/login --quick-uin`

## Reviewer-Derived Next Hardening Targets

- [ ] Add runtime/account identity banner before export and after login
  - print:
    - effective `uin/nick/online`
    - pinned `quick_login_uin`
    - launcher / webui endpoint
    - whether runtime was reused or newly started
- [ ] Emit explicit fast-path downgrade note when history source falls from fast plugin to HTTP fallback mid-run
  - avoid operator seeing “suddenly slow” with no explanation
- [ ] Reword `materialize_asset_substep timeout/unavailable` as degraded-substep, not hard failed-export semantics
  - current red `status=failed` line is too easy to over-read as global export failure
- [ ] Split forward-route health from ordinary `/hydrate-media` route health
  - do not let one transient forward-route unavailable event disable all fast context hydration for the whole process
- [ ] Add in-flight bundle coalescing for forward metadata requests
  - current cache helps after success/timeout/error
  - still vulnerable to sibling stampede if multiple equivalent requests enter before the first one settles
- [ ] Reduce or eliminate plugin-side catastrophic target-miss fallback in `/hydrate-forward-media`
  - targeted miss should not recursively hydrate an entire deep/nested forward tree just to say “not found”
- [ ] Memoize plugin-side forward tree expansion by outer forward/resId
  - avoid reloading and rescanning the same bundle for sibling asset lookups
- [ ] Make retry hints explicitly show retryability and asset-type coverage
  - especially distinguish:
    - actionable missing
    - background-only missing
    - asset classes without useful second-pass recovery
    - to `36.914s`
- [x] Reorder eager remote prefetch scheduling behind the cheapest local recovery checks
  - `prepare_for_export(...)` now delays eager request remote prefetch until after:
    - forward-parent skip
    - stale-local recovery
    - hinted-local recovery
    - old placeholder eager-prefetch skip
- [x] Improve operator surfacing for large export runs
  - CLI `export-history` now prints:
    - `export_session`
    - `export_verdict`
  - REPL `/export` now also prints:
    - `export_session`
    - `zero_result_hint`
    - `export_verdict`
  - compact retry hints now include:
    - `kinds=[...]`

## Next Reviewer-Driven Hardening Candidates

- [ ] Add a coarser negative-outcome cache above message-scoped asset resolution
  - current reviewer finding:
    - repeated bad URLs / repeated placeholder assets can still churn through per-message resolution paths even after downloader-level caches help
- [ ] Improve completion/operator surfacing when backend lookups degrade
  - current reviewer finding:
    - friend machines can still perceive “补全没反应” without enough prompt-level explanation of whether completion is stale-cache, endpoint-unavailable, or real lookup failure
- [x] Make quick-login completion candidate sourcing NapCat-first
  - `/login` / `/login --quick-uin` candidates now prefer:
    - NapCat quick-login list
    - current NapCat session login info
  - empty warmup results no longer get cached as fresh
  - startup warmup now gets a short head start before REPL is shown
- [x] Warm NapCat WebUI during REPL startup before exposing the prompt
  - startup now prints:
    - `startup_napcat: ...`
  - REPL tries to get WebUI into a ready state before `Slash REPL ready`
  - reduces first-command friction on `/login`
- [x] Include runtime starter in the quick-login/startup release bundle
  - `quick_login_uin` propagation now must cover:
    - `repl/app`
    - `bootstrap`
    - `runtime`
  - prevents one-layer-deeper signature failures after partial release sync
- [x] Stop `/login` completion from mutating the input buffer while the operator is only navigating the quick-login menu
  - classic Windows console now keeps `/login` buffer text stable during `Tab/Up/Down`
  - selected QQ is only inserted on explicit accept
- [x] Make `start_cli.bat` hand off to the freshly updated script after a successful `main` fast-forward
  - ensures newly pulled launcher/runtime logic can take effect in the same run
- [x] Remove internal launcher-only CLI sentinels from `start_cli.bat` handoff
  - `--post-update-handoff` leaked into `app.py` on a real `main` clone after auto-update
  - launcher now keeps post-update handoff state in environment only
- [x] Stop running post-update launcher labels in the same mutated batch process
  - `git pull`-updated `start_cli.bat` could still emit broken fragment commands such as:
    - `'T_BRANCH.' is not recognized`
  - launcher now re-execs through a new `cmd /c` process and the old process exits immediately
- [x] Add a best-effort NapCat service restart helper for update runs that touch NapCat runtime/launcher paths
  - implemented via:
    - [restart_napcat_service.ps1](../../restart_napcat_service.ps1)
  - current policy is repo-scoped process stop + relaunch through [start_napcat_logged.bat](../../start_napcat_logged.bat)
- [x] Make `/login` default completion QQ-first and option-on-demand
  - when the operator has not explicitly typed `--`, `/login` now only shows QQ number candidates
  - login options are still available once the operator enters an option prefix such as:
    - `--`
    - `--quick-uin`
- [x] Stop classic-console `/login` completion navigation from concatenating multiple QQ numbers into one line
  - compat-mode `Tab/Up/Down` navigation now keeps the input buffer stable and only moves the menu cursor
- [x] Make `/login` quick-login filtering behave like QQ-number input rather than loose substring search
  - numeric input now filters quick-login candidates by QQ-number prefix
  - blank-like quick-login nicknames now render as:
    - `<空白ID>`
- [x] Add light auto-refresh for command/login completion while typing
  - covers:
    - `/l`
    - `/login `
    - `/login 3`
    - `/login --quick-uin`
- [x] Make classic-console completion menus reserve more bottom space
  - compat mode now uses a true column menu instead of `READLINE_LIKE`
  - menu reserve grows with terminal height, so `/login` candidates are less likely to disappear at the bottom edge
- [ ] Surface runtime bootstrap drift more explicitly in CLI export entrypoints
  - when `ensure_endpoint(...)` auto-starts or auto-configures the runtime, `export-history` should print the effective runtime note more prominently
- [ ] Show active runtime session identity even when no fixed `quick_login_uin` is configured
  - current guards reject wrong-account reuse when the pinned account exists
  - reviewer still wants the active account identity to stay operator-visible in every export flow

## Related Files

- [technical-roadmap.md](../documents/technical-roadmap.md)
- [branch-sync-incidents.md](../documents/branch-sync-incidents.md)
- [git_branching_plan.md](../documents/git_branching_plan.md)
- [GitBranch_AGENTs.md](../agents/GitBranch_AGENTs.md)
- [TODOs.export-performance.md](TODOs.export-performance.md)
- [TODOs.export-optimization.md](TODOs.export-optimization.md)
