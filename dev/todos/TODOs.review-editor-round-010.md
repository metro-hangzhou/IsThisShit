# Review Editor Round 010 TODOs

## P0. Reviewer Loop

- [x] reviewer questions and blockers opened
- [x] worker/explorer responses recorded
- [x] reviewer recheck completed in the same round

## P1. Raw Sender Mapping

- [x] expose raw sender id/name on all primary visible sender surfaces
- [x] eliminate visible `user_xxx` leakage
- [x] keep group id as the primary conversation identity

## P2. Shell / Conversation

- [x] reduce top bar tool branding
- [x] make conversation rows feel more like chat sessions
- [x] reduce synthetic system-object identity in the list

## P3. Chat / Composer

- [x] reduce anchor/review overlay feel
- [x] make media messages feel more native to chat
- [x] remove internal-state narration from the composer shell

## P4. Drawer

- [x] keep drawer stable under verdict changes
- [x] reduce tool taxonomy visibility
- [x] keep details/profile semantics dominant

## P5. Validation

- [x] add raw sender visibility tests
- [x] add alias invisibility tests
- [x] keep frontend and backend regression green

## Remaining Non-Blocking Work

- [ ] do one fresh live UI pass in the browser after the latest shell / drawer / composer tweaks
- [ ] decide whether to keep or delete legacy unused components such as `ModelTab.vue`, `WindowSummaryTab.vue`, and `ReviewFormTab.vue`
