from __future__ import annotations

import hashlib
import inspect
import json
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from time import monotonic
from typing import Any, Callable, Iterable, Literal

import orjson

from .export_forensics import (
    ExportForensicsCollector,
    ExportInvestigativeFailure,
    ForensicsRecordResult,
)
from .models import ExportBundleResult, MaterializedAsset, NormalizedMessage, NormalizedSegment, NormalizedSnapshot

MATERIALIZE_SLOW_STEP_WARN_S = 5.0


@dataclass(frozen=True, slots=True)
class _AssetCandidate:
    asset_type: str
    asset_role: str | None
    file_name: str | None
    source_path: str | None
    md5: str | None
    timestamp_ms: int
    download_hint: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _MediaSearchContext:
    search_roots: list[Path]
    account_hints: set[str] = field(default_factory=set)
    legacy_md5_matches: dict[tuple[str, str], Path] = field(default_factory=dict)
    legacy_loose_bucket_results: dict[tuple[str, str], dict[str, Path | None]] = field(default_factory=dict)
    wanted_md5_by_bucket: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    month_hints: set[str] = field(default_factory=set)
    time_window_ms: tuple[int, int] | None = None
    media_cache_dir: Path | None = None


def write_export_bundle(
    snapshot: NormalizedSnapshot,
    data_path: Path,
    *,
    write_data: Callable[[NormalizedSnapshot, Path], Path],
    media_resolution_mode: Literal["napcat_only", "legacy_local_research"] = "legacy_local_research",
    media_search_roots: Iterable[Path] | None = None,
    media_cache_dir: Path | None = None,
    media_download_callback: Callable[[dict[str, Any]], str | Path | None] | None = None,
    media_download_manager: Any | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    forensics_collector: ExportForensicsCollector | None = None,
) -> ExportBundleResult:
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "write_data_file",
                "stage": "start",
                "record_count": len(snapshot.messages),
                "target_path": str(data_path),
            }
        )
    written_data_path = write_data(snapshot, data_path)
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "write_data_file",
                "stage": "done",
                "record_count": len(snapshot.messages),
                "target_path": str(written_data_path),
            }
    )
    assets_dir = written_data_path.parent / f"{written_data_path.stem}_assets"
    manifest_path = written_data_path.with_suffix(".manifest.json")
    assets = materialize_snapshot_media(
        snapshot,
        assets_dir,
        media_resolution_mode=media_resolution_mode,
        media_search_roots=media_search_roots,
        media_cache_dir=media_cache_dir,
        media_download_callback=media_download_callback,
        media_download_manager=media_download_manager,
        progress_callback=progress_callback,
        forensics_collector=forensics_collector,
    )
    summary = _summarize_assets(assets)
    _write_manifest_json(
        manifest_path,
        {
        "schema_version": 1,
        "chat_type": snapshot.chat_type,
        "chat_id": snapshot.chat_id,
        "chat_name": snapshot.chat_name,
        "exported_at": snapshot.exported_at.isoformat(),
        "record_count": len(snapshot.messages),
        "metadata": snapshot.metadata,
        "data_file": written_data_path.name,
        "assets_dir": assets_dir.name,
        "asset_summary": summary,
        "missing_breakdown": _summarize_missing_breakdown(assets),
        },
        assets=assets,
    )
    return ExportBundleResult(
        data_path=written_data_path,
        manifest_path=manifest_path,
        assets_dir=assets_dir,
        record_count=len(snapshot.messages),
        copied_asset_count=summary["copied"],
        reused_asset_count=summary["reused"],
        missing_asset_count=summary["missing"],
        error_asset_count=summary["error"],
        forensic_run_dir=forensics_collector.run_dir if forensics_collector is not None else None,
        forensic_summary_path=forensics_collector.summary_path if forensics_collector is not None else None,
        forensic_incident_count=forensics_collector.incident_count if forensics_collector is not None else 0,
        assets=assets,
    )


