# Export Forensics TODOs

Spec baseline: 2026-03-16

This file tracks a stricter export-debugging and failure-escalation policy.

It exists because "asset missing" is not one class of outcome.

There is a critical difference between:

- a missing asset whose reason is already well-explained and accepted
  - for example `qq_expired_after_napcat`
- a missing asset whose reason is still unknown, contradictory, or only weakly inferred

The second class must no longer be treated as a normal export result.

This track is specifically for a non-release debugging branch.

For this branch, the priority order is:

1. reduce remote tester rerun count
2. maximize evidence density per run
3. turn unknown failure into explainable failure
4. only then optimize polish, noise, and operator comfort

Current explicit stance for this branch:

- ordinary-user emotional comfort is not the primary goal here
- privacy minimization is not the primary goal here when the remote tester has explicitly agreed to provide full local QQ/NapCat evidence
- implementation should still stay bounded and structured, but should bias toward over-collection rather than under-collection
- release-facing privacy protection, redaction, and calmer UX remain important, but they belong to the later release track, not this debug branch

For strict external testing, an unexplained or unreasonable missing result should be treated as a diagnostic failure that must:

- emit high-signal red error output
- capture a local forensic bundle
- optionally abort the export immediately

See also:

- [CodeStrict_AGENTs.md](../agents/CodeStrict_AGENTs.md)
- [TODOs.production-review.md](TODOs.production-review.md)
- [TODOs.export-fidelity.md](TODOs.export-fidelity.md)
- [NapCat.media_AGENTs.md](../agents/NapCat.media_AGENTs.md)

## Design Position

The current exporter is already good at distinguishing several "known bad but acceptable" outcomes.

That is not enough.

The stricter production position is:

- known and well-justified missing is acceptable
- unknown missing is not acceptable
- unreasonable missing is not acceptable
- a long timeout with no precise substep attribution is not acceptable

In other words:

- `missing` is only a valid export outcome when the reason is explicit and believable
- otherwise the exporter has failed to explain itself

For this debug branch, there is one more practical rule:

- when in doubt, prefer collecting more evidence in the current run over saving a future rerun

## Known-Acceptable Missing vs Investigative Failure

### Acceptable missing classes

These are candidates for "record and continue":

- `qq_expired_after_napcat`
- `missing_after_napcat` only when the route chain is fully known and intentionally exhausted
- explicitly skipped old-bucket routes with documented policy

### Investigative-failure classes

These should be treated as high-severity diagnostic failures:

- `missing_kind` absent or empty
- `missing_kind=missing_after_napcat` but no route-attempt chain recorded
- timeout with no substep attribution
- stale local path hinted, but no sibling directory snapshot captured
- contradictory identifiers
  - for example `file_name=A` but `source_path` leaf is `B`
- forward file/video miss where no direct statement exists about:
  - local hinted path existence
  - file-id route attempted or not
  - targeted forward hydration attempted or not

## P0. Strict Missing Policy

- [ ] Define export failure severity levels:
  - `record_and_continue`
  - `incident_and_continue`
  - `abort_export`
- [ ] Define strict collection policies instead of a single "fail immediately" rule:
  - `collect_all`
  - `abort_on_first`
  - `abort_after_n_incidents`
- [ ] Make `collect_all` the default strict-debug behavior for remote tester runs.
- [ ] Add formal strict switches, for example:
  - `--strict-missing collect`
  - `--strict-missing abort`
  - `--strict-missing threshold:3`
  - or matching env vars
- [ ] In strict `collect_all` mode, if a missing asset lands in an unknown/unreasonable class:
  - print a red CLI incident line immediately
  - keep exporting
  - keep writing forensic bundles for each unique incident
  - print a final incident summary with all forensic bundle paths
- [ ] In strict `abort` mode:
  - stop on the first investigative failure
  - point to the forensic bundle path
- [ ] In strict `threshold` mode:
  - stop only after enough incidents have been collected to justify ending the run
- [ ] Add forensic-budget controls so `collect_all` does not degenerate into uncontrolled evidence spam:
  - `max_incidents`
  - `max_unique_failure_fingerprints`
  - `max_forensic_bytes`
  - `max_dir_snapshots`
  - budget-exceeded downgrade behavior

Why:

