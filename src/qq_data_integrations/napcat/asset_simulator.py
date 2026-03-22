from __future__ import annotations

import copy
import json
import os
import shutil
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .fast_history_client import NapCatFastHistoryTimeoutError, NapCatFastHistoryUnavailable
from .http_client import NapCatApiError, NapCatApiTimeoutError
from .media_downloader import NapCatMediaDownloader


class _DummyClient:
    pass


class _SleepingTimeoutPublicFileClient:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = max(0.0, float(delay_s))
        self.get_file_calls = 0

    def get_file(self, *args, **kwargs):
        self.get_file_calls += 1
        if self.delay_s > 0.0:
            time.sleep(self.delay_s)
        raise NapCatApiTimeoutError("NapCat action timed out: get_file")


class _SleepingTimeoutPublicRecordClient:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = max(0.0, float(delay_s))
        self.get_record_calls = 0

    def get_record(self, *args, **kwargs):
        self.get_record_calls += 1
        if self.delay_s > 0.0:
            time.sleep(self.delay_s)
        raise NapCatApiTimeoutError("NapCat action timed out: get_record")


class _SleepingTimeoutForwardClient:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = max(0.0, float(delay_s))
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay_s > 0.0:
            time.sleep(self.delay_s)
        raise NapCatFastHistoryTimeoutError("timed out")


@dataclass(frozen=True, slots=True)
class AssetSimulationResult:
    route: str
    asset_type: str
    age_days: int
    parents: int
    siblings_per_parent: int
    total_requests: int
    backend_timeout_calls: int
    short_circuited_requests: int
    simulated_elapsed_s: float
    equivalent_live_timeout_s: float
    timeout_budget_s: float
    progress_snapshot: dict[str, Any]
    trace_event_count: int
    trace_status_breakdown: dict[str, int]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _age_bucket_label(age_days: int) -> str:
    normalized = max(0, int(age_days))
    if normalized >= 180:
        return "old_forward"
    if normalized >= 30:
        return "aged"
    return "recent"


def build_forward_timeout_request(
    *,
    asset_type: str,
    parent_index: int,
    sibling_index: int,
    age_days: int = 20,
) -> dict[str, object]:
    suffix = {
        "video": "mp4",
        "speech": "mp3",
        "file": "bin",
    }.get(asset_type, "dat")
    return {
        "asset_type": asset_type,
        "asset_role": "forward_media",
        "file_name": f"{asset_type}-p{parent_index:04d}-s{sibling_index:04d}.{suffix}",
        "md5": f"{parent_index:04d}{sibling_index:04d}".lower(),
        "timestamp_ms": _timestamp_ms_for_age_days(age_days),
        "download_hint": {
            "_forward_parent": {
                "message_id_raw": f"7617{parent_index:012d}",
                "element_id": f"7617{parent_index:012d}",
                "peer_uid": "u_simulated",
                "chat_type_raw": "2",
            }
        },
    }


def run_forward_timeout_simulation(
    *,
    route: str,
    asset_type: str,
    parents: int,
    siblings_per_parent: int,
    age_days: int = 20,
    delay_s: float = 0.0,
    trace_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AssetSimulationResult:
    normalized_route = str(route or "").strip().lower()
    normalized_asset_type = str(asset_type or "").strip().lower()
    if normalized_route not in {"public-token", "forward-materialize", "forward-metadata"}:
        raise ValueError(f"unsupported route: {route}")
    if normalized_asset_type not in {"video", "speech", "file"}:
        raise ValueError(f"unsupported asset_type: {asset_type}")
    parents = max(1, int(parents))
    siblings_per_parent = max(1, int(siblings_per_parent))
    age_days = max(0, int(age_days))

    events: list[dict[str, Any]] = []

    def _trace(event: dict[str, Any]) -> None:
        events.append(dict(event))
        if trace_callback is not None:
            trace_callback(dict(event))

    if normalized_route == "public-token":
        if normalized_asset_type == "speech":
            client = _SleepingTimeoutPublicRecordClient(delay_s=delay_s)
            downloader = NapCatMediaDownloader(client)
            backend_call_getter = lambda: client.get_record_calls
            action = "get_record"
        else:
            client = _SleepingTimeoutPublicFileClient(delay_s=delay_s)
            downloader = NapCatMediaDownloader(client)
            backend_call_getter = lambda: client.get_file_calls
            action = "get_file"
        timeout_probe_request = build_forward_timeout_request(
            asset_type=normalized_asset_type,
            parent_index=0,
            sibling_index=0,
            age_days=age_days,
        )
        timeout_budget_s = downloader._public_action_timeout_s(action, request=timeout_probe_request)
        started = time.perf_counter()
        for parent_index in range(parents):
            for sibling_index in range(siblings_per_parent):
                request = build_forward_timeout_request(
                    asset_type=normalized_asset_type,
                    parent_index=parent_index,
                    sibling_index=sibling_index,
                    age_days=age_days,
                )
                token = f"token-{normalized_asset_type}-{parent_index:04d}-{sibling_index:04d}"
                downloader._call_public_action_with_token(
                    action,
                    token,
                    request=request,
                    trace_callback=_trace,
                )
        elapsed_s = time.perf_counter() - started
        backend_timeout_calls = int(backend_call_getter())
    else:
        fast_client = _SleepingTimeoutForwardClient(delay_s=delay_s)
        downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
        timeout_probe_request = build_forward_timeout_request(
            asset_type=normalized_asset_type,
            parent_index=0,
            sibling_index=0,
            age_days=age_days,
        )
        timeout_budget_s = downloader._forward_context_timeout_s(
            timeout_probe_request,
            materialize=(normalized_route == "forward-materialize"),
        )
        started = time.perf_counter()
        for parent_index in range(parents):
            for sibling_index in range(siblings_per_parent):
                request = build_forward_timeout_request(
                    asset_type=normalized_asset_type,
                    parent_index=parent_index,
                    sibling_index=sibling_index,
                    age_days=age_days,
                )
                downloader._download_via_forward_context(
                    request,
                    materialize=(normalized_route == "forward-materialize"),
                    trace_callback=_trace,
                )
        elapsed_s = time.perf_counter() - started
        backend_timeout_calls = len(fast_client.calls)

    total_requests = parents * siblings_per_parent
    short_circuited_requests = max(0, total_requests - backend_timeout_calls)
    equivalent_live_timeout_s = backend_timeout_calls * timeout_budget_s
    trace_status_breakdown: dict[str, int] = {}
    for event in events:
        if str(event.get("phase") or "") != "materialize_asset_substep":
            continue
        status = str(event.get("status") or "").strip()
        if not status:
            continue
        trace_status_breakdown[status] = trace_status_breakdown.get(status, 0) + 1
    explanation = (
        "Parent-scoped timeout short-circuit is working for siblings under the same forward parent."
        if parents == 1 and siblings_per_parent > 1
        else "Each distinct forward parent still pays one full timeout; short-circuit only helps repeated siblings under the same parent."
    )

    return AssetSimulationResult(
        route=normalized_route,
        asset_type=normalized_asset_type,
        age_days=age_days,
        parents=parents,
        siblings_per_parent=siblings_per_parent,
        total_requests=total_requests,
        backend_timeout_calls=backend_timeout_calls,
        short_circuited_requests=short_circuited_requests,
        simulated_elapsed_s=round(elapsed_s, 6),
        equivalent_live_timeout_s=round(equivalent_live_timeout_s, 3),
        timeout_budget_s=round(timeout_budget_s, 3),
        progress_snapshot=downloader.export_download_progress_snapshot(),
        trace_event_count=len(events),
        trace_status_breakdown=trace_status_breakdown,
        explanation=explanation,
    )


def default_forward_timeout_matrix(*, delay_s: float = 0.0) -> list[AssetSimulationResult]:
    scenarios = [
        (route, asset_type, parents, siblings_per_parent, age_days)
        for route in ("public-token", "forward-materialize", "forward-metadata")
        for asset_type in ("video", "file", "speech")
        for age_days in (20, 260)
        for parents, siblings_per_parent in ((1, 8), (8, 1), (4, 4))
    ]
    return [
        run_forward_timeout_simulation(
            route=route,
            asset_type=asset_type,
            parents=parents,
            siblings_per_parent=siblings_per_parent,
            age_days=age_days,
            delay_s=delay_s,
        )
        for route, asset_type, parents, siblings_per_parent, age_days in scenarios
    ]


def summarize_forward_timeout_results(results: list[AssetSimulationResult]) -> dict[str, Any]:
    route_counts: Counter[str] = Counter()
    asset_counts: Counter[str] = Counter()
    age_bucket_counts: Counter[str] = Counter()
    trace_totals: Counter[str] = Counter()
    trace_by_route: dict[str, Counter[str]] = {}
    total_live_timeout = 0.0
    total_breaker_savings = 0.0
    max_backend_calls = 0
    max_timeout_budget = 0.0
    worst_case: AssetSimulationResult | None = None
    storm_risk_count = 0
    short_circuit_help_count = 0
    threshold_counts = {30: 0, 60: 0, 120: 0}
    for item in results:
        route_counts[item.route] += 1
        asset_counts[item.asset_type] += 1
        age_bucket = _age_bucket_label(item.age_days)
        age_bucket_counts[age_bucket] += 1
        total_live_timeout += float(item.equivalent_live_timeout_s)
        for threshold in threshold_counts:
            if float(item.equivalent_live_timeout_s) > float(threshold):
                threshold_counts[threshold] += 1
        total_breaker_savings += max(
            0.0,
            (float(item.total_requests) * float(item.timeout_budget_s))
            - float(item.equivalent_live_timeout_s),
        )
        max_backend_calls = max(max_backend_calls, int(item.backend_timeout_calls))
        max_timeout_budget = max(max_timeout_budget, float(item.timeout_budget_s))
        if item.short_circuited_requests > 0:
            short_circuit_help_count += 1
        if item.parents > 1 and item.siblings_per_parent == 1 and item.backend_timeout_calls == item.total_requests:
            storm_risk_count += 1
        if worst_case is None or float(item.equivalent_live_timeout_s) > float(worst_case.equivalent_live_timeout_s):
            worst_case = item
        for status, count in item.trace_status_breakdown.items():
            trace_totals[status] += int(count)
            route_counter = trace_by_route.setdefault(
                f"{item.route}:{item.asset_type}:{age_bucket}",
                Counter(),
            )
            route_counter[status] += int(count)
    summary = {
        "total": len(results),
        "route_counts": dict(route_counts),
        "asset_type_counts": dict(asset_counts),
        "age_bucket_counts": dict(age_bucket_counts),
        "trace_status_totals": dict(trace_totals),
        "trace_status_by_route": {
            key: dict(counter) for key, counter in trace_by_route.items()
        },
        "equivalent_live_timeout_total_s": round(total_live_timeout, 3),
        "breaker_savings_total_s": round(total_breaker_savings, 3),
        "max_backend_timeout_calls": max_backend_calls,
        "max_timeout_budget_s": round(max_timeout_budget, 3),
        "storm_risk_count": storm_risk_count,
        "short_circuit_help_count": short_circuit_help_count,
        "threshold_counts": {
            f"over_{threshold}s": count for threshold, count in threshold_counts.items()
        },
    }
    if worst_case is not None:
        summary["worst_case"] = {
            "route": worst_case.route,
            "asset_type": worst_case.asset_type,
            "age_days": worst_case.age_days,
            "parents": worst_case.parents,
            "siblings_per_parent": worst_case.siblings_per_parent,
            "equivalent_live_timeout_s": round(float(worst_case.equivalent_live_timeout_s), 3),
            "backend_timeout_calls": int(worst_case.backend_timeout_calls),
            "timeout_budget_s": round(float(worst_case.timeout_budget_s), 3),
        }
    return summary


@dataclass(frozen=True, slots=True)
class PrefetchPlanningScenario:
    name: str
    profile: str
    request_count: int
    old_forward_ratio: float
    duplicate_ratio: float
    local_hit_ratio: float
    eager_remote_ratio: float
    context_only_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PrefetchPlanningResult:
    name: str
    profile: str
    request_count: int
    total_prefetchable: int
    eager_remote_prefetchable: int
    context_only_prefetchable: int
    local_hit_count: int
    old_forward_count: int
    duplicate_shared_key_count: int
    eager_remote_skip_count: int
    remote_workers: int
    public_token_workers: int
    batch_size: int
    batch_timeout_s: float
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _PrefetchPlanningDownloader(NapCatMediaDownloader):
    def _create_prefetch_executors(self) -> None:
        self._public_token_executor = None
        self._remote_loop = None
        self._remote_loop_thread = None
        self._remote_async_client = None
        self._remote_async_semaphore = None
        self._remote_prefetch_runtime_disabled = True
        self._remote_prefetch_runtime_disable_reason = "simulated"

    def _rebuild_prefetch_executors(self, *, wait: bool, recreate: bool) -> None:
        _ = wait, recreate
        return


def _make_prefetch_local_file(root: Path, *, asset_type: str, index: int) -> str:
    suffix = _asset_suffix(asset_type)
    target = root / "local" / asset_type / f"{asset_type}-{index:05d}.{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"local:{asset_type}:{index}".encode("utf-8"))
    return str(target.resolve())


def _build_prefetch_request(
    *,
    root: Path,
    asset_type: str,
    index: int,
    old_forward: bool,
    local_hit: bool,
    eager_remote: bool,
) -> dict[str, Any]:
    suffix = _asset_suffix(asset_type)
    request: dict[str, Any] = {
        "asset_type": asset_type,
        "asset_role": "forward_media" if old_forward else "",
        "file_name": f"{asset_type}-{index:05d}.{suffix}",
        "md5": f"{asset_type[:2]}{index:030x}"[:32],
        "timestamp_ms": _timestamp_ms_for_age_days(260 if old_forward else 20),
        "download_hint": {},
    }
    if old_forward:
        request["download_hint"] = {
            "_forward_parent": {
                "message_id_raw": f"parent_{index // 3:06d}",
                "element_id": f"el_{index // 3:06d}",
                "peer_uid": "u_prefetch",
                "chat_type_raw": "2",
            }
        }
    if local_hit:
        request["source_path"] = _make_prefetch_local_file(root, asset_type=asset_type, index=index)
    elif eager_remote:
        request["download_hint"]["remote_url"] = (
            f"https://assets.example.invalid/{asset_type}/{index:05d}.{suffix}"
        )
    return request


def default_prefetch_planning_scenarios() -> list[PrefetchPlanningScenario]:
    profile_defaults = {
        "recent_image_heavy": (0.0, 0.45, 0.40, 0.15),
        "old_forward_video_heavy": (0.80, 0.05, 0.10, 0.85),
        "token_heavy_low_yield": (0.45, 0.08, 0.02, 0.90),
        "mixed_realistic_large_window": (0.35, 0.25, 0.30, 0.45),
    }
    scenarios: list[PrefetchPlanningScenario] = []
    for profile, (old_ratio, duplicate_ratio, local_ratio, eager_ratio) in profile_defaults.items():
        context_ratio = max(0.0, 1.0 - local_ratio - eager_ratio)
        for request_count in (32, 256, 1024, 4096, 16384):
            scenarios.append(
                PrefetchPlanningScenario(
                    name=f"{profile}_{request_count}",
                    profile=profile,
                    request_count=request_count,
                    old_forward_ratio=old_ratio,
                    duplicate_ratio=duplicate_ratio,
                    local_hit_ratio=local_ratio,
                    eager_remote_ratio=eager_ratio,
                    context_only_ratio=context_ratio,
                )
            )
    return scenarios


def run_prefetch_planning_scenario(
    scenario: PrefetchPlanningScenario,
) -> PrefetchPlanningResult:
    repo_root = Path(__file__).resolve().parents[3]
    temp_root = repo_root / ".tmp" / "asset_simulator_prefetch" / scenario.name
    shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    downloader = _PrefetchPlanningDownloader(_DummyClient())
    progress_events: list[dict[str, Any]] = []
    try:
        requests: list[dict[str, Any]] = []
        asset_cycle = {
            "recent_image_heavy": ("image", "image", "image", "file"),
            "old_forward_video_heavy": ("video", "video", "file", "speech"),
            "token_heavy_low_yield": ("video", "file", "speech", "image"),
            "mixed_realistic_large_window": ("image", "video", "file", "speech"),
        }.get(scenario.profile, ("image", "video", "file", "speech"))
        base_unique_count = max(1, int(round(scenario.request_count * (1.0 - scenario.duplicate_ratio))))
        unique_requests: list[dict[str, Any]] = []
        for index in range(base_unique_count):
            asset_type = asset_cycle[index % len(asset_cycle)]
            ratio_slot = index / max(1, base_unique_count)
            old_forward = ratio_slot < scenario.old_forward_ratio
            local_hit = ratio_slot < scenario.local_hit_ratio
            eager_remote = (not local_hit) and (ratio_slot < (scenario.local_hit_ratio + scenario.eager_remote_ratio))
            unique_requests.append(
                _build_prefetch_request(
                    root=temp_root,
                    asset_type=asset_type,
                    index=index,
                    old_forward=old_forward,
                    local_hit=local_hit,
                    eager_remote=eager_remote,
                )
            )
        requests.extend(copy.deepcopy(item) for item in unique_requests)
        duplicate_count = max(0, scenario.request_count - len(requests))
        for index in range(duplicate_count):
            requests.append(copy.deepcopy(unique_requests[index % len(unique_requests)]))

        downloader._configure_prefetch_pools_for_requests(
            requests,
            progress_callback=progress_events.append,
        )
        local_hit_count = 0
        old_forward_count = 0
        eager_remote_prefetchable = 0
        total_prefetchable = 0
        eager_remote_skip_count = 0
        shared_keys: list[tuple[Any, ...] | None] = []
        for request in requests:
            hint = downloader._request_hint(request)
            old_bucket = downloader._old_context_bucket(str(request.get("asset_type") or "").strip(), request)
            if downloader._resolve_from_source_local_path(request) != (None, None):
                local_hit_count += 1
            if downloader._has_forward_parent_hint(hint) and old_bucket is not None:
                old_forward_count += 1
            shared_keys.append(downloader._shared_request_key(request))
            if str(request.get("asset_type") or "").strip() not in downloader.REMOTE_PREFETCHABLE_ASSET_TYPES:
                continue
            if downloader._resolve_from_source_local_path(request) != (None, None):
                continue
            if downloader._resolve_from_hint_local_path(hint) != (None, None):
                continue
            total_prefetchable += 1
            resolved_remote = downloader._resolve_remote_url(
                str(hint.get("remote_url") or hint.get("url") or "").strip()
            )
            if resolved_remote:
                eager_remote_prefetchable += 1
                if downloader._should_skip_eager_remote_prefetch(request, old_bucket=old_bucket):
                    eager_remote_skip_count += 1
        duplicate_shared_key_count = len(
            [key for key in shared_keys if key is not None]
        ) - len({key for key in shared_keys if key is not None})
        return PrefetchPlanningResult(
            name=scenario.name,
            profile=scenario.profile,
            request_count=len(requests),
            total_prefetchable=total_prefetchable,
            eager_remote_prefetchable=eager_remote_prefetchable,
            context_only_prefetchable=max(0, total_prefetchable - eager_remote_prefetchable),
            local_hit_count=local_hit_count,
            old_forward_count=old_forward_count,
            duplicate_shared_key_count=max(0, duplicate_shared_key_count),
            eager_remote_skip_count=eager_remote_skip_count,
            remote_workers=downloader._remote_media_fetch_workers,
            public_token_workers=downloader._public_token_prefetch_workers,
            batch_size=downloader._prefetch_batch_size_for_request_count(len(requests)),
            batch_timeout_s=downloader._prefetch_batch_timeout_s(
                downloader._prefetch_batch_size_for_request_count(len(requests)),
                len(requests),
            ),
            notes=f"progress_events={len(progress_events)} profile={scenario.profile}",
        )
    finally:
        downloader.close()
        shutil.rmtree(temp_root, ignore_errors=True)


def run_prefetch_planning_matrix() -> list[PrefetchPlanningResult]:
    return [run_prefetch_planning_scenario(item) for item in default_prefetch_planning_scenarios()]


def summarize_prefetch_planning_results(
    results: list[PrefetchPlanningResult],
) -> dict[str, Any]:
    profile_counts: Counter[str] = Counter()
    total_prefetchable = 0
    eager_remote_total = 0
    context_only_total = 0
    local_hits_total = 0
    old_forward_total = 0
    duplicate_shared_key_total = 0
    eager_remote_skip_total = 0
    max_batch_size = 0
    large_window_case_count = 0
    large_window_batch_size_min: int | None = None
    large_window_batch_size_max = 0
    max_remote_workers = 0
    max_public_token_workers = 0
    worst_case: PrefetchPlanningResult | None = None
    for item in results:
        profile_counts[item.profile] += 1
        total_prefetchable += item.total_prefetchable
        eager_remote_total += item.eager_remote_prefetchable
        context_only_total += item.context_only_prefetchable
        local_hits_total += item.local_hit_count
        old_forward_total += item.old_forward_count
        duplicate_shared_key_total += item.duplicate_shared_key_count
        eager_remote_skip_total += item.eager_remote_skip_count
        max_batch_size = max(max_batch_size, item.batch_size)
        if item.request_count >= NapCatMediaDownloader.PREFETCH_LARGE_REQUEST_THRESHOLD:
            large_window_case_count += 1
            large_window_batch_size_max = max(large_window_batch_size_max, item.batch_size)
            if large_window_batch_size_min is None:
                large_window_batch_size_min = item.batch_size
            else:
                large_window_batch_size_min = min(large_window_batch_size_min, item.batch_size)
        max_remote_workers = max(max_remote_workers, item.remote_workers)
        max_public_token_workers = max(max_public_token_workers, item.public_token_workers)
        if worst_case is None or item.total_prefetchable > worst_case.total_prefetchable:
            worst_case = item
    summary = {
        "total": len(results),
        "profile_counts": dict(profile_counts),
        "total_prefetchable": total_prefetchable,
        "eager_remote_total": eager_remote_total,
        "context_only_total": context_only_total,
        "local_hits_total": local_hits_total,
        "old_forward_total": old_forward_total,
        "duplicate_shared_key_total": duplicate_shared_key_total,
        "eager_remote_skip_total": eager_remote_skip_total,
        "max_batch_size": max_batch_size,
        "large_window_case_count": large_window_case_count,
        "large_window_batch_size_min": large_window_batch_size_min,
        "large_window_batch_size_max": large_window_batch_size_max,
        "max_remote_workers": max_remote_workers,
        "max_public_token_workers": max_public_token_workers,
    }
    if worst_case is not None:
        summary["worst_case"] = worst_case.to_dict()
    return summary


@dataclass(frozen=True, slots=True)
class ForwardCandidatePriorityCase:
    name: str
    asset_type: str
    profile: str
    primary_signals: tuple[str, ...]
    primary_recoverability: str
    decoy_signals: tuple[str, ...]
    decoy_recoverability: str
    expected_winner: str = "primary"
    expected_path_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ForwardCandidatePriorityResult:
    name: str
    asset_type: str
    profile: str
    expected_winner: str
    expected_path_kind: str
    actual_winner: str | None
    matched: bool
    resolver: str | None
    path_kind: str
    primary_signals: tuple[str, ...]
    primary_recoverability: str
    decoy_signals: tuple[str, ...]
    decoy_recoverability: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SharedOutcomeScopeCase:
    name: str
    asset_type: str
    topology: str
    identity_mode: str
    expected_same_key: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SharedOutcomeScopeResult:
    name: str
    asset_type: str
    topology: str
    identity_mode: str
    expected_same_key: bool
    actual_same_key: bool
    matched: bool
    key_a: tuple[Any, ...] | None
    key_b: tuple[Any, ...] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PublicTimeoutScopeCase:
    name: str
    asset_type: str
    relationship: str
    expected_same_key: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PublicTimeoutScopeResult:
    name: str
    asset_type: str
    relationship: str
    expected_same_key: bool
    actual_same_key: bool
    matched: bool
    key_a: tuple[str, ...] | None
    key_b: tuple[str, ...] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _CandidatePriorityDownloader(NapCatMediaDownloader):
    def __init__(
        self,
        *,
        token_paths: dict[tuple[str, str], str],
        remote_paths: dict[str, str],
    ) -> None:
        self._candidate_token_paths = token_paths
        self._candidate_remote_paths = remote_paths
        super().__init__(_DummyClient())

    def _create_prefetch_executors(self) -> None:
        self._public_token_executor = None
        self._remote_loop = None
        self._remote_loop_thread = None
        self._remote_async_client = None
        self._remote_async_semaphore = None

    def _rebuild_prefetch_executors(self, *, wait: bool, recreate: bool) -> None:
        _ = wait, recreate
        return

    def _resolve_from_public_token(  # type: ignore[override]
        self,
        data: dict[str, Any] | None,
        *,
        old_bucket: tuple[str, str] | None = None,
        expired_candidate: bool = False,
        request: dict[str, Any] | None = None,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path | None, str | None] | None:
        _ = old_bucket, expired_candidate, request, trace_callback
        if not isinstance(data, dict):
            return None
        action = str(data.get("public_action") or "").strip().lower()
        token = str(data.get("public_file_token") or "").strip()
        path_text = self._candidate_token_paths.get((action, token))
        if not path_text:
            return None
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            return None
        return path.resolve(), f"napcat_public_token_{action}"

    def _download_remote_media(  # type: ignore[override]
        self,
        *,
        asset_type: str,
        file_name: str | None,
        hint: dict[str, Any],
    ) -> str | None:
        _ = asset_type, file_name
        resolved_remote_url = self._resolve_remote_url(str(hint.get("url") or "").strip())
        if not resolved_remote_url:
            return None
        return self._candidate_remote_paths.get(resolved_remote_url)


def _candidate_suffix(asset_type: str) -> str:
    return {
        "image": "jpg",
        "video": "mp4",
        "file": "bin",
        "speech": "mp3",
    }.get(asset_type, "dat")


def _candidate_action(asset_type: str) -> str:
    return "get_record" if asset_type == "speech" else "get_file" if asset_type in {"video", "file"} else "get_image"


def _recoverability_path_kind(recoverability: str) -> str:
    normalized = str(recoverability or "").strip().lower()
    if normalized in {"local", "remote", "public"}:
        return normalized
    return "missing"


def _candidate_request(asset_type: str) -> dict[str, Any]:
    suffix = _candidate_suffix(asset_type)
    return {
        "asset_type": asset_type,
        "asset_role": "forward_media",
        "file_name": f"target.asset.{suffix}",
        "md5": f"{asset_type}-md5-target",
        "download_hint": {
            "_forward_parent": {
                "message_id_raw": f"parent_{asset_type}",
                "element_id": f"element_{asset_type}",
                "peer_uid": "u_candidate",
                "chat_type_raw": "2",
            },
            "file_id": f"/fileid/{asset_type}/target",
            "remote_url": f"https://assets.example.invalid/{asset_type}/target.asset.{suffix}",
            "file_biz_id": f"biz-{asset_type}-target",
        },
    }


def _candidate_test_file(root: Path, *, name: str) -> str:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"candidate:{name}".encode("utf-8"))
    return str(target.resolve())


