# Code Review Risk Register

## Goal

Build a strict reviewer-style risk register before more fixes.

Focus:
- hidden session state
- cross-export contamination
- "disable until restart" behavior
- stale caches
- partial output / ambiguous failure states
- startup/debug tooling becoming its own source of failure
- scheduler / trace / cleanup paths that can create coupling or cascading faults

## Review stance

- Prefer over-reporting credible failure risks to under-reporting them.
- Distinguish:
  - confirmed issues
  - high-confidence suspected issues
  - areas still pending scan
- Do not treat third-party vendored code as first-fix scope unless our code depends on a risky behavior boundary.

## Coverage Map

### Scanned in this pass

- `src/qq_data_cli/app.py`
- `src/qq_data_cli/completion.py`
- `src/qq_data_cli/completion_runtime.py`
- `src/qq_data_cli/export_commands.py`
- `src/qq_data_cli/qr.py`
- `src/qq_data_cli/repl.py`
- `src/qq_data_cli/startup_capture.py`
- `src/qq_data_cli/terminal_compat.py`
- `src/qq_data_cli/watch_view.py`
- `src/qq_data_cli/export_cleanup.py`
- `src/qq_data_core/time_expr.py`
- `src/qq_data_core/media_bundle.py`
- `src/qq_data_core/export_forensics.py`
- `src/qq_data_core/export_perf.py`
- `src/qq_data_core/export_selection.py`
- `src/qq_data_core/normalize.py`
- `src/qq_data_core/services.py`
- `src/qq_data_integrations/local_qq.py`
- `src/qq_data_integrations/napcat/bootstrap.py`
- `src/qq_data_integrations/napcat/directory.py`
- `src/qq_data_integrations/napcat/fast_history_client.py`
- `src/qq_data_integrations/napcat/gateway.py`
- `src/qq_data_integrations/napcat/http_client.py`
- `src/qq_data_integrations/napcat/login.py`
- `src/qq_data_integrations/napcat/provider.py`
- `src/qq_data_integrations/napcat/realtime.py`
- `src/qq_data_integrations/napcat/media_downloader.py`
- `src/qq_data_integrations/napcat/diagnostics.py`
- `src/qq_data_integrations/napcat/runtime.py`
- `src/qq_data_integrations/napcat/settings.py`
- `src/qq_data_integrations/napcat/websocket_client.py`
- `src/qq_data_integrations/napcat/webui_client.py`

### Lower-priority helpers not yet given a dedicated risk pass

- `src/qq_data_cli/export_input.py`
- `src/qq_data_cli/logging_utils.py`
- `src/qq_data_cli/target_display.py`
- `src/qq_data_core/debug.py`
- `src/qq_data_core/exporters/*`
- vendored `src/pypinyin/*`

## Confirmed Findings

### CRR-001 High: session-scoped bad token cache can poison later exports

- Area:
  - `src/qq_data_integrations/napcat/media_downloader.py`
  - `src/qq_data_integrations/napcat/gateway.py`
  - `src/qq_data_cli/repl.py`
- Problem:
  - `_known_bad_public_tokens` is retained for the lifetime of the downloader / gateway.
  - normal export cleanup does not clear it.
- Consequence:
  - one transient token failure can short-circuit later exports in the same REPL session even after relogin, manual local download, or NapCat recovery.
- Relevant code:
  - `_known_bad_public_tokens`
  - `_reset_transient_export_state()`
  - `_call_public_action_with_token()`

### CRR-002 High: media fast route disable can persist for the whole session after one temporary failure

- Area:
  - `src/qq_data_integrations/napcat/media_downloader.py`
- Problem:
  - `_fast_context_route_disabled` flips to `True` on route unavailable / related failures.
  - it is then used to suppress later `/hydrate-media` style attempts.
  - it is not reset per export.
- Consequence:
  - one transient fast-route outage can silently degrade all later exports in the same REPL session.

### CRR-003 High: provider fast availability flags can become "fail once, stay degraded"

- Area:
  - `src/qq_data_integrations/napcat/provider.py`
- Problem:
  - `_fast_available` and `_fast_tail_bulk_available` are process-session flags.
  - transient fast plugin failures set them to `False`.
  - later exports reuse those flags.
- Consequence:
  - fast history can stay disabled longer than the real outage, causing silent fallback to slower / weaker HTTP paths.

### CRR-004 High: forward hydration suppression is too global

- Area:
  - `src/qq_data_integrations/napcat/provider.py`
- Problem:
  - `_disable_parse_mult_forward_hydration`
  - `_known_forward_history_failures`
  - `_known_unavailable_forward_ids`
  - `_known_unavailable_history_keys`
  all live for the whole provider session.
- Consequence:
  - a burst of old-forward failures in one export can suppress useful forward recovery in later unrelated exports until CLI restart.

### CRR-005 High: export cleanup only resets downloader-side transient state, not broader session degradation state

- Area:
  - `src/qq_data_cli/export_cleanup.py`
  - `src/qq_data_integrations/napcat/gateway.py`
  - `src/qq_data_integrations/napcat/media_downloader.py`
  - `src/qq_data_integrations/napcat/provider.py`
- Problem:
  - cleanup currently goes through `cleanup_remote_cache()` on the downloader.
  - provider-level failure flags and gateway-level caches remain alive.
- Consequence:
  - users can believe each export starts fresh, while in reality some degraded state continues across exports.

### CRR-006 Medium: history bounds cache can go stale in long-lived REPL/watch sessions

- Area:
  - `src/qq_data_integrations/napcat/gateway.py`
  - call sites in `src/qq_data_cli/repl.py` and `src/qq_data_cli/watch_view.py`
- Problem:
  - `_history_bounds_cache` key is only `(chat_type, chat_id, need_earliest, need_final)`.
  - no time/version dimension.
- Consequence:
  - interval exports that depend on earliest/final content can use stale bounds after new messages arrive.

### CRR-007 Medium: startup capture is eager and heavy on every CLI startup

- Area:
  - `src/qq_data_cli/app.py`
  - `src/qq_data_cli/startup_capture.py`
- Problem:
  - startup capture runs automatically at CLI start.
  - it performs directory discovery, nested QQ snapshots, config snapshots, storage probes, and log capture up front.
- Consequence:
  - startup latency can become a debugging tax, especially on large QQ trees or busy machines.

