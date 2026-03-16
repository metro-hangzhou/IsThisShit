# Production Review TODOs

Spec baseline: 2026-03-14

This file tracks third-party CodeStrict review follow-ups: issues, likely large-scale risks, and hardening work that should happen before or during external tester rollout.

See also:

- [CodeStrict_AGENTs.md](../agents/CodeStrict_AGENTs.md)
- [TODOs.export-performance.md](TODOs.export-performance.md)
- [TODOs.export-forensics.md](TODOs.export-forensics.md)
- [NapCat.media_AGENTs.md](../agents/NapCat.media_AGENTs.md)

## Current Review Findings To Harden

### P0. Unknown Missing Must Escalate

- [ ] Stop treating unexplained or weakly-explained `missing` outcomes as normal successful completion.
- [ ] Define the strict production rule:
  - known-expired and clearly-justified missing may continue
  - unknown or contradictory missing should raise a high-severity diagnostic incident
- [ ] Add a strict mode family that supports:
  - collect-all incidents in one run
  - abort-on-first
  - abort-after-threshold
- [ ] Make collect-all the preferred external-tester mode so one scarce remote run can expose multiple unrelated failure families.
- [ ] Write a bounded forensic bundle on those failures instead of asking testers for the whole `state/` directory.
- [ ] Capture enough local directory/path evidence to prove or disprove path-based assumptions.

Why:

- a production reviewer should not have to guess whether a suspicious missing is acceptable
- if the exporter cannot explain a missing asset well enough, that is itself a failure mode
- but first-failure abort is not always the right default when remote test opportunities are scarce

### P0. Batch Failure Domain

- [x] Split `prepare_for_export()` prefetch into bounded chunks instead of one request for the whole export.
- [x] Record chunk count and chunk size in perf traces.
- [ ] If one chunk fails, keep the rest of the chunks usable instead of silently losing the whole prefetch benefit.
- [ ] Emit one scoped warning when batch prefetch degrades for the current process.

Why:

- one giant `hydrate_media_batch` request is a likely production cliff on very large exports
- current behavior can silently fall back to slower per-asset work

### P0. Bulk Tail Failure Domain

- [x] Define a safe ceiling for one plugin `/history-tail-bulk` request instead of assuming one huge `data_count` should always map to one huge plugin call.
- [x] For very large requested tails, split provider fetch into multiple bulk chunks and merge them deterministically.
- [x] Make bulk-tail degradation chunk-scoped so one oversized/failing bulk call does not throw away the whole tail-speed benefit.
- [ ] Keep improving bulk-route timing metadata so traces can distinguish:
  - Python wall time
  - plugin internal scan time when available
  - whether the fetch completed in one chunk or multiple chunks

Why:

- current bulk-tail route is faster on real `2000`-message samples
- but it also concentrates timeout, response-size, and plugin-work risk into one larger failure domain

### P0. Non-REPL CLI Observability

- [x] Add perf trace writing to `app.py export-history`, not only root `/export`.
- [x] Surface trace path in CLI completion output for packaged tester runs.
- [x] Add progress callback support to `app.py export-history` fetch/write path.
- [x] Keep the output compact, but never hide the trace path.

Why:

- remote testers will often use `export-history`, not the maintainer REPL
- current observability mismatch makes remote diagnosis harder than it should be

### P1. Export Memory Profile

- [x] Remove one full duplicate `_iter_asset_candidates()` traversal from `materialize_snapshot_media()` by reusing a single staged candidate-entry list for prefetch and materialization.
- [x] Avoid building one giant `prefetch_requests` list in `materialize_snapshot_media()`; prefetch payloads are now built chunk-by-chunk.
- [ ] Consider a streaming or chunked asset-materialization design.
- [ ] Stop treating the full selected-message tail slice as one always-in-memory unit for very large exports; review chunked snapshot normalization/materialization boundaries.
- [x] Stop building a second full in-memory `assets` JSON payload just to write the manifest; manifest writing now streams asset entries one-by-one.
- [ ] Add a rough memory-usage note or estimate to perf trace output where practical.

Known update:

- [x] Skip legacy-search-context construction entirely in `napcat_only` formal export mode.

Why:

- `10k` may be fine while `100k+` starts to hurt due to repeated whole-export staging

### P1. Duplicate Candidate Traversal

- [x] Remove or reduce the double traversal of `_iter_asset_candidates()`.
- [ ] Confirm forward-heavy exports are not paying unnecessary repeated recursion cost.

Why:

- current structure extracts all asset candidates, then re-extracts them again during materialization

### P1. Route Selection Audits

- [ ] Continue auditing stale/old-bucket route choices for cases where the wrong route costs seconds before failing.
- [ ] Prefer evidence from per-asset traces over intuition.
- [ ] Document every class of route we intentionally skip for old expired-like assets.
- [ ] Centralize second-pass/retry policy by asset family so `image`, `file`, and `video` do not gradually diverge into ad hoc per-branch behavior.
- [x] Stop debug preflight capability collection from probing action routes with empty payloads; use side-effect-free `health` / `capabilities` evidence instead.
- [x] In fast-history snapshots, do not re-enter per-message `parse_mult_msg` forward retries after page-level forward hydration has already run.
- [x] Treat known old-forward `get_forward_msg` fallback failures as a run-scoped unavailable condition so one export run does not keep re-triggering the same low-yield NapCat core fallback noise.

Why:

- the `60s` stale-forward timeout proved route mistakes can dominate export time even when local search is fine

### P1. CLI Target Identity And Operator Ergonomics

