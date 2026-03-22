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

### [2026-03-22][006] forward candidate matrix previously over-reported green while hiding recoverability loss

- Problem:
  - candidate winner selection could look correct even when the simulated resolver/path kind fell through to `missing`
  - root cause was simulator-side:
    - candidate token/remote path maps were copied too early
    - matrix matching only checked winner label, not terminal recoverability
- Current fix:
  - candidate simulator now keeps live token/remote maps
  - matrix matching now requires both:
    - expected winner
    - expected `path_kind`
  - bounded candidate-priority matrix is now a real recoverability check instead of a label-only check

### [2026-03-22][007] shared miss/outcome scope was under-tested

- Problem:
  - exporter correctness depends on not poisoning shared old-asset outcomes across weak identities
  - previous simulator coverage did not systematically check when `_shared_request_key(...)` should or should not collapse requests
- Current fix:
  - simulator now has a bounded shared-outcome scope matrix covering:
    - `image`
    - `video`
    - `file`
    - `speech`
    - `top_level`
    - `forward`
    - identity modes:
      - `file_name_only`
      - `md5`
      - `file_id`
      - `source_leaf`
      - `remote_url_same`
      - `none`

### [2026-03-22][008] public-token timeout-key scope was under-tested

- Problem:
  - exporter speed depends on timeout suppression keys being neither too broad nor too narrow
  - prior simulator coverage did not explicitly lock:
    - same parent / same token reuse
    - new token separation
    - new file separation
    - different parent separation
    - non-forward ignore behavior
- Current fix:
  - simulator now has a bounded public-timeout-scope matrix covering:
    - `video`
    - `file`
    - `speech`
    - ignored `image`

## Remaining High-Value Gaps

- [x] add batch / pair simulations for cross-parent cache poisoning and shared-outcome scope
- [x] add explicit multi-candidate forward matching scenarios:
  - local-path vs token
  - remote-url vs token
  - `file_id` vs remote-url
- [x] add bounded exhaustive prefetch/executor pressure simulation:
  - many remote candidates
  - many stale forward candidates
  - mixed recent/old batches
- [ ] extend bounded exhaustive coverage to multi-stage cache interaction:
  - shared outcome reuse after public timeout
  - forward timeout breaker after slow-noop materialize
  - mixed local+remote+public candidate reuse across repeats
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

## Current Quantitative Baseline

- `resolution-matrix`: `570/570 matched`, `cost_overruns=0`
- `forward-candidate-matrix`: `42/42 matched`
- `shared-scope-matrix`: `48/48 matched`
- `public-timeout-scope-matrix`: `16/16 matched`
- `prefetch-planning-matrix`:
  - `total=20`
  - `max_batch_size=200`
  - `large_window_batch=50..50`
  - `duplicate_shared_key_total=18088`
