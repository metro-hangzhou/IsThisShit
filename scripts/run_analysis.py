from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from qq_data_analysis import (
    AnalysisJobConfig,
    AnalysisService,
    AnalysisTarget,
    AnalysisTimeScope,
)


def _parse_timestamp(value: str) -> int:
    for fmt in ("%Y-%m-%d_%H-%M-%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(value, fmt).astimezone().timestamp() * 1000)
        except ValueError:
            continue
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run target-driven QQ chat analysis from an existing preprocess state. "
            "This resolves a bounded window and produces pack-ready analysis output; "
            "it is not a raw full-history prompt path."
        )
    )
    parser.add_argument("target_type", choices=["group", "friend"])
    parser.add_argument("target_id")
    parser.add_argument("--state-dir", type=Path, default=Path("state/preprocess"))
    parser.add_argument("--sqlite-path", type=Path)
    parser.add_argument("--qdrant-path", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--auto-window-hours", type=int, default=24)
    parser.add_argument(
        "--agent",
        dest="agents",
        action="append",
        default=[],
        help="May be repeated. Defaults to base_stats + content_composition.",
    )
    parser.add_argument("--projection-mode", choices=["alias", "raw"], default="alias")
    parser.add_argument("--danger-allow-raw-identity-output", action="store_true")
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()

    sqlite_path = args.sqlite_path or args.state_dir / "db" / "analysis.db"
    qdrant_path = args.qdrant_path or args.state_dir / "qdrant"
    if args.start or args.end:
        if not args.start or not args.end:
            raise SystemExit("Manual analysis requires both --start and --end.")
        time_scope = AnalysisTimeScope(
            mode="manual",
            start_timestamp_ms=_parse_timestamp(args.start),
            end_timestamp_ms=_parse_timestamp(args.end),
        )
    else:
        time_scope = AnalysisTimeScope(
            mode="auto_adaptive",
            auto_window_ms=args.auto_window_hours * 60 * 60 * 1000,
        )

    config = AnalysisJobConfig(
        target=AnalysisTarget(
            target_type=args.target_type,
            target_id=args.target_id,
            run_id=args.run_id,
        ),
        time_scope=time_scope,
        projection_mode=args.projection_mode,
        danger_allow_raw_identity_output=args.danger_allow_raw_identity_output,
        agent_names=args.agents or ["base_stats", "content_composition"],
    )

    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(config)
    finally:
        service.close()

    print(result.summary_report)
    print("\n## Compact JSON")
    print(result.compact_machine_output)

    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"analysis_{args.target_type}_{args.target_id}_{stamp}"
        (args.out_dir / f"{prefix}.txt").write_text(
            result.summary_report,
            encoding="utf-8",
        )
        (args.out_dir / f"{prefix}.json").write_text(
            result.compact_machine_output,
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
