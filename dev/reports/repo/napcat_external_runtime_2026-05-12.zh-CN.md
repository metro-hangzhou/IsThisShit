# NapCat external runtime reference - 2026-05-12

## Current decision

NapCat runtime is treated as an external upstream project, not ordinary parent-repo source.

Official upstream:

- `https://github.com/NapNeko/NapCatQQ.git`

Parent repo reference:

- submodule path: `NapCatQQ`
- pinned commit at migration time: `7ee2f1c40de1cdac7819b2d0db6aa7e4de4212f7`

## What changed

- `NapCatQQ` is now registered in `.gitmodules` as a submodule.
- Root `.gitignore` no longer ignores `/NapCatQQ/`, because Git must be able to track the submodule gitlink.
- The project-owned fast history plugin has been copied out of the runtime tree into:
  - `plugins/napcat-plugin-qq-data-fast/`

## What did not change

- Existing tracked `NapCat/` runtime files were not deleted, moved, or removed from Git index.
- Existing local dirty changes inside `NapCatQQ` were not modified.
- Existing local runtime config/cache files were not touched.

## Follow-up migration

The next safe migration step is separate and requires explicit approval:

1. Decide whether `NapCat/` should remain as a local ignored runtime workdir or be replaced by `NapCatQQ` directly.
2. If replacing/removing tracked `NapCat/` runtime files, use Git index operations and native shell commands only after approval.
3. Update launcher/bootstrap docs and scripts to install or sync `plugins/napcat-plugin-qq-data-fast/` into the active NapCat runtime plugin directory.
4. Validate with a live NapCat restart because plugin route changes are not hot-loaded.

## Known caveat

`NapCatQQ` currently has local dirty content in its own checkout. The parent repository submodule pointer records only the pinned commit above. Treat the submodule dirty state as a local upstream-research/runtime matter, not as parent-repo content.