### CRR-008 Medium: startup capture becomes stale within the same session

- Area:
  - `src/qq_data_cli/startup_capture.py`
  - `src/qq_data_cli/repl.py`
- Problem:
  - `_SESSION_CAPTURE_PATH` memoizes one capture per process session.
  - later state changes such as login completion, endpoint readiness, or launcher changes are not reflected unless a new process starts.
- Consequence:
  - `/status` may point to a startup report that no longer matches the live state.

### CRR-009 Medium: log tail capture reads whole files into memory

- Area:
  - `src/qq_data_cli/startup_capture.py`
- Problem:
  - `_tail_text()` reads the full log file, then slices the last lines.
- Consequence:
  - large CLI/NapCat logs can create avoidable startup I/O and memory churn.

### CRR-010 Medium: worker "adaptive" behavior is not truly feedback-driven yet

- Area:
  - `src/qq_data_integrations/napcat/media_downloader.py`
- Problem:
  - feedback is collected and emitted, but worker sizing still uses CPU count and request counts only.
- Consequence:
  - current auto-tuning may be misleading and may not adapt well on friend machines with different latency/failure characteristics.

### CRR-011 Medium: data file is written before asset materialization fully succeeds

- Area:
  - `src/qq_data_core/media_bundle.py`
  - `src/qq_data_core/services.py`
- Problem:
  - `write_export_bundle()` writes the main data file first, then materializes assets, then writes the manifest.
- Consequence:
  - if asset materialization aborts or crashes later, users can be left with a partial export state:
    - data file exists
    - assets dir may be incomplete
    - manifest may be missing or incomplete
  - this creates ambiguity about whether the export "really succeeded".

### CRR-012 Medium: perf trace flushing is still eager for many non-materialize events

- Area:
  - `src/qq_data_core/export_perf.py`
- Problem:
  - every non-`materialize_asset_step` event is persisted and flushed eagerly.
- Consequence:
  - on verbose scans, tracing itself can contribute non-trivial I/O overhead and distort benchmark realism.

### CRR-013 Medium: invalid export format values can silently fall back to JSONL

- Area:
  - `src/qq_data_cli/app.py`
  - `src/qq_data_cli/export_commands.py`
  - `src/qq_data_core/services.py`
- Problem:
  - root export parsing accepts arbitrary `--format` text.
  - `ChatExportService.write_bundle()` treats anything other than `"txt"` as JSONL.
- Consequence:
  - a typo like `--format jsnol` can quietly produce JSONL instead of failing fast.
  - this is the kind of non-crashing behavior that wastes remote test cycles.

### CRR-014 Medium: watch export uses a shared gateway across threads without an explicit thread-safety boundary

- Area:
  - `src/qq_data_cli/watch_view.py`
  - `src/qq_data_integrations/napcat/gateway.py`
- Problem:
  - watch mode keeps one long-lived gateway for live events.
  - export is then pushed into `asyncio.to_thread(...)` and reuses the same gateway.
  - provider/downloader caches are stateful but not generally synchronized.
- Consequence:
  - live watch traffic and export traffic can mutate shared gateway/provider/downloader state concurrently.
  - this is a credible source of rare, hard-to-reproduce watch/export coupling bugs.

### CRR-017 High: runtime/config autodiscovery can silently bind to the wrong NapCat tree

- Area:
  - `src/qq_data_integrations/napcat/settings.py`
- Problem:
  - `_resolve_napcat_dir()`, `_resolve_workdir()`, and config candidate scanning use heuristic search across project roots and multiple likely directories.
  - when multiple NapCat/NapCatQQ/runtime trees exist, the first “looks plausible” path can win silently.
- Consequence:
  - the CLI can talk to the wrong launcher, wrong workdir, or wrong config set without an explicit error.
  - on friend machines with multiple clones/runtimes/accounts, this is a high-blast-radius misbinding risk.

### CRR-018 Medium: endpoint bootstrap mutates NapCat OneBot config as a side effect of a readiness check

- Area:
  - `src/qq_data_integrations/napcat/bootstrap.py`
  - `src/qq_data_integrations/napcat/webui_client.py`
- Problem:
  - `ensure_endpoint()` does not just check/start NapCat; once WebUI is reachable and logged in, it may call `ensure_default_onebot_servers(...)` and rewrite NapCat OB11 config.
- Consequence:
  - “make the endpoint ready” can unexpectedly become “change the user's runtime config”.
  - this raises coupling risk between diagnostics/startup and persistent runtime behavior.

### CRR-019 Medium: metadata directory cache has no freshness policy

- Area:
  - `src/qq_data_integrations/napcat/directory.py`
- Problem:
  - friend/group metadata is cached to disk and reloaded later with no TTL, no version marker, and no last-refresh guard.
- Consequence:
  - target search/resolve can drift from live NapCat state across sessions.
  - stale display names or missing/new chats can produce confusing lookup results until a manual refresh happens.

### CRR-020 Medium: watch mode eagerly discovers QQ media roots before export is even requested

- Area:
  - `src/qq_data_cli/watch_view.py`
  - `src/qq_data_integrations/local_qq.py`
- Problem:
  - `WatchConversationView.__init__()` immediately runs `discover_qq_media_roots()`.
  - that discovery scans multiple drives and nested child folders.
- Consequence:
  - opening watch mode pays local QQ root discovery up front, even if the user never exports from watch.
  - this adds avoidable latency and stale-environment coupling.

### CRR-021 Medium: normalization fabricates “now” as message time when source timestamp is missing

- Area:
  - `src/qq_data_core/normalize.py`
- Problem:
  - `_parse_timestamp()` falls back to `datetime.now(EXPORT_TIMEZONE)` when neither `timestamp` nor epoch fields exist.
- Consequence:
  - missing source timestamps silently become “current time”.
  - this can distort ordering, interval export boundaries, and debugging of malformed payloads.

### CRR-022 Medium: normalized snapshots reuse source metadata by reference

- Area:
  - `src/qq_data_core/normalize.py`
  - mutating call sites in `src/qq_data_cli/repl.py` and `src/qq_data_cli/watch_view.py`
- Problem:
  - `normalize_snapshot()` assigns `metadata=snapshot.metadata` directly.
  - later code mutates normalized snapshot metadata in place.
