# Shi Analyzer TODO Overview

Near-term execution order:

1. register local corpora and protect `shi_group_751365230`
2. restore and verify preprocess / analysis baseline
3. normalize exporter-manifest compatibility
4. run preprocess smoke on local corpora
5. run deterministic analysis smoke on local corpora
6. review corpus-role assignment with evidence before fixing long-term labels
7. batch those calibrated corpora through a stable corpus-directory suite facade before broader manual-review scaling
8. make the batch suite persist incremental manifests, per-corpus logs, and human-auditable batch reports so long-running corpora do not leave an opaque half-run state

Current hold points:

- retro-review of restored analyzer code is still required
- after the stable corpus-directory suite facade, the next infrastructure checkpoint is a repeatable batch run surface with per-corpus logs and human-auditable reports
