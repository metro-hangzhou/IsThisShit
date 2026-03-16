from __future__ import annotations

import importlib.metadata as importlib_metadata
import locale
import os
import platform
import shutil
import socket
import struct
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

import orjson

from qq_data_integrations import discover_qq_media_roots
from qq_data_integrations.napcat import (
    NapCatSettings,
    collect_debug_preflight_evidence,
    get_latest_napcat_launch_log_path,
)
from qq_data_cli.logging_utils import get_cli_log_path, get_cli_logger
from qq_data_cli.terminal_compat import TerminalProbe, TerminalUiDecision

_SESSION_CAPTURE_PATH: Path | None = None
_SESSION_CAPTURE_LOCK = Lock()
_MAX_QQ_ROOT_SNAPSHOTS = 8
_MAX_DIR_ENTRIES = 24
_MAX_NESTED_ENTRIES = 12
_MAX_LOG_TAIL_LINES = 80
_MAX_JSON_STRING = 400
_PACKAGE_VERSION_KEYS = (
    "typer",
    "rich",
    "prompt-toolkit",
    "httpx",
    "orjson",
    "pydantic",
    "websockets",
)
_ENV_KEYS = (
    "PROJECT_ROOT",
    "EXPORT_DIR",
    "STATE_DIR",
    "QQ_MEDIA_ROOTS",
    "NAPCAT_DIR",
    "NAPCAT_LAUNCHER",
    "NAPCAT_WORKDIR",
    "NAPCAT_HTTP_URL",
    "NAPCAT_WS_URL",
    "NAPCAT_WEBUI_URL",
    "NAPCAT_FAST_HISTORY_MODE",
    "NAPCAT_FAST_HISTORY_URL",
    "NAPCAT_FAST_HISTORY_PLUGIN_ID",
    "NAPCAT_AUTO_START",
    "NAPCAT_USE_SYSTEM_PROXY",
    "CLI_UI_MODE",
    "WT_SESSION",
    "TERM",
    "TERM_PROGRAM",
    "COMSPEC",
    "OS",
    "PROCESSOR_IDENTIFIER",
    "NUMBER_OF_PROCESSORS",
)


def capture_startup_snapshot(
    settings: NapCatSettings,
    *,
    terminal_probe: TerminalProbe | None = None,
    ui_decision: TerminalUiDecision | None = None,
) -> Path | None:
    global _SESSION_CAPTURE_PATH

    with _SESSION_CAPTURE_LOCK:
        if _SESSION_CAPTURE_PATH is not None and _SESSION_CAPTURE_PATH.exists():
            return _SESSION_CAPTURE_PATH
        try:
            capture_dir = settings.state_dir / "startup_capture"
            capture_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
            capture_path = capture_dir / f"startup_{stamp}.json"
            payload = _build_startup_payload(
                settings,
                terminal_probe=terminal_probe,
                ui_decision=ui_decision,
            )
            encoded = orjson.dumps(payload, option=orjson.OPT_INDENT_2)
            capture_path.write_bytes(encoded)
            (capture_dir / "latest.json").write_bytes(encoded)
            (capture_dir / "latest.path").write_text(str(capture_path), encoding="utf-8")
            _SESSION_CAPTURE_PATH = capture_path
            get_cli_logger("startup_capture").info("startup_capture_ready path=%s", capture_path)
            return capture_path
        except Exception:
            get_cli_logger("startup_capture").exception("startup_capture_failed")
            return None


def get_session_startup_capture_path() -> Path | None:
    return _SESSION_CAPTURE_PATH


def get_latest_startup_capture_path(state_dir: Path) -> Path | None:
    session_path = _SESSION_CAPTURE_PATH
    if session_path is not None and session_path.exists():
        return session_path
    latest_path = state_dir / "startup_capture" / "latest.path"
    try:
        if latest_path.exists():
            resolved = Path(latest_path.read_text(encoding="utf-8").strip())
            if resolved.exists():
                return resolved
    except OSError:
        return None
    return None


