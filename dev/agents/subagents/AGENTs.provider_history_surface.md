# AGENTs.provider_history_surface

## Scope

Analyze only provider/history behavior in:

- `src/qq_data_integrations/napcat/provider.py`
- fast history client
- fast plugin history/full-bulk/forward-detail routes
- provider-facing tests

## Goal

Extract the evidence dimensions that affect exporter behavior before media resolution begins.

Focus on:

- history source
- chat provenance
- bulk/before fallback
- forward-detail hydration and fallback
- route-state memory

## Do Not

- drift into media downloader internals except where provider hands state into downloader

