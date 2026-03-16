from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from .diagnostics import probe_endpoint
from .settings import NapCatSettings


EndpointName = Literal["webui", "onebot_http", "onebot_ws"]


class NapCatLaunchInfo(BaseModel):
    napcat_dir: Path | None = None
    launcher_path: Path | None = None
    launchable: bool = False
    reason: str | None = None


class NapCatStartResult(BaseModel):
    endpoint: EndpointName
    already_running: bool = False
    attempted_start: bool = False
    attempted_configure: bool = False
    ready: bool = False
    launcher_path: Path | None = None
    napcat_log_path: Path | None = None
    message: str = ""


class NapCatRuntimeStarter:
    def __init__(
        self,
        settings: NapCatSettings,
        *,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        launch_process: Callable[[Path], Path | None] | None = None,
    ) -> None:
        self._settings = settings
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep
        self._launch_process = launch_process or (
            lambda launcher_path: _launch_napcat_process(launcher_path, settings.state_dir)
        )

    def describe_launch(self) -> NapCatLaunchInfo:
        launcher_path = self._settings.napcat_launcher_path
        napcat_dir = self._settings.napcat_dir
        if napcat_dir is None:
            return NapCatLaunchInfo(reason="No NapCat directory configured.")
        if launcher_path is None:
            return NapCatLaunchInfo(
                napcat_dir=napcat_dir,
                reason="No launcher script found under the configured NapCat directory.",
            )
        if not _looks_like_launchable_runtime(launcher_path):
            return NapCatLaunchInfo(
                napcat_dir=napcat_dir,
                launcher_path=launcher_path,
                reason="Launcher exists, but the directory does not look like a runnable NapCat release.",
            )
        return NapCatLaunchInfo(
            napcat_dir=napcat_dir,
            launcher_path=launcher_path,
            launchable=True,
        )

    def ensure_endpoint(
        self,
        endpoint: EndpointName,
        *,
        timeout_seconds: float = 20.0,
        poll_interval: float = 0.5,
    ) -> NapCatStartResult:
        url = _endpoint_url(self._settings, endpoint)
        current = probe_endpoint(endpoint, url)
        if current.listening:
            return NapCatStartResult(
                endpoint=endpoint,
                already_running=True,
                ready=True,
                launcher_path=self._settings.napcat_launcher_path,
                message=f"{endpoint} already listening at {url}",
            )

        if endpoint != "webui":
            for sibling in ("webui", "onebot_http", "onebot_ws"):
                if sibling == endpoint:
                    continue
                sibling_probe = probe_endpoint(sibling, _endpoint_url(self._settings, sibling))
                if sibling_probe.listening:
                    return NapCatStartResult(
                        endpoint=endpoint,
                        launcher_path=self._settings.napcat_launcher_path,
                        message=(
                            f"NapCat is already running, but {endpoint} is not listening at {url}. "
                            "Enable the matching OneBot server in NapCat, or let the CLI configure it after /login."
                        ),
                    )

        launch_info = self.describe_launch()
        if not self._settings.auto_start_napcat:
            return NapCatStartResult(
                endpoint=endpoint,
                launcher_path=launch_info.launcher_path,
                message=f"{endpoint} is not listening and auto-start is disabled.",
            )
        if not launch_info.launchable or launch_info.launcher_path is None:
            return NapCatStartResult(
                endpoint=endpoint,
                launcher_path=launch_info.launcher_path,
                message=launch_info.reason or f"{endpoint} is not listening and no launchable NapCat runtime was found.",
            )

        napcat_log_path = self._launch_process(launch_info.launcher_path)
        deadline = self._monotonic() + timeout_seconds
        while self._monotonic() < deadline:
            self._sleep(poll_interval)
            probe = probe_endpoint(endpoint, url)
            if probe.listening:
                return NapCatStartResult(
                    endpoint=endpoint,
                    attempted_start=True,
                    ready=True,
                    launcher_path=launch_info.launcher_path,
                    napcat_log_path=napcat_log_path,
                    message=_append_napcat_log_hint(
                        f"Started NapCat via {launch_info.launcher_path}",
                        napcat_log_path,
                    ),
                )
        return NapCatStartResult(
            endpoint=endpoint,
            attempted_start=True,
            launcher_path=launch_info.launcher_path,
            napcat_log_path=napcat_log_path,
            message=_append_napcat_log_hint(
                f"Tried to start NapCat via {launch_info.launcher_path}, but {endpoint} at {url} "
                "did not become ready in time.",
                napcat_log_path,
            ),
        )


def _endpoint_url(settings: NapCatSettings, endpoint: EndpointName) -> str:
    if endpoint == "webui":
        return settings.webui_url
    if endpoint == "onebot_http":
        return settings.http_url
    return settings.ws_url


def _looks_like_launchable_runtime(launcher_path: Path) -> bool:
    launcher_dir = launcher_path.parent
    node_runtime_files = [
        launcher_dir / "node.exe",
        launcher_dir / "index.js",
        launcher_dir / "wrapper.node",
        launcher_dir / "napcat" / "napcat.mjs",
    ]
    if all(path.exists() for path in node_runtime_files):
        return True
    release_files = [
        launcher_dir / "NapCatWinBootMain.exe",
        launcher_dir / "NapCatWinBootHook.dll",
    ]
    if all(path.exists() for path in release_files):
        return True
    source_files = [
        launcher_dir / "NapCatWinBootMain.exe",
        launcher_dir / "NapCatWinBootHook.dll",
        launcher_dir / "qqnt.json",
        launcher_dir / "napcat.mjs",
    ]
    return all(path.exists() for path in source_files)


def _launch_napcat_process(launcher_path: Path, state_dir: Path) -> Path | None:
    log_path, wrapper_path = _prepare_napcat_launch_artifacts(launcher_path, state_dir)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["cmd.exe", "/d", "/c", str(wrapper_path)],
        cwd=str(launcher_path.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return log_path


def _prepare_napcat_launch_artifacts(launcher_path: Path, state_dir: Path) -> tuple[Path, Path]:
    logs_dir = state_dir / "napcat_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"napcat_{stamp}.log"
    wrapper_path = logs_dir / f"launch_napcat_{stamp}.cmd"
    latest_pointer_path = logs_dir / "latest.path"
    latest_pointer_path.write_text(str(log_path), encoding="utf-8")
    wrapper_path.write_text(
        "\n".join(
            [
                "@echo off",
                f'cd /d "{launcher_path.parent}"',
                f'call "{launcher_path}" >> "{log_path}" 2>&1',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return log_path, wrapper_path


def _append_napcat_log_hint(message: str, log_path: Path | None) -> str:
    if log_path is None:
        return message
    return f"{message} NapCat log: {log_path}"


def get_latest_napcat_launch_log_path(state_dir: Path) -> Path | None:
    latest_pointer_path = state_dir / "napcat_logs" / "latest.path"
    if not latest_pointer_path.exists():
        return None
    try:
        raw = latest_pointer_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    return Path(raw)
