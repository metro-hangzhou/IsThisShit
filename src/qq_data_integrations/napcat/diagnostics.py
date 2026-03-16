from __future__ import annotations

import socket
from urllib.parse import urlparse

from pydantic import BaseModel

from .fast_history_client import NapCatFastHistoryClient
from .settings import NapCatSettings


class NapCatEndpointProbe(BaseModel):
    name: str
    url: str
    host: str
    port: int
    listening: bool
    detail: str | None = None


class NapCatRouteProbe(BaseModel):
    name: str
    method: str
    path: str
    reachable: bool
    status_code: int | None = None
    detail: str | None = None
    timed_out: bool = False
    connect_error: bool = False
    elapsed_ms: int | None = None


def probe_settings_endpoints(settings: NapCatSettings, *, timeout: float = 0.25) -> list[NapCatEndpointProbe]:
    return [
        probe_endpoint("webui", settings.webui_url, timeout=timeout),
        probe_endpoint("onebot_http", settings.http_url, timeout=timeout),
        probe_endpoint("onebot_ws", settings.ws_url, timeout=timeout),
    ]


def collect_debug_preflight_evidence(
    settings: NapCatSettings,
    *,
    timeout: float = 0.5,
) -> dict[str, object]:
    endpoint_probes = [probe.model_dump(mode="json") for probe in probe_settings_endpoints(settings, timeout=timeout)]
    return {
        "endpoint_probes": endpoint_probes,
        "path_matrix": collect_path_matrix(settings),
        "capability_matrix": {
            "fast_history_plugin": collect_fast_history_route_matrix(settings, timeout=timeout),
        },
    }


def collect_path_matrix(settings: NapCatSettings) -> list[dict[str, object]]:
    plugin_candidates = _plugin_path_candidates(settings)
    path_specs = [
        ("project_root", settings.project_root),
        ("export_dir", settings.export_dir),
        ("state_dir", settings.state_dir),
        ("napcat_dir", settings.napcat_dir),
        ("napcat_launcher_path", settings.napcat_launcher_path),
        ("workdir", settings.workdir),
        ("onebot_config_path", settings.onebot_config_path),
        ("webui_config_path", settings.webui_config_path),
        *[(f"fast_history_plugin_path[{index}]", path) for index, path in enumerate(plugin_candidates, start=1)],
    ]
    return [_path_probe(label, path) for label, path in path_specs]


def collect_fast_history_route_matrix(
    settings: NapCatSettings,
    *,
    timeout: float = 0.5,
) -> dict[str, object]:
    if settings.fast_history_mode == "off":
        return {
            "enabled": False,
            "base_url": settings.fast_history_url,
            "plugin_id": settings.fast_history_plugin_id,
            "routes": [],
        }
    if not settings.fast_history_url:
        return {
            "enabled": False,
            "base_url": None,
            "plugin_id": settings.fast_history_plugin_id,
            "routes": [],
        }

    client = NapCatFastHistoryClient(
        settings.fast_history_url,
        use_system_proxy=settings.use_system_proxy,
        timeout=timeout,
    )
    try:
        health = _safe_health(client)
        capabilities = _safe_capabilities(client)
    finally:
        client.close()

    return {
        "enabled": True,
        "base_url": settings.fast_history_url,
        "plugin_id": settings.fast_history_plugin_id,
        "health": health,
        "capabilities_source": "plugin_route" if capabilities.get("reachable") else "fallback",
        "routes": capabilities.get("routes", []),
    }


def probe_endpoint(name: str, url: str, *, timeout: float = 0.25) -> NapCatEndpointProbe:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or _default_port(parsed.scheme)
    listening, detail = _try_connect(host, port, timeout=timeout)
    return NapCatEndpointProbe(
        name=name,
        url=url,
        host=host,
        port=port,
        listening=listening,
        detail=detail,
    )


def _default_port(scheme: str) -> int:
    if scheme in {"https", "wss"}:
        return 443
    return 80


def _try_connect(host: str, port: int, *, timeout: float) -> tuple[bool, str | None]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except OSError as exc:
        return False, str(exc)


def _safe_health(client: NapCatFastHistoryClient) -> dict[str, object]:
    try:
        payload = client.health()
        return {
            "reachable": True,
            "status": "ok",
            "payload": payload,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "status": "error",
            "detail": str(exc),
        }


def _safe_capabilities(client: NapCatFastHistoryClient) -> dict[str, object]:
    try:
        payload = client.capabilities()
    except Exception as exc:
        return {
            "reachable": False,
            "detail": str(exc),
            "routes": [
                NapCatRouteProbe(name="health", method="GET", path="/health", reachable=True).model_dump(mode="json"),
            ],
        }
    routes = []
    for item in payload.get("routes", []):
        if not isinstance(item, dict):
            continue
        routes.append(
            NapCatRouteProbe(
                name=str(item.get("name") or "").strip() or "unknown",
                method=str(item.get("method") or "").strip() or "GET",
                path=str(item.get("path") or "").strip() or "/",
                reachable=True,
            ).model_dump(mode="json")
        )
    return {
        "reachable": True,
        "routes": routes,
    }


def _plugin_path_candidates(settings: NapCatSettings) -> list[object]:
    candidates = []
    if settings.napcat_dir is not None:
        candidates.extend(
            [
                settings.napcat_dir / "napcat" / "plugins" / settings.fast_history_plugin_id,
                settings.napcat_dir / "plugins" / settings.fast_history_plugin_id,
            ]
        )
    if settings.workdir is not None:
        candidates.append(settings.workdir / "plugins" / settings.fast_history_plugin_id)
    deduped = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(candidate)
    return deduped


def _path_probe(label: str, path) -> dict[str, object]:
    if path is None:
        return {
            "label": label,
            "path": None,
            "exists": False,
            "is_dir": False,
            "is_file": False,
        }
    try:
        exists = path.exists()
        is_dir = path.is_dir() if exists else False
        is_file = path.is_file() if exists else False
    except OSError as exc:
        return {
            "label": label,
            "path": str(path),
            "exists": False,
            "is_dir": False,
            "is_file": False,
            "detail": str(exc),
        }
    return {
        "label": label,
        "path": str(path),
        "exists": exists,
        "is_dir": is_dir,
        "is_file": is_file,
    }
