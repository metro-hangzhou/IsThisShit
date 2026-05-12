# Round Lifecycle

Status: `draft_round_001`

Each round follows this lifecycle:

1. archive snapshot confirmed
2. explorer source digest produced
3. worker draft produced
4. reviewer questions/blockers produced
5. worker response produced
6. user checkpoint packaged
7. next round only after explicit user approval

Promotion rules:

- `draft` -> `reviewed` only after reviewer blocker count is zero
- `reviewed` -> `canonical` only after user gate is marked approved
