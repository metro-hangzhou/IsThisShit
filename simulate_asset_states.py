from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
RUNTIME_SITE_PACKAGES = REPO_ROOT / "runtime_site_packages"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
if RUNTIME_SITE_PACKAGES.exists() and str(RUNTIME_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SITE_PACKAGES))

from qq_data_integrations.napcat.asset_simulator import (  # noqa: E402
    all_asset_resolution_scenarios,
    default_asset_resolution_scenarios,
    default_forward_timeout_matrix,
    run_asset_resolution_matrix,
    run_asset_resolution_sequence,
    run_asset_resolution_scenario,
    run_forward_timeout_simulation,
    summarize_asset_resolution_catalog,
    summarize_asset_resolution_results,
    summarize_forward_timeout_results,
    write_simulation_trace,
)

RESOLUTION_SUITES = sorted({item.suite for item in all_asset_resolution_scenarios()})


def _render_result(result: dict[str, Any]) -> str:
    snapshot = result.get("progress_snapshot") or {}
    return "\n".join(
        [
            "asset_simulation:",
            f"  route={result['route']} asset_type={result['asset_type']}",
            f"  parents={result['parents']} siblings_per_parent={result['siblings_per_parent']}",
            f"  total_requests={result['total_requests']}",
            f"  backend_timeout_calls={result['backend_timeout_calls']}",
            f"  short_circuited_requests={result['short_circuited_requests']}",
            (
                "  timing="
                f"simulated_elapsed={result['simulated_elapsed_s']:.3f}s "
                f"timeout_budget={result['timeout_budget_s']:.1f}s "
                f"equivalent_live_timeout={result['equivalent_live_timeout_s']:.1f}s"
            ),
            (
                "  snapshot="
                f"timeout_count={int(snapshot.get('timeout_count') or 0)} "
                f"forward_context_timeout_count={int(snapshot.get('forward_context_timeout_count') or 0)} "
                f"forward_context_empty_count={int(snapshot.get('forward_context_empty_count') or 0)} "
                f"forward_context_error_count={int(snapshot.get('forward_context_error_count') or 0)}"
            ),
            f"  trace_status_breakdown={result['trace_status_breakdown']}",
            f"  explanation={result['explanation']}",
        ]
    )


def _render_forward_timeout_summary(summary: dict[str, Any]) -> str:
    worst_case = summary.get("worst_case") or {}
    return "\n".join(
        [
            "forward_timeout_summary:",
            (
                "  totals="
                f"scenarios={summary['total']} "
                f"equivalent_live_timeout_total_s={summary['equivalent_live_timeout_total_s']:.1f} "
                f"breaker_savings_total_s={summary['breaker_savings_total_s']:.1f}"
            ),
            (
                "  risk="
                f"storm_risk_count={summary['storm_risk_count']} "
                f"short_circuit_help_count={summary['short_circuit_help_count']}"
            ),
            f"  route_counts={summary['route_counts']}",
            f"  asset_type_counts={summary['asset_type_counts']}",
            f"  age_bucket_counts={summary['age_bucket_counts']}",
            f"  trace_status_totals={summary['trace_status_totals']}",
            (
                "  worst_case="
                f"{worst_case.get('route')} {worst_case.get('asset_type')} "
                f"age_days={worst_case.get('age_days')} "
                f"parents={worst_case.get('parents')} siblings={worst_case.get('siblings_per_parent')} "
                f"equivalent_live_timeout_s={worst_case.get('equivalent_live_timeout_s')}"
            ),
        ]
    )


def _render_resolution_result(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "asset_resolution_simulation:",
            f"  name={result['name']}",
            f"  suite={result['suite']}",
            f"  asset_type={result['asset_type']} topology={result['topology']} age_days={result['age_days']}",
            (
                "  expectation="
                f"resolver={result['expected_resolver']} path_kind={result['expected_path_kind']}"
            ),
            (
                "  actual="
                f"resolver={result['actual_resolver']} path_kind={result['actual_path_kind']} matched={result['matched']}"
            ),
            (
                "  calls="
                f"public={result['client_call_count']} fast={result['fast_call_count']} remote={result['remote_attempt_count']}"
            ),
            f"  cost_matched={result['cost_matched']}",
            f"  trace_status_breakdown={result['trace_status_breakdown']}",
            f"  notes={result['notes']}",
        ]
    )