def _candidate_asset_payload(
    *,
    root: Path,
    asset_type: str,
    label: str,
    signals: tuple[str, ...],
    recoverability: str,
    request: dict[str, Any],
    token_paths: dict[tuple[str, str], str],
    remote_paths: dict[str, str],
) -> dict[str, Any]:
    suffix = _candidate_suffix(asset_type)
    hint = request.get("download_hint") if isinstance(request.get("download_hint"), dict) else {}
    request_file_name = str(request.get("file_name") or "").strip()
    request_md5 = str(request.get("md5") or "").strip()
    request_file_id = str(hint.get("file_id") or "").strip()
    request_remote_url = str(hint.get("remote_url") or hint.get("url") or "").strip()
    request_file_biz_id = str(hint.get("file_biz_id") or request.get("file_biz_id") or "").strip()
    payload: dict[str, Any] = {
        "asset_type": asset_type,
        "asset_role": "forward_media",
        "_candidate_label": label,
        "file_name": f"{label}.{suffix}",
        "md5": f"{asset_type}-md5-{label}",
        "file_id": f"/fileid/{asset_type}/{label}",
        "file_biz_id": f"biz-{asset_type}-{label}",
    }
    if "file_name" in signals:
        payload["file_name"] = request_file_name
    elif "stem" in signals:
        payload["file_name"] = f"target.asset.alt.{suffix}"
    if "md5" in signals:
        payload["md5"] = request_md5
    if "file_id" in signals:
        payload["file_id"] = request_file_id
    if "file_biz_id" in signals:
        payload["file_biz_id"] = request_file_biz_id
    if "url" in signals:
        payload["remote_url"] = request_remote_url
        payload["url"] = request_remote_url
    if recoverability == "local":
        payload["file"] = _candidate_test_file(root, name=f"local/{label}.{suffix}")
    elif recoverability == "remote":
        remote_url = (
            request_remote_url
            if "url" in signals
            else f"https://assets.example.invalid/{asset_type}/{label}.{suffix}"
        )
        payload["remote_url"] = remote_url
        payload["url"] = remote_url
        remote_paths[remote_url] = _candidate_test_file(root, name=f"remote/{label}.{suffix}")
    elif recoverability == "public":
        token = f"token-{asset_type}-{label}"
        payload["public_action"] = _candidate_action(asset_type)
        payload["public_file_token"] = token
        token_paths[(payload["public_action"], token)] = _candidate_test_file(
            root,
            name=f"public/{label}.{suffix}",
        )
    return payload


def default_forward_candidate_priority_cases() -> list[ForwardCandidatePriorityCase]:
    cases: list[ForwardCandidatePriorityCase] = []
    recoverability_order = ("local", "remote", "public", "blank")
    for asset_type in ("image", "video", "file", "speech"):
        for index, primary_recoverability in enumerate(recoverability_order):
            for decoy_recoverability in recoverability_order[index + 1 :]:
                cases.append(
                    ForwardCandidatePriorityCase(
                        name=f"{asset_type}_tiebreak_{primary_recoverability}_over_{decoy_recoverability}",
                        asset_type=asset_type,
                        profile="recoverability_tiebreak",
                        primary_signals=("file_name",),
                        primary_recoverability=primary_recoverability,
                        decoy_signals=("file_name",),
                        decoy_recoverability=decoy_recoverability,
                        expected_path_kind=_recoverability_path_kind(primary_recoverability),
                    )
                )
        cases.extend(
            [
                ForwardCandidatePriorityCase(
                    name=f"{asset_type}_signal_md5_over_filename",
                    asset_type=asset_type,
                    profile="signal_priority",
                    primary_signals=("md5",),
                    primary_recoverability="public",
                    decoy_signals=("file_name",),
                    decoy_recoverability="local",
                    expected_path_kind="public",
                ),
                ForwardCandidatePriorityCase(
                    name=f"{asset_type}_signal_file_id_over_filename",
                    asset_type=asset_type,
                    profile="signal_priority",
                    primary_signals=("file_id",),
                    primary_recoverability="public",
                    decoy_signals=("file_name",),
                    decoy_recoverability="local",
                    expected_path_kind="public",
                ),
                ForwardCandidatePriorityCase(
                    name=f"{asset_type}_signal_url_over_filename",
                    asset_type=asset_type,
                    profile="signal_priority",
                    primary_signals=("url",),
                    primary_recoverability="remote",
                    decoy_signals=("file_name",),
                    decoy_recoverability="local",
                    expected_path_kind="remote",
                ),
                ForwardCandidatePriorityCase(
                    name=f"{asset_type}_signal_filename_over_stem",
                    asset_type=asset_type,
                    profile="signal_priority",
                    primary_signals=("file_name",),
                    primary_recoverability="public",
                    decoy_signals=("stem",),
                    decoy_recoverability="local",
                    expected_path_kind="public",
                ),
            ]
        )
    for asset_type in ("video", "file"):
        cases.append(
            ForwardCandidatePriorityCase(
                name=f"{asset_type}_signal_file_biz_id_over_filename",
                asset_type=asset_type,
                profile="signal_priority",
                primary_signals=("file_biz_id",),
                primary_recoverability="public",
                decoy_signals=("file_name",),
                decoy_recoverability="local",
                expected_path_kind="public",
            )
        )
    return cases


