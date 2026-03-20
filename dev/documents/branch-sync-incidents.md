# Branch Sync Incidents

This document records release-line and branch-sync incidents that caused broken or partially broken local/runtime behavior even though the underlying feature had already been implemented elsewhere.

Use it as:

- a release checklist reminder
- a failure log
- a "do not repeat this sync pattern" reference

## Scope

Focus on incidents where:

- `full-dev` and release lines drifted
- `main` / `runtime` received only half of a feature bundle
- start scripts, CLI entry, REPL, completer, settings, or tests were not shipped together
- auto-update pulled a release branch into a locally broken state

## Incident Log

### [2026-03-20][001] Release line missed `NapCatMediaDownloader` progress helpers

- Symptom:
  - `/export group ...` failed on friend machine and maintainer local `main`
  - errors included missing downloader progress methods such as:
    - `begin_export_download_tracking`
    - `_new_download_progress_state`
    - `settle_export_download_progress`
- Root cause:
  - release branch got downloader/runtime changes only partially
  - progress-tracking helpers were not shipped as a complete bundle
- Fix:
  - sync downloader progress implementation and tests into `main` / `runtime`
- Lesson:
  - exporter progress changes must ship atomically across:
    - downloader
    - CLI/export caller
    - release regression tests

### [2026-03-20][002] Release line missed login quick-completion bundle

- Symptom:
  - `main` local `start_cli.bat` auto-updated successfully
  - REPL then crashed immediately on startup with:
    - `TypeError: SlashCommandCompleter.__init__() got an unexpected keyword argument 'quick_login_lookup'`
- Root cause:
  - `repl.py` was already updated to use:
    - `quick_login_lookup=...`
  - but release `completion.py` still exposed the old constructor signature
  - corresponding completion regression test was also missing from the release bundle
- Fix:
  - sync:
    - `src/qq_data_cli/completion.py`
    - `tests/test_cli_login_completion.py`
  - into `main` / `runtime`
- Lesson:
  - REPL changes must ship together with:
    - completer implementation
    - command parser assumptions
    - completion regression tests

### [2026-03-20][003] Release line can look healthy while still being behaviorally skewed

- Symptom:
  - code updated
  - CLI started
  - but runtime behavior still diverged from `full-dev`
- Root cause:
  - release-line cherry-picks were functionally incomplete, not syntactically invalid
- Fix:
  - add explicit incident recording
  - tighten release sync discipline
- Lesson:
  - "it starts" is not a sufficient release check
  - release validation must include narrow smoke tests for the feature family being shipped

### [2026-03-20][004] Release line missed runtime bootstrap family while REPL/login family had already advanced

- Symptom:
  - `main` local `start_cli.bat` auto-updated successfully
  - REPL entered normally
  - but `/login` immediately failed with:
    - `NapCatBootstrapper.ensure_endpoint() got an unexpected keyword argument 'quick_login_uin'`
- Root cause:
  - release line had already received:
    - REPL `/login` startup warmup
    - `quick_login_uin`-aware endpoint calls
  - but release `src/qq_data_integrations/napcat/bootstrap.py` was still on the older signature
  - release `tests/test_napcat_bootstrap.py` was also absent, so this bundle skew had no guardrail
- Fix:
  - sync the runtime bootstrap family into `main` / `runtime`:
    - `src/qq_data_integrations/napcat/bootstrap.py`
    - `tests/test_napcat_bootstrap.py`
  - validate together with:
    - `tests/test_repl_login.py`
    - `tests/test_cli_login_completion.py`
- Lesson:
  - login/startup work cannot be released as:
    - REPL-only
    - completion-only
    - startup banner-only
  - it must ship with the runtime bootstrap family as one bundle

### [2026-03-20][005] Release line missed runtime starter family while bootstrap family had already advanced

- Symptom:
  - after syncing `bootstrap.py`, `main` startup no longer failed in the same place
  - but startup warmup immediately failed one layer deeper with:
    - `NapCatRuntimeStarter.ensure_endpoint() got an unexpected keyword argument 'quick_login_uin'`
- Root cause:
  - release line had already received:
    - `repl.py` startup warmup
    - `bootstrap.py` quick-login-aware endpoint plumbing
  - but release `src/qq_data_integrations/napcat/runtime.py` was still on the old launcher/ensure signature
  - related runtime launch diagnostics tests were also absent on the release line
- Fix:
  - sync the runtime starter family into `main` / `runtime`:
    - `src/qq_data_integrations/napcat/runtime.py`
    - `tests/test_napcat_runtime_diagnostics.py`
- Lesson:
  - startup/login release bundles must include the full chain:
    - `repl/app`
    - `bootstrap`
    - `runtime starter`
    - launch/diagnostic regression tests

## Required Release Sync Checklist

When syncing a feature from `full-dev` into `main` / `runtime`, check whether the change touches any of these families and ship the whole family together:

1. CLI / REPL family
- `src/qq_data_cli/app.py`
- `src/qq_data_cli/repl.py`
- `src/qq_data_cli/completion.py`
- related tests:
  - `tests/test_repl_login.py`
  - `tests/test_cli_login_completion.py`
  - `tests/test_cli_app_login.py`

2. Export progress / summary family
- `src/qq_data_core/export_selection.py`
- `src/qq_data_integrations/napcat/media_downloader.py`
- `src/qq_data_cli/app.py`
- related tests:
  - `tests/test_media_downloader_progress_and_forward_timeout.py`
  - `tests/test_export_selection_summary.py`

3. Login / runtime bootstrap family
- `src/qq_data_integrations/napcat/login.py`
- `src/qq_data_integrations/napcat/settings.py`
- `src/qq_data_integrations/napcat/webui_client.py`
- `src/qq_data_integrations/napcat/bootstrap.py`
- related tests:
  - `tests/test_napcat_quick_login.py`
  - `tests/test_cli_app_login.py`
  - `tests/test_napcat_bootstrap.py`

4. Start script family
- `start_cli.bat`
- `start_cli_compat.bat`
- `start_cli_modern_host.bat`
- `start_napcat_logged.bat`

## Required Post-Sync Validation

After syncing a release-line fix, do not stop at "cherry-pick succeeded". Run the smallest matching regression set for the feature family:

- login / completion issue:
  - `tests/test_cli_login_completion.py`
  - `tests/test_repl_login.py` when present on the release line
- export/downloader issue:
  - `tests/test_media_downloader_progress_and_forward_timeout.py`
  - `tests/test_export_selection_summary.py`
- start/runtime issue:
  - `tests/test_cli_app_login.py`
  - `tests/test_napcat_bootstrap.py`

If the release line does not contain the matching regression test yet, that is itself a warning sign and should be recorded here.
