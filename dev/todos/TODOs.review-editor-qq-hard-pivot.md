# Review Editor QQ Hard Pivot TODOs

Spec baseline: 2026-03-29

## P0. Reviewer-Driven Target Reset

- [ ] Treat round_006 as structurally useful but target-incomplete
- [ ] Keep a harsh reviewer finding file alive during implementation
- [ ] Require every major front-end batch to answer:
  - does this read more like QQ or more like a tool?

## P1. Shell Fidelity

- [ ] Make the outer shell read like a Windows chat client window
- [ ] Reduce custom-dashboard feeling from spacing, gradients, and panel framing
- [ ] Rework the far-left narrow rail to feel more like a native chat-client nav strip

## P2. Conversation Pane Fidelity

- [ ] Make conversation rows feel like QQ sessions, not analysis items
- [ ] Prioritize avatar, snippet, recency, and badge treatment over raw metadata
- [ ] De-emphasize `candidateId` as the loudest text

## P3. Chat Surface Fidelity

- [ ] Make message flow feel like QQ chat reading, not transcript inspection
- [ ] Tighten avatar/message/timestamp hierarchy
- [ ] Make media messages feel native to chat
- [ ] Reduce visible review scaffolding inside the primary chat surface

## P4. Drawer Fidelity

- [ ] Make the right side feel like a profile/details drawer
- [ ] Keep review/model/window tools, but soften tool-like labeling
- [ ] Make the open/close behavior feel like a side panel rather than an inspector

## P5. Composer Fidelity

- [ ] Make the bottom bar visually inherit QQ composer structure
- [ ] Keep it non-sending, but stop making it read as a generic status panel

## P6. Validation

- [ ] Preserve run/candidate/message/card save flow tests
- [ ] Add at least one fidelity-oriented test around the new shell semantics
- [ ] Keep `vitest`, `vue-tsc`, and `vite build` green through the pivot
