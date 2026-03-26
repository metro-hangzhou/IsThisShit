# AGENTs.coverage_reachability_surface

## Scope

Analyze simulator coverage and reachability only in:

- `src/qq_data_integrations/napcat/asset_simulator.py`
- `tests/test_asset_simulator.py`

## Goal

Answer:

- which dimensions are fully covered
- which are partial
- which values lack witness scenarios
- which values should be unreachable with reasons
- which gates are still too weak

## Do Not

- patch exporter logic
- propose “just add more cases” without identifying the dimension or reachability gap