- Consequence:
  - source and normalized layers can share one mutable metadata dict.
  - this creates subtle “why did upstream metadata change?” style coupling bugs.

### CRR-023 Medium: watch stream accepts every notice event and guesses ownership heuristically

- Area:
  - `src/qq_data_integrations/napcat/realtime.py`
- Problem:
  - `_is_watch_event()` admits all `post_type == "notice"` events.
  - `_resolve_chat_id()` then guesses ownership from `group_id`, `peer_id`, `user_id`, `sender_id`, `target_id`.
- Consequence:
  - unrelated notice traffic can leak into a watched chat if identifiers happen to line up.
  - this can pollute watch transcript/state and make export/watch coupling harder to reason about.

### CRR-024 Medium: HTTP/WebUI/fast-history clients normalize connect/timeout failures but leak generic HTTP failures raw

- Area:
  - `src/qq_data_integrations/napcat/http_client.py`
  - `src/qq_data_integrations/napcat/webui_client.py`
  - `src/qq_data_integrations/napcat/fast_history_client.py`
- Problem:
  - connect and timeout errors are wrapped into domain-specific exceptions.
  - generic non-2xx HTTP responses still go through `response.raise_for_status()` and surface as raw `httpx.HTTPStatusError`.
- Consequence:
  - caller behavior can become inconsistent depending on failure shape.
  - some graceful degradation paths may miss these raw exceptions and treat them like unexpected faults.

### CRR-025 Medium: QQ media root discovery is both broad and ambiguous

- Area:
  - `src/qq_data_integrations/local_qq.py`
  - consumers in `src/qq_data_cli/startup_capture.py` and `src/qq_data_cli/watch_view.py`
- Problem:
  - root discovery scans `C:` through `G:` and also walks one level of nested folders for likely QQ roots.
  - it treats existence as enough to include a candidate.
- Consequence:
  - startup/debug tooling can pick up false-positive roots.
  - large or cluttered disks make this discovery heavier and less predictable than it appears.

### CRR-026 Low: runtime auto-start leaves wrapper script artifacts with no cleanup policy

- Area:
  - `src/qq_data_integrations/napcat/runtime.py`
- Problem:
  - each auto-start writes a new `launch_napcat_*.cmd` into `state/napcat_logs` and never reclaims old wrapper scripts.
- Consequence:
  - operational clutter accumulates over time.
  - not a correctness bug, but it is the sort of silent buildup that later confuses debugging.

### CRR-028 High: default output naming is only second-granular and can collide under repeated exports

- Area:
  - `src/qq_data_core/paths.py`
  - callers that rely on `build_default_output_path(...)`
- Problem:
  - default export filenames use `%Y%m%d_%H%M%S` only.
  - two exports of the same chat/type/format within one second resolve to the same output path.
- Consequence:
  - repeated quick exports can overwrite earlier output or create ambiguous partial-state races.
  - this is especially risky for scripted retries, watch-triggered exports, and debugging loops.

### CRR-029 Medium: startup capture and NapCat launch artifacts also use second-granular names

- Area:
  - `src/qq_data_cli/startup_capture.py`
  - `src/qq_data_integrations/napcat/runtime.py`
- Problem:
  - startup capture files and launch wrapper/log files are named with second-level timestamps only.
- Consequence:
  - concurrent or near-simultaneous starts can collide on filenames.
  - this can overwrite capture/log artifacts precisely when we most need reliable forensic evidence.

### CRR-030 Medium: latest pointer files are cross-process shared and trusted without provenance checks

- Area:
  - `src/qq_data_cli/startup_capture.py`
  - `src/qq_data_integrations/napcat/runtime.py`
- Problem:
  - `latest.path` files are overwritten without cross-process locking.
  - readers trust their content and then open the pointed file directly.
- Consequence:
  - concurrent CLI processes can stomp each other's “latest” pointer.
  - a corrupted or poisoned pointer can make `/status` or startup capture read and expose an unintended file.

### CRR-031 Medium: exporter data writes are direct, not temp-file + atomic replace

- Area:
  - `src/qq_data_core/exporters/jsonl.py`
  - `src/qq_data_core/exporters/txt.py`
- Problem:
  - JSONL/TXT writers write directly to the final target path.
- Consequence:
  - process interruption, disk/full I/O faults, or concurrent same-path writes can leave truncated files that still look “present”.
  - combined with CRR-011, this raises the chance of misleading partial export states.

### CRR-032 Medium: NapCat client layers do not normalize malformed/non-JSON responses

- Area:
  - `src/qq_data_integrations/napcat/http_client.py`
  - `src/qq_data_integrations/napcat/fast_history_client.py`
  - `src/qq_data_integrations/napcat/webui_client.py`
- Problem:
  - after `raise_for_status()`, these clients call `response.json()` directly.
  - malformed HTML/proxy/error bodies bubble up as raw JSON decode exceptions.
- Consequence:
  - failure handling becomes inconsistent across “connect/timeout/http/json-shape” classes.
  - higher layers may treat broken upstream responses as unexpected code bugs instead of transport/runtime faults.

### CRR-033 Medium: WebSocket watch can hang in infinite reconnect mode without surfacing a decisive terminal fault

- Area:
  - `src/qq_data_integrations/napcat/websocket_client.py`
- Problem:
  - default `max_retries=None` means reconnect loops forever with fixed delay.
  - auth/config/protocol failures are not distinguished from transient disconnects.
- Consequence:
  - watch mode can remain in a “quietly retrying forever” state instead of surfacing a clear actionable error.
  - this is especially painful on friend machines where wrong token/endpoint issues should fail loudly.

### CRR-034 Medium: startup capture over-collects highly identifying local environment data

- Area:
  - `src/qq_data_cli/startup_capture.py`
- Problem:
  - capture includes hostname, username, full `sys.path`, selected env vars, QQ roots, and config snapshots.
- Consequence:
  - great for debugging, but easy to overshare if a report is passed around casually.
  - this becomes a concrete operational risk once reports leave the original machine.

### CRR-039 Medium: fast-history route probing can report broken routes as "reachable"

- Area:
  - `src/qq_data_integrations/napcat/fast_history_client.py`
- Problem:
  - `probe_route()` treats every non-404 response as `reachable=True`.
  - 401/403/500/502 responses are therefore reported as route-present with `detail=None`.
