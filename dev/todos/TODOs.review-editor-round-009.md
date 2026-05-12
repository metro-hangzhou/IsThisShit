# Review Editor Round 009 TODOs

Spec baseline: 2026-03-29

## P0. Raw Sender Mapping

- [ ] Query `analysis_state/db/analysis.db` for raw sender identity by `message_uid`
- [ ] Extend review-service payloads with:
  - raw sender QQ id
  - raw sender name
  - raw group id where useful for display
- [ ] Stop showing aliased `user_xxx` labels in the visible review editor during test mode
- [ ] Prefer raw sender name, then raw sender QQ id, and only then fallback placeholders

## P1. Group / Sender Display Rules

- [ ] Keep group id as the primary conversation identity
- [ ] Make sender display consistent across:
  - message bubbles
  - drawer header
  - review panel
  - model panel
- [ ] Remove mixed alias/raw/fallback display confusion

## P2. QQ Fidelity Final Push

- [ ] Reduce remaining product branding from the shell
- [ ] Improve conversation session believability
- [ ] Further reduce visible review overlay feel in the chat pane
- [ ] Improve drawer details semantics
- [ ] Make the composer shell feel more like QQ input, less like a status surface

## P3. Residual Bug Closure

- [ ] Re-check right drawer header / chips layout after verdict changes
- [ ] Re-check save-state transitions for both card and window review
- [ ] Re-check message click -> card selection -> drawer update flow
- [ ] Re-check alias leakage in all visible header and subtitle regions

## P4. Validation

- [ ] Keep frontend regression green
- [ ] Keep `vue-tsc --noEmit` green
- [ ] Keep `vite build` green
- [ ] Extend backend review-service tests to lock raw sender mapping behavior
