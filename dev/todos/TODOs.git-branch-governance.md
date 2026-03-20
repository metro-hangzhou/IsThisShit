# TODOs.git-branch-governance.md

## Goal

Reduce "runtime bug that later turns out to be branch skew" incidents by making branch management explicit, repeatable, and test-backed.

## Done

- [x] Create a dedicated branch-governance handbook:
  - [GitBranch_AGENTs.md](../agents/GitBranch_AGENTs.md)
- [x] Route top-level project guidance to the branch handbook from:
  - [AGENTS.md](../../AGENTS.md)
- [x] Add index entry for branch governance:
  - [dev/agents/INDEX.md](../agents/INDEX.md)

## Next

- [ ] Add a scripted release-bundle preflight check
  - compare staged file set against expected feature families
  - fail fast when a known family is obviously incomplete
- [ ] Add a small "release sync checklist" helper command or script
  - print:
    - branch
    - staged files
    - matching test set
    - push target
- [ ] Add a lightweight release smoke checklist for:
  - `/login`
  - `/export group 922065597 ...`
  - `/export private 1507833383 ...`
- [ ] Keep incident log current
  - every release skew incident must be recorded in:
    - [branch-sync-incidents.md](../documents/branch-sync-incidents.md)
