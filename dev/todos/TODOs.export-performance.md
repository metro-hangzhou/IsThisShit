# Export Performance TODOs

Spec baseline: 2026-03-07

This file is dedicated to export-speed analysis and fixes. It is separate from the main `TODOs.md` so performance work does not get buried under feature tasks.

## Problem Statement

Observed user-facing symptom:

- Full-history export for `group 922065597` completed, but `11999` records and roughly `1400 KB` of TXT output still took several minutes.
- The current throughput is not acceptable for developer use.
- The CLI now shows progress, but the export is still too slow.
- A deeper NapCat-side path is now under active evaluation instead of only tweaking public OneBot action flags.

## What We Know Now

### Live measurements from the current codebase

- Latest-page fetch, `count=200`:
  - NapCat fetch: about `0.81s`
  - local normalize: about `0.005s`
  - local TXT write: about `0.003s`
- Sequential page fetch timings, `count=200`:
  - page 1: `0.715s`
  - page 2: `0.404s`
  - page 3: `0.617s`
  - page 4: `0.332s`
  - page 5: `3.29s`
- Full-history progress sample:
  - page 1 -> `199` records, earliest around `2025-10-02`
  - page 2 -> `397` records, earliest around `2025-09-28`
  - page 3 -> `595` records, earliest around `2025-09-25`
- Real full-history export in watch mode:
  - `11999` unique records
  - `221.6s`
  - `127` pages
  - `0` timeout retries
- Fixed-size benchmark, public API only, `count=200` without adaptive backoff:
  - `12060` raw page records
  - `232.9s`
  - `62` pages
- Public-API micro-benchmark over the first 10 pages:
  - default profile: `26.48s`
  - `quick_reply=true`: `25.11s`
  - gain is only about `5%`
- Throughput by adaptive page size from the real perf trace:
  - `200/page`: about `106.7 msgs/s`
  - `150/page`: about `113.2 msgs/s`
  - `100/page`: about `57.1 msgs/s`
  - `50/page`: about `26.0 msgs/s`
- Live benchmark after adding the raw-history plugin:
  - public OneBot, first 10 pages at `200/page`: `1990 msgs / 17.56s`, about `113.33 msg/s`
  - fast plugin, first 10 pages at `200/page`: `1991 msgs / 1.39s`, about `1429.39 msg/s`
  - fast plugin full export, same group: `12000 msgs / 8.33s` end-to-end including normalize + TXT write
  - benchmark artifact: [deep_history_benchmark_20260307_161612.json](../../state/export_perf/deep_history_benchmark_20260307_161612.json)
  - fast export artifact: [benchmark_fast_group_922065597.txt](../../exports/benchmark_fast_group_922065597.txt)

Conclusion:

- Python-side normalization and TXT writing are negligible.
- The main bottleneck is NapCat history paging itself.
- The cost is page-dependent and spikes on some pages.
- Adaptive backoff is not the dominant cause of slowness. It is slightly faster than fixed `200/page`, but the total wall time is still dominated by NapCat page fetch cost.
- `quick_reply=true` does not appear large enough to deliver an order-of-magnitude improvement by itself.
- The first change that actually produces an order-of-magnitude improvement is skipping public `parseMessage(...)` entirely through a NapCat-side slim raw-history plugin.

### NapCat source-level evidence

In NapCat's public history actions, each history page does all of the following before returning:

- raw history fetch via `MsgApi.getMsgHistory` / `getAioFirstViewLatestMsgs`
- message ID conversion
- `parseMessage(...)` for every message in the page

That means exporter speed is bounded mostly by NapCat's per-message parse cost, not by local file output.

Relevant public action parameters confirmed from NapCat source:

- `disable_get_url`
- `parse_mult_msg`
- `quick_reply`

The current exporter already uses:

- `disable_get_url=true`
- `parse_mult_msg=false`

These reduce avoidable URL resolution and merged-forward expansion, but do not remove reply-resolution cost.

### Likely remaining heavy path

NapCat still performs reply parsing for history messages.

For old-client reply messages, NapCat source shows multiple fallback lookups and warning/error logs such as:

- `似乎是旧版客户端，尝试仅通过序号获取引用消息`
- `所有查找方法均失败，获取不到旧客户端的引用消息`

These lookups are server-side work inside NapCat's history action and are very likely a major contributor to slow pages.

## Current Mitigations Already Implemented

- [x] Explicit datetime intervals no longer scan full history for bounds first.
- [x] `@final_content @earliest_content` full-history export now uses a single history pass instead of two.
- [x] Watch-mode export now reports progress instead of staying at `Export started...`.
- [x] History paging now guards against anchor cycles instead of only checking the immediately previous anchor.
- [x] History requests now default to `disable_get_url=true`.
- [x] History requests now default to `parse_mult_msg=false`.
- [x] Added a NapCat-side raw-history plugin path that skips public OneBot `parseMessage(...)` for bulk export.

