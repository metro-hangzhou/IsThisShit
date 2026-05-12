# Review Editor QQ Fidelity Sprint TODOs

Spec baseline: 2026-03-29

## P0. Reviewer-Coupled Sprint Discipline

- [ ] Keep round_008 reviewer findings live during implementation
- [ ] Treat "still looks like a tool" as blocker-grade, not cosmetic feedback
- [ ] Require every major UI batch to answer:
  - what specifically became more QQ-like
  - what still looks custom/tool-like

## P1. Shell Fidelity

- [ ] Make the outer window chrome feel more like a desktop client
- [ ] Reduce custom branding and dashboard-ish chrome
- [ ] Make the far-left rail quieter and more native
- [ ] Add a more believable desktop titlebar rhythm:
  - left app identity
  - center search
  - right utility/status area
- [ ] Remove remaining product-demo feeling from the first screen
- [ ] Make the global background and frame feel like a client window, not a showcase panel
- [ ] Tighten corner radii and borders toward NTQQ-like restraint

## P2. Conversation List Fidelity

- [ ] Emphasize avatar, name, snippet, time, unread/review badge
- [ ] Demote raw system-facing identifiers
- [ ] Increase IM-like row density and rhythm
- [ ] Reduce analysis metadata in the default row
- [ ] Make active conversation state more QQ-like and less dashboard-like
- [ ] Improve hover/selection rhythm to feel like a chat client
- [ ] Make the search bar look like QQ list search, not a generic input
- [ ] Ensure list rows feel like conversations first, review units second

## P3. Chat Surface Fidelity

- [ ] Make bubbles, spacing, avatars, and timestamps feel more QQ-native
- [ ] Make image messages feel like chat media, not asset cards
- [ ] Hide or soften review scaffolding inside the main transcript
- [ ] Rework date / anchor separators so they read like in-chat helper chrome
- [ ] Make sender name / time / bubble rhythm closer to QQ group chat
- [ ] Tighten the visual contrast between text messages and media messages
- [ ] Reduce "evidence viewer" styling from the message stream
- [ ] Ensure click/selection states feel like chat focus, not inspection highlight

## P4. Drawer Fidelity

- [ ] Make the right side feel like a details/profile drawer first
- [ ] Subordinate tool blocks under contextual details
- [ ] Improve drawer chrome, hierarchy, and identity feel
- [ ] Strengthen cover/header/avatar/details composition
- [ ] Make tabs feel like drawer tabs, not tool tabs
- [ ] Reduce explicit tool naming in primary drawer chrome
- [ ] Keep forms and model output secondary to contextual info
- [ ] Make collapse/open behavior feel like a side drawer, not a detachable inspector

## P5. Composer Fidelity

- [ ] Make the bottom area visually inherit QQ input-composer grammar
- [ ] Reduce status-tray feeling
- [ ] Keep our actions, but hide them inside a believable composer shell
- [ ] Add a clearer fake-input hierarchy:
  - input shell first
  - utility actions second
- [ ] Make action buttons feel closer to attachments / send-zone logic
- [ ] Ensure the bottom area no longer reads as a toolbar
- [ ] Keep status text embedded inside the composer, not above it

## P6. Micro-Fidelity

- [ ] Normalize cold/desktop color temperature across shell, list, chat, drawer
- [ ] Tighten spacing and density to reduce "custom web app" feel
- [ ] Reduce decorative gradients that hurt NTQQ likeness
- [ ] Improve avatar shape, badge sizing, and subtle shadows
- [ ] Ensure the strongest text hierarchy matches a chat client, not a product demo

## P7. Validation

- [ ] Keep frontend regression green
- [ ] Keep `vue-tsc --noEmit` green
- [ ] Keep `vite build` green
- [ ] Keep backend summary regression green
- [ ] Extend harness expectations to match the more QQ-like shell semantics
