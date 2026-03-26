# AGENTs.forward_recursive_surface

## Scope

Analyze forward recursion and repeated identity in:

- `src/qq_data_core/normalize.py`
- `src/qq_data_core/media_bundle.py`
- `src/qq_data_integrations/napcat/provider.py`
- `src/qq_data_integrations/napcat/media_downloader.py`
- `src/qq_data_integrations/napcat/asset_simulator.py`

## Goal

Define a finite symbolic model for theoretically unbounded nested `forward` chains.

Focus on:

- recursive invariants
- repeated handle / alias / rejoin behavior
- parent partiality
- identity promotion
- finite chain families that replace infinite expansion

## Do Not

- propose arbitrary max-depth expansion

