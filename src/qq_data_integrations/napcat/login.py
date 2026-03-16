from __future__ import annotations

import time
from collections.abc import Callable

from .models import NapCatLoginInfo, NapCatLoginStatus
from .webui_client import NapCatWebUiClient


QrCallback = Callable[[str], None]
StatusCallback = Callable[[NapCatLoginStatus], None]


class NapCatQrLoginService:
    def __init__(
        self,
        client: NapCatWebUiClient,
        *,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep

    def check_status(self) -> NapCatLoginStatus:
        return self._client.check_login_status()

    def get_login_info(self) -> NapCatLoginInfo:
        return self._client.get_login_info()

    def login_until_success(
        self,
        *,
        timeout_seconds: float = 300.0,
        poll_interval: float = 3.0,
        refresh: bool = False,
        on_qrcode: QrCallback | None = None,
        on_status: StatusCallback | None = None,
    ) -> NapCatLoginInfo:
        status = self._client.check_login_status()
        if status.effectively_logged_in():
            return self._client.get_login_info()

        if refresh or not status.qrcode_url:
            self._client.refresh_qrcode()
            status = self._client.check_login_status()

        qrcode_url = status.qrcode_url or self._client.get_qrcode()
        if on_qrcode:
            on_qrcode(qrcode_url)
        if on_status:
            on_status(status)

        last_qrcode = qrcode_url
        last_error = status.login_error or ""
        deadline = self._monotonic() + timeout_seconds

        while self._monotonic() < deadline:
            self._sleep(poll_interval)
            status = self._client.check_login_status()
            if status.effectively_logged_in():
                return self._client.get_login_info()

            next_error = status.login_error or ""
            if next_error != last_error:
                last_error = next_error
                if on_status:
                    on_status(status)

            if status.qr_expired():
                self._client.refresh_qrcode()
                status = self._client.check_login_status()

            next_qrcode = status.qrcode_url or last_qrcode
            if next_qrcode and next_qrcode != last_qrcode:
                last_qrcode = next_qrcode
                if on_qrcode:
                    on_qrcode(next_qrcode)

        raise TimeoutError("Timed out waiting for QQ QR login confirmation")
