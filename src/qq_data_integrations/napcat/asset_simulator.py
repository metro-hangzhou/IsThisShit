from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import asdict, dataclass
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
        self._scenario_state.remote_attempts.append(
            {
                "asset_type": asset_type,
                "file_name": file_name,
                "remote_url": resolved_remote_url or remote_url,
            }
        )
        if not resolved_remote_url:
            return None
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
        self._scenario_state.remote_attempts.append(
            {
                "asset_type": "sticker",
                "file_name": file_name,
                "remote_url": resolved_remote_url or remote_url,
            }
        )
        if not resolved_remote_url:
            return None
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
                        max_fast_calls=2,
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
