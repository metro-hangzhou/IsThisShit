from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .diagnostics import probe_endpoint
from .runtime import EndpointName, NapCatStartResult, NapCatRuntimeStarter
from .settings import NapCatSettings
from .webui_client import NapCatWebUiClient, NapCatWebUiError


class NapCatBootstrapper:
    def __init__(
        self,
        settings: NapCatSettings,
        *,
        runtime_starter: NapCatRuntimeStarter | None = None,
        settings_loader: Callable[[], NapCatSettings] | None = None,
        webui_client_factory: Callable[[NapCatSettings], NapCatWebUiClient] | None = None,
        probe: Callable[[str, str, float], Any] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings
        self._runtime_starter = runtime_starter or NapCatRuntimeStarter(settings)
        self._settings_loader = settings_loader or NapCatSettings.from_env
        self._webui_client_factory = webui_client_factory or _default_webui_client_factory
        self._probe = probe or _default_probe
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep

    def ensure_endpoint(
        self,
        endpoint: EndpointName,
        *,
        timeout_seconds: float = 20.0,
        poll_interval: float = 0.5,
    ) -> NapCatStartResult:
        result = self._runtime_starter.ensure_endpoint(
            endpoint,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
        )
        if result.ready or endpoint == "webui":
            return result

        webui_result = self._runtime_starter.ensure_endpoint(
            "webui",
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
        )
        if not webui_result.ready:
            return result

        refreshed_settings = self._settings_loader()
        client = self._webui_client_factory(refreshed_settings)
        try:
            status = client.check_login_status()
            if not status.effectively_logged_in():
                return NapCatStartResult(
                    endpoint=endpoint,
                    attempted_start=result.attempted_start or webui_result.attempted_start,
                    launcher_path=refreshed_settings.napcat_launcher_path,
                    napcat_log_path=result.napcat_log_path or webui_result.napcat_log_path,
                    message=(
                        "NapCat WebUI is running, but QQ is not logged in. "
                        "Run /login first, then retry the command."
                        + _napcat_log_hint(result.napcat_log_path or webui_result.napcat_log_path)
                    ),
                )

            changed = client.ensure_default_onebot_servers(
                http_url=refreshed_settings.http_url,
                ws_url=refreshed_settings.ws_url,
                token=refreshed_settings.access_token,
            )
        except NapCatWebUiError as exc:
            return NapCatStartResult(
                endpoint=endpoint,
                attempted_start=result.attempted_start or webui_result.attempted_start,
                launcher_path=refreshed_settings.napcat_launcher_path,
                napcat_log_path=result.napcat_log_path or webui_result.napcat_log_path,
                message=str(exc) + _napcat_log_hint(result.napcat_log_path or webui_result.napcat_log_path),
            )
        finally:
            client.close()

        refreshed_settings = self._settings_loader()
        deadline = self._monotonic() + timeout_seconds
        endpoint_url = _endpoint_url(refreshed_settings, endpoint)
        while self._monotonic() < deadline:
            probe = self._probe(endpoint, endpoint_url, 0.25)
            if probe.listening:
                return NapCatStartResult(
                    endpoint=endpoint,
                    attempted_start=result.attempted_start or webui_result.attempted_start,
                    attempted_configure=changed,
                    ready=True,
                    launcher_path=refreshed_settings.napcat_launcher_path,
                    napcat_log_path=result.napcat_log_path or webui_result.napcat_log_path,
                    message=(
                        f"{endpoint} is ready at {endpoint_url}"
                        if not changed
                        else f"Enabled default OneBot HTTP/WS servers and {endpoint} is ready at {endpoint_url}"
                    )
                    + _napcat_log_hint(result.napcat_log_path or webui_result.napcat_log_path),
                )
            self._sleep(poll_interval)

        return NapCatStartResult(
            endpoint=endpoint,
            attempted_start=result.attempted_start or webui_result.attempted_start,
            attempted_configure=changed,
            launcher_path=refreshed_settings.napcat_launcher_path,
            napcat_log_path=result.napcat_log_path or webui_result.napcat_log_path,
            message=(
                f"NapCat WebUI is running, but {endpoint} is still not listening at {endpoint_url}. "
                "Check the OneBot network config in NapCat."
            )
            + _napcat_log_hint(result.napcat_log_path or webui_result.napcat_log_path),
        )


def _default_webui_client_factory(settings: NapCatSettings) -> NapCatWebUiClient:
    return NapCatWebUiClient(
        settings.webui_url,
        raw_token=settings.webui_token,
        use_system_proxy=settings.use_system_proxy,
    )


def _default_probe(name: str, url: str, timeout: float):
    return probe_endpoint(name, url, timeout=timeout)


def _endpoint_url(settings: NapCatSettings, endpoint: EndpointName) -> str:
    if endpoint == "webui":
        return settings.webui_url
    if endpoint == "onebot_http":
        return settings.http_url
    return settings.ws_url


def _napcat_log_hint(log_path) -> str:
    if not log_path:
        return ""
    return f" NapCat log: {log_path}"