def run_forward_candidate_priority_case(
    case: ForwardCandidatePriorityCase,
) -> ForwardCandidatePriorityResult:
    repo_root = Path(__file__).resolve().parents[3]
    temp_root = repo_root / ".tmp" / "asset_simulator_candidates" / case.name
    shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    token_paths: dict[tuple[str, str], str] = {}
    remote_paths: dict[str, str] = {}
    request = _candidate_request(case.asset_type)
    downloader = _CandidatePriorityDownloader(
        token_paths=token_paths,
        remote_paths=remote_paths,
    )
    try:
        primary = _candidate_asset_payload(
            root=temp_root,
            asset_type=case.asset_type,
            label="primary",
            signals=case.primary_signals,
            recoverability=case.primary_recoverability,
            request=request,
            token_paths=token_paths,
            remote_paths=remote_paths,
        )
        decoy = _candidate_asset_payload(
            root=temp_root,
            asset_type=case.asset_type,
            label="decoy",
            signals=case.decoy_signals,
            recoverability=case.decoy_recoverability,
            request=request,
            token_paths=token_paths,
            remote_paths=remote_paths,
        )
        resolved, matched_payload = downloader._pick_forward_asset_match(
            request,
            [decoy, primary],
        )
        actual_winner = (
            str(matched_payload.get("_candidate_label") or "").strip() or None
            if isinstance(matched_payload, dict)
            else None
        )
        path_kind = "missing"
        resolved_tuple = (
            resolved
            if isinstance(resolved, tuple) and len(resolved) == 2
            else (None, None)
        )
        if resolved_tuple[0] is not None:
            resolver = str(resolved_tuple[1] or "").strip() or None
            if resolver == "napcat_forward_hydrated":
                path_kind = "local"
            elif "remote_url" in str(resolver or ""):
                path_kind = "remote"
            elif "public_token" in str(resolver or ""):
                path_kind = "public"
            else:
                path_kind = "local"
        else:
            resolver = None
        expected_path_kind = case.expected_path_kind or _recoverability_path_kind(
            case.primary_recoverability if case.expected_winner == "primary" else case.decoy_recoverability
        )
        return ForwardCandidatePriorityResult(
            name=case.name,
            asset_type=case.asset_type,
            profile=case.profile,
            expected_winner=case.expected_winner,
            expected_path_kind=expected_path_kind,
            actual_winner=actual_winner,
            matched=(
                actual_winner == case.expected_winner
                and path_kind == expected_path_kind
            ),
            resolver=resolver,
            path_kind=path_kind,
            primary_signals=case.primary_signals,
            primary_recoverability=case.primary_recoverability,
            decoy_signals=case.decoy_signals,
            decoy_recoverability=case.decoy_recoverability,
        )
    finally:
        downloader.close()
        shutil.rmtree(temp_root, ignore_errors=True)


def run_forward_candidate_priority_matrix() -> list[ForwardCandidatePriorityResult]:
    return [
        run_forward_candidate_priority_case(item)
        for item in default_forward_candidate_priority_cases()
    ]


def summarize_forward_candidate_priority_results(
    results: list[ForwardCandidatePriorityResult],
) -> dict[str, Any]:
    profile_counts: Counter[str] = Counter()
    asset_type_counts: Counter[str] = Counter()
    resolver_counts: Counter[str] = Counter()
    path_kind_counts: Counter[str] = Counter()
    mismatches: list[str] = []
    for item in results:
        profile_counts[item.profile] += 1
        asset_type_counts[item.asset_type] += 1
        resolver_counts[str(item.resolver or "<none>")] += 1
        path_kind_counts[item.path_kind] += 1
        if not item.matched:
            mismatches.append(item.name)
    return {
        "total": len(results),
        "matched": len(results) - len(mismatches),
        "mismatched": len(mismatches),
        "profile_counts": dict(profile_counts),
        "asset_type_counts": dict(asset_type_counts),
        "resolver_counts": dict(resolver_counts),
        "path_kind_counts": dict(path_kind_counts),
        "mismatch_names": mismatches,
    }


def _scope_request(
    *,
    asset_type: str,
    topology: str,
    identity_mode: str,
    variant: str,
) -> dict[str, Any]:
    suffix = _candidate_suffix(asset_type)
    request: dict[str, Any] = {
        "asset_type": asset_type,
        "asset_role": "forward_media" if topology == "forward" else "",
        "file_name": "" if identity_mode == "none" else f"scope-target-{asset_type}.{suffix}",
        "md5": "",
        "source_path": "",
    }
    hint: dict[str, Any] = {}
    if topology == "forward":
        hint["_forward_parent"] = {
            "message_id_raw": "parent-shared-scope",
            "element_id": "element-shared-scope",
            "peer_uid": "u-shared-scope",
            "chat_type_raw": "2",
        }
    if identity_mode == "md5":
        request["md5"] = f"scope-md5-{asset_type}"
    elif identity_mode == "remote_url":
        hint["remote_url"] = f"https://assets.example.invalid/shared/{asset_type}/{variant}.bin"
    elif identity_mode == "remote_url_same":
        hint["remote_url"] = f"https://assets.example.invalid/shared/{asset_type}/shared.bin"
    elif identity_mode == "file_id":
        hint["file_id"] = f"/scope/{asset_type}/shared"
    elif identity_mode == "source_leaf":
        request["source_path"] = f"C:\\QQ\\cache\\{asset_type}\\shared-{asset_type}.bin"
    elif identity_mode == "file_name_only":
        pass
    elif identity_mode == "none":
        request["file_name"] = ""
    else:
        raise ValueError(f"unsupported identity_mode: {identity_mode}")
    if hint:
        request["download_hint"] = hint
    return request


def default_shared_outcome_scope_cases() -> list[SharedOutcomeScopeCase]:
    cases: list[SharedOutcomeScopeCase] = []
    for asset_type in ("image", "video", "file", "speech"):
        for topology in ("top_level", "forward"):
            cases.append(
                SharedOutcomeScopeCase(
                    name=f"{asset_type}_{topology}_file_name_only",
                    asset_type=asset_type,
                    topology=topology,
                    identity_mode="file_name_only",
                    expected_same_key=not (
                        topology == "forward" and asset_type in {"video", "file", "speech"}
                    ),
                )
            )
            for identity_mode in ("md5", "file_id", "source_leaf"):
                cases.append(
                    SharedOutcomeScopeCase(
                        name=f"{asset_type}_{topology}_{identity_mode}",
                        asset_type=asset_type,
                        topology=topology,
                        identity_mode=identity_mode,
                        expected_same_key=True,
                    )
                )
            cases.append(
                SharedOutcomeScopeCase(
                    name=f"{asset_type}_{topology}_remote_url_same",
                    asset_type=asset_type,
                    topology=topology,
                    identity_mode="remote_url_same",
                    expected_same_key=True,
                )
            )
            cases.append(
                SharedOutcomeScopeCase(
                    name=f"{asset_type}_{topology}_none",
                    asset_type=asset_type,
                    topology=topology,
                    identity_mode="none",
                    expected_same_key=False,
                )
            )
    return cases


def run_shared_outcome_scope_case(
    case: SharedOutcomeScopeCase,
) -> SharedOutcomeScopeResult:
    downloader = NapCatMediaDownloader(_DummyClient())
    try:
        request_a = _scope_request(
            asset_type=case.asset_type,
            topology=case.topology,
            identity_mode=case.identity_mode,
            variant="a",
        )
        request_b = _scope_request(
            asset_type=case.asset_type,
            topology=case.topology,
            identity_mode=case.identity_mode,
            variant="b",
        )
        if case.identity_mode == "remote_url_same":
            request_a = _scope_request(
                asset_type=case.asset_type,
                topology=case.topology,
                identity_mode="remote_url_same",
                variant="a",
            )
            request_b = _scope_request(
                asset_type=case.asset_type,
                topology=case.topology,
                identity_mode="remote_url_same",
                variant="b",
            )
        key_a = downloader._shared_request_key(request_a)
        key_b = downloader._shared_request_key(request_b)
        actual_same_key = bool(key_a and key_b and key_a == key_b)
        return SharedOutcomeScopeResult(
            name=case.name,
            asset_type=case.asset_type,
            topology=case.topology,
            identity_mode=case.identity_mode,
            expected_same_key=case.expected_same_key,
            actual_same_key=actual_same_key,
            matched=actual_same_key == case.expected_same_key,
            key_a=key_a,
            key_b=key_b,
        )
    finally:
        downloader.close()


def run_shared_outcome_scope_matrix() -> list[SharedOutcomeScopeResult]:
    return [
        run_shared_outcome_scope_case(case)
        for case in default_shared_outcome_scope_cases()
    ]


def summarize_shared_outcome_scope_results(
    results: list[SharedOutcomeScopeResult],
) -> dict[str, Any]:
    asset_type_counts: Counter[str] = Counter()
    topology_counts: Counter[str] = Counter()
    identity_mode_counts: Counter[str] = Counter()
    mismatches: list[str] = []
    for item in results:
        asset_type_counts[item.asset_type] += 1
        topology_counts[item.topology] += 1
        identity_mode_counts[item.identity_mode] += 1
        if not item.matched:
            mismatches.append(item.name)
    return {
        "total": len(results),
        "matched": len(results) - len(mismatches),
        "mismatched": len(mismatches),
        "asset_type_counts": dict(asset_type_counts),
        "topology_counts": dict(topology_counts),
        "identity_mode_counts": dict(identity_mode_counts),
        "mismatch_names": mismatches,
    }


def _timeout_scope_request(
    *,
    asset_type: str,
    parent_id: str,
    token: str,
    file_name: str,
    md5: str,
    file_id: str,
    forward: bool = True,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "asset_type": asset_type,
        "asset_role": "forward_media",
        "file_name": file_name,
        "md5": md5,
        "download_hint": {
            "file_id": file_id,
        },
    }
    if forward:
        request["download_hint"]["_forward_parent"] = {
            "message_id_raw": parent_id,
            "element_id": f"element:{parent_id}",
            "peer_uid": "u-timeout-scope",
            "chat_type_raw": "2",
        }
    request["download_hint"]["public_file_token"] = token
    return request


def default_public_timeout_scope_cases() -> list[PublicTimeoutScopeCase]:
    cases: list[PublicTimeoutScopeCase] = []
    for asset_type in ("video", "file", "speech"):
        cases.extend(
            [
                PublicTimeoutScopeCase(
                    name=f"{asset_type}_same_parent_same_token_same_request",
                    asset_type=asset_type,
                    relationship="same_parent_same_token_same_request",
                    expected_same_key=True,
                ),
                PublicTimeoutScopeCase(
                    name=f"{asset_type}_same_parent_new_token",
                    asset_type=asset_type,
                    relationship="same_parent_new_token",
                    expected_same_key=False,
                ),
                PublicTimeoutScopeCase(
                    name=f"{asset_type}_same_parent_same_token_new_file",
                    asset_type=asset_type,
                    relationship="same_parent_same_token_new_file",
                    expected_same_key=False,
                ),
                PublicTimeoutScopeCase(
                    name=f"{asset_type}_different_parent_same_token",
                    asset_type=asset_type,
                    relationship="different_parent_same_token",
                    expected_same_key=False,
                ),
                PublicTimeoutScopeCase(
                    name=f"{asset_type}_non_forward_ignored",
                    asset_type=asset_type,
                    relationship="non_forward_ignored",
                    expected_same_key=False,
                ),
            ]
        )
    cases.append(
        PublicTimeoutScopeCase(
            name="image_ignored_even_with_forward_parent",
            asset_type="image",
            relationship="image_ignored_even_with_forward_parent",
            expected_same_key=False,
        )
    )
    return cases


def run_public_timeout_scope_case(
    case: PublicTimeoutScopeCase,
) -> PublicTimeoutScopeResult:
    action = "get_record" if case.asset_type == "speech" else "get_file"
    request_a = _timeout_scope_request(
        asset_type=case.asset_type,
        parent_id="parent-a",
        token="token-a",
        file_name=f"{case.asset_type}-a.bin",
        md5=f"{case.asset_type}-md5-a",
        file_id=f"/scope/{case.asset_type}/a",
        forward=True,
    )
    request_b = _timeout_scope_request(
        asset_type=case.asset_type,
        parent_id="parent-a",
        token="token-a",
        file_name=f"{case.asset_type}-a.bin",
        md5=f"{case.asset_type}-md5-a",
        file_id=f"/scope/{case.asset_type}/a",
        forward=True,
    )
    if case.relationship == "same_parent_new_token":
        request_b["download_hint"]["public_file_token"] = "token-b"
    elif case.relationship == "same_parent_same_token_new_file":
        request_b["file_name"] = f"{case.asset_type}-b.bin"
        request_b["md5"] = f"{case.asset_type}-md5-b"
        request_b["download_hint"]["file_id"] = f"/scope/{case.asset_type}/b"
    elif case.relationship == "different_parent_same_token":
        request_b["download_hint"]["_forward_parent"]["message_id_raw"] = "parent-b"
        request_b["download_hint"]["_forward_parent"]["element_id"] = "element:parent-b"
    elif case.relationship == "non_forward_ignored":
        request_a = _timeout_scope_request(
            asset_type=case.asset_type,
            parent_id="parent-a",
            token="token-a",
            file_name=f"{case.asset_type}-a.bin",
            md5=f"{case.asset_type}-md5-a",
            file_id=f"/scope/{case.asset_type}/a",
            forward=False,
        )
        request_b = dict(request_a)
    elif case.relationship == "image_ignored_even_with_forward_parent":
        action = "get_file"
    key_a = NapCatMediaDownloader._request_scoped_public_action_timeout_key(
        request_a,
        action=action,
        token=str(request_a.get("download_hint", {}).get("public_file_token") or "").strip(),
    )
    key_b = NapCatMediaDownloader._request_scoped_public_action_timeout_key(
        request_b,
        action=action,
        token=str(request_b.get("download_hint", {}).get("public_file_token") or "").strip(),
    )
    actual_same_key = bool(key_a and key_b and key_a == key_b)
    return PublicTimeoutScopeResult(
        name=case.name,
        asset_type=case.asset_type,
        relationship=case.relationship,
        expected_same_key=case.expected_same_key,
        actual_same_key=actual_same_key,
        matched=actual_same_key == case.expected_same_key,
        key_a=key_a,
        key_b=key_b,
    )


def run_public_timeout_scope_matrix() -> list[PublicTimeoutScopeResult]:
    return [
        run_public_timeout_scope_case(case)
        for case in default_public_timeout_scope_cases()
    ]


def summarize_public_timeout_scope_results(
    results: list[PublicTimeoutScopeResult],
) -> dict[str, Any]:
    asset_type_counts: Counter[str] = Counter()
    relationship_counts: Counter[str] = Counter()
    mismatches: list[str] = []
    for item in results:
        asset_type_counts[item.asset_type] += 1
        relationship_counts[item.relationship] += 1
        if not item.matched:
            mismatches.append(item.name)
    return {
        "total": len(results),
        "matched": len(results) - len(mismatches),
        "mismatched": len(mismatches),
        "asset_type_counts": dict(asset_type_counts),
        "relationship_counts": dict(relationship_counts),
        "mismatch_names": mismatches,
    }


