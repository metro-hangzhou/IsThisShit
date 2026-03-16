# NapCat Research TODOs

> Scope: official-doc coverage, upstream-source coverage, and GitHub community coverage for NapCat-specific knowledge maintenance.

## Completed In This Snapshot

- [x] Split NapCat knowledge out of a single monolithic `NapCat_AGENTs.md`.
- [x] Turn `NapCat_AGENTs.md` into a master index and truth-source router.
- [x] Add:
  - `NapCat.docs_AGENTs.md`
  - `NapCat.source_AGENTs.md`
  - `NapCat.community_AGENTs.md`
  - `NapCat.media_AGENTs.md`
- [x] Record the current local-source warning:
  - `NapCatQQ` checkout is on `napcat-direct-media-hydration`
  - working tree is dirty
  - do not mistake local experiments for upstream official behavior
- [x] Record the official-doc/site snapshot date:
  - `2026-03-14`

## Official Docs Coverage

- [x] Capture the official docs site map at a first-pass level.
- [x] Read and summarize:
  - introduction / quick start
  - startup methods
  - framework access
  - basic config
  - advanced config
  - security
  - request interfaces
  - event/message/file pages
  - plugin docs family
- [ ] Do a second pass over every plugin subpage and extract reusable repo patterns page by page.
- [ ] Do a field-by-field second pass over protocol/event pages rather than only first-pass thematic notes.
- [ ] Revisit every official page whose wording is too high-level and pair it with upstream source confirmation.

## Source Coverage

- [x] Capture a package-level architecture map for `NapCatQQ/packages`.
- [x] Trace the current message path:
  - `napcat-core/apis/msg.ts`
  - public history actions
  - `parseMessage(...)`
- [x] Trace the current media path:
  - `downloadMedia(...)`
  - `GetImage`
  - `GetFile`
  - `GetRecord`
  - `FileNapCatOneBotUUID`
- [x] Trace the plugin path:
  - plugin types
  - plugin manager
  - builtin plugin example
- [ ] Deep-read stream-related actions and docs, then decide whether they matter for exporter debugging or only for client frameworks.
- [ ] Deep-read `napcat-protocol`, `napcat-adapter`, and `napcat-schema` enough to explain where protocol truth vs OneBot truth diverge.
- [ ] Extract a clearer WebUI/backend/frontend boundary map.
- [ ] Extract a clearer shell/framework/bootstrap boundary map.

## Community Coverage

- [x] Capture repo scale/activity snapshot from public GitHub surfaces.
- [x] Capture discussions category map.
- [x] Record first-pass recurring community themes:
  - installation/startup drift
  - token/auth/WebUI confusion
  - media/file handling pain
  - protocol/framework integration confusion
  - platform compatibility
  - capability-expectation mismatch
- [ ] Build a deeper issue index for:
  - media/token
  - forward
  - plugin
  - startup/runtime
- [ ] Build a deeper PR discussion index for:
  - stream API changes
  - file/media changes
  - plugin system changes
  - framework/bootstrap changes
- [ ] Build a deeper discussions appendix with direct links grouped by subject.

## Knowledge-Maintenance Rules

- [ ] When new NapCat facts are learned, decide whether they belong in:
  - `NapCat.docs_AGENTs.md`
  - `NapCat.source_AGENTs.md`
  - `NapCat.community_AGENTs.md`
  - `NapCat.media_AGENTs.md`
  rather than stuffing them back into the master index.
- [ ] Keep `NapCat_AGENTs.md` short and routing-focused.
- [ ] Promote only repository-contract-changing NapCat findings into `AGENTS.md`.
- [ ] Keep exporter-only implementation backlog in `TODOs.export-fidelity.md`, not here.
