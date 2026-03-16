# NapCat_AGENTs.md

> Last updated: 2026-03-14
> Scope: NapCat documentation routing, truth-source rules, and repository-level integration decisions.

## Purpose

This file is now the NapCat master index for this repository.

Use it to decide:

- which NapCat sub-handbook to read first
- which statements come from official docs vs upstream source vs community vs maintainer runtime evidence
- which NapCat conclusions are already approved for this repository's exporter/integration stack

Do not keep expanding this file into a giant mixed notebook.

Put detailed material into the dedicated child handbooks below.

## Snapshot And Truth Sources

This handbooks set is a `2026-03-14` snapshot of four evidence layers:

1. `Official docs`
   - `https://napneko.github.io/`
2. `Upstream source`
   - GitHub `NapNeko/NapCatQQ`
   - treat `origin/main` as the upstream code truth source
3. `Community evidence`
   - published GitHub issues
   - published PR metadata / visible discussion
   - published GitHub discussions
4. `Maintainer-side runtime findings`
   - live exporter runs
   - local plugin/runtime debug
   - benchmark traces

Repository rule:

- never blur these sources together
- every high-value claim in NapCat child handbooks should be labeled as one of:
  - `Official doc fact`
  - `Upstream source fact`
  - `Community finding`
  - `Maintainer-side runtime finding`
  - `Unresolved`
  - `Docs do not specify`

## Local Checkout Status

Relevant local paths:

- runtime: [NapCat/napcat](/d:/Coding_Project/IsThisShit/NapCat/napcat)
- upstream checkout: [NapCatQQ](/d:/Coding_Project/IsThisShit/NapCatQQ)
- Git maintenance note: `NapCatQQ/` should remain an independently managed upstream-tracking checkout so future QQ-driven upstream merges can still be applied onto the custom local branch there. Do not collapse it into ordinary parent-repo content just for convenience.

Current local source warning:

- local `NapCatQQ` is on branch `napcat-direct-media-hydration`
- working tree is dirty
- local history is shallow/grafted enough that it must not be treated as a complete upstream-history archive

Implication:

- use local source for architecture reading and file-level implementation truth
- but do not write local experimental edits back into the handbooks as if they were upstream official design

## Current Repository Decisions

These decisions remain active for this repository:

- formal integration target is still NapCat public HTTP / WS, not private injection hooks
- forward WebSocket remains the preferred transport; HTTP remains fallback and diagnosis path
- bulk history export may use the local fast plugin because it still stays inside the repo's NapCat runtime and returns data through explicit plugin routes
- formal media extraction is strict NapCat-only:
  - direct local path first
  - then plugin context hydration
  - then plugin-issued public token plus public `get_image` / `get_file` / `get_record`
  - otherwise `missing_after_napcat`
- legacy local cache scan and MD5 recovery remain benchmark/research tools only
- current last-mile fidelity focus is still `forward` / `nested-forward` media, not ordinary top-level image recovery

## Child Handbooks

Read these in this order when working on NapCat-heavy tasks:

1. [NapCat.docs_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/NapCat.docs_AGENTs.md)
   - official docs site map
   - section-by-section summary
   - what official docs clearly state
   - what official docs do not specify
2. [NapCat.source_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/NapCat.source_AGENTs.md)
   - upstream package map
   - message, file, plugin, WebUI, and action-router architecture
   - token/LRU/file handling implementation facts
3. [NapCat.community_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/NapCat.community_AGENTs.md)
   - GitHub repo scale snapshot
   - recurring operator pain points
   - discussion / issue / PR theme map
4. [NapCat.media_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/NapCat.media_AGENTs.md)
   - exporter-facing media semantics
   - `url/path/file/file_id/public token`
   - `speech`
   - `forward/nested-forward media`
   - current benchmark and runtime findings

## TODO Routing

NapCat-specific backlog is now split:

- [TODOs.napcat-research.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.napcat-research.md)
  - official docs coverage
  - upstream source coverage
  - community coverage
  - knowledge-base maintenance work
- [TODOs.export-fidelity.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.export-fidelity.md)
  - exporter-facing NapCat media fidelity decisions and remaining implementation gaps
- [TODOs.export-performance.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.export-performance.md)
  - speed and throughput

## How To Use This Doc Set

If the task is mostly about:

- startup, framework access, token/auth, WebUI, config
  - start with `NapCat.docs_AGENTs.md`
- source reading, routing, tokens, parser internals, plugin manager
  - start with `NapCat.source_AGENTs.md`
- recurring user pain, upstream maintainer signals, what people keep misunderstanding
  - start with `NapCat.community_AGENTs.md`
- files, images, record, forward bundles, `get_*`, public token, benchmarks
  - start with `NapCat.media_AGENTs.md`

## Important Memory Notes

- Official docs were previously under-read for this repository, which led to avoidable wasted time.
- The handbooks now explicitly preserve official-doc facts such as:
  - public file interfaces and direct-URL handling
  - plugin API route surfaces
  - framework access/token/403 guidance
  - resource/message-id design and cache semantics
- Do not start new NapCat debugging from memory alone when the relevant child handbook exists.