def _retarget_simulation_clients(
    downloader: "_ScenarioAwareDownloader",
    client: "_ScenarioPublicClient",
    fast_client: "_ScenarioFastClient",
    runtime: "_ScenarioRuntimeState",
    scenario: "AssetResolutionScenario",
) -> None:
    downloader._scenario_state = runtime
    client._scenario = scenario
    client._state = runtime
    fast_client._scenario = scenario
    fast_client._state = runtime


def default_asset_resolution_pair_cases() -> list[AssetResolutionPairCase]:
    scenarios = {item.name: item for item in all_asset_resolution_scenarios()}
    cases: list[AssetResolutionPairCase] = []

    shared_image_name = "pair_top_level_image_shared_identity"
    cases.append(
        AssetResolutionPairCase(
            name="top_level_image_placeholder_then_public_remote",
            first=replace(
                scenarios["top_level_image_placeholder_zero_byte"],
                name=shared_image_name,
                age_days=240,
            ),
            second=replace(
                scenarios["top_level_image_public_token_remote"],
                name=shared_image_name,
                age_days=20,
            ),
            expected_second_resolver="napcat_public_token_get_image_remote_url",
            expected_second_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=1,
            notes="Old placeholder image missing must not poison later recoverable public-token remote recovery for the same logical asset identity.",
        )
    )

    shared_video_name = "pair_top_level_video_shared_identity"
    cases.append(
        AssetResolutionPairCase(
            name="top_level_video_old_timeout_then_direct_remote",
            first=AssetResolutionScenario(
                name=shared_video_name,
                suite="pair_sequence",
                asset_type="video",
                topology="top_level",
                age_days=240,
                context_payload_state="timeout",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=1,
                max_remote_attempts=0,
                notes="Synthetic old top-level video timeout miss for cross-scenario cache poisoning checks.",
            ),
            second=replace(
                scenarios["top_level_video_context_timeout_direct_file_id_remote"],
                name=shared_video_name,
                age_days=20,
            ),
            expected_second_resolver="napcat_segment_file_id_get_file_remote_url",
            expected_second_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=2,
            max_remote_attempts=1,
            notes="Old unresolved top-level video timeout miss must not poison later direct-file-id remote recovery for the same logical asset identity.",
        )
    )

    shared_file_name = "pair_top_level_file_shared_identity"
    cases.append(
        AssetResolutionPairCase(
            name="top_level_file_old_timeout_then_direct_remote",
            first=AssetResolutionScenario(
                name=shared_file_name,
                suite="pair_sequence",
                asset_type="file",
                topology="top_level",
                age_days=240,
                context_payload_state="timeout",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=1,
                max_remote_attempts=0,
                notes="Synthetic old top-level file timeout miss for cross-scenario cache poisoning checks.",
            ),
            second=AssetResolutionScenario(
                name=shared_file_name,
                suite="pair_sequence",
                asset_type="file",
                topology="top_level",
                age_days=20,
                context_payload_state="unavailable",
                direct_file_result_state="valid_remote",
                expected_resolver="napcat_segment_file_id_get_file_remote_url",
                expected_path_kind="remote",
                max_client_calls=1,
                max_fast_calls=1,
                max_remote_attempts=1,
                notes="Same logical asset identity later becomes recoverable through direct-file-id remote path.",
            ),
            expected_second_resolver="napcat_segment_file_id_get_file_remote_url",
            expected_second_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=2,
            max_remote_attempts=1,
            notes="Top-level file timeout miss must not poison later remote direct-file-id recovery.",
        )
    )

    shared_speech_name = "pair_top_level_speech_shared_identity"
    cases.append(
        AssetResolutionPairCase(
            name="top_level_speech_old_timeout_then_public_remote",
            first=AssetResolutionScenario(
                name=shared_speech_name,
                suite="pair_sequence",
                asset_type="speech",
                topology="top_level",
                age_days=240,
                context_payload_state="timeout",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=1,
                max_remote_attempts=0,
            ),
            second=replace(
                scenarios["top_level_speech_public_token_remote"],
                name=shared_speech_name,
                age_days=20,
            ),
            expected_second_resolver="napcat_public_token_get_record_remote_url",
            expected_second_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=2,
            max_remote_attempts=1,
            notes="Old unresolved top-level speech timeout miss must not poison later public-token remote recovery.",
        )
    )

    shared_forward_name = "pair_forward_video_identity"
    cases.append(
        AssetResolutionPairCase(
            name="forward_old_public_timeout_then_recent_remote",
            first=replace(
                scenarios["forward_old_video_public_token_timeout"],
                name=shared_forward_name,
            ),
            second=AssetResolutionScenario(
                name=shared_forward_name,
                suite="pair_sequence",
                asset_type="video",
                topology="forward",
                age_days=20,
                source_path_state="stale_missing",
                hint_remote_state="live_http",
                forward_payload_state="remote_url",
                expected_resolver="napcat_forward_remote_url",
                expected_path_kind="remote",
                max_client_calls=0,
                max_fast_calls=0,
                max_remote_attempts=1,
                notes="Recent forward remote recovery should not be poisoned by a prior old forward public-token timeout under the same logical asset identity.",
            ),
            expected_second_resolver="napcat_forward_remote_url",
            expected_second_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=1,
        )
    )

    return cases