def materialize_snapshot_media(
    snapshot: NormalizedSnapshot,
    assets_dir: Path,
    *,
    media_resolution_mode: Literal["napcat_only", "legacy_local_research"] = "legacy_local_research",
    media_search_roots: Iterable[Path] | None = None,
    media_cache_dir: Path | None = None,
    media_download_callback: Callable[[dict[str, Any]], str | Path | None] | None = None,
    media_download_manager: Any | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    forensics_collector: ExportForensicsCollector | None = None,
) -> list[MaterializedAsset]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    candidate_entries: list[tuple[NormalizedMessage, _AssetCandidate]] = []
    for message in snapshot.messages:
        for candidate in _iter_asset_candidates(message):
            candidate_entries.append((message, candidate))
    search_context: _MediaSearchContext | None = None
    if media_resolution_mode != "napcat_only":
        candidates = [candidate for _message, candidate in candidate_entries]
        roots = [root.resolve() for root in (media_search_roots or []) if root.exists()]
        search_context = _build_media_search_context(
            roots,
            candidates,
            snapshot=snapshot,
            media_cache_dir=media_cache_dir,
        )
    if media_resolution_mode == "napcat_only" and media_download_manager is not None:
        request_count = len(candidate_entries)
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "prefetch_media",
                    "stage": "start",
                    "request_count": request_count,
                }
            )
        started_prefetch = monotonic()
        try:
            chunk_size = max(
                1,
                int(getattr(media_download_manager, "PREFETCH_BATCH_SIZE", 200) or 200),
            )
            for start in range(0, request_count, chunk_size):
                chunk_requests = [
                    {
                        "asset_type": candidate.asset_type,
                        "asset_role": candidate.asset_role,
                        "file_name": candidate.file_name,
                        "source_path": candidate.source_path,
                        "md5": candidate.md5,
                        "timestamp_ms": candidate.timestamp_ms,
                        "download_hint": candidate.download_hint,
                    }
                    for _message, candidate in candidate_entries[start : start + chunk_size]
                ]
                if progress_callback is None:
                    media_download_manager.prepare_for_export(chunk_requests)
                else:
                    media_download_manager.prepare_for_export(
                        chunk_requests,
                        progress_callback=progress_callback,
                    )
        except Exception as exc:
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "prefetch_media",
                        "stage": "error",
                        "request_count": request_count,
                        "elapsed_s": round(monotonic() - started_prefetch, 4),
                        "error": str(exc),
                    }
                )
        else:
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "prefetch_media",
                        "stage": "done",
                        "request_count": request_count,
                        "elapsed_s": round(monotonic() - started_prefetch, 4),
                    }
                )
    copied_map: dict[str, str] = {}
    copied_content_map: dict[tuple[str, int, str], list[tuple[str, str]]] = {}
    export_path_payloads: dict[str, tuple[Any, ...]] = {}
    content_key_cache: dict[str, tuple[str, int, str] | None] = {}
    content_match_cache: dict[tuple[str, str], bool] = {}
    resolution_cache: dict[tuple[Any, ...], tuple[Path | None, str]] = {}
    assets: list[MaterializedAsset] = []
    second_pass_candidates: list[tuple[MaterializedAsset, _AssetCandidate]] = []
    copied_count = 0
    reused_count = 0
    missing_count = 0
    error_count = 0
    total_candidates = len(candidate_entries)

    for message, candidate in candidate_entries:
        current_index = len(assets) + 1
        step_started = monotonic()
        route_attempts: list[dict[str, Any]] = []
        pre_path_evidence: dict[str, Any] | None = None

        def _candidate_trace_callback(payload: dict[str, Any]) -> None:
            if str(payload.get("phase") or "") == "materialize_asset_substep":
                route_attempts.append(dict(payload))
            if progress_callback is not None:
                progress_callback(payload)

        _emit_materialization_step_trace(
            progress_callback,
            stage="start",
            current=current_index,
            total=total_candidates,
            candidate=candidate,
        )
        cache_key = _asset_resolution_cache_key(candidate)
        cached_resolution = resolution_cache.get(cache_key)
        if cached_resolution is None:
            if (
                forensics_collector is not None
                and forensics_collector.enabled
                and candidate.asset_type in {"video", "file"}
                and _candidate_has_forward_parent_hint(candidate)
            ):
                pre_path_evidence = forensics_collector.collect_candidate_path_evidence(
                    candidate=_candidate_forensics_payload(candidate),
                    asset_type=candidate.asset_type,
                    file_name=candidate.file_name,
                    source_path=candidate.source_path,
                )
            if media_resolution_mode == "napcat_only":
                resolved_path, resolver = _resolve_candidate_path_napcat_only(
                    candidate,
                    media_download_manager=media_download_manager,
                    media_download_callback=media_download_callback,
                    progress_callback=_candidate_trace_callback,
                )
            else:
                assert search_context is not None
                resolved_path, resolver = _resolve_candidate_path(candidate, context=search_context)
                if resolved_path is None and media_download_callback is not None:
                    resolved_path = _resolve_via_download_callback(candidate, media_download_callback)
                    if resolved_path is not None:
                        resolver = (
                            "sticker_remote_download"
                            if candidate.asset_type == "sticker"
                            else "napcat_action_download"
                        )
            resolution_cache[cache_key] = (resolved_path, resolver)
        else:
            resolved_path, resolver = cached_resolution
        asset = MaterializedAsset(
            message_id=message.message_id,
            message_seq=message.message_seq,
            sender_id=message.sender_id,
            timestamp_iso=message.timestamp_iso,
            asset_type=str(candidate.asset_type),
            asset_role=candidate.asset_role,
            file_name=candidate.file_name,
            source_path=candidate.source_path,
            resolved_source_path=str(resolved_path) if resolved_path else None,
            resolver=resolver,
            extra={
                "chat_id": message.chat_id,
                "chat_type": message.chat_type,
                "sender_name": message.sender_name,
            },
        )
        if resolved_path is None:
            asset.status = "missing"
            asset.missing_kind = resolver or "missing"
            asset.note = _missing_asset_note(resolver)
            assets.append(asset)
            missing_count += 1
            forensic_result = _record_forensic_incident(
                forensics_collector=forensics_collector,
                message=message,
                candidate=candidate,
                asset=asset,
                route_attempts=route_attempts,
                pre_path_evidence=pre_path_evidence,
            )
            if (
                forensic_result is not None
                and forensic_result.is_new_incident
                and progress_callback is not None
            ):
                progress_callback(
                    {
                        "phase": "forensic_incident",
                        "stage": "recorded",
                        "incident_id": forensic_result.incident_id,
                        "reason_category": forensic_result.reason_category,
                        "file_name": asset.file_name,
                        "asset_type": asset.asset_type,
                        "occurrence_count": forensic_result.occurrence_count,
                        "is_new_incident": forensic_result.is_new_incident,
                        "incident_path": str(forensic_result.incident_path)
                        if forensic_result.incident_path is not None
                        else None,
                    }
                )
            if (
                media_resolution_mode == "napcat_only"
                and media_download_manager is not None
                and candidate.asset_type == "image"
                and resolver == "missing_after_napcat"
                and hasattr(media_download_manager, "resolve_via_public_token_route")
            ):
                second_pass_candidates.append((asset, candidate))
            step_elapsed_s = round(monotonic() - step_started, 4)
            _emit_materialization_step_trace(
                progress_callback,
                stage="done",
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                status=asset.status,
                resolver=asset.resolver,
                missing_kind=asset.missing_kind,
                note=asset.note,
                step_elapsed_s=step_elapsed_s,
            )
            _emit_materialization_progress(
                progress_callback,
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                copied=copied_count,
                reused=reused_count,
                missing=missing_count,
                error=error_count,
                status=asset.status,
                resolver=asset.resolver,
                step_elapsed_s=step_elapsed_s,
            )
            continue

        dedupe_key = str(resolved_path).lower()
        if dedupe_key in copied_map:
            asset.status = "reused"
            asset.exported_rel_path = copied_map[dedupe_key]
            assets.append(asset)
            reused_count += 1
            step_elapsed_s = round(monotonic() - step_started, 4)
            _emit_materialization_step_trace(
                progress_callback,
                stage="done",
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                status=asset.status,
                resolver=asset.resolver,
                resolved_source_path=asset.resolved_source_path,
                step_elapsed_s=step_elapsed_s,
            )
            _emit_materialization_progress(
                progress_callback,
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                copied=copied_count,
                reused=reused_count,
                missing=missing_count,
                error=error_count,
                status=asset.status,
                resolver=asset.resolver,
                step_elapsed_s=step_elapsed_s,
            )
            continue

        content_key = _content_dedupe_key(
            candidate,
            resolved_path,
            cache=content_key_cache,
        )
        # Content-level dedupe intentionally reuses the first successful export
        # path for a payload, even if later references come from different local
        # files or nominal names.
        matched_rel_path = _matching_export_rel_path_for_content_key(
            content_key=content_key,
            resolved_path=resolved_path,
            copied_content_map=copied_content_map,
            compare_cache=content_match_cache,
        )
        if matched_rel_path is not None:
            asset.status = "reused"
            asset.exported_rel_path = matched_rel_path
            copied_map[dedupe_key] = asset.exported_rel_path
            assets.append(asset)
            reused_count += 1
            step_elapsed_s = round(monotonic() - step_started, 4)
            _emit_materialization_step_trace(
                progress_callback,
                stage="done",
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                status=asset.status,
                resolver=asset.resolver,
                resolved_source_path=asset.resolved_source_path,
                step_elapsed_s=step_elapsed_s,
            )
            _emit_materialization_progress(
                progress_callback,
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                copied=copied_count,
                reused=reused_count,
                missing=missing_count,
                error=error_count,
                status=asset.status,
                resolver=asset.resolver,
                step_elapsed_s=step_elapsed_s,
            )
            continue

        rel_path = _build_export_rel_path(candidate, resolved_path)
        reuse_content_marker = content_key is not None and matched_rel_path is None and content_key not in copied_content_map
        payload_marker = _payload_marker(
            content_key=content_key if reuse_content_marker else None,
            resolved_path_key=dedupe_key,
        )
        rel_path = _allocate_export_rel_path(
            rel_path,
            payload_marker=payload_marker,
            used_payloads=export_path_payloads,
        )
        target_path = assets_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(resolved_path, target_path)
        except Exception as exc:  # pragma: no cover - hard to force all OS copy failures
            _release_allocated_export_rel_path(
                rel_path,
                payload_marker=payload_marker,
                used_payloads=export_path_payloads,
            )
            asset.status = "error"
            asset.note = str(exc)
            assets.append(asset)
            error_count += 1
            step_elapsed_s = round(monotonic() - step_started, 4)
            _emit_materialization_step_trace(
                progress_callback,
                stage="done",
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                status=asset.status,
                resolver=asset.resolver,
                note=asset.note,
                resolved_source_path=asset.resolved_source_path,
                step_elapsed_s=step_elapsed_s,
            )
            _emit_materialization_progress(
                progress_callback,
                current=len(assets),
                total=total_candidates,
                candidate=candidate,
                copied=copied_count,
                reused=reused_count,
                missing=missing_count,
                error=error_count,
                status=asset.status,
                resolver=asset.resolver,
                step_elapsed_s=step_elapsed_s,
            )
            continue

        asset.status = "copied"
        asset.exported_rel_path = rel_path.as_posix()
        copied_map[dedupe_key] = asset.exported_rel_path
        if content_key is not None:
            copied_content_map.setdefault(content_key, []).append(
                (str(resolved_path.resolve()).lower(), asset.exported_rel_path)
            )
        assets.append(asset)
        copied_count += 1
        step_elapsed_s = round(monotonic() - step_started, 4)
        _emit_materialization_step_trace(
            progress_callback,
            stage="done",
            current=len(assets),
            total=total_candidates,
            candidate=candidate,
            status=asset.status,
            resolver=asset.resolver,
            resolved_source_path=asset.resolved_source_path,
            step_elapsed_s=step_elapsed_s,
        )
        _emit_materialization_progress(
            progress_callback,
            current=len(assets),
            total=total_candidates,
            candidate=candidate,
            copied=copied_count,
            reused=reused_count,
            missing=missing_count,
            error=error_count,
            status=asset.status,
            resolver=asset.resolver,
            step_elapsed_s=step_elapsed_s,
        )

    if second_pass_candidates:
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "retry_recent_missing_public_token",
                    "stage": "start",
                    "candidate_count": len(second_pass_candidates),
                }
            )
        recovered_count = 0
        for asset, candidate in second_pass_candidates:
            request_payload = {
                "asset_type": candidate.asset_type,
                "asset_role": candidate.asset_role,
                "file_name": candidate.file_name,
                "source_path": candidate.source_path,
                "md5": candidate.md5,
                "timestamp_ms": candidate.timestamp_ms,
                "download_hint": candidate.download_hint,
            }
            with suppress(Exception):
                resolved_path, resolver = media_download_manager.resolve_via_public_token_route(
                    request_payload
                )
                if resolved_path is None:
                    continue
                dedupe_key = str(resolved_path).lower()
                asset.resolved_source_path = str(resolved_path)
                asset.resolver = resolver
                asset.note = None
                if dedupe_key in copied_map:
                    asset.status = "reused"
                    asset.exported_rel_path = copied_map[dedupe_key]
                    missing_count -= 1
                    reused_count += 1
                    recovered_count += 1
                    continue
                content_key = _content_dedupe_key(
                    candidate,
                    resolved_path,
                    cache=content_key_cache,
                )
                matched_rel_path = _matching_export_rel_path_for_content_key(
                    content_key=content_key,
                    resolved_path=resolved_path,
                    copied_content_map=copied_content_map,
                    compare_cache=content_match_cache,
                )
                if matched_rel_path is not None:
                    asset.status = "reused"
                    asset.exported_rel_path = matched_rel_path
                    copied_map[dedupe_key] = asset.exported_rel_path
                    missing_count -= 1
                    reused_count += 1
                    recovered_count += 1
                    continue
                rel_path = _build_export_rel_path(candidate, resolved_path)
                reuse_content_marker = content_key is not None and matched_rel_path is None and content_key not in copied_content_map
                payload_marker = _payload_marker(
                    content_key=content_key if reuse_content_marker else None,
                    resolved_path_key=dedupe_key,
                )
                rel_path = _allocate_export_rel_path(
                    rel_path,
                    payload_marker=payload_marker,
                    used_payloads=export_path_payloads,
                )
                target_path = assets_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(resolved_path, target_path)
                except Exception as exc:  # pragma: no cover - hard to force all OS copy failures
                    _release_allocated_export_rel_path(
                        rel_path,
                        payload_marker=payload_marker,
                        used_payloads=export_path_payloads,
                    )
                    asset.status = "error"
                    asset.note = str(exc)
                    missing_count -= 1
                    error_count += 1
                    continue
                asset.status = "copied"
                asset.exported_rel_path = rel_path.as_posix()
                copied_map[dedupe_key] = asset.exported_rel_path
                if content_key is not None:
                    copied_content_map.setdefault(content_key, []).append(
                        (str(resolved_path.resolve()).lower(), asset.exported_rel_path)
                    )
                missing_count -= 1
                copied_count += 1
                recovered_count += 1
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "retry_recent_missing_public_token",
                    "stage": "done",
                    "candidate_count": len(second_pass_candidates),
                    "recovered_count": recovered_count,
                }
            )

    return assets


