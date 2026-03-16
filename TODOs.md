# TODOs

Detailed specialized TODOs now live under [dev/todos/INDEX.md](/d:/Coding_Project/IsThisShit/dev/todos/INDEX.md).

See also: [TODOs.export-performance.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.export-performance.md) for the dedicated export-speed investigation and fix plan.
See also: [TODOs.export-fidelity.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.export-fidelity.md) for export UX coverage and media/content fidelity follow-ups.
See also: [TODOs.export-forensics.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.export-forensics.md) for fail-fast missing policy, forensic debug bundles, and investigative-failure handling.
See also: [TODOs.napcat-research.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.napcat-research.md) for NapCat official-doc, source, and GitHub-community coverage.
See also: [TODOs.production-review.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.production-review.md) for third-party production hardening, scale-risk review, and strict-environment fixes.
See also: [TODOs.export-cli.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.export-cli.md) for export command parsing, batch export UX, and root/watch progress parity.
See also: [TODOs.cli-ux.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.cli-ux.md) for slash-command completion, followup, and cursor-movement regressions.
See also: [TODOs.cli-product-review.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.cli-product-review.md) for product-shaped CLI review, fear-reduction, and ordinary-user ergonomics.
See also: [TODOs.windows-terminal-compat.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.windows-terminal-compat.md) for Win10/Win11 terminal-host rendering, compatibility mode, and visual stability work.
See also: [TODOs.preprocess.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.preprocess.md) for the preprocessing and indexing subsystem plan.
See also: [TODOs.rag.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.rag.md) for the retrieval and generation layer built on top of preprocessing.
See also: [TODOs.analysis-agents.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.analysis-agents.md) for the target-driven analysis substrate and pluggable agent plan.
See also: [TODOs.llm-analysis.md](/d:/Coding_Project/IsThisShit/dev/todos/TODOs.llm-analysis.md) for the first-phase abstract LLM analysis layer and its later schema-convergence path.

## P0. Project Skeleton

- [x] Create `src/qq_data_core/`, `src/qq_data_integrations/`, and `src/qq_data_cli/`.
- [x] Add a console entrypoint for the developer CLI shell.
- [x] Keep runtime dependencies focused on `typer`, `prompt_toolkit`, `httpx`, `websockets`, `pydantic`, `orjson`, and `rich`.
- [x] Move heavyweight analysis dependencies out of the default runtime path.
- [x] Add a small config model for `NAPCAT_WS_URL`, `NAPCAT_HTTP_URL`, `NAPCAT_TOKEN`, `NAPCAT_WEBUI_URL`, `NAPCAT_WEBUI_TOKEN`, `EXPORT_DIR`, and `STATE_DIR`.

## P1. NapCat Transport Layer

- [x] Implement a forward WebSocket client for realtime events plus action calls.
- [x] Implement an HTTP fallback client for action-only paths.
- [x] Wrap the metadata actions:
  - `get_group_list`
  - `get_group_member_list`
  - `get_friend_list`
- [x] Wrap the history actions:
  - `get_group_msg_history`
  - `get_friend_msg_history`
- [x] Handle token auth, reconnect, timeout, and structured error reporting.
- [x] Ensure the client consumes structured array message payloads instead of relying on CQ-code strings.
- [x] Add a WebUI auth client for QQ login status and QR login routes.
- [x] Support repo-relative NapCat path discovery from the `IsThisShit/` project root.
- [x] Add optional NapCat auto-start bootstrap logic for login/export/watch flows.

## P2. Metadata Cache

- [ ] Cache groups, friends, and group members locally for fast completion.
- [x] Support fuzzy lookup by name, remark, card, and numeric ID.
- [x] When duplicate names exist, always surface QQ ID in the suggestion row.
- [x] Add a refresh path so `/groups` and `/friends` can force a metadata sync.

## P3. Message Normalization

- [x] Define `NormalizedMessage`, `NormalizedSegment`, and `ReplyRef` models.
- [x] Preserve segment order exactly as returned by NapCat.
- [x] Implement normalization for:
  - `text`
  - `at`
  - `image`
  - `record`
  - `file`
  - `onlinefile`
  - `face`
  - `mface`
  - `reply`
- [x] Emit both `content` and structured `segments`.
- [x] Emit `text_content`, `image_file_names`, `uploaded_file_names`, and `emoji_tokens`.
- [x] Keep raw payload export optional behind an explicit flag.

## P4. Interactive CLI

- [x] Build a REPL where every top-level command must start with `/`.
- [x] Implement `/help`.
- [x] Implement `/login [--refresh] [--timeout N] [--poll N]`.
- [x] Implement `/groups [keyword]`.
- [x] Implement `/friends [keyword]`.
- [x] Implement `/watch group <group-name-or-id>`.
- [x] Implement `/watch friend <friend-name-or-id>`.
- [x] Implement `/export group <group-name-or-id>`.
- [x] Implement `/export friend <friend-name-or-id>`.
- [x] Implement `/export group|friend <name-or-id> <time-a> <time-b>` with closed-interval semantics.
- [x] Implement `/export_onlyText`, `/export_TextImage`, and `/export_TextImageEmoji`.
- [x] Support `data_count=NN` and `--data-count NN` for newest-N export, with interval-tail behavior when a closed interval is present.
- [x] Print per-export extraction summaries that include total messages plus expected/actual/missing content counts by type.
- [x] Implement `/quit`.
- [x] Reject bare top-level input with a short hint instead of guessing intent.