- Consequence:
  - diagnostics and startup capture can imply "the route exists and is basically usable" when the plugin is actually misconfigured, auth-gated, or crashing.
  - this is exactly the kind of false-positive health signal that wastes remote test cycles.

### CRR-040 Medium: WebSocket watch silently drops malformed frames

- Area:
  - `src/qq_data_integrations/napcat/websocket_client.py`
- Problem:
  - `iter_events()` catches `orjson.JSONDecodeError` and simply `continue`s.
  - no counter, warning, or terminal error is surfaced.
- Consequence:
  - protocol corruption, partial frames, or upstream regressions can look like an ordinary quiet watch session instead of an actionable runtime fault.
  - this can hide exactly the class of "service is up but payloads are broken" problems that are hardest to diagnose remotely.

## High-Confidence Suspected Findings

### CRR-015 Suspected: resolution caches may be more export-global than some failure modes deserve

- Area:
  - `src/qq_data_core/media_bundle.py`
- Problem:
  - `resolution_cache` and shared outcome reuse are beneficial, but likely need continued audit for "negative result reused too broadly" cases.
- Why suspected:
  - current key is richer than before, but still shared across the whole bundle, while some failures are highly timing-sensitive.
- Needed next:
  - targeted scan of repeated `missing_after_napcat` and second-pass recovery interactions.

### CRR-016 Suspected: forward-related missing classification may still collapse structurally different failures too early

- Area:
  - `src/qq_data_core/export_forensics.py`
  - `src/qq_data_core/media_bundle.py`
- Problem:
  - several forward structure/resource failure shapes still converge into a small set of terminal labels.
- Why suspected:
  - current classification is much better than before, but likely still under-separates:
    - structure unavailable
    - URL unavailable
    - local placeholder only
    - stale per-forward token/path
- Needed next:
  - compare route ledgers for remaining forward misses and expand taxonomy only where it clarifies actionability.

### CRR-027 Suspected: unsupported/flattened normalization may still discard structure we later need for debugging

- Area:
  - `src/qq_data_core/normalize.py`
  - `src/qq_data_core/export_selection.py`
- Problem:
  - several segment shapes are collapsed into plain text, fallback tokens, or `[unsupported:*]` markers during normalization/profile filtering.
- Why suspected:
  - the export path is intentionally text-friendly, but some later debugging/materialization decisions benefit from richer untouched structure.
- Needed next:
  - compare a few raw messages against normalized output for reply/share/unsupported/system segments and identify whether any later decisions are being forced by early flattening.

### CRR-035 Suspected: explicit config path environment variables may resolve relative to surprising anchors

- Area:
  - `src/qq_data_integrations/napcat/settings.py`
- Problem:
  - explicit config env vars are resolved with plain `Path(explicit).resolve()`, while many other paths are resolved relative to project/runtime bases.
- Why suspected:
  - a relative `NAPCAT_ONEBOT_CONFIG` / `NAPCAT_WEBUI_CONFIG` can bind to the current working directory instead of the NapCat/runtime tree a user had in mind.
- Needed next:
  - confirm intended semantics and decide whether explicit config vars should resolve relative to project root, workdir, or cwd.

### CRR-036 Suspected: time expression parser and interactive date tooling accept different literal shapes

- Area:
  - `src/qq_data_core/time_expr.py`
  - `src/qq_data_cli/export_input.py`
  - `src/qq_data_cli/completion.py`
  - `src/qq_data_cli/repl.py`
  - `src/qq_data_cli/watch_view.py`
- Problem:
  - backend parsing accepts single-digit month/day/hour/minute/second fields.
  - interactive highlighting, field-jump, rollover, and some completion helpers only recognize strict `YYYY-MM-DD_HH-MM-SS`.
- Consequence:
  - users can enter literals that parse successfully but do not get the expected editor assistance.
  - this creates a “command works, but UI behaves strangely” class of silent inconsistency.
- Needed next:
  - decide whether to tighten parsing to strict literals only, or broaden UI tooling to match the more permissive parser.

### CRR-037 Suspected: export date highlighting can match timestamp-like substrings inside unrelated tokens

- Area:
  - `src/qq_data_cli/export_input.py`
- Problem:
  - `_DATE_TOKEN_RE` is applied across the whole `/export...` command line, not just the first two positional time-expression tokens.
- Consequence:
  - a timestamp-like substring inside `--out` or another unrelated token can be highlighted and treated like a date field by the editor helpers.
  - this creates a confusing “UI edits the wrong thing” failure mode.
- Needed next:
  - make date highlighting/token-range detection token-aware, not regex-over-the-whole-line.

### CRR-038 Suspected: `NormalizedMessage.raw_message` field name is semantically misleading

- Area:
  - `src/qq_data_core/models.py`
  - `src/qq_data_core/normalize.py`
- Problem:
  - `NormalizedMessage.raw_message` currently stores the full source message object when `include_raw=True`, not just the nested `rawMessage`/`raw_message` inner payload.
- Consequence:
  - static readers and ad-hoc debug tooling can easily inspect the wrong layer and conclude that raw structure is missing when it is actually nested one level deeper.
  - this is a debugging-footgun rather than a runtime crash, but it raises the chance of bad conclusions during remote triage.
- Needed next:
  - decide whether to rename the field, split it into `source_message` + `raw_message`, or at minimum document the current semantics clearly in debug/reporting paths.

### CRR-039 High: export cleanup can race with in-flight prefetch workers and shared cache teardown

- Area:
  - `src/qq_data_integrations/napcat/media_downloader.py`
  - `src/qq_data_integrations/napcat/gateway.py`
  - `src/qq_data_cli/export_cleanup.py`
- Problem:
  - remote/token prefetch work is submitted into background executors.
  - export cleanup clears in-memory future maps immediately and then removes the whole shared `state/media_downloads` tree.
  - executor tasks are only cancelled later on `close()`, and already-running tasks are not guaranteed to stop.
- Consequence:
  - one export can still be writing into the cache while cleanup is deleting it.
  - a just-finished export can repopulate cleared caches after reset, polluting the next export in the same process.
  - concurrent CLI processes sharing the same `state_dir` can delete each other's in-flight remote cache artifacts.

### CRR-040 Medium: subcommand `--state-dir` overrides do not apply to startup logging/capture initialization

- Area:
  - `src/qq_data_cli/app.py`
