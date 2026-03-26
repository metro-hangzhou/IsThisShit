# AGENTs.speech_output_surface

## Scope

Analyze speech/record behavior in:

- `src/qq_data_integrations/napcat/media_downloader.py`
- `src/qq_data_core/media_bundle.py`
- `src/qq_data_core/normalize.py`
- speech-related tests

## Goal

Extract speech-specific evidence dimensions and final-output semantics.

Focus on:

- `get_record` route shapes
- format/original-vs-converted semantics
- terminal proof families
- manifest and materialization outcome semantics

## Do Not

- generalize from image/video rules unless the code actually shares them