def _asset_resolution_cache_key(candidate: _AssetCandidate) -> tuple[Any, ...]:
    hint = candidate.download_hint
    return (
        candidate.asset_type,
        candidate.asset_role,
        _normalize_identity_string(candidate.file_name),
        _normalize_identity_string(candidate.source_path),
        _normalize_identity_string(candidate.md5),
        _normalize_identity_string(hint.get("file_id")),
        _normalize_identity_string(hint.get("message_id_raw")),
        _normalize_identity_string(hint.get("element_id")),
        _normalize_identity_string(hint.get("peer_uid")),
        _normalize_identity_string(hint.get("chat_type_raw")),
        _normalize_identity_string(hint.get("remote_url")),
        _normalize_identity_string(hint.get("url")),
        _normalize_identity_string(hint.get("emoji_id")),
        _normalize_identity_string(hint.get("emoji_package_id")),
    )


def _record_forensic_incident(
    *,
    forensics_collector: ExportForensicsCollector | None,
    message: NormalizedMessage,
    candidate: _AssetCandidate,
    asset: MaterializedAsset,
    route_attempts: list[dict[str, Any]],
    pre_path_evidence: dict[str, Any] | None = None,
) -> ForensicsRecordResult | None:
    if forensics_collector is None or not forensics_collector.enabled:
        return None
    result = forensics_collector.record_investigative_missing(
        message=message,
        candidate=_candidate_forensics_payload(candidate),
        asset=asset,
        route_attempts=route_attempts,
        pre_path_evidence=pre_path_evidence,
    )
    if result is None:
        return None
    asset.extra["forensic_incident_id"] = result.incident_id
    asset.extra["forensic_reason_category"] = result.reason_category
    if result.should_abort:
        raise ExportInvestigativeFailure(
            incident_id=result.incident_id,
            forensic_summary_path=forensics_collector.summary_path,
            incident_path=result.incident_path,
            reason_category=result.reason_category,
        )
    return result


def _candidate_forensics_payload(candidate: _AssetCandidate) -> dict[str, Any]:
    return {
        "asset_type": candidate.asset_type,
        "asset_role": candidate.asset_role,
        "file_name": candidate.file_name,
        "source_path": candidate.source_path,
        "md5": candidate.md5,
        "timestamp_ms": candidate.timestamp_ms,
        "download_hint": dict(candidate.download_hint),
    }


def _candidate_has_forward_parent_hint(candidate: _AssetCandidate) -> bool:
    hint = candidate.download_hint if isinstance(candidate.download_hint, dict) else {}
    parent = hint.get("_forward_parent")
    return isinstance(parent, dict) and bool(str(parent.get("message_id_raw") or "").strip())