def run_asset_resolution_pair_case(
    case: AssetResolutionPairCase,
    *,
    trace_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AssetResolutionPairResult:
    runtime_first = _ScenarioRuntimeState(case.first)
    runtime_second: _ScenarioRuntimeState | None = None
    events: list[dict[str, Any]] = []
    client = _ScenarioPublicClient(case.first, runtime_first)
    fast_client = _ScenarioFastClient(case.first, runtime_first)
    downloader = _ScenarioAwareDownloader(client, fast_client=fast_client, state=runtime_first)
    try:
        first_result = downloader.resolve_for_export(
            copy.deepcopy(runtime_first.request),
            trace_callback=(
                (lambda event: (events.append(dict(event)), trace_callback and trace_callback(dict(event))))
                if trace_callback is not None
                else events.append
            ),
        )
        first_path_kind, _ = _path_kind_for_result(first_result, runtime_first)

        runtime_second = _ScenarioRuntimeState(case.second)
        _retarget_simulation_clients(
            downloader,
            client,
            fast_client,
            runtime_second,
            case.second,
        )
        second_result = downloader.resolve_for_export(
            copy.deepcopy(runtime_second.request),
            trace_callback=(
                (lambda event: (events.append(dict(event)), trace_callback and trace_callback(dict(event))))
                if trace_callback is not None
                else events.append
            ),
        )
        second_path_kind, _ = _path_kind_for_result(second_result, runtime_second)
        cost_matched = True
        if case.max_client_calls is not None and len(client.calls) > case.max_client_calls:
            cost_matched = False
        if case.max_fast_calls is not None and len(fast_client.calls) > case.max_fast_calls:
            cost_matched = False
        total_remote_attempts = len(runtime_first.remote_attempts) + len(runtime_second.remote_attempts)
        if case.max_remote_attempts is not None and total_remote_attempts > case.max_remote_attempts:
            cost_matched = False
        matched = (
            second_result[1] == case.expected_second_resolver
            and second_path_kind == case.expected_second_path_kind
            and cost_matched
        )
        trace_status_breakdown: dict[str, int] = {}
        for event in events:
            if str(event.get("phase") or "").strip() != "materialize_asset_substep":
                continue
            status = str(event.get("status") or "").strip()
            if not status:
                continue
            trace_status_breakdown[status] = trace_status_breakdown.get(status, 0) + 1
        return AssetResolutionPairResult(
            name=case.name,
            first_name=case.first.name,
            second_name=case.second.name,
            expected_second_resolver=case.expected_second_resolver,
            expected_second_path_kind=case.expected_second_path_kind,
            actual_first_resolver=first_result[1],
            actual_first_path_kind=first_path_kind,
            actual_second_resolver=second_result[1],
            actual_second_path_kind=second_path_kind,
            matched=matched,
            client_call_count=len(client.calls),
            fast_call_count=len(fast_client.calls),
            remote_attempt_count=total_remote_attempts,
            trace_event_count=len(events),
            trace_status_breakdown=trace_status_breakdown,
            cost_matched=cost_matched,
            notes=case.notes,
        )
    finally:
        downloader.close()
        runtime_first.close()
        if runtime_second is not None:
            runtime_second.close()


def run_asset_resolution_pair_matrix() -> list[AssetResolutionPairResult]:
    return [
        run_asset_resolution_pair_case(case)
        for case in default_asset_resolution_pair_cases()
    ]


def summarize_asset_resolution_pair_results(
    results: list[AssetResolutionPairResult],
) -> dict[str, Any]:
    mismatches = [item.name for item in results if not item.matched]
    resolver_counts: Counter[str] = Counter(
        str(item.actual_second_resolver or "<none>") for item in results
    )
    path_kind_counts: Counter[str] = Counter(item.actual_second_path_kind for item in results)
    return {
        "total": len(results),
        "matched": len(results) - len(mismatches),
        "mismatched": len(mismatches),
        "resolver_counts": dict(resolver_counts),
        "path_kind_counts": dict(path_kind_counts),
        "mismatch_names": mismatches,
    }


def default_cross_run_reset_cases() -> list[AssetResolutionPairCase]:
    return [
        replace(
            case,
            name=f"cross_run_reset_{case.name}",
            notes=(
                f"{case.notes} The second step runs after reset_export_state() to prove per-run caches "
                "and breakers do not poison the next run."
            ).strip(),
        )
        for case in default_asset_resolution_pair_cases()
    ]


def run_cross_run_reset_case(
    case: AssetResolutionPairCase,
    *,
    trace_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AssetResolutionPairResult:
    runtime_first = _ScenarioRuntimeState(case.first)
    runtime_second: _ScenarioRuntimeState | None = None
    events: list[dict[str, Any]] = []
    client = _ScenarioPublicClient(case.first, runtime_first)
    fast_client = _ScenarioFastClient(case.first, runtime_first)
    downloader = _ScenarioAwareDownloader(client, fast_client=fast_client, state=runtime_first)
    try:
        first_result = downloader.resolve_for_export(
            copy.deepcopy(runtime_first.request),
            trace_callback=(
                (lambda event: (events.append(dict(event)), trace_callback and trace_callback(dict(event))))
                if trace_callback is not None
                else events.append
            ),
        )
        first_path_kind, _ = _path_kind_for_result(first_result, runtime_first)

        downloader.reset_export_state()

        runtime_second = _ScenarioRuntimeState(case.second)
        _retarget_simulation_clients(
            downloader,
            client,
            fast_client,
            runtime_second,
            case.second,
        )
        second_result = downloader.resolve_for_export(
            copy.deepcopy(runtime_second.request),
            trace_callback=(
                (lambda event: (events.append(dict(event)), trace_callback and trace_callback(dict(event))))
                if trace_callback is not None
                else events.append
            ),
        )
        second_path_kind, _ = _path_kind_for_result(second_result, runtime_second)
        cost_matched = True
        if case.max_client_calls is not None and len(client.calls) > case.max_client_calls:
            cost_matched = False
        if case.max_fast_calls is not None and len(fast_client.calls) > case.max_fast_calls:
            cost_matched = False
        total_remote_attempts = len(runtime_first.remote_attempts) + len(runtime_second.remote_attempts)
        if case.max_remote_attempts is not None and total_remote_attempts > case.max_remote_attempts:
            cost_matched = False
        matched = (
            second_result[1] == case.expected_second_resolver
            and second_path_kind == case.expected_second_path_kind
            and cost_matched
        )
        trace_status_breakdown: dict[str, int] = {}
        for event in events:
            if str(event.get("phase") or "").strip() != "materialize_asset_substep":
                continue
            status = str(event.get("status") or "").strip()
            if not status:
                continue
            trace_status_breakdown[status] = trace_status_breakdown.get(status, 0) + 1
        return AssetResolutionPairResult(
            name=case.name,
            first_name=case.first.name,
            second_name=case.second.name,
            expected_second_resolver=case.expected_second_resolver,
            expected_second_path_kind=case.expected_second_path_kind,
            actual_first_resolver=first_result[1],
            actual_first_path_kind=first_path_kind,
            actual_second_resolver=second_result[1],
            actual_second_path_kind=second_path_kind,
            matched=matched,
            client_call_count=len(client.calls),
            fast_call_count=len(fast_client.calls),
            remote_attempt_count=total_remote_attempts,
            trace_event_count=len(events),
            trace_status_breakdown=trace_status_breakdown,
            cost_matched=cost_matched,
            notes=case.notes,
        )
    finally:
        downloader.close()
        runtime_first.close()
        if runtime_second is not None:
            runtime_second.close()


def run_cross_run_reset_matrix() -> list[AssetResolutionPairResult]:
    return [
        run_cross_run_reset_case(case)
        for case in default_cross_run_reset_cases()
    ]


def summarize_cross_run_reset_results(
    results: list[AssetResolutionPairResult],
) -> dict[str, Any]:
    return summarize_asset_resolution_pair_results(results)


def default_direct_file_id_scope_cases() -> list[DirectFileIdScopeCase]:
    cases: list[DirectFileIdScopeCase] = []
    for asset_type in ("video", "file", "speech"):
        cases.extend(
            [
                DirectFileIdScopeCase(
                    name=f"{asset_type}_same_parent_same_file_id",
                    asset_type=asset_type,
                    relationship="same_parent_same_file_id",
                    expected_same_key=True,
                ),
                DirectFileIdScopeCase(
                    name=f"{asset_type}_same_parent_different_file_id",
                    asset_type=asset_type,
                    relationship="same_parent_different_file_id",
                    expected_same_key=False,
                ),
                DirectFileIdScopeCase(
                    name=f"{asset_type}_same_parent_same_file_id_different_remote",
                    asset_type=asset_type,
                    relationship="same_parent_same_file_id_different_remote",
                    expected_same_key=False,
                ),
                DirectFileIdScopeCase(
                    name=f"{asset_type}_different_parent_same_file_id",
                    asset_type=asset_type,
                    relationship="different_parent_same_file_id",
                    expected_same_key=False,
                ),
            ]
        )
    return cases


def run_direct_file_id_scope_case(
    case: DirectFileIdScopeCase,
) -> DirectFileIdScopeResult:
    request_a = _timeout_scope_request(
        asset_type=case.asset_type,
        parent_id="parent-a",
        token="unused-token-a",
        file_name=f"{case.asset_type}-a.bin",
        md5=f"{case.asset_type}-md5-a",
        file_id=f"/scope/{case.asset_type}/a",
        forward=True,
    )
    request_b = copy.deepcopy(request_a)
    if case.relationship == "same_parent_different_file_id":
        request_b["download_hint"]["file_id"] = f"/scope/{case.asset_type}/b"
    elif case.relationship == "same_parent_same_file_id_different_remote":
        request_a["download_hint"]["remote_url"] = f"https://assets.example.invalid/{case.asset_type}/a.bin"
        request_b["download_hint"]["remote_url"] = f"https://assets.example.invalid/{case.asset_type}/b.bin"
    elif case.relationship == "different_parent_same_file_id":
        request_b["download_hint"]["_forward_parent"]["message_id_raw"] = "parent-b"
        request_b["download_hint"]["_forward_parent"]["element_id"] = "element:parent-b"
    key_a = NapCatMediaDownloader._request_key(request_a)
    key_b = NapCatMediaDownloader._request_key(request_b)
    actual_same_key = key_a == key_b
    return DirectFileIdScopeResult(
        name=case.name,
        asset_type=case.asset_type,
        relationship=case.relationship,
        expected_same_key=case.expected_same_key,
        actual_same_key=actual_same_key,
        matched=actual_same_key == case.expected_same_key,
        key_a=key_a,
        key_b=key_b,
    )


def run_direct_file_id_scope_matrix() -> list[DirectFileIdScopeResult]:
    return [
        run_direct_file_id_scope_case(case)
        for case in default_direct_file_id_scope_cases()
    ]


def summarize_direct_file_id_scope_results(
    results: list[DirectFileIdScopeResult],
) -> dict[str, Any]:
    asset_type_counts: Counter[str] = Counter()
    relationship_counts: Counter[str] = Counter()
    mismatches: list[str] = []
    for item in results:
        asset_type_counts[item.asset_type] += 1
        relationship_counts[item.relationship] += 1
        if not item.matched:
            mismatches.append(item.name)
    return {
        "total": len(results),
        "matched": len(results) - len(mismatches),
        "mismatched": len(mismatches),
        "asset_type_counts": dict(asset_type_counts),
        "relationship_counts": dict(relationship_counts),
        "mismatch_names": mismatches,
    }


def write_simulation_trace(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


@dataclass(frozen=True, slots=True)
class AssetResolutionScenario:
    name: str
    asset_type: str
    suite: str = "core"
    topology: str = "top_level"
    age_days: int = 7
    asset_role: str | None = None
    forward_parent_state: str = "valid"
    source_path_state: str = "none"
    hint_local_state: str = "none"
    hint_remote_state: str = "none"
    context_payload_state: str = "none"
    forward_payload_state: str = "none"
    forward_metadata_state: str = "inherit"
    forward_materialize_state: str = "inherit"
    public_result_state: str = "none"
    public_fallback_result_state: str = "inherit"
    direct_file_result_state: str = "none"
    expected_resolver: str | None = None
    expected_path_kind: str = "missing"
    max_client_calls: int | None = None
    max_fast_calls: int | None = None
    max_remote_attempts: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssetResolutionResult:
    name: str
    suite: str
    asset_type: str
    topology: str
    age_days: int
    expected_resolver: str | None
    actual_resolver: str | None
    expected_path_kind: str
    actual_path_kind: str
    matched: bool
    resolved_path: str | None
    client_call_count: int
    fast_call_count: int
    remote_attempt_count: int
    trace_event_count: int
    trace_status_breakdown: dict[str, int]
    cost_matched: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssetResolutionSequenceResult:
    name: str
    suite: str
    repeats: int
    expected_resolver: str | None
    expected_path_kind: str
    actual_resolver: str | None
    actual_path_kind: str
    matched: bool
    unique_resolvers: tuple[str | None, ...]
    unique_path_kinds: tuple[str, ...]
    client_call_count: int
    fast_call_count: int
    remote_attempt_count: int
    trace_event_count: int
    trace_status_breakdown: dict[str, int]
    cost_matched: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssetResolutionPairCase:
    name: str
    first: AssetResolutionScenario
    second: AssetResolutionScenario
    expected_second_resolver: str | None
    expected_second_path_kind: str
    max_client_calls: int | None = None
    max_fast_calls: int | None = None
    max_remote_attempts: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "expected_second_resolver": self.expected_second_resolver,
            "expected_second_path_kind": self.expected_second_path_kind,
            "max_client_calls": self.max_client_calls,
            "max_fast_calls": self.max_fast_calls,
            "max_remote_attempts": self.max_remote_attempts,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class AssetResolutionPairResult:
    name: str
    first_name: str
    second_name: str
    expected_second_resolver: str | None
    expected_second_path_kind: str
    actual_first_resolver: str | None
    actual_first_path_kind: str
    actual_second_resolver: str | None
    actual_second_path_kind: str
    matched: bool
    client_call_count: int
    fast_call_count: int
    remote_attempt_count: int
    trace_event_count: int
    trace_status_breakdown: dict[str, int]
    cost_matched: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DirectFileIdScopeCase:
    name: str
    asset_type: str
    relationship: str
    expected_same_key: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DirectFileIdScopeResult:
    name: str
    asset_type: str
    relationship: str
    expected_same_key: bool
    actual_same_key: bool
    matched: bool
    key_a: tuple[Any, ...] | None
    key_b: tuple[Any, ...] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_asset_resolution_results(
    results: list[AssetResolutionResult],
) -> dict[str, Any]:
    suite_counts: Counter[str] = Counter()
    asset_counts: Counter[str] = Counter()
    topology_counts: Counter[str] = Counter()
    age_bucket_counts: Counter[str] = Counter()
    resolver_counts: Counter[str] = Counter()
    path_kind_counts: Counter[str] = Counter()
    trace_totals: Counter[str] = Counter()
    call_cost_totals: dict[str, dict[str, float]] = {}
    terminal_missing_quality: dict[str, int] = {
        "classified_missing_count": 0,
        "unresolved_missing_count": 0,
        "resolver_none_and_missing_count": 0,
    }
    cost_vs_result_cross_tab: Counter[str] = Counter()
    mismatches: list[str] = []
    cost_overruns: list[str] = []

    def _bump_cost_totals(key: str, item: AssetResolutionResult) -> None:
        bucket = call_cost_totals.setdefault(
            key,
            {
                "cases": 0.0,
                "public_calls_total": 0.0,
                "fast_calls_total": 0.0,
                "remote_attempts_total": 0.0,
                "max_public_calls": 0.0,
                "max_fast_calls": 0.0,
                "max_remote_attempts": 0.0,
            },
        )
        bucket["cases"] += 1.0
        bucket["public_calls_total"] += float(item.client_call_count)
        bucket["fast_calls_total"] += float(item.fast_call_count)
        bucket["remote_attempts_total"] += float(item.remote_attempt_count)
        bucket["max_public_calls"] = max(bucket["max_public_calls"], float(item.client_call_count))
        bucket["max_fast_calls"] = max(bucket["max_fast_calls"], float(item.fast_call_count))
        bucket["max_remote_attempts"] = max(bucket["max_remote_attempts"], float(item.remote_attempt_count))

    for item in results:
        suite_counts[item.suite] += 1
        asset_counts[item.asset_type] += 1
        topology_counts[item.topology] += 1
        age_bucket = _age_bucket_label(item.age_days)
        age_bucket_counts[age_bucket] += 1
        resolver_counts[str(item.actual_resolver or "<none>")] += 1
        path_kind_counts[item.actual_path_kind] += 1
        if not item.matched:
            mismatches.append(item.name)
        if not item.cost_matched:
            cost_overruns.append(item.name)
        if item.actual_path_kind == "missing":
            if item.actual_resolver is None:
                terminal_missing_quality["resolver_none_and_missing_count"] += 1
                terminal_missing_quality["unresolved_missing_count"] += 1
            else:
                terminal_missing_quality["classified_missing_count"] += 1
        cross_tab_key = (
            "matched_and_cheap"
            if item.matched and item.cost_matched
            else "matched_but_expensive"
            if item.matched and not item.cost_matched
            else "mismatched_and_cheap"
            if (not item.matched and item.cost_matched)
            else "mismatched_and_expensive"
        )
        cost_vs_result_cross_tab[cross_tab_key] += 1
        _bump_cost_totals(f"suite:{item.suite}", item)
        _bump_cost_totals(f"asset_type:{item.asset_type}", item)
        _bump_cost_totals(f"topology:{item.topology}", item)
        _bump_cost_totals(f"age_bucket:{age_bucket}", item)
        for status, count in item.trace_status_breakdown.items():
            trace_totals[status] += int(count)
    normalized_call_cost_totals: dict[str, dict[str, float]] = {}
    for key, raw in call_cost_totals.items():
        cases = max(1.0, raw["cases"])
        normalized_call_cost_totals[key] = {
            "cases": int(raw["cases"]),
            "public_calls_total": int(raw["public_calls_total"]),
            "fast_calls_total": int(raw["fast_calls_total"]),
            "remote_attempts_total": int(raw["remote_attempts_total"]),
            "avg_public_calls_per_case": round(raw["public_calls_total"] / cases, 3),
            "avg_fast_calls_per_case": round(raw["fast_calls_total"] / cases, 3),
            "avg_remote_attempts_per_case": round(raw["remote_attempts_total"] / cases, 3),
            "max_public_calls": int(raw["max_public_calls"]),
            "max_fast_calls": int(raw["max_fast_calls"]),
            "max_remote_attempts": int(raw["max_remote_attempts"]),
        }
    return {
        "total": len(results),
        "matched": len(results) - len(mismatches),
        "mismatched": len(mismatches),
        "cost_overruns": len(cost_overruns),
        "suite_counts": dict(suite_counts),
        "asset_type_counts": dict(asset_counts),
        "topology_counts": dict(topology_counts),
        "age_bucket_counts": dict(age_bucket_counts),
        "resolver_counts": dict(resolver_counts),
        "path_kind_counts": dict(path_kind_counts),
        "trace_status_totals": dict(trace_totals),
        "call_cost_totals": normalized_call_cost_totals,
        "terminal_missing_quality": terminal_missing_quality,
        "cost_vs_result_cross_tab": dict(cost_vs_result_cross_tab),
        "mismatch_names": mismatches,
        "cost_overrun_names": cost_overruns,
    }


def summarize_asset_resolution_catalog(
    scenarios: list["AssetResolutionScenario"] | None = None,
) -> dict[str, Any]:
    active = list(all_asset_resolution_scenarios() if scenarios is None else scenarios)
    suite_counts: Counter[str] = Counter()
    asset_counts: Counter[str] = Counter()
    topology_counts: Counter[str] = Counter()
    age_bucket_counts: Counter[str] = Counter()
    asset_role_counts: Counter[str] = Counter()
    terminality_flags: Counter[str] = Counter()
    route_signal_flags: Counter[str] = Counter()
    shared_cache_risk_flags: Counter[str] = Counter()
    payload_shape_counts: dict[str, Counter[str]] = {
        "hint_remote_state": Counter(),
        "context_payload_state": Counter(),
        "forward_payload_state": Counter(),
        "public_result_state": Counter(),
        "public_fallback_result_state": Counter(),
        "direct_file_result_state": Counter(),
    }
    state_field_names = (
        "forward_parent_state",
        "source_path_state",
        "hint_local_state",
        "hint_remote_state",
        "context_payload_state",
        "forward_payload_state",
        "forward_metadata_state",
        "forward_materialize_state",
        "public_result_state",
        "public_fallback_result_state",
        "direct_file_result_state",
    )
    state_field_counts: dict[str, Counter[str]] = {
        field_name: Counter() for field_name in state_field_names
    }
    for item in active:
        suite_counts[item.suite] += 1
        asset_counts[item.asset_type] += 1
        topology_counts[item.topology] += 1
        age_bucket = _age_bucket_label(item.age_days)
        age_bucket_counts[age_bucket] += 1
        asset_role_counts[str(item.asset_role or "<none>")] += 1
        if item.expected_path_kind == "missing" and item.expected_resolver is not None:
            terminality_flags["expected_terminal_missing"] += 1
        elif item.expected_path_kind == "missing":
            terminality_flags["expected_unresolved"] += 1
        elif item.expected_path_kind == "remote":
            terminality_flags["expected_recoverable_remote"] += 1
        elif item.expected_path_kind == "local":
            terminality_flags["expected_recoverable_local"] += 1
        if item.topology in {"forward", "nested_forward", "forward_missing_parent"}:
            route_signal_flags["has_forward_parent"] += 1
        if item.hint_local_state in {"path_existing", "file_existing", "path_zero", "file_zero"}:
            route_signal_flags["has_hint_local_path"] += 1
        if item.source_path_state in {"existing", "existing_zero", "stale_missing", "placeholder_zero"}:
            route_signal_flags["has_source_path"] += 1
        if item.hint_remote_state in {"live_http", "relative_http", "stale_http"}:
            route_signal_flags["has_hint_remote_url"] += 1
        if item.public_result_state != "none" or item.public_fallback_result_state not in {"", "inherit"}:
            route_signal_flags["has_public_token_shape"] += 1
        if item.direct_file_result_state != "none" or item.forward_metadata_state == "payload_file_id_only":
            route_signal_flags["has_direct_file_id_shape"] += 1
        if item.source_path_state in {"existing_zero", "placeholder_zero"} or item.hint_local_state in {"path_zero", "file_zero"}:
            route_signal_flags["has_zero_byte_local"] += 1
        if item.topology in {"forward", "nested_forward"} and item.asset_type in {"file", "video"}:
            shared_cache_risk_flags[f"{age_bucket}_forward_{item.asset_type}"] += 1
            if item.expected_path_kind == "missing":
                shared_cache_risk_flags["shared_miss_eligible_shape"] += 1
        for field_name in state_field_names:
            raw_value = getattr(item, field_name)
            normalized = str(raw_value or "<none>")
            state_field_counts[field_name][normalized] += 1
        for field_name in payload_shape_counts:
            raw_value = getattr(item, field_name)
            normalized = str(raw_value or "<none>")
            payload_shape_counts[field_name][normalized] += 1
    return {
        "total": len(active),
        "suite_counts": dict(suite_counts),
        "asset_type_counts": dict(asset_counts),
        "topology_counts": dict(topology_counts),
        "age_bucket_counts": dict(age_bucket_counts),
        "asset_role_counts": dict(asset_role_counts),
        "terminality_flags": dict(terminality_flags),
        "route_signal_flags": dict(route_signal_flags),
        "shared_cache_risk_flags": dict(shared_cache_risk_flags),
        "payload_shape_counts": {
            field_name: dict(counter) for field_name, counter in payload_shape_counts.items()
        },
        "state_field_counts": {
            field_name: dict(counter)
            for field_name, counter in state_field_counts.items()
        },
    }


def _asset_suffix(asset_type: str) -> str:
    return {
        "image": "jpg",
        "video": "mp4",
        "file": "bin",
        "speech": "mp3",
        "sticker": "gif",
    }.get(asset_type, "dat")


def _timestamp_ms_for_age_days(age_days: int) -> int:
    target = datetime.now(timezone.utc) - timedelta(days=max(0, int(age_days)))
    return int(target.timestamp() * 1000)


def _context_hint(seed: str) -> dict[str, str]:
    return {
        "message_id_raw": f"msg_{seed}",
        "element_id": f"el_{seed}",
        "peer_uid": f"peer_{seed}",
        "chat_type_raw": "2",
    }


class _ScenarioPublicClient:
    def __init__(self, scenario: AssetResolutionScenario, state: "_ScenarioRuntimeState") -> None:
        self._scenario = scenario
        self._state = state
        self.calls: list[dict[str, Any]] = []

    def get_image(self, *args, **kwargs):
        return self._dispatch("get_image", **kwargs)

    def get_file(self, *args, **kwargs):
        return self._dispatch("get_file", **kwargs)

    def get_record(self, *args, **kwargs):
        return self._dispatch("get_record", **kwargs)

    def _dispatch(self, action: str, **kwargs):
        self.calls.append(
            {
                "action": action,
                "file": kwargs.get("file"),
                "file_id": kwargs.get("file_id"),
                "timeout": kwargs.get("timeout"),
                "out_format": kwargs.get("out_format"),
            }
        )
        file_token = str(kwargs.get("file") or "").strip()
        file_id = str(kwargs.get("file_id") or "").strip()
        if file_id.startswith("/"):
            mode = self._scenario.direct_file_result_state
        elif file_id:
            fallback_mode = str(self._scenario.public_fallback_result_state or "").strip()
            mode = (
                self._scenario.public_result_state
                if fallback_mode in {"", "inherit"}
                else fallback_mode
            )
        else:
            mode = self._scenario.public_result_state
        return self._state.public_action_payload(
            scenario=self._scenario,
            action=action,
            mode=mode,
            token=file_token,
            file_id=file_id,
        )


class _ScenarioFastClient:
    def __init__(self, scenario: AssetResolutionScenario, state: "_ScenarioRuntimeState") -> None:
        self._scenario = scenario
        self._state = state
        self.calls: list[dict[str, Any]] = []

    def hydrate_media(self, **kwargs):
        self.calls.append({"method": "hydrate_media", **kwargs})
        return self._state.context_payload(self._scenario)

    def hydrate_forward_media(self, **kwargs):
        self.calls.append({"method": "hydrate_forward_media", **kwargs})
        return self._state.forward_payload(self._scenario, materialize=bool(kwargs.get("materialize")))


class _ScenarioAwareDownloader(NapCatMediaDownloader):
    def __init__(
        self,
        client: _ScenarioPublicClient,
        *,
        fast_client: _ScenarioFastClient | None,
        state: "_ScenarioRuntimeState",
    ) -> None:
        self._scenario_state = state
        super().__init__(
            client,
            fast_client=fast_client,
            remote_cache_dir=state.cache_root,
            remote_base_url=state.remote_base_url,
        )

    def _create_prefetch_executors(self) -> None:
        self._public_token_executor = None
        self._remote_loop = None
        self._remote_loop_thread = None
        self._remote_async_client = None
        self._remote_async_semaphore = None

    def _rebuild_prefetch_executors(self, *, wait: bool, recreate: bool) -> None:
        _ = wait, recreate
        return

    def _download_remote_media(
        self,
        *,
        asset_type: str,
        file_name: str | None,
        hint: dict[str, Any],
    ) -> str | None:
        remote_url = str(hint.get("url") or "").strip()
        resolved_remote_url = self._resolve_remote_url(remote_url)
        if not resolved_remote_url:
            return None
        self._scenario_state.remote_attempts.append(
            {
                "asset_type": asset_type,
                "file_name": file_name,
                "remote_url": resolved_remote_url,
            }
        )
        return self._scenario_state.remote_payload_path(resolved_remote_url)

    def _download_remote_sticker(
        self,
        hint: dict[str, Any],
        *,
        asset_role: str | None,
        file_name: str | None,
    ) -> str | None:
        _ = asset_role, file_name
        remote_url = str(hint.get("remote_url") or hint.get("url") or "").strip()
        resolved_remote_url = self._resolve_remote_url(remote_url)
        if not resolved_remote_url:
            return None
        self._scenario_state.remote_attempts.append(
            {
                "asset_type": "sticker",
                "file_name": file_name,
                "remote_url": resolved_remote_url,
            }
        )
        return self._scenario_state.remote_payload_path(resolved_remote_url)


class _ScenarioRuntimeState:
    def __init__(self, scenario: AssetResolutionScenario) -> None:
        self.scenario = scenario
        repo_root = Path(__file__).resolve().parents[3]
        temp_root = repo_root / ".tmp" / "asset_simulator"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.root = temp_root / (
            f"asset-sim-{int(time.time() * 1_000_000)}-{os.getpid()}-{abs(hash(scenario.name)) % 100000}"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_root = self.root / "cache"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.remote_root = self.root / "remote"
        self.remote_root.mkdir(parents=True, exist_ok=True)
        self.remote_base_url = "http://napcat.local/api"
        self.remote_map: dict[str, str] = {}
        self.kind_map: dict[str, str] = {}
        self.remote_attempts: list[dict[str, Any]] = []
        self.file_name = f"{scenario.name}.{_asset_suffix(scenario.asset_type)}"
        self.local_path = self._make_file("local", self.file_name, kind="local")
        self.zero_local_path = self._make_file("local_zero", self.file_name, kind="local_zero", zero=True)
        self.remote_path = self._make_file("remote", self.file_name, kind="remote")
        self.sticker_remote_path = self._make_file("remote_sticker", self.file_name, kind="remote")
        self.request = self._build_request()

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _make_file(self, folder: str, name: str, *, kind: str, zero: bool = False) -> str:
        target = self.root / folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"" if zero else f"{folder}:{name}".encode("utf-8"))
        self.kind_map[str(target.resolve())] = kind
        return str(target.resolve())

    def _build_request(self) -> dict[str, Any]:
        request: dict[str, Any] = {
            "asset_type": self.scenario.asset_type,
            "asset_role": self.scenario.asset_role or "",
            "file_name": self.file_name,
            "md5": f"{self.scenario.name[:16]:0<16}",
            "timestamp_ms": _timestamp_ms_for_age_days(self.scenario.age_days),
            "download_hint": {},
        }
        hint: dict[str, Any] = {}
        if self.scenario.topology == "top_level":
            hint.update(_context_hint(f"{self.scenario.name}_top"))
        elif self.scenario.topology in {"forward", "nested_forward", "forward_missing_parent"}:
            hint.update(_context_hint(f"{self.scenario.name}_asset"))
            hint["_forward_parent"] = _context_hint(f"{self.scenario.name}_parent")
        if self.scenario.topology in {"forward", "nested_forward", "forward_missing_parent"}:
            broken_parent = hint.get("_forward_parent") if isinstance(hint.get("_forward_parent"), dict) else {}
            parent_state = self.scenario.forward_parent_state
            if self.scenario.topology == "forward_missing_parent" and parent_state == "valid":
                parent_state = "missing_element_id"
            if parent_state == "missing_element_id":
                broken_parent["element_id"] = ""
            elif parent_state == "missing_message_id_raw":
                broken_parent["message_id_raw"] = ""
            elif parent_state == "missing_peer_uid":
                broken_parent["peer_uid"] = ""
            elif parent_state == "blank_parent_bundle":
                broken_parent.clear()
            elif parent_state != "valid":
                raise ValueError(f"unsupported forward_parent_state: {parent_state}")
            if broken_parent:
                hint["_forward_parent"] = broken_parent

        if self.scenario.hint_local_state == "path_existing":
            hint["path"] = self.local_path
        elif self.scenario.hint_local_state == "file_existing":
            hint["file"] = self.local_path
        elif self.scenario.hint_local_state == "path_zero":
            hint["path"] = self.zero_local_path
        elif self.scenario.hint_local_state == "file_zero":
            hint["file"] = self.zero_local_path
        elif self.scenario.hint_local_state == "stale_local_url":
            hint["url"] = str((self.root / "stale" / self.file_name).resolve())

        if self.scenario.hint_remote_state != "none":
            hint["remote_url"] = self._remote_url_for_state(self.scenario.hint_remote_state)
        if self.scenario.direct_file_result_state != "none":
            hint["file_id"] = f"/fileid/{self.scenario.name}"

        request["download_hint"] = hint
        source_path = self._source_path_for_state(self.scenario.source_path_state)
        if source_path:
            request["source_path"] = source_path
        return request

    def _source_path_for_state(self, state: str) -> str | None:
        if state == "none":
            return None
        if state == "stale_missing":
            target = self.root / "stale" / self.file_name
            return str(target.resolve())
        if state == "placeholder_zero":
            month_root = self.root / "Pic" / "2025-09"
            for folder in ("Ori", "OriTemp", "Thumb"):
                candidate = month_root / folder / self.file_name
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_bytes(b"")
            missing = month_root / "Ori" / self.file_name
            missing.unlink(missing_ok=True)
            return str(missing.resolve())
        if state == "existing":
            return self.local_path
        if state == "existing_zero":
            return self.zero_local_path
        raise ValueError(f"unsupported source_path_state: {state}")

    def _remote_url_for_state(self, state: str) -> str:
        if state == "live_http":
            url = f"https://assets.example.invalid/{self.scenario.name}/{self.file_name}"
            self.remote_map[url] = self.remote_path
            return url
        if state == "relative_http":
            relative = f"download/{self.scenario.name}/{self.file_name}"
            resolved = f"{self.remote_base_url.rstrip('/')}/{relative}"
            self.remote_map[resolved] = self.remote_path
            return relative
        if state == "stale_http":
            return f"https://assets.example.invalid/stale/{self.scenario.name}/{self.file_name}"
        raise ValueError(f"unsupported hint_remote_state: {state}")

    def remote_payload_path(self, resolved_remote_url: str) -> str | None:
        return self.remote_map.get(str(resolved_remote_url))

    def _public_payload(self, *, action: str, mode: str) -> dict[str, Any] | None:
        if mode == "none":
            return None
        if mode == "valid_local":
            return {"file": self.local_path, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if mode == "valid_zero_local":
            return {"file": self.zero_local_path, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if mode == "valid_remote":
            remote_url = f"https://cdn.example.invalid/{self.scenario.name}/{self.file_name}"
            self.remote_map[remote_url] = self.remote_path
            return {"url": remote_url, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if mode == "valid_remote_only":
            remote_url = f"https://cdn.example.invalid/{self.scenario.name}/{self.file_name}"
            self.remote_map[remote_url] = self.remote_path
            return {"remote_url": remote_url, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if mode == "blank_payload":
            return {
                "file": "",
                "url": "",
                "file_name": self.file_name,
                "file_size": "1024",
                "asset_type": self.scenario.asset_type,
            }
        if mode == "known_bad_video":
            raise NapCatApiError("获取视频url失败")
        if mode == "known_bad_file":
            raise NapCatApiError("获取文件url失败")
        if mode == "known_bad_record":
            raise NapCatApiError("获取音频url失败")
        if mode == "timeout":
            raise NapCatApiTimeoutError(f"NapCat action timed out: {action}")
        if mode == "not_found":
            raise NapCatApiError("file not found")
        if mode == "opaque_error":
            raise NapCatApiError("simulated opaque public action error")
        raise ValueError(f"unsupported public result state: {mode}")

    def public_action_payload(
        self,
        *,
        scenario: AssetResolutionScenario,
        action: str,
        mode: str,
        token: str,
        file_id: str,
    ) -> dict[str, Any] | None:
        _ = scenario, token, file_id
        return self._public_payload(action=action, mode=mode)

    def context_payload(self, scenario: AssetResolutionScenario) -> dict[str, Any] | None:
        return self._top_level_payload_for_state(scenario.context_payload_state)

    def forward_payload(
        self,
        scenario: AssetResolutionScenario,
        *,
        materialize: bool,
    ) -> dict[str, Any] | None:
        state = (
            scenario.forward_materialize_state
            if materialize and scenario.forward_materialize_state != "inherit"
            else scenario.forward_metadata_state
            if not materialize and scenario.forward_metadata_state != "inherit"
            else scenario.forward_payload_state
        )
        if state == "none":
            return None
        if state == "timeout":
            raise NapCatFastHistoryTimeoutError("timed out")
        if state == "unavailable":
            raise NapCatFastHistoryUnavailable("route unavailable")
        if state == "error":
            raise RuntimeError("simulated forward route error")
        if state == "empty":
            return {"assets": [], "targeted_mode": "metadata_only"}
        asset_payload = self._asset_payload_for_state(state)
        return {"assets": [asset_payload], "targeted_mode": "single_target_download"}

    def _top_level_payload_for_state(self, state: str) -> dict[str, Any] | None:
        if state == "none":
            return None
        if state == "timeout":
            raise NapCatFastHistoryTimeoutError("timed out")
        if state == "unavailable":
            raise NapCatFastHistoryUnavailable("route unavailable")
        if state == "error":
            raise RuntimeError("simulated context route error")
        return self._asset_payload_for_state(state)

    def _asset_payload_for_state(self, state: str) -> dict[str, Any]:
        action = {
            "image": "get_image",
            "video": "get_file",
            "file": "get_file",
            "speech": "get_record",
        }.get(self.scenario.asset_type, "")
        if state == "local_path":
            return {"file": self.local_path, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if state == "zero_local":
            return {"file": self.zero_local_path, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if state == "public_token":
            return {
                "public_action": action,
                "public_file_token": f"token-{self.scenario.name}",
                "file_name": self.file_name,
                "asset_type": self.scenario.asset_type,
            }
        if state == "payload_file_id_only":
            return {
                "file_id": f"/payload-fileid/{self.scenario.name}",
                "file_name": self.file_name,
                "file_size": "2048",
                "asset_type": self.scenario.asset_type,
            }
        if state == "remote_url":
            remote_state = self.scenario.hint_remote_state if self.scenario.hint_remote_state != "none" else "live_http"
            remote_url = self._remote_url_for_state(remote_state)
            return {"url": remote_url, "remote_url": remote_url, "file_name": self.file_name, "asset_type": self.scenario.asset_type}
        if state == "blank_payload":
            return {
                "public_action": action,
                "public_file_token": f"token-{self.scenario.name}",
                "file_name": self.file_name,
                "file_size": "2048",
                "asset_type": self.scenario.asset_type,
            }
        raise ValueError(f"unsupported payload state: {state}")


def _path_kind_for_result(result: tuple[Path | None, str | None], state: _ScenarioRuntimeState) -> tuple[str, str | None]:
    resolved_path, _resolver = result
    if resolved_path is None:
        return "missing", None
    text = str(Path(resolved_path).resolve())
    return state.kind_map.get(text, "local"), text


def run_asset_resolution_scenario(
    scenario: AssetResolutionScenario,
    *,
    trace_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AssetResolutionResult:
    runtime = _ScenarioRuntimeState(scenario)
    events: list[dict[str, Any]] = []
    client = _ScenarioPublicClient(scenario, runtime)
    fast_client = _ScenarioFastClient(scenario, runtime)
    downloader = _ScenarioAwareDownloader(client, fast_client=fast_client, state=runtime)
    try:
        result = downloader.resolve_for_export(
            runtime.request,
            trace_callback=(lambda event: (events.append(dict(event)), trace_callback and trace_callback(dict(event)))) if trace_callback is not None else events.append,
        )
        actual_path_kind, resolved_path = _path_kind_for_result(result, runtime)
        actual_resolver = result[1]
        cost_matched = True
        if scenario.max_client_calls is not None and len(client.calls) > scenario.max_client_calls:
            cost_matched = False
        if scenario.max_fast_calls is not None and len(fast_client.calls) > scenario.max_fast_calls:
            cost_matched = False
        if scenario.max_remote_attempts is not None and len(runtime.remote_attempts) > scenario.max_remote_attempts:
            cost_matched = False
        matched = (
            actual_resolver == scenario.expected_resolver
            and actual_path_kind == scenario.expected_path_kind
            and cost_matched
        )
        trace_status_breakdown: dict[str, int] = {}
        for event in events:
            if str(event.get("phase") or "").strip() != "materialize_asset_substep":
                continue
            status = str(event.get("status") or "").strip()
            if not status:
                continue
            trace_status_breakdown[status] = trace_status_breakdown.get(status, 0) + 1
        return AssetResolutionResult(
            name=scenario.name,
            suite=scenario.suite,
            asset_type=scenario.asset_type,
            topology=scenario.topology,
            age_days=scenario.age_days,
            expected_resolver=scenario.expected_resolver,
            actual_resolver=actual_resolver,
            expected_path_kind=scenario.expected_path_kind,
            actual_path_kind=actual_path_kind,
            matched=matched,
            resolved_path=resolved_path,
            client_call_count=len(client.calls),
            fast_call_count=len(fast_client.calls),
            remote_attempt_count=len(runtime.remote_attempts),
            trace_event_count=len(events),
            trace_status_breakdown=trace_status_breakdown,
            cost_matched=cost_matched,
            notes=scenario.notes,
        )
    finally:
        downloader.close()
        runtime.close()


def run_asset_resolution_sequence(
    scenario: AssetResolutionScenario,
    *,
    repeats: int = 3,
    trace_callback: Callable[[dict[str, Any]], None] | None = None,
) -> AssetResolutionSequenceResult:
    runtime = _ScenarioRuntimeState(scenario)
    events: list[dict[str, Any]] = []
    client = _ScenarioPublicClient(scenario, runtime)
    fast_client = _ScenarioFastClient(scenario, runtime)
    downloader = _ScenarioAwareDownloader(client, fast_client=fast_client, state=runtime)
    try:
        sequence_results: list[tuple[str | None, str]] = []
        repeats = max(1, int(repeats))
        for _ in range(repeats):
            request = copy.deepcopy(runtime.request)
            result = downloader.resolve_for_export(
                request,
                trace_callback=(
                    (lambda event: (events.append(dict(event)), trace_callback and trace_callback(dict(event))))
                    if trace_callback is not None
                    else events.append
                ),
            )
            actual_path_kind, _resolved_path = _path_kind_for_result(result, runtime)
            sequence_results.append((result[1], actual_path_kind))
        unique_resolvers = tuple(dict.fromkeys(item[0] for item in sequence_results))
        unique_path_kinds = tuple(dict.fromkeys(item[1] for item in sequence_results))
        actual_resolver = sequence_results[-1][0]
        actual_path_kind = sequence_results[-1][1]
        cost_matched = True
        if scenario.max_client_calls is not None and len(client.calls) > scenario.max_client_calls:
            cost_matched = False
        if scenario.max_fast_calls is not None and len(fast_client.calls) > scenario.max_fast_calls:
            cost_matched = False
        if scenario.max_remote_attempts is not None and len(runtime.remote_attempts) > scenario.max_remote_attempts:
            cost_matched = False
        matched = (
            all(resolver == scenario.expected_resolver for resolver, _ in sequence_results)
            and all(path_kind == scenario.expected_path_kind for _, path_kind in sequence_results)
            and cost_matched
        )
        trace_status_breakdown: dict[str, int] = {}
        for event in events:
            if str(event.get("phase") or "").strip() != "materialize_asset_substep":
                continue
            status = str(event.get("status") or "").strip()
            if not status:
                continue
            trace_status_breakdown[status] = trace_status_breakdown.get(status, 0) + 1
        return AssetResolutionSequenceResult(
            name=scenario.name,
            suite=scenario.suite,
            repeats=repeats,
            expected_resolver=scenario.expected_resolver,
            expected_path_kind=scenario.expected_path_kind,
            actual_resolver=actual_resolver,
            actual_path_kind=actual_path_kind,
            matched=matched,
            unique_resolvers=unique_resolvers,
            unique_path_kinds=unique_path_kinds,
            client_call_count=len(client.calls),
            fast_call_count=len(fast_client.calls),
            remote_attempt_count=len(runtime.remote_attempts),
            trace_event_count=len(events),
            trace_status_breakdown=trace_status_breakdown,
            cost_matched=cost_matched,
            notes=scenario.notes,
        )
    finally:
        downloader.close()
        runtime.close()


def default_asset_resolution_scenarios() -> list[AssetResolutionScenario]:
    return [
        AssetResolutionScenario(
            name="top_level_image_hint_local_path",
            asset_type="image",
            suite="live_recovery_paths",
            hint_local_state="file_existing",
            expected_resolver="hint_local_path",
            expected_path_kind="local",
            max_client_calls=0,
            max_fast_calls=0,
            max_remote_attempts=0,
            notes="Direct local hint should bypass NapCat calls.",
        ),
        AssetResolutionScenario(
            name="top_level_image_placeholder_zero_byte",
            asset_type="image",
            suite="classification_fast_fail",
            age_days=240,
            source_path_state="placeholder_zero",
            expected_resolver="qq_not_downloaded_local_placeholder",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=0,
            max_remote_attempts=0,
            notes="Image placeholder should classify quickly without remote work.",
        ),
        AssetResolutionScenario(
            name="top_level_image_public_token_remote",
            asset_type="image",
            suite="live_recovery_paths",
            context_payload_state="public_token",
            public_result_state="valid_remote",
            expected_resolver="napcat_public_token_get_image_remote_url",
            expected_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="top_level_video_public_token_local",
            asset_type="video",
            suite="live_recovery_paths",
            context_payload_state="public_token",
            public_result_state="valid_local",
            expected_resolver="napcat_public_token_get_file",
            expected_path_kind="local",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="top_level_video_old_blank_public_payload",
            asset_type="video",
            suite="classification_fast_fail",
            age_days=240,
            context_payload_state="public_token",
            public_result_state="blank_payload",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="top_level_file_direct_file_id_local",
            asset_type="file",
            suite="live_recovery_paths",
            direct_file_result_state="valid_local",
            expected_resolver="napcat_segment_file_id_get_file",
            expected_path_kind="local",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="top_level_speech_public_token_remote",
            asset_type="speech",
            suite="live_recovery_paths",
            context_payload_state="public_token",
            public_result_state="valid_remote",
            expected_resolver="napcat_public_token_get_record_remote_url",
            expected_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="top_level_sticker_remote_gif",
            asset_type="sticker",
            suite="live_recovery_paths",
            hint_remote_state="live_http",
            expected_resolver="sticker_remote_download",
            expected_path_kind="remote",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="top_level_sticker_relative_remote_gif",
            asset_type="sticker",
            suite="live_recovery_paths",
            hint_remote_state="relative_http",
            expected_resolver="sticker_remote_download",
            expected_path_kind="remote",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="forward_image_remote_url_hit",
            asset_type="image",
            suite="live_recovery_paths",
            topology="forward",
            age_days=45,
            forward_payload_state="remote_url",
            hint_remote_state="live_http",
            expected_resolver="napcat_forward_remote_url",
            expected_path_kind="remote",
            max_client_calls=0,
            max_fast_calls=0,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="forward_old_image_expired_without_payload",
            asset_type="image",
            suite="classification_fast_fail",
            topology="forward",
            age_days=240,
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=0,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_recent_video_public_token_local",
            asset_type="video",
            suite="live_recovery_paths",
            topology="forward",
            age_days=20,
            forward_payload_state="public_token",
            public_result_state="valid_local",
            expected_resolver="napcat_public_token_get_file",
            expected_path_kind="local",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_video_public_token_timeout",
            asset_type="video",
            suite="classification_fast_fail",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="public_token",
            public_result_state="timeout",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_video_metadata_timeout",
            asset_type="video",
            suite="classification_fast_fail",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="timeout",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_video_materialize_timeout",
            asset_type="video",
            suite="classification_fast_fail",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_metadata_state="none",
            forward_materialize_state="timeout",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=2,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_file_public_token_timeout",
            asset_type="file",
            suite="classification_fast_fail",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="public_token",
            public_result_state="timeout",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_speech_public_token_timeout",
            asset_type="speech",
            suite="classification_fast_fail",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="public_token",
            public_result_state="timeout",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_video_direct_file_id_local",
            asset_type="video",
            suite="live_recovery_paths",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            direct_file_result_state="valid_local",
            expected_resolver="napcat_segment_file_id_get_file",
            expected_path_kind="local",
            max_client_calls=1,
            max_fast_calls=2,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_video_known_bad_public_token",
            asset_type="video",
            suite="classification_fast_fail",
            topology="forward",
            age_days=30,
            forward_payload_state="public_token",
            public_result_state="known_bad_video",
            expected_resolver="napcat_video_url_unavailable",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_file_known_bad_public_token",
            asset_type="file",
            suite="classification_fast_fail",
            topology="forward",
            age_days=30,
            forward_payload_state="public_token",
            public_result_state="known_bad_file",
            expected_resolver="napcat_file_url_unavailable",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_speech_known_bad_public_token",
            asset_type="speech",
            suite="classification_fast_fail",
            topology="forward",
            age_days=30,
            forward_payload_state="public_token",
            public_result_state="known_bad_record",
            expected_resolver="napcat_record_url_unavailable",
            expected_path_kind="missing",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_video_relative_remote_url",
            asset_type="video",
            suite="live_recovery_paths",
            topology="forward",
            age_days=20,
            forward_payload_state="remote_url",
            hint_remote_state="relative_http",
            expected_resolver="napcat_forward_remote_url",
            expected_path_kind="remote",
            max_client_calls=0,
            max_fast_calls=0,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="top_level_video_context_timeout_direct_file_id_remote",
            asset_type="video",
            suite="live_recovery_paths",
            age_days=20,
            context_payload_state="timeout",
            direct_file_result_state="valid_remote",
            expected_resolver="napcat_segment_file_id_get_file_remote_url",
            expected_path_kind="remote",
            max_client_calls=1,
            max_fast_calls=1,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="forward_old_video_route_unavailable",
            asset_type="video",
            suite="route_health",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="unavailable",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
            notes="Very old forward video should degrade quickly when the forward route itself is unavailable.",
        ),
        AssetResolutionScenario(
            name="forward_old_file_route_unavailable",
            asset_type="file",
            suite="route_health",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="unavailable",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_old_speech_route_unavailable",
            asset_type="speech",
            suite="route_health",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="unavailable",
            expected_resolver="qq_expired_after_napcat",
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_video_missing_parent_element_id",
            asset_type="video",
            suite="forward_parent_shape",
            topology="forward_missing_parent",
            age_days=260,
            source_path_state="stale_missing",
            expected_resolver=None,
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
            notes="Malformed forward parent should skip forward route and avoid repeated retries.",
        ),
        AssetResolutionScenario(
            name="forward_video_missing_parent_message_id",
            asset_type="video",
            suite="forward_parent_shape",
            topology="forward",
            forward_parent_state="missing_message_id_raw",
            age_days=260,
            source_path_state="stale_missing",
            expected_resolver=None,
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
        AssetResolutionScenario(
            name="forward_video_stale_path_live_remote_url",
            asset_type="video",
            suite="live_recovery_paths",
            topology="forward",
            age_days=260,
            source_path_state="stale_missing",
            forward_payload_state="remote_url",
            hint_remote_state="live_http",
            expected_resolver="napcat_forward_remote_url",
            expected_path_kind="remote",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=1,
        ),
        AssetResolutionScenario(
            name="top_level_video_old_context_route_unavailable",
            asset_type="video",
            suite="route_health",
            age_days=240,
            source_path_state="stale_missing",
            context_payload_state="unavailable",
            expected_resolver=None,
            expected_path_kind="missing",
            max_client_calls=0,
            max_fast_calls=1,
            max_remote_attempts=0,
        ),
    ]


def _exhaustive_old_forward_terminal_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    signal_specs: dict[str, dict[str, Any]] = {
        "payload_timeout": {
            "forward_payload_state": "timeout",
            "max_client_calls": 0,
            "max_fast_calls": 1,
            "max_remote_attempts": 0,
        },
        "payload_unavailable": {
            "forward_payload_state": "unavailable",
            "max_client_calls": 0,
            "max_fast_calls": 1,
            "max_remote_attempts": 0,
        },
        "materialize_empty": {
            "forward_metadata_state": "none",
            "forward_materialize_state": "empty",
            "max_client_calls": 0,
            "max_fast_calls": 2,
            "max_remote_attempts": 0,
        },
        "materialize_error": {
            "forward_metadata_state": "none",
            "forward_materialize_state": "error",
            "max_client_calls": 0,
            "max_fast_calls": 2,
            "max_remote_attempts": 0,
        },
        "materialize_zero_local": {
            "forward_metadata_state": "none",
            "forward_materialize_state": "zero_local",
            "max_client_calls": None,
            "max_fast_calls": 2,
            "max_remote_attempts": 0,
        },
        "public_timeout": {
            "forward_payload_state": "public_token",
            "public_result_state": "timeout",
            "max_client_calls": 1,
            "max_fast_calls": 2,
            "max_remote_attempts": 0,
        },
        "public_blank_payload": {
            "forward_payload_state": "public_token",
            "public_result_state": "blank_payload",
            "max_client_calls": 1,
            "max_fast_calls": 2,
            "max_remote_attempts": 0,
        },
        "public_not_found": {
            "forward_payload_state": "public_token",
            "public_result_state": "not_found",
            "max_client_calls": 1,
            "max_fast_calls": 2,
            "max_remote_attempts": 0,
        },
    }
    for topology in ("forward", "nested_forward"):
        for asset_type in ("video", "file", "speech"):
            for source_state in ("none", "stale_missing", "existing_zero"):
                for signal_name, spec in signal_specs.items():
                    max_client_calls = spec["max_client_calls"]
                    if signal_name == "materialize_zero_local" and asset_type in {"video", "file"}:
                        max_client_calls = 1
                    scenarios.append(
                        AssetResolutionScenario(
                            name=f"exhaustive_{topology}_{asset_type}_{source_state}_{signal_name}",
                            suite="exhaustive_old_forward_terminal",
                            asset_type=asset_type,
                            topology=topology,
                            age_days=260,
                            source_path_state=source_state,
                            expected_resolver="qq_expired_after_napcat",
                            expected_path_kind="missing",
                            max_client_calls=max_client_calls,
                            max_fast_calls=spec["max_fast_calls"],
                            max_remote_attempts=spec["max_remote_attempts"],
                            notes=(
                                "Bounded exhaustive old-forward terminal audit over source-state and "
                                "terminal failure signal combinations."
                            ),
                            **{
                                key: value
                                for key, value in spec.items()
                                if key
                                not in {"max_client_calls", "max_fast_calls", "max_remote_attempts"}
                            },
                        )
                    )
    return scenarios


def _exhaustive_sticker_forward_parent_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    for topology in ("forward", "nested_forward"):
        for parent_state in (
            "missing_element_id",
            "missing_message_id_raw",
            "missing_peer_uid",
            "blank_parent_bundle",
        ):
            scenarios.append(
                AssetResolutionScenario(
                    name=f"exhaustive_{topology}_sticker_{parent_state}_no_remote",
                    suite="exhaustive_sticker_forward_parent",
                    asset_type="sticker",
                    topology=topology,
                    forward_parent_state=parent_state,
                    age_days=20,
                    expected_resolver=None,
                    expected_path_kind="missing",
                    max_client_calls=0,
                    max_fast_calls=1,
                    max_remote_attempts=0,
                )
            )
            for remote_state in ("live_http", "relative_http"):
                scenarios.append(
                    AssetResolutionScenario(
                        name=f"exhaustive_{topology}_sticker_{parent_state}_{remote_state}",
                        suite="exhaustive_sticker_forward_parent",
                        asset_type="sticker",
                        topology=topology,
                        forward_parent_state=parent_state,
                        age_days=20,
                        hint_remote_state=remote_state,
                        expected_resolver="sticker_remote_download",
                        expected_path_kind="remote",
                        max_client_calls=0,
                        max_fast_calls=1,
                        max_remote_attempts=1,
                    )
                )
    return scenarios


def _exhaustive_local_path_state_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    for asset_type in ("image", "video", "file", "speech"):
        scenarios.append(
            AssetResolutionScenario(
                name=f"exhaustive_top_level_{asset_type}_source_existing",
                suite="exhaustive_local_path_states",
                asset_type=asset_type,
                topology="top_level",
                source_path_state="existing",
                expected_resolver="source_local_path",
                expected_path_kind="local",
                max_client_calls=0,
                max_fast_calls=0,
                max_remote_attempts=0,
            )
        )
        scenarios.append(
            AssetResolutionScenario(
                name=f"exhaustive_top_level_{asset_type}_source_existing_zero",
                suite="exhaustive_local_path_states",
                asset_type=asset_type,
                topology="top_level",
                source_path_state="existing_zero",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=1 if asset_type != "image" else 2,
                max_remote_attempts=0,
            )
        )
        scenarios.append(
            AssetResolutionScenario(
                name=f"exhaustive_top_level_{asset_type}_hint_path_existing",
                suite="exhaustive_local_path_states",
                asset_type=asset_type,
                topology="top_level",
                hint_local_state="path_existing",
                expected_resolver="hint_local_path",
                expected_path_kind="local",
                max_client_calls=0,
                max_fast_calls=0,
                max_remote_attempts=0,
            )
        )
        scenarios.append(
            AssetResolutionScenario(
                name=f"exhaustive_top_level_{asset_type}_hint_path_zero",
                suite="exhaustive_local_path_states",
                asset_type=asset_type,
                topology="top_level",
                hint_local_state="path_zero",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=1 if asset_type != "image" else 2,
                max_remote_attempts=0,
            )
        )
        scenarios.append(
            AssetResolutionScenario(
                name=f"exhaustive_top_level_{asset_type}_hint_stale_local_url",
                suite="exhaustive_local_path_states",
                asset_type=asset_type,
                topology="top_level",
                hint_local_state="stale_local_url",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=1 if asset_type != "image" else 2,
                max_remote_attempts=0,
            )
        )
    for asset_type in ("image", "video", "file", "speech", "sticker"):
        kwargs: dict[str, Any] = {
            "name": f"exhaustive_forward_{asset_type}_stale_http_remote_missing",
            "suite": "exhaustive_local_path_states",
            "asset_type": asset_type,
            "topology": "forward",
            "age_days": 20,
            "hint_remote_state": "stale_http",
            "expected_resolver": None,
            "expected_path_kind": "missing",
            "max_client_calls": 0,
            "max_fast_calls": 1,
            "max_remote_attempts": 1,
            "notes": "Dead remote URL should fail after one bounded remote attempt, not silently count as local/hydrated.",
        }
        if asset_type != "sticker":
            kwargs["source_path_state"] = "stale_missing"
            kwargs["forward_payload_state"] = "remote_url"
            kwargs["max_fast_calls"] = 1 if asset_type == "image" else 2
        scenarios.append(AssetResolutionScenario(**kwargs))
    return scenarios


def _exhaustive_old_forward_direct_file_id_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    for topology in ("forward", "nested_forward"):
        for asset_type in ("video", "file"):
            for source_state in ("none", "stale_missing", "existing_zero"):
                for direct_state in ("blank_payload", "timeout", "not_found"):
                    scenarios.append(
                        AssetResolutionScenario(
                            name=f"exhaustive_{topology}_{asset_type}_{source_state}_{direct_state}_direct_file_id",
                            suite="exhaustive_old_forward_direct_file_id",
                            asset_type=asset_type,
                            topology=topology,
                            age_days=260,
                            source_path_state=source_state,
                            direct_file_result_state=direct_state,
                            expected_resolver="qq_expired_after_napcat",
                            expected_path_kind="missing",
                            max_client_calls=1,
                            max_fast_calls=1,
                            max_remote_attempts=0,
                            notes=(
                                "Very old forward video/file assets with only direct file-id fallback "
                                "must classify as expired on blank/timeout/not_found without spilling "
                                "into targeted materialize."
                            ),
                        )
                    )
    return scenarios


def _exhaustive_public_token_shape_drift_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    resolver_by_asset_type = {
        "image": "napcat_public_token_get_image",
        "video": "napcat_public_token_get_file",
        "file": "napcat_public_token_get_file",
        "speech": "napcat_public_token_get_record",
    }
    for topology in ("top_level", "forward", "nested_forward"):
        for asset_type in ("image", "video", "file", "speech"):
            payload_fields: dict[str, Any]
            if topology == "top_level":
                payload_fields = {
                    "context_payload_state": "public_token",
                }
            else:
                payload_fields = {
                    "forward_payload_state": "public_token",
                }
            for fallback_state, expected_path_kind in (
                ("valid_local", "local"),
                ("valid_remote", "remote"),
                ("valid_remote_only", "remote"),
            ):
                scenario_kwargs = {
                    "name": f"public_token_shape_drift_{topology}_{asset_type}_{fallback_state}",
                    "suite": "public_token_shape_drift",
                    "asset_type": asset_type,
                    "topology": topology,
                    "age_days": 20,
                    "public_result_state": "opaque_error",
                    "public_fallback_result_state": fallback_state,
                    "expected_resolver": (
                        resolver_by_asset_type[asset_type]
                        if expected_path_kind == "local"
                        else f"{resolver_by_asset_type[asset_type]}_remote_url"
                    ),
                    "expected_path_kind": expected_path_kind,
                    "max_client_calls": 2,
                    "max_fast_calls": 1,
                    "max_remote_attempts": 1 if fallback_state in {"valid_remote", "valid_remote_only"} else 0,
                    "notes": (
                        "Bounded compatibility coverage for NapCat runtimes that only honor "
                        "`file_id=<token>` after rejecting `file=<token>`."
                    ),
                    **payload_fields,
                }
                if topology != "top_level":
                    scenario_kwargs["source_path_state"] = "none"
                scenarios.append(AssetResolutionScenario(**scenario_kwargs))
    return scenarios


def _exhaustive_old_forward_payload_file_id_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    for topology in ("forward", "nested_forward"):
        for asset_type in ("video", "file"):
            for source_state in ("none", "stale_missing", "existing_zero"):
                for direct_state in ("blank_payload", "timeout", "not_found"):
                    scenarios.append(
                        AssetResolutionScenario(
                            name=f"exhaustive_{topology}_{asset_type}_{source_state}_{direct_state}_payload_file_id",
                            suite="exhaustive_old_forward_payload_file_id",
                            asset_type=asset_type,
                            topology=topology,
                            age_days=260,
                            source_path_state=source_state,
                            forward_metadata_state="payload_file_id_only",
                            direct_file_result_state=direct_state,
                            expected_resolver="qq_expired_after_napcat",
                            expected_path_kind="missing",
                            max_client_calls=1,
                            max_fast_calls=1,
                            max_remote_attempts=0,
                            notes=(
                                "Very old forwarded file/video assets whose only surviving direct-file-id "
                                "arrives in the forward metadata payload should prefer direct-file-id "
                                "before targeted materialize and classify quickly on terminal failures."
                            ),
                        )
                    )
    return scenarios


def _exhaustive_old_public_zero_byte_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []
    for topology in ("top_level", "forward", "nested_forward"):
        for asset_type in ("video", "file", "speech"):
            for source_state in ("none", "stale_missing"):
                scenario_kwargs: dict[str, Any] = {
                    "name": f"exhaustive_{topology}_{asset_type}_{source_state}_public_zero_local",
                    "suite": "exhaustive_old_public_zero_byte",
                    "asset_type": asset_type,
                    "topology": topology,
                    "age_days": 260,
                    "source_path_state": source_state,
                    "public_result_state": "valid_zero_local",
                    "expected_resolver": "qq_expired_after_napcat",
                    "expected_path_kind": "missing",
                    "max_client_calls": 1,
                    "max_fast_calls": 1 if topology == "top_level" else 2,
                    "max_remote_attempts": 0,
                    "notes": (
                        "Old public-token payloads that only expose an existing zero-byte local file "
                        "should classify as expired instead of leaking through as ambiguous missing."
                    ),
                }
                if topology == "top_level":
                    scenario_kwargs["context_payload_state"] = "public_token"
                else:
                    scenario_kwargs["forward_payload_state"] = "public_token"
                scenarios.append(AssetResolutionScenario(**scenario_kwargs))
    return scenarios


def generated_asset_resolution_scenarios() -> list[AssetResolutionScenario]:
    scenarios: list[AssetResolutionScenario] = []

    forward_media_types = ("image", "video", "file", "speech")
    expensive_forward_types = ("video", "file", "speech")
    forward_topologies = ("forward", "nested_forward")
    malformed_parent_states = (
        "missing_element_id",
        "missing_message_id_raw",
        "missing_peer_uid",
        "blank_parent_bundle",
    )

    for topology in forward_topologies:
        for asset_type in forward_media_types:
            for parent_state in malformed_parent_states:
                scenarios.append(
                    AssetResolutionScenario(
                        name=f"{topology}_{asset_type}_{parent_state}_no_remote",
                        suite="forward_parent_shape",
                        asset_type=asset_type,
                        topology=topology,
                        forward_parent_state=parent_state,
                        age_days=260,
                        source_path_state="stale_missing",
                        expected_resolver=None,
                        expected_path_kind="missing",
                        max_client_calls=0,
                        max_fast_calls=1,
                        max_remote_attempts=0,
                    )
                )
                for remote_state in ("live_http", "relative_http"):
                    scenarios.append(
                        AssetResolutionScenario(
                            name=f"{topology}_{asset_type}_{parent_state}_{remote_state}",
                            suite="forward_parent_shape",
                            asset_type=asset_type,
                            topology=topology,
                            forward_parent_state=parent_state,
                            age_days=260,
                            source_path_state="stale_missing",
                            hint_remote_state=remote_state,
                            expected_resolver="napcat_forward_remote_url",
                            expected_path_kind="remote",
                            max_client_calls=0,
                            max_fast_calls=0,
                            max_remote_attempts=1,
                        )
                    )

    for topology in ("forward", "nested_forward"):
        for remote_state in ("live_http", "relative_http"):
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_sticker_{remote_state}_remote_recovery",
                    suite="live_recovery_paths",
                    asset_type="sticker",
                    topology=topology,
                    age_days=20,
                    hint_remote_state=remote_state,
                    expected_resolver="sticker_remote_download",
                    expected_path_kind="remote",
                    max_client_calls=0,
                    max_fast_calls=1,
                    max_remote_attempts=1,
                )
            )
        scenarios.append(
            AssetResolutionScenario(
                name=f"{topology}_sticker_missing_peer_uid_live_http",
                suite="forward_parent_shape",
                asset_type="sticker",
                topology=topology,
                forward_parent_state="missing_peer_uid",
                age_days=20,
                hint_remote_state="live_http",
                expected_resolver="sticker_remote_download",
                expected_path_kind="remote",
                max_client_calls=0,
                max_fast_calls=1,
                max_remote_attempts=1,
            )
        )

    for topology in forward_topologies:
        for asset_type in forward_media_types:
            for age_label, age_days in (("recent", 20), ("old", 260)):
                for remote_state in ("live_http", "relative_http"):
                    scenarios.append(
                        AssetResolutionScenario(
                            name=f"{topology}_{asset_type}_{age_label}_{remote_state}_remote_recovery",
                            suite="family_diff_matrix",
                            asset_type=asset_type,
                            topology=topology,
                            age_days=age_days,
                            source_path_state="stale_missing",
                            hint_remote_state=remote_state,
                            forward_payload_state="remote_url",
                            expected_resolver="napcat_forward_remote_url",
                            expected_path_kind="remote",
                            max_client_calls=0,
                            max_fast_calls=0,
                            max_remote_attempts=1,
                        )
                    )

    for topology in forward_topologies:
        for asset_type in expensive_forward_types:
            for signal_state in ("unavailable", "timeout"):
                scenarios.append(
                    AssetResolutionScenario(
                        name=f"{topology}_{asset_type}_very_old_{signal_state}",
                        suite="route_health",
                        asset_type=asset_type,
                        topology=topology,
                        age_days=260,
                        source_path_state="stale_missing",
                        forward_payload_state=signal_state,
                        expected_resolver="qq_expired_after_napcat",
                        expected_path_kind="missing",
                        max_client_calls=0,
                        max_fast_calls=1,
                        max_remote_attempts=0,
                    )
                )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_empty_terminal",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    forward_metadata_state="none",
                    forward_materialize_state="empty",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=0,
                    max_fast_calls=2,
                    max_remote_attempts=0,
                )
            )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_materialize_error",
                    suite="route_health",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    forward_metadata_state="none",
                    forward_materialize_state="error",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=0,
                    max_fast_calls=2,
                    max_remote_attempts=0,
                )
            )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_public_not_found",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    forward_payload_state="public_token",
                    public_result_state="not_found",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=2,
                    max_fast_calls=1,
                    max_remote_attempts=0,
                )
            )
            for remote_state in ("live_http", "relative_http"):
                scenarios.append(
                    AssetResolutionScenario(
                        name=f"{topology}_{asset_type}_recent_unavailable_{remote_state}_remote_wins",
                        suite="route_health",
                        asset_type=asset_type,
                        topology=topology,
                        age_days=20,
                        source_path_state="stale_missing",
                        hint_remote_state=remote_state,
                        forward_payload_state="unavailable",
                        expected_resolver="napcat_forward_remote_url",
                        expected_path_kind="remote",
                        max_client_calls=0,
                        max_fast_calls=0,
                        max_remote_attempts=1,
                    )
                )

    for topology in forward_topologies:
        for asset_type in ("video", "file"):
            for direct_mode, expected_path_kind in (
                ("valid_local", "local"),
                ("valid_remote", "remote"),
            ):
                scenarios.append(
                    AssetResolutionScenario(
                        name=f"{topology}_{asset_type}_very_old_blank_payload_direct_{direct_mode}",
                        suite="live_recovery_paths",
                        asset_type=asset_type,
                        topology=topology,
                        age_days=260,
                        source_path_state="stale_missing",
                        forward_payload_state="blank_payload",
                        direct_file_result_state=direct_mode,
                        expected_resolver="napcat_segment_file_id_get_file"
                        if direct_mode == "valid_local"
                        else "napcat_segment_file_id_get_file_remote_url",
                        expected_path_kind=expected_path_kind,
                        max_client_calls=2,
                        max_fast_calls=1,
                        max_remote_attempts=1 if direct_mode == "valid_remote" else 0,
                    )
                )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_direct_not_found",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    direct_file_result_state="not_found",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=1,
                    max_fast_calls=2,
                    max_remote_attempts=0,
                )
            )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_blank_payload_direct_not_found",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    forward_payload_state="blank_payload",
                    direct_file_result_state="not_found",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=2,
                    max_fast_calls=1,
                    max_remote_attempts=0,
                )
            )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_blank_payload_direct_timeout",
                    suite="route_health",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    forward_payload_state="blank_payload",
                    direct_file_result_state="timeout",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=2,
                    max_fast_calls=1,
                    max_remote_attempts=0,
                )
            )

    for topology in forward_topologies:
        for asset_type in expensive_forward_types:
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_timeout_no_local_hint",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="none",
                    forward_payload_state="timeout",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=0,
                    max_fast_calls=2,
                    max_remote_attempts=0,
                )
            )
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_very_old_empty_no_local_hint",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="none",
                    forward_metadata_state="none",
                    forward_materialize_state="empty",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=0,
                    max_fast_calls=2,
                    max_remote_attempts=0,
                )
            )

    for asset_type in ("image", "video", "file", "speech"):
        scenarios.append(
            AssetResolutionScenario(
                name=f"top_level_{asset_type}_hint_local_zero_byte_rejected",
                suite="classification_fast_fail",
                asset_type=asset_type,
                topology="top_level",
                age_days=20,
                hint_local_state="file_zero",
                expected_resolver=None,
                expected_path_kind="missing",
                max_client_calls=0,
                max_fast_calls=2 if asset_type == "image" else 1,
                max_remote_attempts=0,
            )
        )
    for topology in forward_topologies:
        for asset_type in ("video", "file", "speech"):
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_materialize_zero_byte_rejected",
                    suite="classification_fast_fail",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=260,
                    source_path_state="stale_missing",
                    forward_metadata_state="none",
                    forward_materialize_state="zero_local",
                    expected_resolver="qq_expired_after_napcat",
                    expected_path_kind="missing",
                    max_client_calls=0 if asset_type == "speech" else 1,
                    max_fast_calls=2,
                    max_remote_attempts=0,
                )
            )

    for topology in ("top_level",):
        for asset_type in ("video", "file", "speech"):
            scenarios.append(
                AssetResolutionScenario(
                    name=f"{topology}_{asset_type}_recent_context_unavailable_direct_remote",
                    suite="route_health",
                    asset_type=asset_type,
                    topology=topology,
                    age_days=20,
                    context_payload_state="unavailable",
                    direct_file_result_state="valid_remote" if asset_type in {"video", "file"} else "none",
                    expected_resolver=(
                        "napcat_segment_file_id_get_file_remote_url"
                        if asset_type in {"video", "file"}
                        else None
                    ),
                    expected_path_kind=("remote" if asset_type in {"video", "file"} else "missing"),
                    max_client_calls=(1 if asset_type in {"video", "file"} else 0),
                    max_fast_calls=1,
                    max_remote_attempts=(1 if asset_type in {"video", "file"} else 0),
                )
            )

    scenarios.extend(_exhaustive_old_forward_terminal_scenarios())
    scenarios.extend(_exhaustive_sticker_forward_parent_scenarios())
    scenarios.extend(_exhaustive_local_path_state_scenarios())
    scenarios.extend(_exhaustive_old_forward_direct_file_id_scenarios())
    scenarios.extend(_exhaustive_public_token_shape_drift_scenarios())
    scenarios.extend(_exhaustive_old_forward_payload_file_id_scenarios())
    scenarios.extend(_exhaustive_old_public_zero_byte_scenarios())

    return scenarios


def all_asset_resolution_scenarios() -> list[AssetResolutionScenario]:
    return [*default_asset_resolution_scenarios(), *generated_asset_resolution_scenarios()]


def run_asset_resolution_matrix(*, suite: str | None = None) -> list[AssetResolutionResult]:
    normalized_suite = str(suite or "").strip().lower()
    return [
        run_asset_resolution_scenario(scenario)
        for scenario in all_asset_resolution_scenarios()
        if not normalized_suite or scenario.suite.lower() == normalized_suite
    ]
