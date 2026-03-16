from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from qq_data_analysis import AnalysisJobConfig, AnalysisTarget, AnalysisTimeScope
from qq_data_analysis.agents import BaseStatsAgent, ContentCompositionAgent
from qq_data_analysis.compact import dump_compact_json
from qq_data_analysis.llm_agent import (
    DeepSeekAnalysisClient,
    GroundedLlmAgent,
    load_deepseek_runtime_config,
)
from qq_data_analysis.substrate import AnalysisSubstrate


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
            "Run DeepSeek-backed QQ chat analysis on a dense high-signal slice, "
            "not the full chat history."
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
    parser.add_argument("--projection-mode", choices=["alias", "raw"], default="alias")
    parser.add_argument("--danger-allow-raw-identity-output", action="store_true")
    parser.add_argument(
        "--llm-config",
        type=Path,
        default=Path("state/config/llm.local.json"),
    )
    parser.add_argument("--model")
    parser.add_argument("--event-index", type=int, default=0)
    parser.add_argument("--max-messages", type=int, default=240)
    parser.add_argument("--max-rendered-messages", type=int, default=48)
    parser.add_argument("--max-input-tokens", type=int, default=12000)
    parser.add_argument("--max-output-tokens", type=int, default=1200)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("state/analysis_runs"))
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
    )

    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(config)
        base_output = BaseStatsAgent().analyze(materials, materials)
        composition_output = ContentCompositionAgent().analyze(materials, materials)

        runtime = None
        client = None
        if not args.plan_only:
            runtime = load_deepseek_runtime_config(args.llm_config)
            if args.model:
                runtime.model = args.model
            client = DeepSeekAnalysisClient(runtime)
        agent = GroundedLlmAgent(
            client=client if client is not None else _PlanOnlyLlmClient(),
            max_messages=args.max_messages,
            max_rendered_messages=args.max_rendered_messages,
            max_input_tokens=args.max_input_tokens,
            max_output_tokens=args.max_output_tokens,
            event_index=args.event_index,
        )
        plan = agent.prepare(materials)

        print("## LLM Slice Plan")
        print(
            "target={target} window={start} -> {end}".format(
                target=materials.target.display_name or materials.target.display_id,
                start=materials.chosen_time_window.start_timestamp_iso,
                end=materials.chosen_time_window.end_timestamp_iso,
            )
        )
        print(
            "source={src} source_window={start} -> {end} source_messages={count}".format(
                src=plan.source_label,
                start=plan.source_start_iso,
                end=plan.source_end_iso,
                count=plan.source_message_count,
            )
        )
        print(
            "selected_window={start} -> {end} selected_messages={count} trimmed={trimmed}".format(
                start=plan.selected_start_iso,
                end=plan.selected_end_iso,
                count=len(plan.selected_messages),
                trimmed=plan.trimmed,
            )
        )
        print(f"rendered_messages={plan.rendered_message_count}")
        print(
            "token_budget estimated_input={inp} max_output={out}".format(
                inp=plan.estimated_input_tokens,
                out=plan.max_output_tokens,
            )
        )

        if args.plan_only:
            return

        print("Calling DeepSeek...")
        llm_output = agent.analyze(materials, plan)
        print("DeepSeek completed.")
        print(llm_output.human_report)

        args.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = (
            f"llm_{args.target_type}_{args.target_id}_{stamp}"
        )
        summary_report = "\n\n".join(
            [
                base_output.human_report,
                composition_output.human_report,
                llm_output.human_report,
            ]
        )
        compact_payload = {
            "rid": materials.run_id,
            "t": {
                "tt": materials.target.target_type,
                "id": materials.target.display_id,
                "nm": materials.target.display_name,
            },
            "win": {
                "m": materials.chosen_time_window.mode,
                "s": materials.chosen_time_window.start_timestamp_ms,
                "e": materials.chosen_time_window.end_timestamp_ms,
                "si": materials.chosen_time_window.start_timestamp_iso,
                "ei": materials.chosen_time_window.end_timestamp_iso,
                "why": materials.chosen_time_window.rationale,
                "n": materials.chosen_time_window.selected_message_count,
            },
            "ags": [
                {"n": base_output.agent_name, "v": base_output.agent_version, "d": base_output.compact_payload},
                {"n": composition_output.agent_name, "v": composition_output.agent_version, "d": composition_output.compact_payload},
                {"n": llm_output.agent_name, "v": llm_output.agent_version, "d": llm_output.compact_payload},
            ],
        }
        bundle = {
            "plan": {
                "source_label": plan.source_label,
                "source_start_iso": plan.source_start_iso,
                "source_end_iso": plan.source_end_iso,
                "source_message_count": plan.source_message_count,
                "selected_start_iso": plan.selected_start_iso,
                "selected_end_iso": plan.selected_end_iso,
                "selected_message_count": len(plan.selected_messages),
                "rendered_message_count": plan.rendered_message_count,
                "estimated_input_tokens": plan.estimated_input_tokens,
                "max_output_tokens": plan.max_output_tokens,
                "trimmed": plan.trimmed,
            },
            "compact": compact_payload,
            "summary_report": summary_report,
        }

        (args.out_dir / f"{prefix}.txt").write_text(summary_report, encoding="utf-8")
        (args.out_dir / f"{prefix}.compact.json").write_text(
            dump_compact_json(compact_payload),
            encoding="utf-8",
        )
        (args.out_dir / f"{prefix}.bundle.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        substrate.close()

class _PlanOnlyLlmClient:
    def analyze(self, *, system_prompt: str, user_prompt: str, max_output_tokens: int):
        raise RuntimeError("Plan-only mode should not execute the LLM client.")


if __name__ == "__main__":
    main()