def _write_manifest_json(
    manifest_path: Path,
    header: dict[str, Any],
    *,
    assets: list[MaterializedAsset],
) -> None:
    temp_path = manifest_path.with_suffix(f"{manifest_path.suffix}.tmp")
    header_json = orjson.dumps(header, option=orjson.OPT_INDENT_2).decode("utf-8")
    body_prefix = header_json[:-1] + ',\n  "assets": [\n'
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(body_prefix)
            for index, asset in enumerate(assets):
                if index > 0:
                    handle.write(",\n")
                asset_json = json.dumps(
                    asset.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write(_indent_json_block(asset_json, 4))
            if assets:
                handle.write("\n")
            handle.write("  ]\n}\n")
        temp_path.replace(manifest_path)
    finally:
        with suppress(OSError):
            temp_path.unlink(missing_ok=True)


def _indent_json_block(value: str, indent_spaces: int) -> str:
    indent = " " * indent_spaces
    return "\n".join(f"{indent}{line}" if line else line for line in value.splitlines())


def _normalize_identity_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _emit_materialization_progress(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    *,
    current: int,
    total: int,
    candidate: _AssetCandidate,
    copied: int,
    reused: int,
    missing: int,
    error: int,
    status: str | None = None,
    resolver: str | None = None,
    step_elapsed_s: float | None = None,
) -> None:
    if progress_callback is None:
        return
    payload = {
        "phase": "materialize_assets",
        "current": current,
        "total": total,
        "asset_type": candidate.asset_type,
        "asset_role": candidate.asset_role,
        "file_name": candidate.file_name,
        "copied_assets": copied,
        "reused_assets": reused,
        "missing_assets": missing,
        "error_assets": error,
    }
    if status:
        payload["status"] = status
    if resolver:
        payload["resolver"] = resolver
    if step_elapsed_s is not None:
        payload["step_elapsed_s"] = step_elapsed_s
        payload["step_elapsed_ms"] = int(round(step_elapsed_s * 1000))
        if step_elapsed_s >= MATERIALIZE_SLOW_STEP_WARN_S:
            payload["slow_step"] = True
    progress_callback(payload)


def _emit_materialization_step_trace(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    *,
    stage: str,
    current: int,
    total: int,
    candidate: _AssetCandidate,
    status: str | None = None,
    resolver: str | None = None,
    missing_kind: str | None = None,
    note: str | None = None,
    resolved_source_path: str | None = None,
    step_elapsed_s: float | None = None,
) -> None:
    if progress_callback is None:
        return
    hint = candidate.download_hint or {}
    forward_parent = hint.get("_forward_parent") if isinstance(hint.get("_forward_parent"), dict) else {}
    payload: dict[str, Any] = {
        "phase": "materialize_asset_step",
        "stage": stage,
        "current": current,
        "total": total,
        "asset_type": candidate.asset_type,
        "asset_role": candidate.asset_role,
        "file_name": candidate.file_name,
        "source_path": candidate.source_path,
        "md5": candidate.md5,
        "message_id_raw": hint.get("message_id_raw"),
        "element_id": hint.get("element_id"),
        "hint_file_id": hint.get("file_id"),
        "hint_url": hint.get("url"),
        "forward_parent_message_id_raw": forward_parent.get("message_id_raw"),
        "forward_parent_element_id": forward_parent.get("element_id"),
    }
    if status:
        payload["status"] = status
    if resolver:
        payload["resolver"] = resolver
    if missing_kind:
        payload["missing_kind"] = missing_kind
    if note:
        payload["note"] = note
    if resolved_source_path:
        payload["resolved_source_path"] = resolved_source_path
    if step_elapsed_s is not None:
        payload["step_elapsed_s"] = step_elapsed_s
        payload["step_elapsed_ms"] = int(round(step_elapsed_s * 1000))
        if step_elapsed_s >= MATERIALIZE_SLOW_STEP_WARN_S:
            payload["slow_step"] = True
    progress_callback(payload)


def _iter_asset_candidates(message: NormalizedMessage) -> Iterable[_AssetCandidate]:
    for segment in message.segments:
        yield from _iter_asset_candidates_from_segment(
            segment,
            timestamp_ms=message.timestamp_ms,
        )


def _iter_asset_candidates_from_segment(
    segment: NormalizedSegment | dict[str, Any],
    *,
    timestamp_ms: int,
    parent_download_hint: dict[str, Any] | None = None,
) -> Iterable[_AssetCandidate]:
    if isinstance(segment, NormalizedSegment):
        segment_type = segment.type
        file_name = segment.file_name
        path = segment.path
        md5 = segment.md5
        extra = dict(segment.extra or {})
    else:
        segment_type = str(segment.get("type") or "").strip()
        file_name = _string_or_none(segment.get("file_name"))
        path = _string_or_none(segment.get("path"))
        md5 = _string_or_none(segment.get("md5"))
        raw_extra = segment.get("extra") or {}
        extra = dict(raw_extra) if isinstance(raw_extra, dict) else {}
    if not path:
        path = _local_path_from_download_hint(extra)
    if parent_download_hint:
        merged_forward_hint = {
            key: value
            for key, value in parent_download_hint.items()
            if value is not None and value != "" and value != []
        }
        if merged_forward_hint:
            existing = dict(extra)
            existing["_forward_parent"] = merged_forward_hint
            for key, value in merged_forward_hint.items():
                existing.setdefault(f"_forward_parent_{key}", value)
            extra = existing

    if segment_type == "image":
        yield _AssetCandidate(
            "image",
            None,
            file_name,
            path,
            md5,
            timestamp_ms,
            download_hint=extra,
        )
        return
    if segment_type == "file":
        yield _AssetCandidate(
            "file",
            None,
            file_name,
            path,
            md5,
            timestamp_ms,
            download_hint=extra,
        )
        return
    if segment_type == "speech":
        yield _AssetCandidate(
            "speech",
            None,
            file_name,
            path,
            md5,
            timestamp_ms,
            download_hint=extra,
        )
        return
    if segment_type == "video":
        yield _AssetCandidate(
            "video",
            None,
            file_name,
            path,
            md5,
            timestamp_ms,
            download_hint=extra,
        )
        return
    if segment_type == "sticker":
        static_path = _string_or_none(extra.get("static_path"))
        dynamic_path = _string_or_none(extra.get("dynamic_path"))
        if static_path:
            yield _AssetCandidate(
                "sticker",
                "static",
                Path(PureWindowsPath(static_path)).name or file_name,
                static_path,
                md5,
                timestamp_ms,
                download_hint=extra,
            )
        if dynamic_path:
            yield _AssetCandidate(
                "sticker",
                "dynamic",
                Path(PureWindowsPath(dynamic_path)).name or file_name,
                dynamic_path,
                md5,
                timestamp_ms,
                download_hint=extra,
            )
        if not static_path and not dynamic_path and path:
            yield _AssetCandidate(
                "sticker",
                None,
                file_name,
                path,
                md5,
                timestamp_ms,
                download_hint=extra,
            )
        return
    if segment_type == "forward":
        forward_parent_hint = {
            "message_id_raw": _string_or_none(extra.get("message_id_raw"))
            or _string_or_none(extra.get("_forward_parent_message_id_raw")),
            "element_id": _string_or_none(extra.get("element_id"))
            or _string_or_none(extra.get("_forward_parent_element_id")),
            "peer_uid": _string_or_none(extra.get("peer_uid"))
            or _string_or_none(extra.get("_forward_parent_peer_uid")),
            "chat_type_raw": extra.get("chat_type_raw")
            if extra.get("chat_type_raw") is not None
            else extra.get("_forward_parent_chat_type_raw"),
        }
        for node in extra.get("forward_messages") or []:
            if not isinstance(node, dict):
                continue
            for child in node.get("segments") or []:
                if isinstance(child, dict) or isinstance(child, NormalizedSegment):
                    yield from _iter_asset_candidates_from_segment(
                        child,
                        timestamp_ms=timestamp_ms,
                        parent_download_hint=forward_parent_hint,
                    )
        return


def _resolve_candidate_path_napcat_only(
    candidate: _AssetCandidate,
    *,
    media_download_manager: Any | None,
    media_download_callback: Callable[[dict[str, Any]], str | Path | None] | None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Path | None, str]:
    raw_path = _existing_path(candidate.source_path)
    if raw_path is not None:
        return raw_path, "direct_local_path"
    request_payload = {
        "asset_type": candidate.asset_type,
        "asset_role": candidate.asset_role,
        "file_name": candidate.file_name,
        "source_path": candidate.source_path,
        "md5": candidate.md5,
        "timestamp_ms": candidate.timestamp_ms,
        "download_hint": candidate.download_hint,
    }
    if media_download_manager is not None and hasattr(media_download_manager, "resolve_for_export"):
        with suppress(Exception):
            resolve_for_export = media_download_manager.resolve_for_export
            parameters = inspect.signature(resolve_for_export).parameters
            if "trace_callback" in parameters:
                resolved_path, resolver = resolve_for_export(
                    request_payload,
                    trace_callback=progress_callback,
                )
            else:
                resolved_path, resolver = resolve_for_export(request_payload)
            if resolved_path is not None:
                return resolved_path, resolver or "napcat_context_hydrated"
            if resolver:
                return None, resolver
    # In strict NapCat-only mode, do not fall back to generic callback download,
    # local root scans, or MD5 cache matching. If context hydration cannot recover
    # a file, formal export must record a true NapCat-side miss.
    return None, "missing_after_napcat"


def _missing_asset_note(resolver: str | None) -> str:
    if resolver == "qq_expired_after_napcat":
        return "asset appears expired in QQ/NapCat; no local file and remote URL unavailable"
    return "source file not found"


def _resolve_via_download_callback(
    candidate: _AssetCandidate,
    media_download_callback: Callable[[dict[str, Any]], str | Path | None],
) -> Path | None:
    if candidate.asset_type not in {"image", "file", "speech", "video", "sticker"}:
        return None
    file_id = _string_or_none(candidate.download_hint.get("file_id"))
    file_name = _string_or_none(candidate.file_name)
    has_context_hint = any(
        _string_or_none(candidate.download_hint.get(key))
        for key in ("message_id_raw", "element_id", "peer_uid", "chat_type_raw")
    )
    if not file_id and not file_name and not has_context_hint:
        return None
    try:
        result = media_download_callback(
            {
                "asset_type": candidate.asset_type,
                "asset_role": candidate.asset_role,
                "file_name": candidate.file_name,
                "source_path": candidate.source_path,
                "md5": candidate.md5,
                "timestamp_ms": candidate.timestamp_ms,
                "download_hint": candidate.download_hint,
            }
        )
    except Exception:
        return None
    if result is None:
        return None
    candidate_path = Path(result)
    if not candidate_path.exists() or not candidate_path.is_file():
        return None
    return candidate_path.resolve()


def _resolve_candidate_path(
    candidate: _AssetCandidate,
    *,
    context: _MediaSearchContext,
) -> tuple[Path | None, str]:
    raw_path = _existing_path(candidate.source_path)
    if raw_path is not None:
        upgraded = _prefer_original_media_path(candidate, raw_path, context=context)
        if upgraded is not None and upgraded != raw_path:
            return upgraded, "segment_path_upgraded"
        return raw_path, "segment_path"
    if candidate.source_path:
        ntqq_original = _resolve_via_ntqq_originals(
            candidate,
            search_roots=context.search_roots,
            account_hints=context.account_hints,
        )
        if ntqq_original is not None:
            return ntqq_original, "qq_media_root_original_scan"
    else:
        ntqq_hinted = _resolve_via_ntqq_month_hints(candidate, context=context)
        if ntqq_hinted is not None:
            return ntqq_hinted, "qq_media_root_original_scan"
    legacy = _resolve_via_legacy_md5(candidate, context=context)
    if legacy is not None:
        return legacy, "legacy_md5_index"
    fallback = _resolve_via_roots(
        candidate,
        search_roots=context.search_roots,
        account_hints=context.account_hints,
    )
    if fallback is not None:
        return fallback, "qq_media_root_scan"
    return None, "unresolved"


def _resolve_via_roots(
    candidate: _AssetCandidate,
    *,
    search_roots: list[Path],
    account_hints: set[str],
) -> Path | None:
    if not search_roots:
        return None
    source = candidate.source_path or ""
    source_parts = list(PureWindowsPath(source).parts)
    suffixes = _candidate_suffixes(source_parts)
    for root in search_roots:
        for suffix in suffixes:
            trial = root.joinpath(*suffix)
            if trial.exists() and trial.is_file():
                upgraded = _prefer_original_media_path(candidate, trial.resolve(), context=None)
                return upgraded or trial.resolve()
    if candidate.asset_type in {"image", "sticker", "video", "speech"} and _normalized_md5(candidate.md5):
        return None
    names_to_try = _candidate_names(candidate)
    if not names_to_try:
        return None
    for directory in _iter_targeted_name_search_directories(
        search_roots,
        account_hints=account_hints,
        asset_type=candidate.asset_type,
        source_path=candidate.source_path,
    ):
        for name in names_to_try:
            try:
                match = next(directory.rglob(name))
            except StopIteration:
                continue
            if match.exists() and match.is_file():
                return match.resolve()
    return None


def _prefer_original_media_path(
    candidate: _AssetCandidate,
    resolved_path: Path,
    *,
    context: _MediaSearchContext | None,
) -> Path | None:
    if candidate.asset_type != "image":
        return None
    if _looks_like_thumbnail_path(resolved_path):
        upgraded = _find_ntqq_original_siblings(resolved_path)
        if upgraded is not None:
            return upgraded
        if context is not None:
            legacy = _resolve_via_legacy_md5(candidate, context=context)
            if legacy is not None and legacy != resolved_path:
                return legacy
    return None


def _resolve_via_ntqq_originals(
    candidate: _AssetCandidate,
    *,
    search_roots: list[Path],
    account_hints: set[str],
) -> Path | None:
    source_path = _string_or_none(candidate.source_path)
    if not source_path:
        return None
    parts = list(PureWindowsPath(source_path).parts)
    lowered = [part.lower() for part in parts]
    if "nt_qq" not in lowered or "nt_data" not in lowered:
        return None
    leaf = parts[-1]
    if not leaf:
        return None

    base_suffixes: list[list[str]] = []
    if "pic" in lowered:
        pic_index = lowered.index("pic")
        if pic_index + 1 < len(parts):
            month = parts[pic_index + 1]
            base_suffixes.extend(
                [
                    ["nt_qq", "nt_data", "Pic", month, "Ori"],
                    ["nt_qq", "nt_data", "Pic", month, "OriTemp"],
                    ["nt_qq", "nt_data", "Pic", month, "Thumb"],
                ]
            )
    if "emoji" in lowered and "emoji-recv" in lowered:
        emoji_index = lowered.index("emoji")
        if emoji_index + 2 < len(parts):
            recv_dir = parts[emoji_index + 1]
            month = parts[emoji_index + 2]
            base_suffixes.extend(
                [
                    ["nt_qq", "nt_data", "Emoji", recv_dir, month, "Ori"],
                    ["nt_qq", "nt_data", "Emoji", recv_dir, month, "Thumb"],
                    ["nt_qq", "nt_data", "Emoji", recv_dir, month, "OriTemp"],
                    ["nt_qq", "nt_data", "Pic", month, "Ori"],
                    ["nt_qq", "nt_data", "Pic", month, "OriTemp"],
                    ["nt_qq", "nt_data", "Pic", month, "Thumb"],
                ]
            )
    if not base_suffixes:
        return None

    stem = _preferred_media_stem(candidate, leaf)
    for root in search_roots:
        for parent in _ntqq_parent_candidates(root, account_hints=account_hints):
            for suffix in base_suffixes:
                directory = parent.joinpath(*suffix)
                if not directory.exists() or not directory.is_dir():
                    continue
                match = _find_candidate_in_directory(directory, stem=stem, asset_type=candidate.asset_type)
                if match is not None:
                    return match
    return None


def _resolve_via_ntqq_month_hints(
    candidate: _AssetCandidate,
    *,
    context: _MediaSearchContext,
) -> Path | None:
    if candidate.asset_type != "image" or not context.search_roots or not context.month_hints:
        return None
    stem = _preferred_media_stem(candidate, candidate.file_name or candidate.md5 or "")
    if not stem:
        return None
    hinted_months = sorted(context.month_hints)
    for root in context.search_roots:
        for parent in _ntqq_parent_candidates(root, account_hints=context.account_hints):
            month_candidates = list(hinted_months)
            pic_root = parent / "nt_qq" / "nt_data" / "Pic"
            if pic_root.exists() and pic_root.is_dir():
                with suppress(Exception):
                    for child in sorted(pic_root.iterdir(), key=lambda item: item.name):
                        if child.is_dir() and re.fullmatch(r"\d{4}-\d{2}", child.name):
                            if child.name not in month_candidates:
                                month_candidates.append(child.name)
            for month in month_candidates:
                for directory in (
                    parent / "nt_qq" / "nt_data" / "Pic" / month / "Thumb",
                    parent / "nt_qq" / "nt_data" / "Pic" / month / "Ori",
                    parent / "nt_qq" / "nt_data" / "Pic" / month / "OriTemp",
                ):
                    if not directory.exists() or not directory.is_dir():
                        continue
                    match = _find_candidate_in_directory(directory, stem=stem, asset_type="image")
                    if match is not None:
                        return match
    return None


def _candidate_suffixes(parts: list[str]) -> list[list[str]]:
    suffixes: list[list[str]] = []
    lowered = [part.lower() for part in parts]
    markers = {
        "qq": 1,
        "tencent files": 1,
        "nt_qq": 0,
        "pic": 0,
        "ptt": 0,
        "filerecv": 0,
        "emoji": 0,
        "video": 0,
    }
    for index, lowered_part in enumerate(lowered):
        if lowered_part in markers:
            skip = markers[lowered_part]
            start = max(0, index + skip)
            suffix = [part for part in parts[start:] if part not in {"\\", "/"}]
            if suffix:
                suffixes.append(suffix)
    if parts:
        suffixes.append([part for part in parts[-6:] if part not in {"\\", "/"}])
    return suffixes


def _candidate_names(candidate: _AssetCandidate) -> list[str]:
    names: list[str] = []
    for item in [candidate.file_name, candidate.md5]:
        value = _string_or_none(item)
        if value and value not in names:
            names.append(value)
    return names


def _build_media_search_context(
    search_roots: list[Path],
    candidates: list[_AssetCandidate],
    *,
    snapshot: NormalizedSnapshot,
    media_cache_dir: Path | None = None,
) -> _MediaSearchContext:
    wanted_md5_by_type: dict[str, set[str]] = {}
    wanted_md5_by_bucket: dict[tuple[str, str], set[str]] = {}
    account_hints: set[str] = set()
    for candidate in candidates:
        account_hints.update(_extract_account_hints(candidate.source_path))
        md5 = _normalized_md5(candidate.md5)
        if not md5:
            continue
        if candidate.asset_type not in {"image", "video", "file", "speech", "sticker"}:
            continue
        wanted_md5_by_type.setdefault(candidate.asset_type, set()).add(md5)
        bucket = _candidate_month_bucket(candidate)
        if bucket is not None:
            wanted_md5_by_bucket.setdefault((candidate.asset_type, bucket), set()).add(md5)

    time_window_ms = _derive_media_time_window(snapshot, candidates)
    month_hints = _derive_month_hints(candidates, time_window_ms=time_window_ms)
    legacy_matches: dict[tuple[str, str], Path] = {}
    if search_roots and wanted_md5_by_type:
        legacy_matches = _build_legacy_md5_matches(
            search_roots,
            wanted_md5_by_type,
            account_hints,
            month_hints=month_hints,
            time_window_ms=time_window_ms,
            media_cache_dir=media_cache_dir,
        )
    return _MediaSearchContext(
        search_roots=search_roots,
        account_hints=account_hints,
        legacy_md5_matches=legacy_matches,
        wanted_md5_by_bucket=wanted_md5_by_bucket,
        month_hints=month_hints,
        time_window_ms=time_window_ms,
        media_cache_dir=media_cache_dir,
    )


def _resolve_via_legacy_md5(
    candidate: _AssetCandidate,
    *,
    context: _MediaSearchContext,
) -> Path | None:
    md5 = _normalized_md5(candidate.md5)
    if not md5:
        return None
    match = context.legacy_md5_matches.get((candidate.asset_type, md5))
    if match is not None:
        return match
    return _resolve_via_legacy_md5_loose(candidate, context=context)


def _resolve_via_legacy_md5_loose(
    candidate: _AssetCandidate,
    *,
    context: _MediaSearchContext,
) -> Path | None:
    md5 = _normalized_md5(candidate.md5)
    if not md5 or not context.search_roots:
        return None
    bucket = _candidate_month_bucket(candidate)
    if bucket is not None:
        bucket_key = (candidate.asset_type, bucket)
        cached = context.legacy_loose_bucket_results.get(bucket_key)
        if cached is None:
            wanted = context.wanted_md5_by_bucket.get(bucket_key, {md5})
            matches = _build_legacy_md5_matches(
                context.search_roots,
                {candidate.asset_type: set(wanted)},
                context.account_hints,
                month_hints=set(),
                time_window_ms=None,
                media_cache_dir=context.media_cache_dir,
            )
            cached = {
                wanted_md5: matches.get((candidate.asset_type, wanted_md5))
                for wanted_md5 in wanted
            }
            context.legacy_loose_bucket_results[bucket_key] = cached
        return cached.get(md5)
    matches = _build_legacy_md5_matches(
        context.search_roots,
        {candidate.asset_type: {md5}},
        context.account_hints,
        month_hints=set(),
        time_window_ms=None,
        media_cache_dir=context.media_cache_dir,
    )
    return matches.get((candidate.asset_type, md5))


def _candidate_month_bucket(candidate: _AssetCandidate) -> str | None:
    with suppress(Exception):
        return datetime.fromtimestamp(candidate.timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m")
    return None


def _build_legacy_md5_matches(
    search_roots: list[Path],
    wanted_md5_by_type: dict[str, set[str]],
    account_hints: set[str],
    *,
    month_hints: set[str],
    time_window_ms: tuple[int, int] | None,
    media_cache_dir: Path | None = None,
) -> dict[tuple[str, str], Path]:
    matches: dict[tuple[str, str], Path] = {}
    pending: dict[str, set[str]] = {
        asset_type: set(md5s)
        for asset_type, md5s in wanted_md5_by_type.items()
        if md5s
    }
    if not pending:
        return matches

    for asset_type, directory in _iter_legacy_media_directories(search_roots, account_hints=account_hints):
        wanted = pending.get(asset_type)
        if not wanted:
            continue
        for path, digest in _iter_legacy_md5_rows(
            directory,
            asset_type=asset_type,
            cache_dir=media_cache_dir,
            month_hints=month_hints,
            time_window_ms=time_window_ms,
        ):
            if not path.is_file():
                continue
            if not digest or digest not in wanted:
                continue
            key = (asset_type, digest)
            if key not in matches:
                matches[key] = path.resolve()
                wanted.remove(digest)
            if not wanted:
                break
        if all(not remaining for remaining in pending.values()):
            break
    return matches


def _iter_legacy_media_directories(
    search_roots: list[Path],
    *,
    account_hints: set[str],
) -> Iterable[tuple[str, Path]]:
    seen: set[Path] = set()
    relative_candidates = [
        ("image", Path("Image") / "Group2"),
        ("image", Path("Image") / "C2C"),
        ("image", Path("Image") / "PicFileThumbnails"),
        ("video", Path("Video")),
        ("speech", Path("Audio")),
        ("file", Path("FileRecv")),
    ]
    for root in search_roots:
        parent_candidates = _legacy_parent_candidates(root, account_hints=account_hints)
        for parent in parent_candidates:
            for asset_type, suffix in relative_candidates:
                directory = (parent / suffix).resolve()
                if directory.exists() and directory.is_dir() and directory not in seen:
                    seen.add(directory)
                    yield asset_type, directory


def _iter_targeted_name_search_directories(
    search_roots: list[Path],
    *,
    account_hints: set[str],
    asset_type: str,
    source_path: str | None,
) -> Iterable[Path]:
    seen: set[Path] = set()

    def emit(path: Path) -> Iterable[Path]:
        resolved = path.resolve()
        if resolved.exists() and resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            yield resolved

    ntqq_suffixes_by_type: dict[str, list[list[str]]] = {
        "file": [
            ["nt_qq", "nt_data", "File"],
            ["nt_qq", "nt_data", "FileRecv"],
            ["ScreenRecorder"],
            ["Video"],
            ["FileRecv"],
        ],
        "video": [
            ["nt_qq", "nt_data", "Video"],
            ["Video"],
            ["ScreenRecorder"],
            ["FileRecv"],
        ],
        "speech": [
            ["nt_qq", "nt_data", "Ptt"],
            ["Audio"],
        ],
        "image": [
            ["nt_qq", "nt_data", "Pic"],
            ["nt_qq", "nt_data", "Emoji"],
            ["Image"],
        ],
        "sticker": [
            ["nt_qq", "nt_data", "Emoji"],
            ["ExpressionRecommend"],
            ["Image"],
        ],
    }

    source = _string_or_none(source_path)
    if source:
        source_parts = list(PureWindowsPath(source).parts)
        for root in search_roots:
            for suffix in _candidate_suffixes(source_parts):
                trial = root.joinpath(*suffix)
                yield from emit(trial.parent if trial.suffix else trial)

    for root in search_roots:
        for parent in _legacy_parent_candidates(root, account_hints=account_hints):
            for suffix in ntqq_suffixes_by_type.get(asset_type, []):
                yield from emit(parent.joinpath(*suffix))


def _legacy_parent_candidates(root: Path, *, account_hints: set[str]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved.exists() and resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    add(root)
    root_name = root.name.strip()
    if root_name.isdigit():
        return candidates

    if account_hints:
        for hint in account_hints:
            add(root / hint)
        return candidates

    with suppress(Exception):
        for child in root.iterdir():
            if child.is_dir():
                add(child)
    return candidates


def _ntqq_parent_candidates(root: Path, *, account_hints: set[str]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved.exists() and resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    add(root)
    if root.name.strip().isdigit():
        return candidates
    for hint in account_hints:
        add(root / hint)
    if account_hints:
        return candidates
    with suppress(Exception):
        for child in root.iterdir():
            if child.is_dir():
                add(child)
    return candidates


def _preferred_media_stem(candidate: _AssetCandidate, leaf_name: str) -> str:
    for value in [candidate.md5, candidate.file_name, leaf_name]:
        text = _string_or_none(value)
        if not text:
            continue
        return _strip_thumb_suffix(Path(text).stem if Path(text).suffix else text)
    return _short_hash(leaf_name)


def _strip_thumb_suffix(value: str) -> str:
    lowered = value.casefold()
    if lowered.endswith("_0"):
        return value[:-2]
    return value


def _looks_like_thumbnail_path(path: Path) -> bool:
    lowered_parts = {part.casefold() for part in path.parts}
    return "thumb" in lowered_parts or "picfilethumbnails" in lowered_parts


def _find_ntqq_original_siblings(path: Path) -> Path | None:
    parent_name = path.parent.name.casefold()
    if parent_name not in {"thumb", "picfilethumbnails"}:
        return None
    stem = _strip_thumb_suffix(path.stem)
    base = path.parent.parent
    for directory in [base / "Ori", base / "OriTemp"]:
        if not directory.exists() or not directory.is_dir():
            continue
        match = _find_candidate_in_directory(directory, stem=stem, asset_type="image")
        if match is not None:
            return match
    return None


def _find_candidate_in_directory(directory: Path, *, stem: str, asset_type: str) -> Path | None:
    candidates: list[Path] = []
    direct = directory / stem
    if direct.exists() and direct.is_file():
        candidates.append(direct.resolve())
    with suppress(Exception):
        candidates.extend(
            sorted(
                candidate.resolve()
                for candidate in directory.glob(f"{stem}.*")
                if candidate.is_file() and _legacy_extension_allowed(asset_type, candidate)
            )
        )
        candidates.extend(
            sorted(
                candidate.resolve()
                for candidate in directory.glob(f"{stem}_*.*")
                if candidate.is_file() and _legacy_extension_allowed(asset_type, candidate)
            )
        )
        candidates.extend(
            sorted(
                candidate.resolve()
                for candidate in directory.glob(f"{stem}_*")
                if candidate.is_file() and _legacy_extension_allowed(asset_type, candidate)
            )
        )
    if not candidates:
        return None
    unique_candidates = {candidate.resolve(): None for candidate in candidates}
    return sorted(unique_candidates, key=_original_candidate_priority)[0]


def _original_candidate_priority(path: Path) -> tuple[int, str]:
    suffix = path.suffix.casefold()
    order = {
        ".gif": 0,
        ".webp": 1,
        ".png": 2,
        ".jpg": 3,
        ".jpeg": 4,
        ".bmp": 5,
        "": 6,
    }
    name_stem = path.stem if path.suffix else path.name
    match = re.search(r"_(\d+)$", name_stem)
    has_variant = 1 if match else 0
    variant_rank = -int(match.group(1)) if match else 0
    return (order.get(suffix, 99), has_variant, variant_rank, str(path))


def _legacy_extension_allowed(asset_type: str, path: Path) -> bool:
    suffix = path.suffix.lower()
    if asset_type == "image":
        return suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"} or suffix == ""
    if asset_type == "video":
        return suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm"} or suffix == ""
    if asset_type == "speech":
        return suffix in {".amr", ".silk", ".ogg", ".wav", ".mp3"} or suffix == ""
    if asset_type == "file":
        return True
    return False


def _iter_legacy_md5_rows(
    directory: Path,
    *,
    asset_type: str,
    cache_dir: Path | None,
    month_hints: set[str] | None = None,
    time_window_ms: tuple[int, int] | None = None,
) -> list[tuple[Path, str | None]]:
    files_with_stat: list[tuple[Path, object]] = []
    for path in directory.rglob("*"):
        if not path.is_file() or not _legacy_extension_allowed(asset_type, path):
            continue
        stat = path.stat()
        if not _legacy_file_in_scope(
            path,
            stat,
            month_hints=month_hints or set(),
            time_window_ms=time_window_ms,
        ):
            continue
        files_with_stat.append((path, stat))
    files_with_stat.sort(key=lambda item: str(item[0]).lower())
    rows_with_digest: list[tuple[Path, str | None]] = []
    if cache_dir is None:
        for path, _stat in files_with_stat:
            rows_with_digest.append((path, _file_md5(path)))
        return rows_with_digest

    cache = _load_legacy_md5_cache(directory, cache_dir=cache_dir)
    refreshed_map = {
        str(item["path"]).lower(): item
        for item in cache.get("files", [])
        if _string_or_none(item.get("path")) is not None
    }
    cached_rows = list(cache.get("files", []))
    cache_map = {str(item["path"]).lower(): item for item in cache.get("files", [])}
    for path, stat in files_with_stat:
        key = str(path.resolve()).lower()
        cached = cache_map.get(key)
        digest: str | None
        if (
            cached is not None
            and int(cached.get("size", -1)) == stat.st_size
            and int(cached.get("mtime_ns", -1)) == stat.st_mtime_ns
        ):
            digest = str(cached.get("md5") or "") or None
        else:
            digest = _file_md5(path)
        refreshed_map[key] = {
            "path": str(path.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "md5": digest,
        }
        rows_with_digest.append((path, digest))
    refreshed = sorted(refreshed_map.values(), key=lambda item: str(item["path"]).lower())
    if refreshed != cached_rows:
        _write_legacy_md5_cache(directory, cache_dir=cache_dir, rows=refreshed)
    return rows_with_digest


def _legacy_file_in_scope(
    path: Path,
    stat: object,
    *,
    month_hints: set[str],
    time_window_ms: tuple[int, int] | None,
) -> bool:
    file_months = _months_from_stat(stat)
    if month_hints and file_months and file_months.isdisjoint(month_hints):
        return False
    if time_window_ms is None:
        return True
    start_ms, end_ms = time_window_ms
    span_ms = max(0, end_ms - start_ms)
    if span_ms > 14 * 24 * 60 * 60 * 1000:
        return True
    slack_ms = 7 * 24 * 60 * 60 * 1000
    lower = start_ms - slack_ms
    upper = end_ms + slack_ms
    timestamps = _timestamps_ms_from_stat(stat)
    if not timestamps:
        return True
    return any(lower <= value <= upper for value in timestamps)


def _file_md5(path: Path) -> str | None:
    try:
        digest = hashlib.md5()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().lower()
    except OSError:
        return None


def _normalized_md5(value: str | None) -> str | None:
    text = _string_or_none(value)
    return text.lower() if text else None


def _derive_media_time_window(
    snapshot: NormalizedSnapshot,
    candidates: list[_AssetCandidate],
) -> tuple[int, int] | None:
    explicit_bounds: list[int] = []
    for key in ("resolved_since", "resolved_until"):
        parsed = _metadata_datetime_ms(snapshot.metadata.get(key))
        if parsed is not None:
            explicit_bounds.append(parsed)
    if len(explicit_bounds) == 2:
        return min(explicit_bounds), max(explicit_bounds)

    timestamps = [candidate.timestamp_ms for candidate in candidates if candidate.timestamp_ms > 0]
    if not timestamps:
        timestamps = [message.timestamp_ms for message in snapshot.messages if message.timestamp_ms > 0]
    if not timestamps:
        return None
    return min(timestamps), max(timestamps)


def _derive_month_hints(
    candidates: list[_AssetCandidate],
    *,
    time_window_ms: tuple[int, int] | None,
) -> set[str]:
    hints: set[str] = set()
    for candidate in candidates:
        if candidate.source_path:
            hints.update(_extract_month_tokens(candidate.source_path))
    if time_window_ms is not None:
        hints.update(_month_tokens_between(*time_window_ms))
    return hints


def _metadata_datetime_ms(value: object) -> int | None:
    text = _string_or_none(value)
    if not text:
        return None
    with suppress(ValueError):
        return int(datetime.fromisoformat(text).timestamp() * 1000)
    return None


def _extract_month_tokens(value: str) -> set[str]:
    return set(re.findall(r"\b\d{4}-\d{2}\b", value))


def _month_tokens_between(start_ms: int, end_ms: int) -> set[str]:
    start_dt = datetime.fromtimestamp(min(start_ms, end_ms) / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(max(start_ms, end_ms) / 1000, tz=timezone.utc)
    cursor = datetime(start_dt.year, start_dt.month, 1, tzinfo=timezone.utc)
    end_cursor = datetime(end_dt.year, end_dt.month, 1, tzinfo=timezone.utc)
    months: set[str] = set()
    while cursor <= end_cursor:
        months.add(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = datetime(cursor.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            cursor = datetime(cursor.year, cursor.month + 1, 1, tzinfo=timezone.utc)
    return months


def _months_from_stat(stat: object) -> set[str]:
    months: set[str] = set()
    for value in _timestamps_ms_from_stat(stat):
        months.add(datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m"))
    return months


def _timestamps_ms_from_stat(stat: object) -> list[int]:
    values: list[int] = []
    for attr in ("st_mtime_ns", "st_ctime_ns"):
        raw = getattr(stat, attr, None)
        if raw is None:
            continue
        values.append(int(raw // 1_000_000))
    return values


def _extract_account_hints(source_path: str | None) -> set[str]:
    if not source_path:
        return set()
    hints = set()
    for part in PureWindowsPath(source_path).parts:
        text = str(part).strip()
        if text.isdigit() and len(text) >= 5:
            hints.add(text)
    return hints


def _load_legacy_md5_cache(directory: Path, *, cache_dir: Path) -> dict[str, object]:
    cache_path = _legacy_md5_cache_path(directory, cache_dir=cache_dir)
    if not cache_path.exists():
        return {"files": []}
    try:
        return orjson.loads(cache_path.read_bytes())
    except Exception:
        return {"files": []}


def _write_legacy_md5_cache(
    directory: Path,
    *,
    cache_dir: Path,
    rows: list[dict[str, object]],
) -> None:
    cache_path = _legacy_md5_cache_path(directory, cache_dir=cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "directory": str(directory.resolve()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": rows,
    }
    cache_path.write_bytes(orjson.dumps(payload))


def _legacy_md5_cache_path(directory: Path, *, cache_dir: Path) -> Path:
    digest = hashlib.sha1(str(directory.resolve()).encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"legacy_md5_{digest}.json"


def _build_export_rel_path(candidate: _AssetCandidate, resolved_path: Path) -> Path:
    folder = {
        "image": "images",
        "video": "videos",
        "speech": "audio",
        "file": "files",
        "sticker": "stickers",
    }[candidate.asset_type]
    preferred_name = candidate.file_name or resolved_path.name or f"{candidate.asset_type}_{_short_hash(str(resolved_path))}"
    file_name = _normalize_file_name(preferred_name, resolved_path=resolved_path, asset_type=candidate.asset_type)
    if candidate.asset_role:
        return Path(folder) / candidate.asset_role / file_name
    return Path(folder) / file_name


def _normalize_file_name(name: str, *, resolved_path: Path, asset_type: str) -> str:
    clean = "".join(char if char not in '<>:"/\\|?*' else "_" for char in name).strip() or f"{asset_type}_{_short_hash(str(resolved_path))}"
    guessed = _guess_extension(resolved_path)
    suffix = Path(clean).suffix.lower()
    if suffix:
        if _should_replace_suffix(asset_type=asset_type, current_suffix=suffix, guessed_suffix=guessed):
            return Path(clean).with_suffix(guessed).name
        return clean
    return f"{clean}{guessed}" if guessed else clean


def _should_replace_suffix(*, asset_type: str, current_suffix: str, guessed_suffix: str) -> bool:
    if not guessed_suffix:
        return False
    if asset_type not in {"image", "sticker", "video", "speech"}:
        return False
    equivalent_groups = [
        {".jpg", ".jpeg"},
    ]
    if current_suffix == guessed_suffix:
        return False
    if any({current_suffix, guessed_suffix}.issubset(group) for group in equivalent_groups):
        return False
    return True


def _guess_extension(path: Path) -> str:
    try:
        header = path.read_bytes()[:16]
    except Exception:
        return path.suffix
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    if header.startswith(b"BM"):
        return ".bmp"
    if header.startswith(b"#!AMR"):
        return ".amr"
    if header.startswith(b"#!SILK_V3"):
        return ".silk"
    if header.startswith(b"OggS"):
        return ".ogg"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return ".wav"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".mp4"
    return path.suffix


def _existing_path(value: str | None) -> Path | None:
    text = _string_or_none(value)
    if not text:
        return None
    candidate = Path(PureWindowsPath(text))
    if candidate.exists() and candidate.is_file():
        return candidate.resolve()
    return None


def _string_or_none(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _local_path_from_download_hint(hint: dict[str, Any] | None) -> str | None:
    if not isinstance(hint, dict):
        return None
    for key in ("path", "file", "url"):
        text = _string_or_none(hint.get(key))
        if text and _looks_like_local_path(text):
            return text
    return None


def _looks_like_local_path(value: str) -> bool:
    text = _string_or_none(value)
    if not text:
        return False
    return bool(re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"))


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def _content_dedupe_key(
    candidate: _AssetCandidate,
    resolved_path: Path,
    *,
    cache: dict[str, tuple[str, int, str] | None],
) -> tuple[str, int, str] | None:
    path_key = str(resolved_path.resolve()).lower()
    if path_key in cache:
        return cache[path_key]
    try:
        size = resolved_path.stat().st_size
    except OSError:
        cache[path_key] = None
        return None

    digest = _content_signature(resolved_path, size=size)
    if not digest:
        cache[path_key] = None
        return None
    key = (candidate.asset_type, size, digest)
    cache[path_key] = key
    return key


def _content_signature(path: Path, *, size: int) -> str | None:
    try:
        with path.open("rb") as handle:
            if size <= 256 * 1024:
                digest = hashlib.blake2b(digest_size=16)
                digest.update(handle.read())
                return f"full:{digest.hexdigest()}"

            sample_size = 64 * 1024
            window = min(sample_size, size)
            positions = [0]
            middle = max(0, (size // 2) - (window // 2))
            tail = max(0, size - window)
            for position in (middle, tail):
                if position not in positions:
                    positions.append(position)

            digest = hashlib.blake2b(digest_size=16)
            digest.update(str(size).encode("ascii"))
            for position in positions:
                handle.seek(position)
                chunk = handle.read(window)
                digest.update(str(position).encode("ascii"))
                digest.update(chunk)
            return f"sample:{digest.hexdigest()}"
    except OSError:
        return None


def _matching_export_rel_path_for_content_key(
    *,
    content_key: tuple[str, int, str] | None,
    resolved_path: Path,
    copied_content_map: dict[tuple[str, int, str], list[tuple[str, str]]],
    compare_cache: dict[tuple[str, str], bool],
) -> str | None:
    if content_key is None:
        return None
    entries = copied_content_map.get(content_key)
    if not entries:
        return None
    resolved_key = str(resolved_path.resolve()).lower()
    for existing_source_key, exported_rel_path in entries:
        if existing_source_key == resolved_key:
            return exported_rel_path
        if _file_contents_equal(
            Path(existing_source_key),
            resolved_path,
            cache=compare_cache,
        ):
            return exported_rel_path
    return None


def _file_contents_equal(
    left: Path,
    right: Path,
    *,
    cache: dict[tuple[str, str], bool],
) -> bool:
    left_key = str(left.resolve()).lower()
    right_key = str(right.resolve()).lower()
    pair = tuple(sorted((left_key, right_key)))
    if pair in cache:
        return cache[pair]
    try:
        left_stat = left.stat()
        right_stat = right.stat()
    except OSError:
        cache[pair] = False
        return False
    if left_stat.st_size != right_stat.st_size:
        cache[pair] = False
        return False
    chunk_size = 1024 * 1024
    try:
        with left.open("rb") as left_handle, right.open("rb") as right_handle:
            while True:
                left_chunk = left_handle.read(chunk_size)
                right_chunk = right_handle.read(chunk_size)
                if left_chunk != right_chunk:
                    cache[pair] = False
                    return False
                if not left_chunk:
                    cache[pair] = True
                    return True
    except OSError:
        cache[pair] = False
        return False


def _payload_marker(
    *,
    content_key: tuple[str, int, str] | None,
    resolved_path_key: str,
) -> tuple[Any, ...]:
    if content_key is not None:
        return ("content", *content_key)
    return ("source_path", resolved_path_key)


def _allocate_export_rel_path(
    rel_path: Path,
    *,
    payload_marker: tuple[Any, ...],
    used_payloads: dict[str, tuple[Any, ...]],
) -> Path:
    rel_key = rel_path.as_posix().lower()
    existing = used_payloads.get(rel_key)
    if existing is None or existing == payload_marker:
        used_payloads[rel_key] = payload_marker
        return rel_path

    stem = rel_path.stem
    suffix = rel_path.suffix
    parent = rel_path.parent
    marker_token = _payload_marker_token(payload_marker)
    candidate = parent / f"{stem}_{marker_token}{suffix}"
    candidate_key = candidate.as_posix().lower()
    if candidate_key not in used_payloads or used_payloads[candidate_key] == payload_marker:
        used_payloads[candidate_key] = payload_marker
        return candidate

    counter = 2
    while True:
        numbered = parent / f"{stem}_{marker_token}_{counter}{suffix}"
        numbered_key = numbered.as_posix().lower()
        if numbered_key not in used_payloads or used_payloads[numbered_key] == payload_marker:
            used_payloads[numbered_key] = payload_marker
            return numbered
        counter += 1


def _release_allocated_export_rel_path(
    rel_path: Path,
    *,
    payload_marker: tuple[Any, ...],
    used_payloads: dict[str, tuple[Any, ...]],
) -> None:
    rel_key = rel_path.as_posix().lower()
    if used_payloads.get(rel_key) == payload_marker:
        used_payloads.pop(rel_key, None)


def _payload_marker_token(payload_marker: tuple[Any, ...]) -> str:
    if payload_marker and payload_marker[0] == "content" and len(payload_marker) >= 4:
        return str(payload_marker[-1])[:8]
    if len(payload_marker) >= 2:
        return _short_hash(str(payload_marker[1]))
    return _short_hash(repr(payload_marker))


def _summarize_assets(assets: list[MaterializedAsset]) -> dict[str, int]:
    return {
        "copied": sum(1 for item in assets if item.status == "copied"),
        "reused": sum(1 for item in assets if item.status == "reused"),
        "missing": sum(1 for item in assets if item.status == "missing"),
        "error": sum(1 for item in assets if item.status == "error"),
        "total": len(assets),
    }


def _summarize_missing_breakdown(assets: list[MaterializedAsset]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in assets:
        if item.status != "missing":
            continue
        key = str(item.resolver or "missing").strip() or "missing"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