These were necessary, but they are not sufficient.

## Root-Cause Assessment

Priority-ordered causes:

1. NapCat history export is inherently serial.
   Each page depends on the previous page's oldest `message_seq`, so page fetches cannot simply be parallelized.

2. NapCat parses every message into OneBot format before returning the page.
   This is much slower than local normalization and file writing.

3. Some pages contain reply/voice-heavy messages that trigger much slower server-side paths.
   The page-latency spread already proves this.

4. Full-history TXT export currently waits for the whole snapshot before writing the final file.
   This hurts time-to-first-output and makes the export feel slower than it is.

5. The current system has almost no durable performance telemetry.
   We can see progress in the UI, but we are not yet recording which pages are slow and why.

Updated assessment:

- For bulk export, the real bottleneck is specifically the public OneBot history action path.
- Once that path is bypassed with a NapCat-side slim raw-history plugin, end-to-end export drops from minutes to single-digit seconds on the tested group.

## Fix Plan

### P0. Instrumentation First

- [x] Add structured per-page timing capture for export runs.
- [x] Persist a small perf trace in `state/export_perf/`:
  - target chat ID
  - requested mode
  - page index
  - page size
  - page fetch duration
  - oldest/newest timestamps in that page
  - collected message count so far
- [x] Show live throughput in watch export:
  - `pages`
  - `records`
  - `records/sec`
  - elapsed seconds
- [x] Add final trace path and perf summary to export completion output.
- [x] Surface timeout-driven page-size retries to the user instead of hiding them.
- [ ] Show a slow-page warning when a single page exceeds a threshold such as `3s`, `5s`, `10s`.
- [x] Distinguish QQ-expired old-image misses from generic `missing_after_napcat` in manifests and compact summaries.
  - live probe after this change:
    - [debug_probe_group_922065597_20260314_195933_pagesize500_full.json](../../state/export_perf/debug_probe_group_922065597_20260314_195933_pagesize500_full.json)
    - `229` total missing assets
    - `134` are now `qq_expired_after_napcat`
    - `95` remain generic `missing_after_napcat`
  - timing moved only slightly:
    - `materialize_progress_window_s`: `63.43s -> 62.27s`
  - current interpretation:
    - semantic visibility improved a lot
    - raw wall-clock improvement is limited because the remaining `95` misses are concentrated in other residual buckets (`2026-01 emoji-recv`, `2025-12`, `2026-02`) that still pay full NapCat miss cost
  - latest post-fix large-tail CLI rerun:
    - [group_922065597_20260314_215230.manifest.json](../../exports/group_922065597_20260314_215230.manifest.json)
    - `record_count = 2000`
    - `missing = 172`
    - `qq_expired_after_napcat = 169`
    - `missing_after_napcat = 3`
  - latest stale-forward follow-up rerun:
    - [group_922065597_20260314_220705.manifest.json](../../exports/group_922065597_20260314_220705.manifest.json)
    - `record_count = 2000`
    - `missing = 172`
    - `qq_expired_after_napcat = 172`
    - `missing_after_napcat = 0`
  - practical implication:
    - perf work on this slice should no longer focus on unresolved recovery for old images
    - the next worthwhile investigations are UX/reporting improvements and faster early-stop behavior for very large expired tails
  - later root-REPL trace evidence refined the actual stall source:
    - [root_export_group_922065597_20260314_223522.jsonl](../../state/export_perf/root_export_group_922065597_20260314_223522.jsonl) showed a `60.1251s` stall on step `401`, file `3BE10FA97950F66D11876F8E815A763C.gif`
    - after skipping plugin `/hydrate-forward-media` for stale blank-source forwarded images already known to be expired-like, rerun [root_export_group_922065597_20260314_224143.jsonl](../../state/export_perf/root_export_group_922065597_20260314_224143.jsonl) reduced:
      - total export elapsed from `86.75s` to `27.266s`
      - slowest materialization step from `60.1251s` to `1.6836s`
    - interpretation: that large perceived stall was a stale forward-route timeout, not broad local-cache search

### P1. Adaptive Paging

- [x] Stop treating page size as fixed.
- [x] Add adaptive page sizing:
  - start with `200`
  - increase when pages are consistently fast
  - decrease when a page becomes slow or times out
- [x] On timeout, retry the same anchor with a smaller page size before failing the whole export.
- [x] Record the chosen page-size transitions in perf traces.
- [x] Ensure root CLI `app.py export-history --limit N` also uses cross-page tail fetch when `N > 200`.
- [x] Persist per-asset materialization timing in root export perf traces so a "stuck at 399/564" report can be mapped to a concrete asset and resolver.

