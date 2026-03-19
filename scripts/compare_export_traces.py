from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _load_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _summary_for_trace(path: Path) -> dict:
    rows = _load_rows(path)
    export_complete = next((row for row in rows if row.get("kind") == "export_complete"), None)
    if export_complete is None:
        raise RuntimeError(f"export_complete not found in {path}")
    pool_config = None
    for row in rows:
        if row.get("phase") == "prefetch_pool_config" and str(row.get("stage") or "") == "done":
            pool_config = row
    substeps = Counter(
        (row.get("substep"), row.get("status"))
        for row in rows
        if row.get("phase") == "materialize_asset_substep"
    )
    interesting = {}
    for (substep, status), count in sorted(
        substeps.items(),
        key=lambda item: ((item[0][0] or ""), (item[0][1] or "")),
    ):
        if not substep:
            continue
        if (
            "public_token" in substep
            or "prefetch" in substep
            or "forward_context" in substep
            or "direct_file_id" in substep
        ):
            interesting[f"{substep}:{status or '-'}"] = count
    return {
        "path": str(path),
        "elapsed_s": export_complete.get("elapsed_s"),
        "copied": export_complete.get("copied_asset_count"),
        "reused": export_complete.get("reused_asset_count"),
        "missing": export_complete.get("missing_asset_count"),
        "slowest_materialize_step_s": export_complete.get("slowest_materialize_step_s"),
        "missing_breakdown": (
            export_complete.get("content_summary", {}) or {}
        ).get("missing_breakdown", {}),
        "prefetch_pool_config": {
            "remote_workers": pool_config.get("remote_workers"),
            "public_token_workers": pool_config.get("public_token_workers"),
            "total_prefetchable": pool_config.get("total_prefetchable"),
            "eager_remote_prefetchable": pool_config.get("eager_remote_prefetchable"),
            "feedback": pool_config.get("feedback"),
        }
        if isinstance(pool_config, dict)
        else None,
        "interesting_substeps": interesting,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare export trace summaries.")
    parser.add_argument("trace", nargs="+", help="Path(s) to export trace jsonl files")
    args = parser.parse_args()

    summaries = [_summary_for_trace(Path(trace)) for trace in args.trace]
    for summary in summaries:
        print(f"trace={summary['path']}")
        print(
            "  "
            f"elapsed={summary['elapsed_s']}s copied={summary['copied']} "
            f"reused={summary['reused']} missing={summary['missing']} "
            f"slowest_materialize_step_s={summary['slowest_materialize_step_s']}"
        )
        if summary["prefetch_pool_config"]:
            print(f"  prefetch_pool_config={summary['prefetch_pool_config']}")
        if summary["missing_breakdown"]:
            print(f"  missing_breakdown={summary['missing_breakdown']}")
        for key, value in summary["interesting_substeps"].items():
            print(f"  {key}={value}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
