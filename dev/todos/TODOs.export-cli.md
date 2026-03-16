# Export CLI TODOs

> Scope: export command parsing, batch export ergonomics, root/watch progress parity, and operator-facing export UX.

## Completed

- [x] Accept non-zero-padded explicit datetime literals such as `2026-3-09_00-00-00`.
- [x] Add batch export parsing for:
  - `group_asBatch=<target1,target2,...>`
  - `friend_asBatch=<target1,target2,...>`
- [x] Support completion for batch export stubs from `/export `.
- [x] Support fuzzy/pinyin completion for each comma-separated batch target fragment.
- [x] Reopen completion after `,` inside a batch token.
- [x] Hand off from a completed batch token to time-expression completion on the following space.
- [x] Hide `group_asBatch=` / `friend_asBatch=` prefixes from batch completion menu display.
- [x] Exclude already-selected batch targets from later completion suggestions in the same token.
- [x] Mirror watch-style staged export progress in the top-level REPL export path.
- [x] Refresh root and batch export progress in-place instead of appending one callback line per progress event.
- [x] Keep top-level REPL final export output as multiline detail instead of a single compressed summary line.
- [x] Normalize NapCat history pages before interval/tail/bounds decisions so explicit date exports do not silently degenerate into full-history scans when the provider returns reverse-ordered pages.
- [x] Make batch target parsing robust to space-split names so `group_asBatch=<name with spaces> @final_content @earliest_content` still recognizes the time range.

## Open

- [ ] Do a manual operator pass on batch export with quoted names containing spaces.
- [ ] Verify root-CLI progress readability on narrow terminals during long batch exports.
- [ ] Decide whether batch export should support mixed `group` and `friend` lists in a future v2 syntax, or stay split by command family.
- [ ] Add a manifest-level batch summary artifact when one batch command produces many outputs.
- [ ] Revisit whether batch export should stop on the first target failure or always continue and report per-target failures only.

## Notes

- Batch export parsing must treat completion-inserted quoted names as valid target entries.
- Export interval parsing must not silently fall back to full-history semantics when explicit dates were provided.
- NapCat history payload order is not stable enough to use raw first/last message as oldest/newest boundaries; provider pages must be sorted first.
- Root REPL export is expected to surface:
  - scan progress
  - write-data progress
  - asset materialization progress
  - final multiline `export_summary`