def _render_resolution_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "resolution_summary:",
            (
                "  totals="
                f"total={summary['total']} matched={summary['matched']} "
                f"mismatched={summary['mismatched']} cost_overruns={summary['cost_overruns']}"
            ),
            f"  suite_counts={summary['suite_counts']}",
            f"  asset_type_counts={summary['asset_type_counts']}",
            f"  topology_counts={summary['topology_counts']}",
            f"  age_bucket_counts={summary['age_bucket_counts']}",
            f"  resolver_counts={summary['resolver_counts']}",
            f"  path_kind_counts={summary['path_kind_counts']}",
            f"  trace_status_totals={summary['trace_status_totals']}",
        ]
    )


def _render_catalog_summary(summary: dict[str, Any]) -> str:
    interesting_fields = (
        "forward_parent_state",
        "source_path_state",
        "hint_local_state",
        "hint_remote_state",
        "forward_payload_state",
        "public_result_state",
        "public_fallback_result_state",
        "direct_file_result_state",
    )
    lines = [
        "resolution_catalog:",
        f"  total={summary['total']}",
        f"  suite_counts={summary['suite_counts']}",
        f"  asset_type_counts={summary['asset_type_counts']}",
        f"  topology_counts={summary['topology_counts']}",
        f"  age_bucket_counts={summary['age_bucket_counts']}",
    ]
    state_field_counts = summary.get("state_field_counts") or {}
    for field_name in interesting_fields:
        lines.append(f"  {field_name}={state_field_counts.get(field_name, {})}")
    return "\n".join(lines)


def _render_resolution_sequence_result(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "asset_resolution_sequence:",
            f"  name={result['name']}",
            f"  suite={result['suite']} repeats={result['repeats']}",
            (
                "  expectation="
                f"resolver={result['expected_resolver']} path_kind={result['expected_path_kind']}"
            ),
            (
                "  actual="
                f"resolver={result['actual_resolver']} path_kind={result['actual_path_kind']} matched={result['matched']}"
            ),
            f"  unique_resolvers={list(result['unique_resolvers'])}",
            f"  unique_path_kinds={list(result['unique_path_kinds'])}",
            (
                "  calls="
                f"public={result['client_call_count']} fast={result['fast_call_count']} remote={result['remote_attempt_count']}"
            ),
            f"  cost_matched={result['cost_matched']}",
            f"  trace_status_breakdown={result['trace_status_breakdown']}",
            f"  notes={result['notes']}",
        ]
    )