def _build_startup_payload(
    settings: NapCatSettings,
    *,
    terminal_probe: TerminalProbe | None,
    ui_decision: TerminalUiDecision | None,
) -> dict[str, Any]:
    roots = discover_qq_media_roots()
    probe_payload = terminal_probe
    decision_payload = ui_decision
    return {
        "captured_at": datetime.now().astimezone().isoformat(),
        "process": {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "cwd": str(Path.cwd()),
            "argv": sys.argv,
        },
        "system": {
            "platform_system": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "platform_machine": platform.machine(),
            "platform_processor": platform.processor(),
            "hostname": socket.gethostname(),
            "username": os.getenv("USERNAME") or os.getenv("USER") or "",
            "preferred_encoding": locale.getpreferredencoding(False) or "",
            "filesystem_encoding": sys.getfilesystemencoding() or "",
        },
        "hardware": {
            "cpu_count_logical": os.cpu_count() or 0,
            "python_architecture_bits": struct.calcsize("P") * 8,
            "memory": _memory_snapshot(),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro,
                "releaselevel": sys.version_info.releaselevel,
                "serial": sys.version_info.serial,
            },
            "implementation": platform.python_implementation(),
            "prefix": sys.prefix,
            "base_prefix": getattr(sys, "base_prefix", sys.prefix),
            "in_virtual_env": getattr(sys, "base_prefix", sys.prefix) != sys.prefix,
            "packages": _package_versions(),
            "sys_path": list(sys.path),
        },
        "selected_env": {key: os.getenv(key) for key in _ENV_KEYS if os.getenv(key) is not None},
        "cli": {
            "log_path": str(get_cli_log_path()) if get_cli_log_path() is not None else None,
            "startup_capture_dir": str(settings.state_dir / "startup_capture"),
        },
        "storage": _storage_snapshot(settings, roots),
        "napcat": {
            "project_root": str(settings.project_root),
            "export_dir": str(settings.export_dir),
            "state_dir": str(settings.state_dir),
            "http_url": settings.http_url,
            "ws_url": settings.ws_url,
            "webui_url": settings.webui_url,
            "auto_start_napcat": settings.auto_start_napcat,
            "use_system_proxy": settings.use_system_proxy,
            "fast_history_mode": settings.fast_history_mode,
            "fast_history_url": settings.fast_history_url,
            "fast_history_plugin_id": settings.fast_history_plugin_id,
            "latest_napcat_log_path": str(get_latest_napcat_launch_log_path(settings.state_dir) or ""),
            "config_snapshots": _napcat_config_snapshots(settings),
            "plugin_directory_snapshots": _napcat_plugin_snapshots(settings),
            **collect_debug_preflight_evidence(settings),
        },
        "logs": _log_snapshot(settings),
        "terminal": {
            "probe": asdict(probe_payload) if probe_payload is not None else None,
            "ui_decision": asdict(decision_payload) if decision_payload is not None else None,
        },
        "qq_media_roots": {
            "count": len(roots),
            "roots": [str(root) for root in roots],
            "snapshots": [_snapshot_qq_root(root) for root in roots[:_MAX_QQ_ROOT_SNAPSHOTS]],
        },
    }


def _memory_snapshot() -> dict[str, int] | None:
    if platform.system() != "Windows":
        return None
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return {
            "memory_load_percent": int(status.dwMemoryLoad),
            "total_physical_bytes": int(status.ullTotalPhys),
            "available_physical_bytes": int(status.ullAvailPhys),
            "total_pagefile_bytes": int(status.ullTotalPageFile),
            "available_pagefile_bytes": int(status.ullAvailPageFile),
            "total_virtual_bytes": int(status.ullTotalVirtual),
            "available_virtual_bytes": int(status.ullAvailVirtual),
        }
    except Exception:
        return None


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package_name in _PACKAGE_VERSION_KEYS:
        try:
            versions[package_name] = importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError:
            versions[package_name] = "missing"
        except Exception as exc:
            versions[package_name] = f"error:{exc}"
    return versions


def _snapshot_qq_root(root: Path) -> dict[str, Any]:
    return {
        "root": str(root),
        "exists": root.exists(),
        "entries": _directory_entries(root, limit=_MAX_DIR_ENTRIES),
        "interesting_paths": _interesting_qq_paths(root),
    }


