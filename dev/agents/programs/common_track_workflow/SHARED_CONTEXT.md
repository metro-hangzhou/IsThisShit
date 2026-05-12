# Common Track Workflow Shared Context

## Goal

Refactor the shared workflow into a self-governing, archive-first, reviewable system that can later drive full-project refactors.

## Why This Phase Exists

- The current workflow is already partially generic, but still structurally centered on exporter history.
- Review state exists in multiple ledgers and multiple directory roots.
- User review gates are intended but not yet formalized.
- Archive-first behavior is not yet a first-class contract.

## Required Gate Order

1. Gate A: old-workflow source digest
2. Gate B: first draft architecture
3. Gate C: reviewer first strict critique
4. Gate D: worker revised architecture
5. Gate E: final user approval

No broader subsystem refactor should begin before these gates are satisfied.
