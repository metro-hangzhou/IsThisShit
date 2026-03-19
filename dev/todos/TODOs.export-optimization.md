# Export Optimization TODOs

## Goal

Make export faster and more correct without increasing remote testing cost.

## Current baseline

- Done: early remote URL prefetch for `image/file/video/speech`
- Done: token-only payload prefetch
- Done: split pools for token exchange and remote download
- Done: basic auto worker sizing from machine + request scale
- Known remaining pain:
  - export path collisions for same-named assets across buckets/months
  - stubborn forward assets still need dedicated treatment
  - repeated dead token / dead URL attempts should short-circuit earlier
  - benchmark comparison is still too manual

## Batch 1: Correctness First

- [x] Fix exported relative path collisions for `stale_source_neighbor` and other same-name assets.
- [ ] Canonicalize same-content asset duplicates during export so multiple references/index entries can point to one physical file.
  - Field note from `group_751365230` export:
    - Many image files share the same logical stem and are exported as `stem.jpg`, `stem_<hash>.jpg`, etc.
    - In almost all sampled cases these suffixed variants are byte-identical duplicate copies.
  - Current local testdata confirmation:
    - The derived local dataset for `shi_group_751365230` contains `270` aligned image references and `5 video + 1 file` true missing assets.
    - The aligned image side is therefore a good ground-truth set for validating same-content dedup behavior without mixing in source-expired file/video noise.
  - Desired behavior:
    - Keep all message/asset references and provenance.
    - Store only one on-disk payload for same-content duplicates.
    - Let manifest / index / exported_rel_path reuse a single physical file path instead of writing duplicate bytes repeatedly.
    - Treat “same content, many references” as a storage/layout optimization, not as permission to collapse distinct message-asset edges.
  - Important exception:
    - Rare same-stem variants can still be different content/versioned payloads.
    - Dedup must be by actual file content identity, not by stem alone.
  - Implementation guardrails:
    - Physical-file dedup must happen after content identity is known, not from `file_name` alone.
    - Multiple references may still need distinct manifest/index rows even when they share one exported file.
    - Reused path decisions must remain provenance-safe:
      - keep `source_message_id`
      - keep `source_asset_key`
      - keep per-reference status/note fields
    - Missing/expired assets must never be “deduped into success” by borrowing another reference's live file.
    - Same-content reuse should be stable across repeated exports of the same dataset; avoid random winner selection when choosing the canonical physical file.
- [x] Tighten repeated dead URL / dead token outcome sharing so one known-bad remote chain does not keep paying full cost.
- [x] Extend early prefetch coverage for stubborn forward asset payloads, not just the easy image path.
- [ ] Review missing classification so recovered/expired paths do not emit misleading forensic noise.
- [ ] Clear or age out session-scoped bad-token state between exports.
  - Current risk: `_known_bad_public_tokens` survives across repeated exports in one REPL session.
  - Consequence: one transient `token -> known_missing` classification can poison later exports after relogin/manual download/NapCat recovery.
- [ ] Reset or re-probe media fast-route disable flags per export instead of per process.
  - Current risk: `_fast_context_route_disabled` is set once and then suppresses `/hydrate-media` for the rest of the REPL session.
  - Consequence: one temporary route outage can silently degrade all later exports to slower/weaker paths until CLI restart.

## Batch 2: Scheduler And Throughput

- [ ] Keep three-stage scheduling explicit:
  - local path/cache fast path
  - public token exchange
  - remote URL fetch
- [ ] Keep NapCat interaction low-concurrency and bounded.
- [ ] Continue improving auto worker selection from:
  - CPU count
  - current prefetchable asset count
  - token-only pressure
  - remote hit / error ratio
- [ ] Consider lightweight runtime feedback tuning instead of one-shot worker guessing.
- [ ] Make worker auto-tuning genuinely feedback-driven.
  - Current risk: `feedback` is collected and emitted into trace, but worker sizing still ignores it.
  - Consequence: "adaptive" behavior is weaker than it appears and may choose poor defaults on friend machines.

## Batch 3: Forward-Specific Hardening