- Problem:
  - app callback runs `_init_cli_logging()` and `capture_startup_snapshot()` before command-specific options like `export-history --state-dir ...` are parsed.
- Consequence:
  - one-shot commands can write logs and startup captures into the wrong state directory while the actual export uses another one.
  - this creates misleading diagnostics and split evidence on friend machines.

### CRR-041 Medium: fast-history route probing overstates capability on 401/500-style failures

- Area:
  - `src/qq_data_integrations/napcat/fast_history_client.py`
- Problem:
  - `probe_route()` currently marks any non-404 HTTP response as `reachable=True`.
  - auth failures, 500s, or other broken-route responses therefore look like a healthy capability instead of a degraded one.
- Consequence:
  - startup/debug preflight can over-report fast-history availability.
  - later fallbacks then look “surprising” because diagnostics said the route was reachable.

### CRR-042 Medium: constructing a gateway eagerly authenticates WebUI for fast-history headers

- Area:
  - `src/qq_data_integrations/napcat/gateway.py`
- Problem:
  - gateway construction calls `_build_fast_history_headers(settings)`, which creates a WebUI client and runs `ensure_authenticated()`.
  - this happens even for flows that only need OneBot HTTP or metadata access.
- Consequence:
  - creating a fresh gateway can incur unexpected WebUI latency and auth coupling.
  - temporary WebUI auth issues can silently degrade fast-history setup before any actual history request is made.

### CRR-043 Medium: target completion cache can become “stale but considered primed”

- Area:
  - `src/qq_data_cli/repl.py`
- Problem:
  - `_prime_target_cache()` marks a chat type as primed if refresh fails but some cached targets already exist.
  - after that, completion priming for that chat type stops retrying automatically.
- Consequence:
  - a transient endpoint failure can freeze stale completion suggestions for the rest of the REPL session.
  - this is easy to miss because the UI still “works”, just with quietly outdated target metadata.

### CRR-044 Low: QQ media root discovery cache can preserve stale environment/path assumptions for the whole TTL

- Area:
  - `src/qq_data_integrations/local_qq.py`
- Problem:
  - discovered QQ roots are cached process-locally for 30 seconds with no awareness of environment changes such as `QQ_MEDIA_ROOTS` updates, mount changes, or newly created roots.
- Consequence:
  - startup capture, watch, and export heuristics can keep using stale roots for the rest of the TTL window.
  - on remote debugging sessions where the user changes env/path config live, this can make the first retry misleading.

### CRR-045 Low: startup capture persists two full copies of the same report on every refresh

- Area:
  - `src/qq_data_cli/startup_capture.py`
- Problem:
  - each capture writes both a timestamped `startup_*.json` and a full `latest.json`, then a `latest.path` pointer.
- Consequence:
  - every refresh doubles disk I/O and duplicates a privacy-sensitive artifact.
  - this is not a correctness bug, but it is unnecessary evidence amplification on machines where captures may be shared.

### CRR-041 Suspected: client success criteria may accept malformed "error-looking" JSON as success if sentinel fields are missing

- Area:
  - `src/qq_data_integrations/napcat/http_client.py`
  - `src/qq_data_integrations/napcat/fast_history_client.py`
- Problem:
  - OneBot HTTP success is currently decided mainly by `payload["status"]`.
  - fast-history success is currently decided mainly by `payload["code"]`.
  - if an adapter/proxy/plugin regression returns a JSON dict that omits those sentinel fields but still contains an error-shaped body, the client layer may pass it through as success and leave later layers to fail ambiguously.
- Consequence:
  - the first visible error can move far away from the real transport/protocol fault.
  - callers may appear to "work but with missing data" instead of failing decisively at the boundary.
- Needed next:
  - audit real upstream success/error payload shapes and decide whether boundary validation should also require expected keys beyond `status` / `code`.

### CRR-039 High: protocol clients accept underspecified “success” payloads and can silently treat errors as valid data

- Area:
  - `src/qq_data_integrations/napcat/http_client.py`
  - `src/qq_data_integrations/napcat/fast_history_client.py`
- Problem:
  - `NapCatHttpClient.call_action()` treats `payload["status"] is None` as success and does not check `retcode`.
  - `NapCatFastHistoryClient._extract_data()` likewise treats `code is None` as success.
- Consequence:
  - upstream protocol drift, malformed plugin responses, or partially broken reverse proxies can be misclassified as valid data instead of transport/runtime faults.
  - this is exactly the kind of “looks successful, but data is already wrong or incomplete” failure that wastes remote debugging cycles.
- Needed next:
  - define strict success criteria per upstream:
    - OneBot HTTP: require explicit `status == "ok"` and/or validated zero retcode semantics.
    - fast-history: require explicit `code == 0` unless a compatibility exemption is intentionally documented.

### CRR-040 Medium: naive ISO timestamp parsing depends on the local machine timezone

- Area:
  - `src/qq_data_core/normalize.py`
- Problem:
  - `_parse_timestamp()` uses `datetime.fromisoformat(...).astimezone(EXPORT_TIMEZONE)` directly for string timestamps.
  - if the string is ISO-like but timezone-naive, Python interprets it in the local machine timezone before conversion.
- Consequence:
  - the same exported payload can normalize to different wall-clock timestamps on different machines.
  - ordering, interval boundaries, and “why is this message in/out of range?” debugging can drift silently across environments.
- Needed next:
  - make naive timestamp handling explicit:
    - either reject naive literals,
    - or assign a documented default timezone before conversion.

### CRR-041 Medium: snapshot metadata is only shallow-copied and can still share nested state

- Area:
  - `src/qq_data_core/normalize.py`
- Problem:
  - `normalize_snapshot()` now uses `dict(snapshot.metadata)`, which avoids direct top-level aliasing.
  - nested dict/list values inside `metadata` are still shared by reference.
- Consequence:
  - later mutation of nested metadata structures in normalized/export/debug paths can still rewrite source snapshot metadata indirectly.
  - this is a quieter variant of the shared-state bug we already fixed for raw messages.
- Needed next:
  - decide whether snapshot metadata should be fully detached with `deepcopy`, or formally treated as immutable after snapshot creation.

### CRR-042 Medium: CLI logging globally overrides exception hooks and never restores prior handlers

- Area:
  - `src/qq_data_cli/logging_utils.py`
