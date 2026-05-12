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
- Root `.gitignore` now ignores `/NapCat/`; this path is reserved as a local runtime workdir.
- Existing parent-repo tracked `NapCat/` runtime files were removed from the parent Git index with `git rm --cached`.
- The project-owned fast history plugin has been copied out of the runtime tree into:
  - `plugins/napcat-plugin-qq-data-fast/`

## What did not change

- Existing local `NapCat/` runtime files were not physically deleted or moved.
- Existing local dirty changes inside `NapCatQQ` were not modified.
- Existing local runtime config/cache files were not touched.

## Follow-up migration

The next safe migration steps are separate:

1. Keep `NapCat/` as a local ignored runtime workdir unless a release task explicitly replaces it.
2. Update launcher/bootstrap docs and scripts to install or sync `plugins/napcat-plugin-qq-data-fast/` into the active NapCat runtime plugin directory.
3. Validate with a live NapCat restart because plugin route changes are not hot-loaded.
4. If runtime files ever need to be removed from disk, ask for explicit approval first.

## Known caveat

`NapCatQQ` currently has local dirty content in its own checkout. The parent repository submodule pointer records only the pinned commit above. Treat the submodule dirty state as a local upstream-research/runtime matter, not as parent-repo content.