- [ ] Add stronger duplicate suppression for old forward expansion failures.
- [ ] Extend token/remote prefetch logic to forward `video/file` stubborn cases.
- [ ] Keep forward failure reasons isolated from ordinary image expiry to avoid mixing root causes.
- [ ] Keep page-scan forward expansion lightweight; avoid deep forward parsing during scan when final enrichment can do it later.
- [ ] Scope forward failure suppression so one bad chat/message family does not globally degrade forward enrichment.
  - Current risk: `_disable_parse_mult_forward_hydration`, `_known_unavailable_forward_ids`, and `_known_unavailable_history_keys` live for the whole gateway session.
  - Consequence: a burst of old-forward failures in one export can suppress useful forward recovery in later unrelated exports until REPL restart.
- [ ] Re-probe fast history availability after temporary failures.
  - Current risk: `_fast_available` / `_fast_tail_bulk_available` flip to `False` after a transient failure and stay there.
  - Consequence: later exports may silently fall back to HTTP even if the fast plugin recovered.

## Batch 4: Benchmark Harness

- [x] Add a repeatable benchmark command/script for local comparison.
- [x] Record:
  - elapsed time
  - copied / reused / missing
  - slowest materialize step
  - selected worker counts
  - key substep counters
- [x] Make before/after comparison cheap enough to run every optimization pass.
- [ ] Add a targeted file/video retest harness for friend environments.
  - Input: latest export manifest.
  - Behavior: cluster only missing `file/video` assets by timestamp, rerun narrow time windows, and capture per-strategy logs/results.
  - Goal: avoid repeated 500s full-history re-exports when only a few `get_file` timeout cases need diagnosis.
  - Field note from friend machine:
    - The current `19` missing `file/video` assets in group `751365230` were manually checked in QQ.
    - They show a cover/thumbnail and a download button in the UI, but clicking download reports that the resource is expired.
    - Treat these as genuinely expired/unavailable assets, not as evidence that the retry harness simply has not tried hard enough.

## Ground truth notes from local `shi_group_751365230` testdata

- This extracted local test set currently represents:
  - `270` image references fully aligned and locally usable
  - `5` video references missing because the upstream resource is expired
  - `1` file reference missing because the upstream resource is expired
- For exporter optimization work, this means:
  - image-side duplicate storage/path reuse can be optimized aggressively but conservatively
  - `5 video + 1 file` should not be used as a success-recovery target in dedup benchmarks
  - those six items should instead remain classification/regression fixtures for `expired` handling

## Batch 5: CLI Startup Capture And Debugging Ergonomics

- [ ] Split startup capture into light-at-start and heavier follow-up evidence.
  - Current risk: every `start_cli` pays QQ root discovery, nested snapshots, config snapshots, storage probes, and log tail capture up front.
  - Consequence: startup latency grows with environment size and becomes its own source of friction.
- [ ] Tail logs without reading full files into memory.
  - Current risk: `_tail_text()` reads the entire CLI/NapCat log file and only then slices the last lines.
  - Consequence: very large logs can create avoidable startup overhead and memory churn.
- [ ] Refresh startup capture after login / endpoint-ready transitions.
  - Current risk: startup capture is memoized once per CLI session.
  - Consequence: if CLI starts before NapCat/QQ is fully ready, the saved report can stay stale for the entire session and mislead debugging.

## Batch 6: Long-Lived Session State Review

- [ ] Audit all gateway/provider/downloader caches for "disable until restart" behavior.
  - Focus:
    - `_history_bounds_cache`
    - `_fast_available`
    - `_fast_tail_bulk_available`
    - `_disable_parse_mult_forward_hydration`
    - `_known_bad_public_tokens`
    - `_fast_context_route_disabled`
- [ ] Revisit history bounds caching for long-lived REPL/watch sessions.
  - Current risk: bounds cache key only uses `(chat_type, chat_id, need_earliest, need_final)`.
  - Consequence: interval exports that depend on latest/earliest content can use stale bounds after new messages arrive in the same session.

## Execution order

1. Batch 1 correctness
2. Batch 2 scheduler tuning
3. Batch 3 forward hardening
4. Batch 4 benchmark harness