- Problem:
  - `setup_cli_logging()` installs process-global `sys.excepthook` and `threading.excepthook` replacements.
  - previous hooks are not preserved/restored via lifecycle management.
- Consequence:
  - embedded/test/in-process reuse scenarios can inherit CLI logging behavior unexpectedly.
  - future tooling that reuses these modules in the same process can get cross-tool exception handling side effects that are hard to attribute.
- Needed next:
  - preserve previous hooks and define ownership/restoration rules, or explicitly scope this behavior to standalone CLI entry only.

### CRR-043 Medium: fast-history diagnostics can falsely report the plugin as unavailable

- Area:
  - `src/qq_data_integrations/napcat/diagnostics.py`
- Problem:
  - `collect_fast_history_route_matrix()` constructs `NapCatFastHistoryClient` without the authenticated headers that the runtime gateway may use.
  - on machines where the fast-history plugin expects WebUI-derived bearer auth, diagnostics probe a weaker path than export does.
- Consequence:
  - startup capture and `/doctor` can report “fast history unavailable” even though the actual export path can use the plugin.
  - this creates a high-cost false negative during remote debugging because investigators chase the wrong subsystem.
- Needed next:
  - align diagnostics auth/header behavior with runtime gateway construction, or label the route probe as explicitly unauthenticated.

### CRR-044 Medium: constructing `NapCatGateway` already performs WebUI-dependent fast-history auth side effects

- Area:
  - `src/qq_data_integrations/napcat/gateway.py`
  - `src/qq_data_integrations/napcat/webui_client.py`
- Problem:
  - `_build_fast_history_headers()` runs during `NapCatGateway` construction and may immediately authenticate against WebUI.
  - if WebUI auth is unavailable, times out, or is misconfigured, gateway creation silently degrades fast-history capability before any export request is made.
- Consequence:
  - “create gateway” is not a cheap/local step; it already carries network, auth, and silent fallback behavior.
  - transient WebUI failures can make fast-history appear disabled long before the code reaches actual history/export logic.
- Needed next:
  - defer fast-history auth/header acquisition until first fast-history use, or surface the degradation explicitly in gateway state/telemetry.

### CRR-045 Medium: QQ media root discovery still hard-codes the scan to `C:` through `G:`

- Area:
  - `src/qq_data_integrations/local_qq.py`
- Problem:
  - discovery scans only a built-in drive-letter set plus a few profile-based paths.
  - machines using `H:` and beyond, subst mounts, network drives, removable volumes, or unusual storage layouts are invisible unless `QQ_MEDIA_ROOTS` is set manually.
- Consequence:
  - on friend machines this can present as “some QQ local media missing” when the real issue is simply that discovery never searched the actual root.
  - because the function can still return some plausible roots, the failure looks partial and is easy to misdiagnose.
- Needed next:
  - broaden the drive discovery strategy or emit a clear warning/report field that discovery was limited to the built-in drive set.

### CRR-046 Medium: export content summary prints a meaningless `x/x` ratio for segment counts

- Area:
  - `src/qq_data_core/export_selection.py`
- Problem:
  - `format_export_content_summary()` currently formats `content_export` as `count/count`, using the same `segment_counts` value for both numerator and denominator.
- Consequence:
  - the summary looks comparative, but the ratio is tautological and conveys no real drop/keep information.
  - this can mislead reviewers into thinking the summary is validating profile correctness when it is not.
- Needed next:
  - either compute a meaningful denominator or drop the fake ratio entirely.

### CRR-047 Medium: profile rebuild quietly compresses forward top-level text down to preview text

- Area:
  - `src/qq_data_core/export_selection.py`
- Problem:
  - `_segment_text_value()` for `forward` uses `preview_text` / `summary`, not `detailed_text`.
  - after `apply_export_profile()`, rebuilt `content` and `text_content` can therefore become materially shorter than the forward detail still stored in `segment.extra`.
- Consequence:
  - JSONL/profile exports can present a top-level textual view that under-represents the actual forward content without any explicit warning.
  - this is a silent semantic drift, not a crash, which makes it especially easy to miss.
- Needed next:
  - decide whether profile exports intend to preserve expanded forward detail in top-level text fields or intentionally collapse to preview-only semantics.

### CRR-048 High: multiple layers silently coerce unknown chat types to `private`

- Area:
  - `src/qq_data_cli/app.py`
  - `src/qq_data_integrations/napcat/gateway.py`
  - `src/qq_data_integrations/napcat/fast_history_client.py`
  - `src/qq_data_cli/completion.py`
- Problem:
  - several call sites normalize chat type using “`group` if value == 'group' else `private`”.
  - this means typos, unexpected enum drift, or malformed internal values do not fail fast; they are silently redirected into the private/friend path.
- Consequence:
  - a wrong input can turn into a valid-looking but semantically wrong export/list/history request.
  - users and reviewers then debug the wrong branch of the system because the program appears to run, just with bizarre lookup/history behavior.
- Needed next:
  - validate chat type strictly at every external and boundary-facing entry point.
  - reserve the “else private” shortcut only for already-validated internal enums, or remove it entirely.

### CRR-049 High: startup capture still over-collects sensitive host context by default

- Area:
  - `src/qq_data_cli/app.py`
  - `src/qq_data_cli/startup_capture.py`
- Problem:
  - startup capture still runs automatically on CLI start and records high-identity fields such as cwd/argv/hostname/username/sys.path/environment slices, QQ tree snapshots, config snapshots, and raw log tails.
- Consequence:
  - reports are excellent for debugging, but easy to overshare when sent off-machine.
  - this remains a privacy and report-size risk until we split "debug rich" and "share-safe" modes or add stronger redaction/budgets.

### CRR-050 High: endpoint readiness still begins from plain TCP listen checks

- Area:
  - `src/qq_data_integrations/napcat/diagnostics.py`
  - `src/qq_data_integrations/napcat/runtime.py`
  - `src/qq_data_integrations/napcat/bootstrap.py`
- Problem:
  - bootstrap/runtime readiness still starts from "can connect to the port" instead of validating protocol identity first.
- Consequence:
  - if another process is bound to the expected port, the runtime can be treated as ready or already started when it is not actually NapCat.

### CRR-051 High: bootstrap can still start one runtime and later bind follow-up work to another discovered tree

