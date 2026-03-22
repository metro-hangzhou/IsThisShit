# Asset Simulator Hardening TODOs

Spec baseline: 2026-03-22

This file tracks exporter-only simulation work for asset resolution, timeout risk, and high-cost missing classification. The goal is to catch expensive or incorrect asset paths during development instead of waiting for long live exports to stall on operator machines.

## Current Scope

Current simulator coverage includes:

- forward timeout matrices for:
  - `public-token`
  - `forward-materialize`
  - `forward-metadata`
- asset families:
  - `image`
  - `video`
  - `file`
  - `speech`
  - `sticker`
- topologies:
  - `top_level`
  - `forward`
  - `nested_forward`
  - malformed forward parent variants
- state drift families:
  - local path state drift
  - public-token payload shape drift
  - old-forward payload-only `file_id`
  - zero-byte local/public payloads
  - route unavailable / route disabled states

## Recorded Findings

### [2026-03-22][001] `public_token` payload shape drift can hide recoverable remote URLs

- Problem:
  - payloads may expose `remote_url` without `url`
- Old effect:
  - exporter could leave recoverable assets unresolved
- Current fix:
  - simulator now covers `remote_url-only`
  - downloader now accepts `remote_url` as a first-class public-token remote recovery field

### [2026-03-22][002] old forward `payload.file_id` was visible but not operational

- Problem:
  - very old forward `video/file` payloads could carry a usable `file_id` only inside the forward payload
- Old effect:
  - exporter could skip the cheaper direct-file-id path and drift into slower missing logic
- Current fix:
  - simulator now covers payload-only `file_id`
  - downloader now activates direct-file-id recovery from forward payloads

### [2026-03-22][003] old public-token zero-byte payloads were under-classified

- Problem:
  - `video/file/speech` could return a zero-byte local path plus no live remote payload
- Old effect:
  - ambiguous missing state and extra slow-path attempts
- Current fix:
  - simulator now covers zero-byte public-token payloads
  - downloader now classifies these as `qq_expired_after_napcat`

### [2026-03-22][004] old forward route-unavailable state for `video/file/speech` was under-classified

- Problem:
  - `forward route unavailable` could leave old forward assets in a vague unresolved state
- Current fix:
  - simulator now covers route-unavailable old forward states
  - downloader now early-classifies these cases as `qq_expired_after_napcat`

### [2026-03-22][005] simulator itself lacked summary / coverage visibility

- Problem:
  - matrix output was scenario-dump first
  - hard to see:
    - overall match rate
    - cost-overrun count
    - state coverage distribution
    - worst timeout-risk shapes
- Current fix:
  - simulator now exposes:
    - forward timeout summary
    - resolution summary
    - resolution coverage catalog

## Remaining High-Value Gaps

- [ ] add batch / pair simulations for cross-parent cache poisoning and shared-outcome scope
- [ ] add explicit multi-candidate forward matching scenarios:
  - local-path vs token
  - remote-url vs token
  - `file_id` vs remote-url
- [ ] add bounded exhaustive prefetch/executor pressure simulation:
  - many remote candidates
  - many stale forward candidates
  - mixed recent/old batches
- [ ] add shape-drift coverage for rarer mixed payloads:
  - share/card media hints
  - malformed nested-forward wrappers
  - partially blank sticker metadata
- [ ] add machine-drift suites for:
  - route available in one family but disabled in another
  - public actions returning opaque but non-terminal payloads
- [ ] keep CLI helper output aligned with simulator summary output so developer diagnosis stays summary-first

## Current Working Rule

- Any exporter-side asset recovery change should first add or update simulator coverage.
- If a live failure can be represented as a bounded synthetic asset state, encode it in the simulator before expanding live tests.
