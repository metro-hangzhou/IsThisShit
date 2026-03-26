from __future__ import annotations

import json
from pathlib import Path

from qq_data_integrations.napcat.asset_simulator import (
    summarize_simulator_cross_track_join_schema,
    summarize_simulator_evidence_dimension_manifest,
    summarize_simulator_global_evidence_registry,
    summarize_simulator_result_algebra_spec,
    summarize_simulator_value_witness_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "state" / "subagent_runs" / "coverage_reachability_surface"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    _write_json(
        OUT_DIR / "evidence_dimension_manifest.json",
        summarize_simulator_evidence_dimension_manifest(),
    )
    _write_json(
        OUT_DIR / "global_evidence_registry.json",
        summarize_simulator_global_evidence_registry(),
    )
    _write_json(
        OUT_DIR / "value_witness_ledger.json",
        summarize_simulator_value_witness_ledger(),
    )
    _write_json(
        OUT_DIR / "cross_track_join_schema.json",
        summarize_simulator_cross_track_join_schema(),
    )
    _write_json(
        OUT_DIR / "result_algebra_spec.json",
        summarize_simulator_result_algebra_spec(),
    )
    print("EXPORTED_EVIDENCE_MANIFESTS")
    print(f"out_dir={OUT_DIR}")


if __name__ == "__main__":
    main()
