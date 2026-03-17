from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_ASSET_TYPES = ("file", "video")
EXPORT_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parent
    candidates = [repo_root / "runtime_site_packages", repo_root / "src", repo_root]
    for candidate in reversed(candidates):
        candidate_str = str(candidate)
        if candidate.exists() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


_bootstrap_repo_imports()


def _json_dumps_safe(payload: Any, *, indent: int | None = None) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=indent, default=str)


@dataclass(frozen=True, slots=True)
class Strategy:
    name: str
    pad_before_s: int
    pad_after_s: int
    refresh: bool


@dataclass(frozen=True, slots=True)
class MissingAsset:
    message_id: str
    timestamp_iso: str
    timestamp_literal: str
    asset_type: str
    file_name: str
    resolver: str | None
    missing_kind: str | None
    sender_name: str | None


@dataclass(frozen=True, slots=True)
class MissingCluster:
    index: int
    start_ts: str
    end_ts: str
    start_literal: str
    end_literal: str
    asset_count: int
    asset_types: tuple[str, ...]
    file_names: tuple[str, ...]
    message_ids: tuple[str, ...]
    assets: tuple[MissingAsset, ...]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retest only missing file/video assets from the latest export manifest.",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Path to a .manifest.json file.")
    parser.add_argument(
        "--asset-type",
        action="append",
        dest="asset_types",
        default=None,
        help="Asset type to retest. Can be repeated. Defaults to file+video.",
    )
    parser.add_argument(
        "--cluster-gap-seconds",
        type=int,
        default=90,
        help="Merge missing assets into one retest cluster if timestamps are within this gap.",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=0,
        help="Only run the first N clusters. 0 means all.",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=None,
        help="Python executable to use. Defaults to the current interpreter.",
    )
    parser.add_argument(
        "--skip-refresh-strategies",
        action="store_true",
        help="Only run non-refresh strategies.",
    )
    parser.add_argument(
        "--only-cluster",
        type=int,
        default=0,
        help="Only run the specified 1-based cluster index. 0 means all clusters.",
    )
    parser.add_argument(
        "--only-strategy",
        choices=("tight_cached", "tight_refresh", "wide_refresh"),
        default=None,
        help="Only run the specified retry strategy.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    asset_types = tuple(args.asset_types or DEFAULT_ASSET_TYPES)
    manifest_path = (args.manifest or _find_latest_manifest(repo_root, allowed_asset_types=asset_types)).resolve()
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chat_type = str(manifest.get("chat_type") or "").strip()
    chat_id = str(manifest.get("chat_id") or "").strip()
    if not chat_type or not chat_id:
        raise SystemExit("manifest is missing chat_type/chat_id")

    missing_assets = _extract_missing_assets(manifest, allowed_asset_types=asset_types)
    if not missing_assets:
        print(f"No missing assets matched types={asset_types} in {manifest_path}")
        return 0

    clusters = _build_clusters(
        missing_assets,
        cluster_gap_s=max(1, int(args.cluster_gap_seconds)),
    )
    if args.only_cluster and args.only_cluster > 0:
        clusters = [cluster for cluster in clusters if cluster.index == int(args.only_cluster)]
    if args.max_clusters and args.max_clusters > 0:
        clusters = clusters[: args.max_clusters]
    if not clusters:
        raise SystemExit("no matching clusters selected")

    strategies = _build_strategies(skip_refresh=args.skip_refresh_strategies)
    if args.only_strategy:
        strategies = [strategy for strategy in strategies if strategy.name == args.only_strategy]
    if not strategies:
        raise SystemExit("no retry strategies selected")
    run_root = _prepare_run_root(repo_root)
    latest_pointer = repo_root / "state" / "targeted_retests" / "latest.path"
    latest_pointer.parent.mkdir(parents=True, exist_ok=True)
    latest_pointer.write_text(str(run_root), encoding="utf-8")

    plan = {
        "created_at": _now_iso(),
        "manifest_path": str(manifest_path),
        "chat_type": chat_type,
        "chat_id": chat_id,
        "asset_types": list(asset_types),
        "cluster_gap_seconds": int(args.cluster_gap_seconds),
        "strategies": [asdict(strategy) for strategy in strategies],
        "clusters": [_cluster_to_json(cluster) for cluster in clusters],
    }
    _write_json(run_root / "plan.json", plan)

    results: list[dict[str, Any]] = []
    for cluster in clusters:
        for strategy in strategies:
            result = _run_cluster_strategy(
                repo_root=repo_root,
                chat_type=chat_type,
                chat_id=chat_id,
                cluster=cluster,
                strategy=strategy,
                run_root=run_root,
            )
            results.append(result)
            _print_result_line(result)

    summary = {
        "created_at": _now_iso(),
        "manifest_path": str(manifest_path),
        "chat_type": chat_type,
        "chat_id": chat_id,
        "cluster_count": len(clusters),
        "strategy_count": len(strategies),
        "results": results,
    }
    _write_json(run_root / "summary.json", summary)
    print(f"summary={run_root / 'summary.json'}")
    return 0


def _find_latest_manifest(repo_root: Path, *, allowed_asset_types: tuple[str, ...]) -> Path:
    exports_dir = repo_root / "exports"
    manifests = sorted(exports_dir.glob("*.manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        raise SystemExit(f"no manifest files found in {exports_dir}")
    wanted = {asset_type.casefold() for asset_type in allowed_asset_types}
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in manifest.get("assets") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").strip().casefold() != "missing":
                continue
            if str(item.get("asset_type") or "").strip().casefold() in wanted:
                return manifest_path
    return manifests[0]


def _extract_missing_assets(manifest: dict[str, Any], *, allowed_asset_types: tuple[str, ...]) -> list[MissingAsset]:
    wanted = {asset_type.casefold() for asset_type in allowed_asset_types}
    assets: list[MissingAsset] = []
    for item in manifest.get("assets") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().casefold() != "missing":
            continue
        asset_type = str(item.get("asset_type") or "").strip().casefold()
        if asset_type not in wanted:
            continue
        timestamp_iso = str(item.get("timestamp_iso") or "").strip()
        if not timestamp_iso:
            continue
        assets.append(
            MissingAsset(
                message_id=str(item.get("message_id") or "").strip(),
                timestamp_iso=timestamp_iso,
                timestamp_literal=_iso_to_literal(timestamp_iso),
                asset_type=asset_type,
                file_name=str(item.get("file_name") or "").strip(),
                resolver=_none_if_blank(item.get("resolver")),
                missing_kind=_none_if_blank(item.get("missing_kind")),
                sender_name=_none_if_blank((item.get("extra") or {}).get("sender_name")),
            )
        )
    assets.sort(key=lambda item: item.timestamp_iso)
    return assets


def _build_clusters(assets: list[MissingAsset], *, cluster_gap_s: int) -> list[MissingCluster]:
    if not assets:
        return []
    clusters: list[list[MissingAsset]] = [[assets[0]]]
    previous_dt = _parse_iso(assets[0].timestamp_iso)
    for asset in assets[1:]:
        current_dt = _parse_iso(asset.timestamp_iso)
        if (current_dt - previous_dt).total_seconds() <= cluster_gap_s:
            clusters[-1].append(asset)
        else:
            clusters.append([asset])
        previous_dt = current_dt

    results: list[MissingCluster] = []
    for index, group in enumerate(clusters, start=1):
        dts = [_parse_iso(item.timestamp_iso) for item in group]
        start_dt = min(dts)
        end_dt = max(dts)
        results.append(
            MissingCluster(
                index=index,
                start_ts=start_dt.isoformat(),
                end_ts=end_dt.isoformat(),
                start_literal=_dt_to_literal(start_dt),
                end_literal=_dt_to_literal(end_dt),
                asset_count=len(group),
                asset_types=tuple(sorted({item.asset_type for item in group})),
                file_names=tuple(item.file_name for item in group),
                message_ids=tuple(item.message_id for item in group),
                assets=tuple(group),
            )
        )
    return results


def _build_strategies(*, skip_refresh: bool) -> list[Strategy]:
    strategies = [
        Strategy("tight_cached", pad_before_s=20, pad_after_s=20, refresh=False),
        Strategy("tight_refresh", pad_before_s=20, pad_after_s=20, refresh=True),
        Strategy("wide_refresh", pad_before_s=120, pad_after_s=120, refresh=True),
    ]
    if skip_refresh:
        return [strategy for strategy in strategies if not strategy.refresh]
    return strategies


def _prepare_run_root(repo_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_root = repo_root / "state" / "targeted_retests" / f"retest_{stamp}"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "exports").mkdir(parents=True, exist_ok=True)
    (run_root / "state").mkdir(parents=True, exist_ok=True)
    (run_root / "logs").mkdir(parents=True, exist_ok=True)
    return run_root


def _run_cluster_strategy(
    *,
    repo_root: Path,
    chat_type: str,
    chat_id: str,
    cluster: MissingCluster,
    strategy: Strategy,
    run_root: Path,
) -> dict[str, Any]:
    from qq_data_cli.export_cleanup import cleanup_gateway_media_cache
    from qq_data_cli.logging_utils import get_cli_log_path, get_cli_logger, setup_cli_logging
    from qq_data_core import (
        ChatExportService,
        ExportForensicsCollector,
        ExportPerfTraceWriter,
        ExportRequest,
        build_export_content_summary,
        resolve_strict_missing_policy,
    )
    from qq_data_core.time_expr import format_export_datetime
    from qq_data_integrations.napcat.bootstrap import NapCatBootstrapper
    from qq_data_integrations.napcat.diagnostics import collect_debug_preflight_evidence
    from qq_data_integrations.napcat.gateway import NapCatGateway
    from qq_data_integrations.napcat.settings import NapCatSettings

    cluster_start = _parse_iso(cluster.start_ts) - timedelta(seconds=strategy.pad_before_s)
    cluster_end = _parse_iso(cluster.end_ts) + timedelta(seconds=strategy.pad_after_s)
    start_literal = _dt_to_literal(cluster_start)
    end_literal = _dt_to_literal(cluster_end)

    case_name = f"cluster{cluster.index:02d}_{strategy.name}"
    out_path = run_root / "exports" / f"{case_name}.jsonl"
    state_dir = run_root / "state" / case_name
    log_path = run_root / "logs" / f"{case_name}.log"
    state_dir.mkdir(parents=True, exist_ok=True)
    command_preview = (
        f"run_targeted_missing_retest.bat --only-cluster {cluster.index} --only-strategy {strategy.name}"
    )
    setup_cli_logging(state_dir)
    logger = get_cli_logger("targeted_retest")
    settings = NapCatSettings.from_env().model_copy(
        update={
            "state_dir": state_dir,
            "export_dir": run_root / "exports",
        }
    )
    start_result = NapCatBootstrapper(
        settings,
        settings_loader=lambda: NapCatSettings.from_env().model_copy(
            update={
                "state_dir": state_dir,
                "export_dir": run_root / "exports",
            }
        ),
    ).ensure_endpoint("onebot_http")
    if not start_result.ready:
        log_path.write_text(
            "\n".join(
                [
                    f"command={command_preview}",
                    "returncode=1",
                    f"bootstrap_error={start_result.message}",
                ]
            ),
            encoding="utf-8",
        )
        return {
            "cluster_index": cluster.index,
            "strategy": asdict(strategy),
            "start_literal": start_literal,
            "end_literal": end_literal,
            "asset_count": cluster.asset_count,
            "asset_types": list(cluster.asset_types),
            "file_names": list(cluster.file_names),
            "message_ids": list(cluster.message_ids),
            "returncode": 1,
            "out_path": str(out_path),
            "manifest_path": str(out_path.with_suffix(".manifest.json")),
            "log_path": str(log_path),
            "state_dir": str(state_dir),
            "manifest_summary": {"error": start_result.message},
        }
    if start_result.attempted_start or start_result.attempted_configure:
        settings = NapCatSettings.from_env().model_copy(
            update={
                "state_dir": state_dir,
                "export_dir": run_root / "exports",
            }
        )

    gateway = NapCatGateway(settings)
    trace = ExportPerfTraceWriter(
        settings.state_dir,
        chat_type=chat_type,
        chat_id=chat_id,
        mode=f"targeted_retest_{strategy.name}",
    )
    forensics = ExportForensicsCollector(
        settings.state_dir,
        chat_type=chat_type,
        chat_id=chat_id,
        policy=resolve_strict_missing_policy("collect", env=os.environ),
        command_context={
            "entrypoint": "targeted_missing_retest",
            "cluster_index": cluster.index,
            "strategy": strategy.name,
            "chat_type": chat_type,
            "chat_id": chat_id,
        },
    )
    forensics.capture_preflight(
        {
            "http_url": settings.http_url,
            "fast_history_mode": settings.fast_history_mode,
            "fast_history_url": settings.fast_history_url,
            "export_dir": str(settings.export_dir),
            "state_dir": str(settings.state_dir),
            "project_root": str(settings.project_root),
            **collect_debug_preflight_evidence(settings),
        }
    )
    service = ChatExportService()
    progress_lines: list[str] = []

    def progress_callback(update: dict[str, Any]) -> None:
        trace.write_event(str(update.get("phase") or "progress"), update)
        phase = str(update.get("phase") or "")
        if phase in {"materialize_asset_substep", "download_assets", "materialize_assets", "interval_scan", "write_data_file"}:
            progress_lines.append(_json_dumps_safe(update))

    returncode = 0
    error_message: str | None = None
    content_summary: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    cleanup_stats: dict[str, Any] | None = None
    forensic_summary_path: Path | None = None
    try:
        request = ExportRequest(
            chat_type=chat_type,
            chat_id=chat_id,
            chat_name=chat_id,
            limit=200,
            since=cluster_start,
            until=cluster_end,
            include_raw=False,
        )
        snapshot = gateway.fetch_snapshot_between(
            request,
            page_size=200,
            progress_callback=progress_callback,
        )
        snapshot.metadata["resolved_since"] = format_export_datetime(min(cluster_start, cluster_end))
        snapshot.metadata["resolved_until"] = format_export_datetime(max(cluster_start, cluster_end))
        snapshot.metadata["interval_mode"] = "closed"
        normalized = service.build_snapshot(snapshot)
        bundle = service.write_bundle(
            normalized,
            out_path,
            fmt="jsonl",
            media_resolution_mode="napcat_only",
            media_download_manager=(
                gateway.build_media_download_manager()
                if hasattr(gateway, "build_media_download_manager")
                else None
            ),
            progress_callback=progress_callback,
            forensics_collector=forensics,
        )
        cleanup_stats = cleanup_gateway_media_cache(gateway, trace=trace, logger=logger)
        content_summary = build_export_content_summary(
            normalized,
            bundle,
            profile="all",
            fmt="jsonl",
            strict_missing="collect",
        )
        summary = trace.build_summary(record_count=len(normalized.messages))
        trace.write_event(
            "export_complete",
            {
                "out_path": str(bundle.data_path.resolve()),
                "manifest_path": str(bundle.manifest_path.resolve()),
                "copied_asset_count": bundle.copied_asset_count,
                "reused_asset_count": bundle.reused_asset_count,
                "missing_asset_count": bundle.missing_asset_count,
                "remote_cache_cleanup": cleanup_stats,
                "content_summary": content_summary,
                **summary,
            },
        )
        forensic_summary_path = forensics.finalize(
            export_completed=True,
            aborted=False,
            data_path=bundle.data_path,
            manifest_path=bundle.manifest_path,
            trace_path=trace.path,
            log_path=get_cli_log_path(),
        )
    except Exception as exc:
        returncode = 1
        error_message = str(exc)
        trace.write_event(
            "export_failed",
            {
                "error": error_message,
            },
        )
        forensics.finalize(
            export_completed=False,
            aborted=False,
            trace_path=trace.path,
            log_path=get_cli_log_path(),
            error=error_message,
        )
        progress_lines.append(traceback.format_exc())
    finally:
        trace.close()
        gateway.close()

    manifest_path = out_path.with_suffix(".manifest.json")
    manifest_summary = _read_manifest_summary(manifest_path)
    log_chunks = [
        f"command={command_preview}",
        f"returncode={returncode}",
        f"cluster={cluster.index}",
        f"strategy={strategy.name}",
        f"window={start_literal} -> {end_literal}",
        f"refresh={strategy.refresh}",
        f"trace_path={trace.path}",
        f"cli_log_path={get_cli_log_path() or ''}",
        f"forensic_summary_path={forensic_summary_path or ''}",
        f"cleanup_stats={cleanup_stats or {}}",
        f"content_summary={_json_dumps_safe(content_summary) if content_summary is not None else ''}",
        f"summary={_json_dumps_safe(summary) if summary is not None else ''}",
        "--- progress ---",
        *progress_lines,
    ]
    if error_message:
        log_chunks.extend(["--- error ---", error_message])
    log_path.write_text("\n".join(log_chunks), encoding="utf-8")

    return {
        "cluster_index": cluster.index,
        "strategy": asdict(strategy),
        "start_literal": start_literal,
        "end_literal": end_literal,
        "asset_count": cluster.asset_count,
        "asset_types": list(cluster.asset_types),
        "file_names": list(cluster.file_names),
        "message_ids": list(cluster.message_ids),
        "returncode": returncode,
        "out_path": str(out_path),
        "manifest_path": str(manifest_path),
        "log_path": str(log_path),
        "state_dir": str(state_dir),
        "manifest_summary": manifest_summary,
    }


def _read_manifest_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {"error": f"manifest_read_failed: {exc}"}
    asset_summary = manifest.get("asset_summary") or {}
    missing_breakdown = manifest.get("missing_breakdown") or {}
    return {
        "record_count": manifest.get("record_count"),
        "asset_summary": asset_summary,
        "missing_breakdown": missing_breakdown,
        "missing_assets": [
            {
                "timestamp_iso": item.get("timestamp_iso"),
                "asset_type": item.get("asset_type"),
                "file_name": item.get("file_name"),
                "missing_kind": item.get("missing_kind"),
                "resolver": item.get("resolver"),
                "message_id": item.get("message_id"),
            }
            for item in (manifest.get("assets") or [])
            if isinstance(item, dict) and str(item.get("status") or "").strip().casefold() == "missing"
        ],
    }


def _cluster_to_json(cluster: MissingCluster) -> dict[str, Any]:
    return {
        "index": cluster.index,
        "start_ts": cluster.start_ts,
        "end_ts": cluster.end_ts,
        "start_literal": cluster.start_literal,
        "end_literal": cluster.end_literal,
        "asset_count": cluster.asset_count,
        "asset_types": list(cluster.asset_types),
        "file_names": list(cluster.file_names),
        "message_ids": list(cluster.message_ids),
        "assets": [asdict(asset) for asset in cluster.assets],
    }


def _print_result_line(result: dict[str, Any]) -> None:
    summary = result.get("manifest_summary") or {}
    asset_summary = summary.get("asset_summary") or {}
    missing_breakdown = summary.get("missing_breakdown") or {}
    copied = asset_summary.get("copied", "-")
    reused = asset_summary.get("reused", "-")
    missing = asset_summary.get("missing", "-")
    print(
        f"[cluster {result['cluster_index']:02d} {result['strategy']['name']}] "
        f"rc={result['returncode']} copied={copied} reused={reused} missing={missing} "
        f"missing_breakdown={missing_breakdown}"
    )


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _dt_to_literal(value: datetime) -> str:
    return value.strftime(EXPORT_TIME_FORMAT)


def _iso_to_literal(value: str) -> str:
    return _dt_to_literal(_parse_iso(value))


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _none_if_blank(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(_json_dumps_safe(payload, indent=2), encoding="utf-8")

if __name__ == "__main__":
    raise SystemExit(main())