- external testers should not be asked to infer whether a bad missing is "probably okay"
- but aborting on the first bad missing can waste a precious remote test run when several independent failure classes are present
- the program should collect as many distinct high-value incidents as possible per run unless the operator explicitly asks for early abort
- however, the collection strategy still needs hard ceilings so the debugging system itself does not become the next failure mode

## P0. Forensic Bundle

- [ ] Create a dedicated export-forensics output area under:
  - `state/export_forensics/`
- [ ] On any investigative failure, write a per-incident forensic bundle containing:
  - asset identity summary
  - message context hints
  - route-attempt chain with start/end/status/elapsed/timeout
  - raw missing classification inputs
  - local path existence checks
  - sibling directory snapshots
  - relevant payload summaries from NapCat/plugin/public actions
  - export command context
  - trace/log file references
- [ ] Give each incident a stable `incident_id` and print it in CLI output.
- [ ] Add a run-level summary file containing:
  - total incident count
  - incident grouping by fingerprint/root cause candidate
  - first/last occurrence
  - whether export completed or aborted
- [ ] Add a run-level preflight bundle containing:
  - exporter build identity
  - plugin route capability matrix
  - NapCat / QQ / Python version hints when obtainable
  - current command profile and strict-debug policy
  - key root paths used by the run
- [ ] Deduplicate repeated incidents for the same underlying asset/root-cause fingerprint within one run so we do not waste remote test budget on identical evidence.
- [ ] Define and persist two different fingerprints:
  - `asset_fingerprint`
  - `failure_fingerprint`
- [ ] Capture the first occurrence of a `failure_fingerprint` in full detail, then only append lightweight occurrences for repeats.

Why:

- asking remote testers to send the whole `state/` directory is too expensive and too noisy
- we need one bounded, high-signal artifact per bad failure
- we also need a run-level view so one remote run can reveal multiple unrelated failure families at once
- and we need environment-level evidence so we can tell asset-specific faults from whole-machine / whole-runtime faults

## P0. Over-Collection For Path/Directory Evidence

- [ ] When a hinted local path exists only as metadata and the file is not found, capture:
  - exact hinted path
  - `exists/is_file/is_dir`
  - parent directory listing snapshot
  - sibling directories likely to matter
- [ ] For image cases, capture bounded snapshots of:
  - `Ori`
  - `OriTemp`
  - `Thumb`
- [ ] For video cases, capture bounded snapshots of:
  - current month `Video/<month>/Ori`
  - sibling or nearby `OriTemp`-like directories when present
  - sibling or nearby `Thumb`-like directories when present
  - nearby month buckets when the route claims month drift is plausible
  - any obvious temp/materialization sibling when present
- [ ] For file cases, capture bounded snapshots of the specific file receive/materialization directory if known.
- [ ] For forward `video` / `file` incidents, capture both:
  - `pre_route` directory snapshot
  - `post_route` directory snapshot
  - plus a compact directory diff
- [ ] Each snapshot should include at least:
  - file name
  - size
  - modified time
  - creation time when cheap
- [ ] Keep snapshots bounded:
  - cap file count
  - prefer closest-name or same-directory evidence over giant recursive dumps

Why:

- the current debugging gap is often "did the file really not exist there, or did we just assume?"
- a small directory snapshot can answer that immediately
- for forward media materialization, the real question is often "did the route actually cause a file to appear?" so before/after evidence is required

## P0. Route Attempt Ledger

- [ ] Create a normalized per-asset route ledger.
- [ ] Every resolver attempt should record:
  - route name
  - start timestamp
  - timeout budget
  - completion status
  - elapsed
  - high-value output summary
  - route-local contradiction flags when present
- [ ] Required route names should include at least:
  - `hint_local_path`
  - `stale_neighbor_probe`
  - `direct_file_id_get_file`
  - `public_token_get_image`
  - `public_token_get_file`
  - `public_token_get_record`
  - `context_hydration`
  - `forward_context_metadata`
  - `forward_context_materialize`
  - `forward_remote_url`
- [ ] On missing or error, the final manifest/forensics record should contain this ledger in compact form.

Why:

- "it timed out somewhere" is not enough
- we need one compact chain that explains exactly what the exporter believed it tried

## P0. Recommended Debug-Branch Operating Mode