- Area:
  - `src/qq_data_integrations/napcat/bootstrap.py`
  - `src/qq_data_integrations/napcat/settings.py`
- Problem:
  - `ensure_endpoint()` refreshes settings multiple times after startup/configure actions instead of pinning the exact runtime/workdir/config tree it just operated on.
- Consequence:
  - on machines with multiple plausible NapCat trees, the flow can still degenerate into "start A, configure or probe B".

### CRR-052 Medium: watch older-history loading still runs synchronously on the UI/event-loop thread

- Area:
  - `src/qq_data_cli/watch_view.py`
- Problem:
  - loading older history still calls sync gateway history fetch directly from the watch UI path.
- Consequence:
  - slow pages can freeze input and live updates, creating "the UI looks dead" behavior even though the process is still working.

### CRR-053 Medium: realtime notice routing still relies on heuristic private-chat inference

- Area:
  - `src/qq_data_integrations/napcat/realtime.py`
- Problem:
  - notice events without `group_id` are still classified as private using permissive field guessing across `peer_id/user_id/sender_id/target_id`.
- Consequence:
  - edge-case notice payloads can still leak unrelated private events into the active watch session.

### CRR-054 Medium: reply semantics are still underrepresented in normalized text output

- Area:
  - `src/qq_data_core/normalize.py`
  - `src/qq_data_core/export_selection.py`
- Problem:
  - top-level reply segments still contribute very little human-readable text to `content` / `text_content`.
  - nested forward replies are now preserved structurally, but reply preview text is still not consistently surfaced in exported plain text.
- Consequence:
  - text exports can still lose conversational context even when the underlying payload carries a usable reply preview.

## Review Backlog

## Recent Mitigations In Current Branch

- Session-scoped export degradation state is now reset per export via gateway/provider/downloader reset hooks.
- `history bounds` cache now has a TTL instead of persisting indefinitely across long sessions.
- `startup_capture` no longer reads whole log files just to tail them, and `/status` now forces a refresh instead of showing stale startup-only state.
- Invalid `--format` values now fail fast instead of silently falling back to JSONL.
- `watch` exports now use a fresh `NapCatGateway` instead of sharing the live watch gateway across threads.
- Endpoint bootstrap no longer rewrites OneBot config unless `NAPCAT_AUTO_CONFIGURE_ONEBOT=1` is explicitly enabled.
- Directory metadata cache now has freshness handling instead of unbounded reuse.
- WebSocket watch no longer retries forever without ever surfacing a decisive failure.
- Output filenames for exports, traces, forensics, startup captures, launcher wrappers, and CLI logs now use microsecond+pid tokens to avoid same-second collisions.
- JSONL/TXT exporters now stream to temp files and use atomic replace semantics instead of writing directly to the final target path.
- Latest CLI log tracking now uses a validated `latest.path` pointer instead of multiple processes sharing one `cli_latest.log`.
- QQ root discovery now uses a short process-local cache to reduce repeated expensive scans within the same CLI session.
- NapCat workdir detection now recognizes account-scoped `onebot11*.json` / `napcat_protocol*.json` layouts, reducing false negatives on real runtimes.
- Config candidate search is now constrained to the project/runtime tree instead of drifting up parent directories.
- `include_raw=True` payloads are now detached snapshots instead of live references to mutable source message dicts.
- `/export` date highlighting and rollover now operate on whole tokens instead of matching timestamp-like substrings inside unrelated arguments such as `--out` paths.
- NapCat runtime wrapper pruning no longer contains a latent `NameError` on `suppress(...)`.
- `startup_capture` now includes settings-resolution diagnostics so misbound NapCat/workdir/config selections are inspectable instead of opaque.
- `include_raw=True` now stores a detached copy of the source message so later in-process mutation cannot rewrite previously captured debug/raw views.
- chat type normalization is now strict at CLI, gateway, and fast-history boundaries instead of silently coercing unknown values to `private`.
- media download cleanup now fences executor shutdown/rebuild and uses process-scoped cache directories to reduce cross-export cleanup races.
- HTTP and fast-history clients now fail closed on missing success markers instead of treating underspecified payloads as successful responses.
- `--state-dir` now applies to startup logging and startup capture initialization instead of only affecting later export artifacts.
- fast-history auth headers are now resolved lazily on first real request, so constructing a gateway no longer authenticates to WebUI up front.
- naive ISO timestamps are now interpreted in the export timezone explicitly, and normalized snapshot metadata is deep-copied instead of shallow-copied.
- export content summaries now report kept/source segment ratios, and forward top-level text prefers `detailed_text` over preview-only collapse.
- diagnostics no longer fabricate a fake reachable `/health` route when fast-history capabilities probing fails.
- QQ media root discovery now enumerates the machine's actual mounted Windows drive roots instead of assuming only `C:` through `G:`.
- explicit relative config env paths no longer drift with the current working directory; they resolve against the runtime base/project tree only.
- NapCat runtime root and workdir autodiscovery now choose the highest-scoring runtime candidate instead of relying on first-match ordering.
- REPL target completion priming now uses TTL/cooldown timing instead of permanently treating stale cached targets as freshly primed after a failed refresh.
- REPL and watch command parsing now reject unknown `--options` instead of silently ignoring typos, and REPL command failures log full traceback context before the friendly message.
- watch export no longer clears the shared live-watch gateway on failure, and watch shutdown now waits for in-flight exports instead of pretending thread-backed exports were cancelled.
- watch shutdown now also waits for in-flight older-history background loads instead of cancelling only the coroutine wrapper while the underlying `to_thread` fetch keeps running.
- media downloader remote/public-token prefetch caches are now guarded by an explicit lock instead of naked cross-thread dict mutation.
- fixture export now uses `settings.state_dir / media_index` instead of hard-coded `./state/media_index`.
- normalization now prefers richer exporter `rawMessage.elements` over weaker OneBot `message` lists when both exist, sorts snapshots deterministically, and uses the snapshot export time as the fallback timestamp source.
- forward node normalization now prefers `text_content` over tokenized `content`, and keeps nested `reply_to` in the forward node payload.
- profile rebuild now deep-copies metadata and rebuilt messages, reducing cross-snapshot nested-state bleed.
- `startup_capture` now defaults to a share-safe mode with reduced log tail, reduced env capture, QQ root summaries instead of full snapshots, and hidden `hostname/username`; `STARTUP_CAPTURE_MODE=debug` restores the richer payload when needed.
- share-safe `startup_capture` now also masks `argv`, `cwd`, startup/log paths, settings-resolution diagnostics, path matrices, and config/plugin path details instead of leaking full local filesystem paths by default.
- share-safe `startup_capture` log tails now also scrub `file:///D:/...` and Windows absolute path fragments out of stack traces instead of only masking the log filename fields.
- explicit `NAPCAT_ONEBOT_CONFIG` / `NAPCAT_WEBUI_CONFIG` paths now fail fast if the pointed file does not exist, instead of silently falling back to guessed defaults.
- runtime/workdir autodiscovery now only auto-selects a uniquely highest-scoring candidate; ties are surfaced in settings diagnostics instead of silently choosing one tree.
- endpoint probes now distinguish transport-level listening from protocol identity and protocol readiness; a plain HTTP service on the expected port is no longer treated as NapCat.
- `onebot_http` protocol probing now has a read-only `/get_status` fallback, so variants whose root route does not self-identify still get recognized without mutating runtime state.
- runtime bootstrap now pins `NAPCAT_DIR` / launcher / workdir / config env vars to the active tree after successful identification or launch, reducing “start A, configure B” drift.
- `napcat_logs/latest.path` is now only written after a successful launcher spawn, and reads remain restricted to the `state/napcat_logs` directory.
- watch-mode “load older history” now fetches data off the UI thread and only ingests/upgrades UI state back on the main thread, reducing apparent freezes on slow pages.
- realtime private notice routing is now narrowed to high-confidence notice types/fields instead of permissive `peer_id/user_id/sender_id/target_id` guessing.
- reply segments now preserve and surface reply preview text into normalized `content` / `text_content`, so plain-text exports retain more conversational context.
- time-expression parsing, completion, and `/export` date tooling now share the same strict zero-padded literal contract; non-canonical literals fail fast instead of being accepted by the backend while the interactive tooling ignores them.
- startup capture is now split into a fast startup-profile capture and a heavier full refresh path; normal CLI startup no longer blocks on QQ root discovery, endpoint probing, config snapshots, or log tail collection.
- QR login output now always writes a root-level `qq_login_qr.png` image in addition to terminal rendering, so CMD-only environments can open the image file directly to scan.