def _interesting_qq_paths(root: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    seen: set[Path] = set()
    candidate_bases = [root]
    try:
        for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
            if not child.is_dir():
                continue
            child_name = child.name.casefold()
            if child.name.isdigit() or child_name in {"nt_qq", "qq", "qqnt"}:
                candidate_bases.append(child)
    except OSError:
        return snapshots

    suffixes = [
        (),
        ("nt_qq",),
        ("nt_qq", "nt_data"),
        ("nt_qq", "nt_data", "Pic"),
        ("nt_qq", "nt_data", "Video"),
        ("nt_qq", "nt_data", "FileRecv"),
        ("nt_qq", "nt_data", "Emoji"),
        ("nt_qq", "nt_data", "Record"),
        ("nt_data",),
        ("nt_data", "Pic"),
        ("nt_data", "Video"),
        ("nt_data", "FileRecv"),
        ("Pic",),
        ("Video",),
        ("FileRecv",),
        ("Emoji",),
    ]

    for base in candidate_bases:
        for suffix in suffixes:
            candidate = base.joinpath(*suffix)
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate
            if resolved in seen or not candidate.exists() or not candidate.is_dir():
                continue
            seen.add(resolved)
            snapshots.append(
                {
                    "path": str(candidate),
                    "entries": _directory_entries(candidate, limit=_MAX_NESTED_ENTRIES),
                }
            )
            if len(snapshots) >= _MAX_QQ_ROOT_SNAPSHOTS:
                return snapshots
    return snapshots


def _directory_entries(path: Path, *, limit: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        children = sorted(path.iterdir(), key=lambda child: (not child.is_dir(), child.name.lower()))
    except OSError as exc:
        return [{"name": "<error>", "detail": str(exc)}]

    for child in children[:limit]:
        entry: dict[str, Any] = {
            "name": child.name,
            "is_dir": child.is_dir(),
            "is_file": child.is_file(),
        }
        try:
            stat = child.stat()
        except OSError as exc:
            entry["detail"] = str(exc)
            entries.append(entry)
            continue
        if child.is_file():
            entry["size_bytes"] = int(stat.st_size)
        entry["modified_at"] = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
        entries.append(entry)
    return entries


def _storage_snapshot(settings: NapCatSettings, roots: list[Path]) -> list[dict[str, Any]]:
    candidates = [
        settings.project_root,
        settings.export_dir,
        settings.state_dir,
        *(roots[:_MAX_QQ_ROOT_SNAPSHOTS]),
    ]
    snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        anchor = _storage_anchor(resolved)
        if anchor in seen:
            continue
        seen.add(anchor)
        usage = _disk_usage(resolved)
        snapshots.append(
            {
                "anchor": anchor,
                "sample_path": str(resolved),
                **usage,
            }
        )
    return snapshots


def _storage_anchor(path: Path) -> str:
    drive = path.drive
    if drive:
        return drive.upper()
    return str(path.anchor or path)


def _disk_usage(path: Path) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_bytes": int(usage.total),
            "used_bytes": int(usage.used),
            "free_bytes": int(usage.free),
        }
    except OSError as exc:
        return {"detail": str(exc)}


def _napcat_config_snapshots(settings: NapCatSettings) -> list[dict[str, Any]]:
    candidates = [
        settings.onebot_config_path,
        settings.webui_config_path,
        _workdir_config_path(settings, "plugins.json"),
        _workdir_config_path(settings, "napcat.json"),
    ]
    snapshots: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        snapshots.append(_config_file_snapshot(resolved))
    return snapshots


def _napcat_plugin_snapshots(settings: NapCatSettings) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if settings.workdir is not None:
        paths.append(settings.workdir / "plugins")
        paths.append(settings.workdir / "config" / "plugins")
    snapshots: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists() or not path.is_dir():
            continue
        snapshots.append(
            {
                "path": str(path),
                "entries": _directory_entries(path, limit=_MAX_DIR_ENTRIES),
            }
        )
    return snapshots


def _workdir_config_path(settings: NapCatSettings, filename: str) -> Path | None:
    if settings.workdir is None:
        return None
    return settings.workdir / "config" / filename


def _config_file_snapshot(path: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        return snapshot
    try:
        stat = path.stat()
        snapshot["size_bytes"] = int(stat.st_size)
        snapshot["modified_at"] = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
        payload = orjson.loads(path.read_bytes())
        snapshot["content"] = _redact_json(payload)
        return snapshot
    except Exception as exc:
        snapshot["detail"] = str(exc)
        return snapshot


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).casefold()
            if "token" in lowered or "password" in lowered or "secret" in lowered:
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact_json(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json(item) for item in value[:64]]
    if isinstance(value, str):
        if len(value) > _MAX_JSON_STRING:
            return value[:_MAX_JSON_STRING] + "...<trimmed>"
        return value
    return value


def _log_snapshot(settings: NapCatSettings) -> dict[str, Any]:
    cli_latest = settings.state_dir / "logs" / "cli_latest.log"
    napcat_latest = get_latest_napcat_launch_log_path(settings.state_dir)
    return {
        "cli_latest_log_path": str(cli_latest) if cli_latest.exists() else None,
        "cli_latest_log_tail": _tail_text(cli_latest),
        "napcat_latest_log_path": str(napcat_latest) if napcat_latest is not None else None,
        "napcat_latest_log_tail": _tail_text(napcat_latest) if napcat_latest is not None else [],
    }


def _tail_text(path: Path | None, *, max_lines: int = _MAX_LOG_TAIL_LINES) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-max_lines:]
    except OSError as exc:
        return [f"<error reading log: {exc}>"]
