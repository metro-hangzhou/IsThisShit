from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from qq_data_core.models import WatchRequest


class EventStreamClient(Protocol):
    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        ...


class NapCatRealtimeProvider:
    def __init__(self, client: EventStreamClient) -> None:
        self._client = client

    async def watch(self, request: WatchRequest) -> AsyncIterator[dict[str, Any]]:
        async for event in self._client.iter_events():
            if not self._is_watch_event(event):
                continue
            if self._resolve_chat_type(event) != request.chat_type:
                continue
            if self._resolve_chat_id(event) != request.chat_id:
                continue
            yield event

    def _is_watch_event(self, event: dict[str, Any]) -> bool:
        post_type = event.get("post_type")
        if post_type in {"message", "message_sent"}:
            return event.get("message_type") in {"group", "private"}
        return post_type == "notice"

    def _resolve_chat_type(self, event: dict[str, Any]) -> str:
        if event.get("post_type") in {"message", "message_sent"}:
            return "group" if event.get("message_type") == "group" else "private"
        return "group" if event.get("group_id") is not None else "private"

    def _resolve_chat_id(self, event: dict[str, Any]) -> str:
        if event.get("post_type") in {"message", "message_sent"}:
            value = event.get("group_id") if event.get("message_type") == "group" else event.get("user_id")
            return str(value or "")
        if event.get("group_id") is not None:
            return str(event.get("group_id") or "")
        for key in ("peer_id", "user_id", "sender_id", "target_id"):
            value = event.get(key)
            if value is not None:
                return str(value or "")
        return ""
