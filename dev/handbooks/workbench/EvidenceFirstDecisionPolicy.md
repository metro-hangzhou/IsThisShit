# Evidence First Decision Policy

Status: `draft_round_003`

## Core Rule

When evidence already reaches the decision threshold, the workflow must allow direct fast-close or fast-fail rather than wasting time on ritualized waiting.

## Meaning

- timeout exists for uncertainty, not for pretending to think
- hierarchy exists for coordination, not for suppressing decisive evidence
- evidence-first is not only anti-timeout; it is anti-any engineering path that keeps circling after the truth is already available
- it demands:
  - evidence thinking
  - decision thinking
  - causal-trace thinking

## Broader Failure Modes

This policy also rejects:

- unnecessary fallback chains
- low-value probes kept alive after evidence already ruled them out
- paths preserved only because “that is how we used to do it”

## Reviewer Enforcement

Reviewer may issue:

- `evidence_decision_fidelity`
- `latency_waste_risk`
- `decision_quality`
- `causal_traceability`

when the system keeps an obviously dead path alive despite sufficient evidence.

## Mandatory Artifact

When evidence is sufficient and a direct shortcut is taken, the system should leave at least one runtime artifact:

- `objection_or_fast_fail_notice.md`
- or an `evidence_based_shortcut` entry inside the challenge register