## P5. Completion UX

- [x] Use `prompt_toolkit` completion menus for command lookup.
- [x] Show the top few matches while typing.
- [x] Support `Up` / `Down` to move the active suggestion.
- [x] Support `Tab` to complete the active suggestion.
- [x] Support `Enter` to accept the active suggestion or execute the full command.
- [x] Support `Esc` to cancel selection prompts.
- [x] Extend completion from commands to group/friend metadata lookup.
- [x] Extend `/export` completion to time expressions and explicit date slots.
- [x] Add pinyin-aware fuzzy matching for Chinese target names.
- [x] Add date-slot validity feedback and field-wise `Up` / `Down` date rolling.

## P6. Realtime Watch

- [x] Subscribe to NapCat message events over WebSocket.
- [x] Render compact debug lines with `group=<id>` or `private=<id>`, `sender=<id>`, and simplified content.
- [x] In watch mode, render:
  - image as `[image]`
  - emoji/sticker as `[meme or emoji]`
  - voice as `[speech audio]`
  - file as `[uploaded file]`
- [x] Do not print raw JSON unless a dedicated debug flag is enabled.

## P7. Historical Export

- [x] Support group export with `get_group_msg_history`.
- [x] Support private export with `get_friend_msg_history`.
- [ ] Support `--since`, `--until`, `--limit`, `--out`, and `--resume`.
- [x] Support `@final_content`, `@earliest_content`, and offset arithmetic such as `@final_content-7d-5h-30s`.
- [x] Support closed-interval export by two explicit dates in `YYYY-MM-DD_HH-MM-SS`.
- [x] Allow `/watch ...` mode to export the active chat with `/export <time-a> <time-b>`.
- [x] Write one JSONL file per export task.
- [x] Add TXT rendering compatible with the `tests/fixtures/testChatRecord/*.txt` style.
- [x] Write a small manifest next to each export output.
- [x] Materialize actual local media files into a sibling `<stem>_assets/` directory during export.
- [x] Support mixed NTQQ + legacy QQ cache recovery, including legacy `Image/Group2` MD5-based lookup.
- [x] Persist reusable legacy media hash indexes under `state/media_index/` so repeated exports do not rehash unchanged cache files.
- [x] Scope legacy cache MD5 hashing by export time window and month hints before scanning large mixed QQ cache trees.
- [ ] Persist per-target export state keyed by `message_seq`.
- [ ] Deduplicate by `message_seq`, then by `message_id`.

## P8. Test Coverage

- [x] Add focused reusable fixtures under `tests/fixtures/`.
- [x] Add unit tests for text/image/file/record/face/mface mapping.
- [ ] Add tests for mixed text-plus-image ordering.
- [x] Add tests for duplicate-name completion behavior.
- [ ] Add mocked transport tests for WS reconnect and history pagination.
- [x] Add mocked transport tests for WebUI QR login and token/config discovery.
- [ ] Run one live manual verification against the user's current NapCat + QQ version.

## P9. Nice-To-Haves

- [ ] Add `/recent` for recent contacts.
- [x] Add `/status` for current NapCat endpoint and auth status.
- [x] Add `/doctor` for endpoint probes plus NapCat runtime/launcher diagnostics.
- [ ] Add optional CSV or TXT rendering as secondary outputs.
- [ ] Add an image filename resolver helper for local QQ media folders.
- [ ] Add optional inclusion of reply/forward metadata in human-readable exports.
- [ ] Add optional inclusion of system messages or gray-tip messages.

## P10. Distribution

- [x] Add a Windows share-bundle builder for the extraction-only stack.
- [x] Ensure the share bundle includes `CLI + NapCat + .venv` and excludes later analysis code.
- [ ] Validate the generated share bundle on a second clean Windows environment.
- [x] Record that the QQ extractor is a separable upstream deliverable that may continue independently from preprocessing and analysis.

## Decisions Already Made

- [x] NapCat is used only via public HTTP/WS interfaces.
- [x] JSONL is the canonical export format.
- [x] TXT is a supported secondary export format.
- [x] `face` and `mface` are normalized separately.
- [x] Voice content is exported as `[speech audio]` in V1.
- [x] Top-level CLI commands must start with `/`.
- [x] Realtime watch is simplified; historical export remains rich.
- [x] CLI, integration, and core export logic are split into separate packages.

## Open Questions To Confirm Later

- [ ] Should `segments.image.path` be exported by default, or only when present plus an opt-in flag?
- [ ] Should reply targets be exported in V1 as structured metadata only, or also as inline content tokens?
- [ ] Is CSV worth supporting in the first milestone, or should it wait until JSONL is stable?