- [ ] Define the recommended default profile for scarce remote-test opportunities:
  - strict mode: `collect_all`
  - forensic depth: `standard`
  - repeated incident policy: dedupe by `failure_fingerprint`
  - forward video/file: always capture pre/post materialization evidence
  - final output: always emit incident summary and rerun recommendation
- [ ] Define a more aggressive profile for one-off maintainer-local debugging:
  - strict mode: `abort_on_first`
  - forensic depth: `deep`
- [ ] Add a one-command debug entrypoint or preset that applies the recommended remote-test profile.

Recommended current posture:

- for friend-side testing, the exporter should prefer one dense evidence run over multiple lightweight reruns
- the default recommendation should therefore be:
  - collect all distinct incidents
  - dedupe repeats
  - over-collect bounded path evidence
  - avoid early abort unless budget thresholds are exceeded

## P1. Reason Taxonomy Tightening

- [ ] Review every place that currently returns `None, None` or generic `missing_after_napcat`.
- [ ] Replace vague endings with more specific classes where possible, for example:
  - `forward_target_timeout`
  - `public_token_timeout`
  - `direct_file_id_timeout`
  - `hint_path_missing`
  - `hint_path_conflicts_with_file_name`
  - `forward_target_not_materialized`
- [ ] Decide which of those are "known and acceptable" vs "diagnostic failure".

Why:

- a program cannot fail fast on unknown missing if its taxonomy still collapses too many cases together

## P1. Contradiction Detection

- [ ] Detect and escalate contradictory evidence, for example:
  - `file_name` vs `source_path` leaf mismatch
  - path says local file should exist, but route says metadata-only and no file
  - repeated forward file with stable `file_id` repeatedly timing out
- [ ] Mark contradiction-driven incidents separately from ordinary timeout incidents.

Why:

- contradictory evidence is often a strong signal that our assumptions are wrong, not just that the asset is old

## P1. CLI Escalation UX

- [ ] In strict mode, render investigative failures with a visibly stronger CLI presentation.
- [ ] Message should include:
  - this export stopped because an unexplained asset failure occurred
  - the asset type / file name
  - the substep or contradiction if known
  - the forensic bundle path
- [ ] Keep the tone calm, but do not hide severity.
- [ ] In strict `collect_all` mode, use wording that makes the policy explicit, for example:
  - `incident recorded; export continues to collect more evidence`
- [ ] At export end, if incidents were recorded, print:
  - incident count
  - grouped root-cause summary
  - bundle directory path
  - whether a rerun is still necessary
- [ ] Prefer a CLI pacing model that highlights:
  - first occurrence of a new failure fingerprint
  - budget exhaustion
  - final grouped summary
  instead of loudly repeating every identical incident line

Why:

- ordinary users should not need to decide whether a suspicious missing is important
- the exporter should say so explicitly

## P1. Remote Tester Artifact Contract

- [ ] Define the minimum artifact set for one investigative failure:
  - exported manifest
  - perf trace
  - forensic incident bundle
  - CLI log
- [ ] Add a short README or help note telling testers what to send back.

Why:

- this reduces support load and avoids whole-directory dump requests unless truly needed

## P2. Optional Deep Probe Mode

- [ ] Add an opt-in deep-debug mode for especially stubborn cases.
- [ ] In this mode, allow bounded extra probes such as:
  - same-directory snapshots with richer metadata
  - nearby month-bucket snapshots
  - additional route-attempt payload summaries
- [ ] Keep this mode explicitly off by default.

Why:

- sometimes we do need "overkill" data
- but it should be deliberate and bounded

## Current Trigger For This Track

The immediate motivating case is the remote `group_751365230` forward-media sample:

- repeated forwarded `video` / `file` misses persisted across multiple iterations
- some hinted local paths were later proven not to exist on the friend machine
- several route attempts spent tens of seconds before failing
- until recently, the exporter could still end with a generic missing without a full causal chain

This is exactly the class of problem that should now move from:

- "a hard case we keep debugging"

to:

- "a first-class investigative failure with mandatory forensic capture"

Operational note:

- for friend-side sparse test opportunities, the preferred strict-debug posture is now:
  - capture all distinct investigative failures in one run
  - deduplicate repeats aggressively
  - abort only when the operator explicitly asks for it or when an incident threshold is reached
- recommended mode for those runs should be treated as the primary design target, not as an edge-case option