def main() -> None:
    logging.getLogger("qq_data_integrations.napcat.media_downloader").setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(
        description="Local simulator for NapCat asset timeout and forward-media failure patterns.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    forward_parser = subparsers.add_parser(
        "forward-timeout",
        help="Simulate forward asset timeout behavior under different parent/sibling layouts.",
    )
    forward_parser.add_argument(
        "--route",
        choices=["public-token", "forward-materialize", "forward-metadata"],
        default="public-token",
    )
    forward_parser.add_argument(
        "--asset-type",
        choices=["video", "speech", "file"],
        default="video",
    )
    forward_parser.add_argument("--parents", type=int, default=8)
    forward_parser.add_argument("--siblings-per-parent", type=int, default=4)
    forward_parser.add_argument(
        "--delay-s",
        type=float,
        default=0.02,
        help="Artificial delay per backend timeout call; keep small for fast local diagnosis.",
    )
    forward_parser.add_argument("--json", action="store_true")
    forward_parser.add_argument("--trace-out", type=Path, default=None)

    matrix_parser = subparsers.add_parser(
        "matrix",
        help="Run a small comparison matrix across common forward timeout scenarios.",
    )
    matrix_parser.add_argument("--delay-s", type=float, default=0.02)
    matrix_parser.add_argument("--json", action="store_true")
    matrix_parser.add_argument("--summary-only", action="store_true")

    resolution_parser = subparsers.add_parser(
        "resolution-matrix",
        help="Run a scenario-driven resolution matrix across asset families and states.",
    )
    resolution_parser.add_argument("--json", action="store_true")
    resolution_parser.add_argument(
        "--suite",
        choices=RESOLUTION_SUITES,
        default=None,
    )
    resolution_parser.add_argument("--summary-only", action="store_true")
    resolution_parser.add_argument("--only-mismatched", action="store_true")
    resolution_parser.add_argument("--only-cost-overrun", action="store_true")

    resolution_catalog_parser = subparsers.add_parser(
        "resolution-catalog",
        help="Summarize scenario coverage and state-shape distribution without running exporter logic.",
    )
    resolution_catalog_parser.add_argument("--json", action="store_true")

    resolution_case_parser = subparsers.add_parser(
        "resolution-case",
        help="Run one named asset resolution scenario.",
    )
    resolution_case_parser.add_argument("name")
    resolution_case_parser.add_argument("--json", action="store_true")

    resolution_sequence_parser = subparsers.add_parser(
        "resolution-sequence",
        help="Run one named asset resolution scenario repeatedly with one downloader instance to inspect cache/breaker reuse.",
    )
    resolution_sequence_parser.add_argument("name")
    resolution_sequence_parser.add_argument("--repeats", type=int, default=3)
    resolution_sequence_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "forward-timeout":
        events: list[dict[str, Any]] = []
        result = run_forward_timeout_simulation(
            route=args.route,
            asset_type=args.asset_type,
            parents=args.parents,
            siblings_per_parent=args.siblings_per_parent,
            delay_s=args.delay_s,
            trace_callback=events.append if args.trace_out else None,
        ).to_dict()
        if args.trace_out is not None:
            write_simulation_trace(args.trace_out, events)
            result["trace_out"] = str(args.trace_out)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(_render_result(result))
        return

    if args.command == "matrix":
        matrix_results = default_forward_timeout_matrix(delay_s=args.delay_s)
        summary = summarize_forward_timeout_results(matrix_results)
        results = [item.to_dict() for item in matrix_results]
        if args.json:
            print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
            return
        print(_render_forward_timeout_summary(summary))
        if args.summary_only:
            return
        for index, result in enumerate(results, start=1):
            if index == 1:
                print()
            else:
                print()
            print(f"[scenario {index}]")
            print(_render_result(result))
        return

    if args.command == "resolution-matrix":
        all_results = run_asset_resolution_matrix(suite=args.suite)
        summary = summarize_asset_resolution_results(all_results)
        results = [item.to_dict() for item in all_results]
        if args.only_mismatched:
            results = [item for item in results if not bool(item.get("matched"))]
        if args.only_cost_overrun:
            results = [item for item in results if not bool(item.get("cost_matched"))]
        if args.json:
            print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
            return
        print(_render_resolution_summary(summary))
        if args.suite:
            print(f"resolution_suite: {args.suite}")
        if args.only_mismatched:
            print("resolution_filter: only_mismatched=1")
        if args.only_cost_overrun:
            print("resolution_filter: only_cost_overrun=1")
        if args.summary_only:
            return
        for index, result in enumerate(results, start=1):
            print()
            print(f"[scenario {index}]")
            print(_render_resolution_result(result))
        return

    if args.command == "resolution-catalog":
        summary = summarize_asset_resolution_catalog()
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(_render_catalog_summary(summary))
        return

    if args.command == "resolution-case":
        scenarios = {item.name: item for item in all_asset_resolution_scenarios()}
        scenario = scenarios.get(args.name)
        if scenario is None:
            raise SystemExit(f"unknown scenario: {args.name}")
        result = run_asset_resolution_scenario(scenario).to_dict()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(_render_resolution_result(result))
        return

    if args.command == "resolution-sequence":
        scenarios = {item.name: item for item in all_asset_resolution_scenarios()}
        scenario = scenarios.get(args.name)
        if scenario is None:
            raise SystemExit(f"unknown scenario: {args.name}")
        result = run_asset_resolution_sequence(scenario, repeats=args.repeats).to_dict()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(_render_resolution_sequence_result(result))
        return


if __name__ == "__main__":
    main()
