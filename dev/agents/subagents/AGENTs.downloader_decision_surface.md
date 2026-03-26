# AGENTs.downloader_decision_surface

## Scope

Analyze only the downloader decision surface in:

- `src/qq_data_integrations/napcat/media_downloader.py`
- downloader-facing tests

## Goal

Extract the complete set of evidence dimensions and route-order rules that affect:

- resolver
- path kind
- terminality
- timeout scope
- shared/reuse scope
- second-pass gate

## Do

- enumerate dimensions
- enumerate reachability constraints
- identify partially modeled or missing dimensions in the simulator
- point to exact file refs

## Do Not

- inspect UI/REPL
- inspect release sync concerns
- propose sample-specific fixes

