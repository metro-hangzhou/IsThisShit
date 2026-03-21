from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .fast_history_client import NapCatFastHistoryTimeoutError
from .http_client import NapCatApiTimeoutError
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


def build_forward_timeout_request(
    *,
    asset_type: str,
    parent_index: int,
    sibling_index: int,
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

    events: list[dict[str, Any]] = []

    def _trace(event: dict[str, Any]) -> None:
        events.append(dict(event))
        if trace_callback is not None:
            trace_callback(dict(event))

    if normalized_route == "public-token":
        if normalized_asset_type == "speech":
            client = _SleepingTimeoutPublicRecordClient(delay_s=delay_s)
            downloader = NapCatMediaDownloader(client)
            timeout_budget_s = downloader.PUBLIC_TOKEN_ACTION_TIMEOUT_S
            backend_call_getter = lambda: client.get_record_calls
            action = "get_record"
        else:
            client = _SleepingTimeoutPublicFileClient(delay_s=delay_s)
            downloader = NapCatMediaDownloader(client)
            timeout_budget_s = downloader.PUBLIC_TOKEN_ACTION_TIMEOUT_S
            backend_call_getter = lambda: client.get_file_calls
            action = "get_file"
        started = time.perf_counter()
        for parent_index in range(parents):
            for sibling_index in range(siblings_per_parent):
                request = build_forward_timeout_request(
                    asset_type=normalized_asset_type,
                    parent_index=parent_index,
                    sibling_index=sibling_index,
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
        timeout_budget_s = downloader.FORWARD_CONTEXT_TIMEOUT_S
        started = time.perf_counter()
        for parent_index in range(parents):
            for sibling_index in range(siblings_per_parent):
                request = build_forward_timeout_request(
                    asset_type=normalized_asset_type,
                    parent_index=parent_index,
                    sibling_index=sibling_index,
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
        ("public-token", "video", 1, 12),
        ("public-token", "video", 12, 1),
        ("forward-materialize", "video", 1, 12),
        ("forward-materialize", "video", 12, 1),
        ("public-token", "speech", 1, 8),
        ("public-token", "speech", 8, 1),
    ]
    return [
        run_forward_timeout_simulation(
            route=route,
            asset_type=asset_type,
            parents=parents,
            siblings_per_parent=siblings_per_parent,
            delay_s=delay_s,
        )
        for route, asset_type, parents, siblings_per_parent in scenarios
    ]


def write_simulation_trace(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