Why:

- Some pages are clearly pathological.
- A smaller retry page may isolate one expensive message cluster without stalling the whole export.
- Current evidence says adaptive paging helps a little, but does not solve the dominant bottleneck.

### P2. Reply Parsing Fast Path Evaluation

- [ ] Benchmark `quick_reply=true` on history export pages.
- [ ] Compare:
  - latency
  - remaining NapCat warnings
  - reply fidelity
- [ ] If the reply fidelity drop is acceptable for export, introduce a `fast_history` profile that enables `quick_reply=true`.

Important note:

- This probably will not remove all old-client reply warnings.
- It still may reduce the work NapCat performs when resolving replies.
- Current early sample suggests the benefit is real but small, roughly `5%` over the first 10 pages.

### P3. Deeper NapCat Path

- [x] Prototype a NapCat-side plugin that exposes a slim raw-history endpoint.
- [x] Add Python-side fast-history client and fallback logic.
- [x] Benchmark the plugin against the public OneBot history action on the same live group.
- [ ] Productize plugin lifecycle management:
  - auto-detect plugin availability
  - optionally auto-enable / reload if runtime permits
  - surface active history source in CLI export summaries

### P4. Streaming Output

- [ ] Add streaming JSONL export so records are flushed page-by-page instead of after the full snapshot is collected.
- [ ] For TXT export, switch to a two-stage pipeline:
  - stage 1: export or cache normalized records incrementally
  - stage 2: render TXT from the normalized store
- [ ] Show the path of the partial output immediately when export begins.

Why:

- Even if total wall time is unchanged, time-to-first-artifact becomes much better.
- Resume support becomes simpler.

### P5. Separate Fast Mode From Rich Mode

- [ ] Define two export profiles:
  - `fast`
  - `rich`
- [ ] `fast` profile should prefer lower server-side cost:
  - `disable_get_url=true`
  - `parse_mult_msg=false`
  - evaluate `quick_reply=true`
  - no raw payload export
- [ ] `rich` profile can keep slower metadata paths when explicitly requested.
- [ ] Make watch-mode `/export` default to `fast`.

### P6. Cancellation, Resume, and Checkpoints

- [ ] Add `/export --resume`.
- [ ] Persist last successful page anchor and accumulated output metadata.
- [ ] Allow cancellation from watch mode without losing completed pages.
- [ ] Resume from the last known oldest anchor instead of restarting the entire export.

### P7. Richer UX For Long Exports

- [ ] Add a progress line that includes ETA estimation.
- [ ] Add a final perf summary:
  - total pages
  - total records
  - total wall time
  - average page time
  - slowest page time
- [ ] Surface timeout-retry events to the user instead of silently waiting.

## Non-Default Escalation Path

Only if the current plugin-assisted path hits a hard ceiling:

- [ ] Evaluate a NapCat-side helper path that exposes cheaper history payloads without full OB11 parse costs.
- [ ] Evaluate direct local message-store reading if a stable QQNT local storage source exists and the project is willing to relax the "NapCat public interface only" rule for bulk export.

This is intentionally not the default plan because it weakens the current "public interface only" architecture rule.

## Acceptance Targets

Targets for the current user workload:

- [ ] Full-history export of the `922065597` group should sustain a clearly visible progress cadence.
- [ ] No long silent period should exceed `5s` without a progress update.
- [ ] Full-history TXT export should feel materially faster than manual scrolling and copy.
- [ ] Single-page `count=200` fetch should stay near the current sub-second baseline on healthy pages.
- [ ] Slow pages should degrade gracefully by shrinking page size instead of stalling the whole export.

## Remember This

- The decisive speedup came from inserting a NapCat runtime plugin, not from Python-side micro-optimization.
- Plugin location:
  - [NapCat/napcat/plugins/napcat-plugin-qq-data-fast](../../NapCat/napcat/plugins/napcat-plugin-qq-data-fast)
- Enable file:
  - [NapCat/napcat/config/plugins.json](../../NapCat/napcat/config/plugins.json)
- Python-side entry points:
  - [fast_history_client.py](../../src/qq_data_integrations/napcat/fast_history_client.py)
  - [provider.py](../../src/qq_data_integrations/napcat/provider.py)
  - [gateway.py](../../src/qq_data_integrations/napcat/gateway.py)
- If future exports become slow again, first verify whether the runtime plugin is still loaded before tuning Python code.

## Recommended Next Implementation Order

1. Productize the fast plugin path in CLI summaries and runtime checks.
2. Add streaming JSONL and staged TXT rendering.
3. Add resume and checkpoint support.
4. Re-evaluate `quick_reply=true` only for fallback public-history mode.
