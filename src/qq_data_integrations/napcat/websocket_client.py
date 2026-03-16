from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import orjson
import websockets


class NapCatWebSocketError(RuntimeError):
    pass


class NapCatWebSocketClient:
    def __init__(
        self,
        url: str,
        *,
        access_token: str | None = None,
        use_system_proxy: bool = False,
        reconnect_delay: float = 1.0,
        max_retries: int | None = None,
        open_timeout: float = 10.0,
        ping_interval: float = 20.0,
    ) -> None:
        self._url = url
        self._access_token = access_token
        self._use_system_proxy = use_system_proxy
        self._reconnect_delay = reconnect_delay
        self._max_retries = max_retries
        self._open_timeout = open_timeout
        self._ping_interval = ping_interval

    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        attempts = 0
        headers = {}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        while True:
            try:
                async with websockets.connect(
                    self._url,
                    additional_headers=headers or None,
                    proxy=True if self._use_system_proxy else None,
                    open_timeout=self._open_timeout,
                    ping_interval=self._ping_interval,
                ) as connection:
                    attempts = 0
                    async for payload in connection:
                        text = payload.decode("utf-8", "ignore") if isinstance(payload, bytes) else payload
                        try:
                            data = orjson.loads(text)
                        except orjson.JSONDecodeError:
                            continue
                        if isinstance(data, dict):
                            yield data
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempts += 1
                if self._max_retries is not None and attempts > self._max_retries:
                    raise NapCatWebSocketError(f"NapCat WebSocket failed after {attempts} attempts") from exc
                await asyncio.sleep(self._reconnect_delay)