### CRR-063 High: remote URL download layer needs strict async isolation

- **Area:** `src/qq_data_integrations/napcat/media_downloader.py` (download cache/future maps) plus `media_bundle.py` progress paths.
- **Problem:** converting remote URL downloads to an asyncio backend introduces a new event loop and AsyncClient that share caches/future tables with the synchronous exporter and watch threads. Without careful ownership, cleanup can delete cache directories while async tasks are still writing, AsyncClient closure can happen on the wrong loop, and shared dictionaries can be mutated concurrently.
- **Consequence:** duplicates downloads, corrupted or missing cache entries, unclosed network sessions, or repeated cancellations that never complete.
- **Next steps:** keep the async loop inside a downloader-owned background thread, have async tasks only emit `(cache_key, result)` to a synchronous `_store_remote_prefetch_result(...)` helper, and enforce a drain-style cleanup sequence (stop accepting tasks, wait for outstanding downloads, close AsyncClient on its loop, then clear caches) before allowing new exports.
- **Validation:** run `app.py export-history group 922065597 --limit 300` with `--strict-missing collect` to ensure cached downloads still fire and `cleanup_remote_cache()` no longer races with pending tasks; inspect logs for AsyncClient lifecycle warnings and ensure no `RuntimeError: Event loop is closed` occurs.

### CRR-064 Medium: download assets need a separate progress queue

- **Area:** `src/qq_data_core/media_bundle.py`, `src/qq_data_cli/repl.py`, `src/qq_data_cli/watch_view.py`
- **Problem:** the existing single progress channel currently combines media prefetch, materialization, and remote downloads. As download concurrency increases, this channel either gets overwhelmed by per-URL noise or fails to surface downloads in progress.
- **Consequence:** CLI progress becomes misleading (asset counts advance while network downloads are still outstanding), the trace log lacks explicit download lifecycle data, and watchers cannot see queued or failed downloads separately.
- **Next steps:** add a `download_assets_*` phase family with `stage` values like `start`, `progress`, `complete`, carrying fields `download_total`, `download_started`, `download_active`, `download_completed`, `download_failed`, `download_cached`. Update CLI and watch progress renderers to display this second line under the main export line so download progress is visible without flooding the main trace.
- **Validation:** run export commands with asserts under `--strict-missing collect` to confirm the downloader emits both `download_assets` and `materialize_assets` events, confirm REPL/watch show two progress lines, and inspect traces for the new phase markers with cached vs fetched breakdowns.

### CRR-065 Field-confirmed: the 19 friend-side `file/video` missings are genuinely expired resources

- **Area:** targeted retest / friend-environment validation for group `751365230`
- **Observed behavior:**
  - The friend machine can see a cover/thumbnail and a download button for these assets inside QQ.
  - Clicking the button does not recover the file; QQ reports that the resource is expired.
- **Consequence:**
  - These `19` missing assets should currently be treated as truly unavailable/expired on the friend machine.
  - Re-running broad time-window retests is unlikely to recover them unless the upstream QQ/NapCat resource state changes.
- **Operational implication:**
  - Do not keep interpreting this set as proof that the exporter is still missing an obvious recovery path.
  - Focus future retest work on reducing noise/cost and on narrow asset-level diagnosis, not on assuming these specific assets are still recoverable.

### Next sweep order

1. `src/qq_data_cli/completion.py` / `completion_runtime.py` / `terminal_compat.py`
   - interactive state and fallback behavior
2. `src/qq_data_core/time_expr.py`
   - expression parsing edge cases that can silently pick wrong intervals
3. `src/qq_data_core/exporters/*`
   - output consistency and partial-write boundaries
4. `src/qq_data_integrations/napcat/websocket_client.py`
   - reconnect semantics under long-running watch sessions
5. selective raw-vs-normalized message comparisons
   - verify where flattening is helpful vs destructive

## Working rule

- Do not fix these items immediately just because they are listed.
- First keep expanding this register until the failure surface is clear enough.
- Then prioritize by:
  - blast radius
  - likelihood
  - recoverability
  - remote test cost