- [x] Make blank-like or visually empty target names render in a recognizable way inside CLI target lists, completion popups, and watch/export headers.
- [x] Stop swallowing target-completion lookup failures silently; emit one compact operator-visible clue or a log entry so “empty completion popup” does not hide metadata/lookup errors.
- [x] Review whether numeric-ID direct watch/export should keep bypassing metadata resolution or should attempt a cheap metadata lookup first for better names and early existence feedback.
- [x] Make batch-export failures expose enough per-target context for remote testers to report back without digging through full logs.
- [x] Harden REPL and watch command parsing against unmatched quotes or malformed shell-like tokens so one typo does not crash or visibly destabilize the UI.
- [x] Review generic `error: {exc}` CLI surfaces and replace the scariest ones with recovery-oriented wording plus log/trace pointers where useful.

Why:

- current CLI can successfully resolve targets that are visually hard to distinguish from empty strings
- invisible or nearly-invisible names are a real operator hazard in watch/export flows
- numeric-ID shortcuts are convenient but can hide target mistakes until later runtime failures

### P1. CLI Product Consistency

- [x] Align root `/export`, watch `/export`, and packaged `export-history` on `jsonl` as the default export format.
- [x] Rework `/help` and first-use guidance so they include:
  - concrete examples
  - quote guidance for names with spaces
  - the current default export format
  - the quickest next steps for common tasks

Why:

- users should not have to infer product defaults from trial and error
- command surfaces that describe the same capability should not feel arbitrarily different

### P1. Root REPL Startup Cost

- [ ] Defer `discover_qq_media_roots()` and other legacy/local-search preparation out of root REPL startup unless the current command path actually needs it.
- [ ] Recheck whether startup status lines should explicitly distinguish:
  - shell ready
  - NapCat reachable
  - metadata loaded
  - legacy-local tooling not yet initialized

Why:

- current formal export path is `napcat_only`
- paying legacy/local setup cost before the user has chosen a path weakens startup trust for ordinary users

### P2. Large-Scale Semantic Confidence

- [x] Clamp fast-history tail/page scans to the plugin's real per-page ceiling instead of pretending `500` is usable when the plugin only returns `200`.
- [x] Audit non-plugin bulk-history alternatives and record the current conclusion: no public non-plugin route removes anchor-chained per-page scans; meaningful further speedup would require plugin-side multi-page tail aggregation.
- [x] Implement a fast-plugin bulk recent-tail route and make provider prefer it while preserving automatic fallback to the old per-page path.
- [x] After the next real NapCat restart, live-verify that `/history-tail-bulk` is actually loaded and compare `2000`-message tail-scan wall time against the current per-page baseline.
  - Live note on `2026-03-15`: first route rollout exposed a semantic bug where anchored follow-up pages were requested with the wrong direction flag and the bulk route stalled at `count=200` even when `requested_data_count=2000`; fixed in plugin code by using the same anchored older-page direction as the known-good provider page loop.
  - Live note on `2026-03-15`: current bulk route is live and returns `count=2000`, with end-to-end CLI export dropping from roughly `21.4s` to `15.1s` on the maintainer sample while keeping asset parity with the per-page baseline.
- [x] Audit bulk-tail vs per-page parity on residual old/blank-source image assets.
  - Live note on `2026-03-15`: the first bulk rollout bypassed the old per-page fast-history forward page hydration layer, which dropped `forward_detail_count` from `4` to `2` and caused a tiny expired-image parity drift.
  - Fixed by replaying the existing page-level `parse_mult_msg` forward hydration over the bulk-fetched windows inside Python provider.
  - Post-fix live parity result on group `922065597`, `limit=2000`: asset summaries and manifest asset keys now match the previous per-page fast-history baseline exactly (`copied=264 reused=128 missing=172`).
- [ ] Review `fetch_snapshot_tail()` semantics under very large `data_count`; confirm no ordering/dedupe surprises when pages are unstable.
  - Live note on `2026-03-16`: after adding provider-side bulk chunking plus chunk-scoped fallback, a real `group 922065597 --limit 2600` export completed correctly with `record_count=2600` and metadata `source=napcat_fast_history_bulk+napcat_fast_history`, `bulk_chunks=3`, `bulk_partial_fallback=true`.
  - Interpretation: the bounded chunk design is working and no ordering drift was observed, but the current anchor handoff can still leave a tiny final remainder (`2599/2600`) that triggers one last small chunk attempt before per-page completion. Treat that as a non-blocking optimization target, not a correctness regression.
- [ ] Add one dedicated test for high-count tail export semantics beyond the single-page boundary.
- [ ] Review whether `trim_snapshot_to_last_messages()` can ever mask upstream pagination bugs instead of revealing them.
- [x] Bulk-tail observability still underreports scan cost: `tail_scan` currently records `page_duration_s=0.0` in bulk mode. Add explicit bulk elapsed/internal scan timing so perf traces and CLI output stop showing misleading `page=0.00s`.
- [ ] Audit old private-chat `parse_mult_msg` payload shapes and make sure malformed nested fields (`rawMessage`, `raw_message`, `sender`) cannot crash watch/export flows.

Why:

- count-based export is now correct for `2000`, but scale safety should not rely only on current live samples
- current faster bulk-tail path still needs bounded semantics, not just good maintainer-side wall time

### P2. Remote Support Pack

- [ ] Define the minimum artifacts a tester should return:
  - manifest
  - CLI log
  - perf trace
  - command line used
- [ ] Put that checklist somewhere package-visible in a later share-bundle README update.

Why:

- remote support gets much easier when artifact expectations are explicit

## Accepted Current Assumptions

- Old `qq_expired_after_napcat` assets are currently treated as a product boundary, not an exporter bug.
- Recent-media recovery should remain conservative; do not sacrifice fidelity just to optimize ancient buckets.
- The current main risk axis is now scale/observability, not unknown fidelity failure.
