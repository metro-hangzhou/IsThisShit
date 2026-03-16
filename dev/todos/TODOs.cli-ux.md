# CLI UX TODOs

> Scope: slash-command completion, followup chaining, cursor movement, and watch-mode command input stability.

## Completed

- [x] Add export-profile commands to watch mode and top-level REPL:
  - `/export`
  - `/export_onlyText`
  - `/export_TextImage`
  - `/export_TextImageEmoji`
- [x] Add inline `data_count=` completion from `/export d...`.
- [x] Prioritize completion-menu `Up` / `Down` over date rolling.
- [x] Make completion followup token-aware for terminal export tokens:
  - `asTXT`
  - `asJSONL`
  - `data_count=`
- [x] Prevent accepted `data_count=` from inserting an unwanted trailing space.
- [x] Prevent accepted format aliases from reopening the format completion menu.
- [x] Cancel lingering completion state before `Left` / `Right` cursor movement in both REPL and watch command input.
- [x] Extend export completion followup to batch target selectors:
  - `group_asBatch=`
  - `friend_asBatch=`
- [x] Reopen completion after `,` when editing a batch target list.

## Open

- [ ] Do a wider manual UX pass for mixed quote-wrapped targets plus export followups.
- [ ] Verify completion behavior around `--data-count` and `data_count=` stays consistent when partially edited in the middle of a line.
- [ ] Add a small operator-facing regression checklist for:
  - command completion
  - date completion
  - watch-mode completion
  - cursor movement after accepting completions
- [ ] Check whether `Tab` should accept the current candidate and cancel followup for `data_count=` exactly the same way as `Enter`.

## Notes

- Export completion followup must be decided from the accepted completion token, not only from the final full line text.
- Cursor navigation keys must treat any stale completion menu as disposable UI state, not as a hard interaction mode.
