# NapCat Runtime Handbook

This handbook records the repository's operating rules around the vendored `NapCat/` runtime.

## Scope

This is not an upstream source handbook.

It exists to answer:

- which local runtime paths are operator-managed state
- which files belong to the repo-side launcher bridge
- when a plugin/config change requires a real restart
- where runtime debugging should begin before deeper source inspection

## Core rules

- treat `NapCat/` as a vendored runtime shell plus mutable local runtime state
- treat `NapCatQQ/` as the upstream/reference source checkout
- do not flatten either tree into ordinary parent-repo content
- use [start_napcat_logged.bat](../../../start_napcat_logged.bat) as the repo-level launch bridge
- use [restart_napcat_service.ps1](../../../restart_napcat_service.ps1) when plugin/launcher changes require a clean restart
- after plugin code changes, do not trust the old process; restart NapCat for routes to refresh

## Read this with

- [NapCat_AGENTs.md](../../../NapCat_AGENTs.md)
- [dev/reports/napcat/runtime_surface.md](../../reports/napcat/runtime_surface.md)
- [dev/reports/napcat/runtime_state_and_plugins.md](../../reports/napcat/runtime_state_and_plugins.md)
