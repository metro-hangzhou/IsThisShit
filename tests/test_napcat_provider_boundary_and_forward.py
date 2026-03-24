from __future__ import annotations

from datetime import datetime
from threading import Lock
import time

from qq_data_core.models import EXPORT_TIMEZONE, ExportRequest, SourceChatSnapshot
from qq_data_integrations.napcat.http_client import NapCatApiError
from qq_data_integrations.napcat.provider import FORWARD_ELEMENT_TYPE, NapCatHistoryProvider


class _DummyClient:
    def get_forward_msg(self, message_id: str):
        raise NotImplementedError


class _ConcurrentFastPluginClient:
    def __init__(self, *, delay_s: float = 0.02) -> None:
        self.delay_s = delay_s
        self.calls: list[dict[str, object]] = []
        self.active = 0
        self.max_active = 0
        self._lock = Lock()

    def hydrate_forward_detail(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay_s)
            return {
                "messages": [
                    {
                        "message_id": f"nested-{len(self.calls)}",
                        "message_seq": "1",
                        "sender": {"uin": "42", "nickname": "Alice"},
                        "rawMessage": {
                            "msgId": "nested",
                            "msgSeq": "1",
                            "senderUin": "42",
                            "sendNickName": "Alice",
                            "peerUid": "922065597",
                            "chatType": 2,
                            "elements": [
                                {
                                    "elementType": 1,
                                    "textElement": {"content": "hello from plugin"},
                                }
                            ],
                        },
                    }
                ]
            }
        finally:
            with self._lock:
                self.active -= 1


def _request() -> ExportRequest:
    return ExportRequest(chat_type="group", chat_id="922065597", chat_name="test", limit=3)


def _message(message_id: str, seq: str) -> dict[str, object]:
    second = int(seq) % 60
    return {
        "message_id": message_id,
        "message_seq": seq,
        "time": 1750000000 + int(seq),
        "timestamp_iso": f"2025-09-02T00:00:{second:02d}+08:00",
    }


def _forward_reference_message(message_id: str, seq: str) -> dict[str, object]:
    message = _message(message_id, seq)
    message["raw_message"] = {
        "msgId": message_id,
        "msgSeq": seq,
        "elements": [
            {
                "elementType": FORWARD_ELEMENT_TYPE,
                "multiForwardMsgElement": {"resId": f"forward-{message_id}"},
            }
        ],
    }
    return message


def _plugin_forward_target(message_id: str, seq: str) -> dict[str, object]:
    return {
        "message_id": message_id,
        "message_seq": seq,
        "raw_message": {
            "msgId": message_id,
            "msgSeq": seq,
            "peerUid": "922065597",
            "chatType": 2,
            "elements": [
                {
                    "elementType": FORWARD_ELEMENT_TYPE,
                    "elementId": f"elem-{message_id}",
                    "multiForwardMsgElement": {"resId": f"fwd-{message_id}"},
                }
            ],
        },
    }


def _snapshot(messages: list[dict[str, object]], *, source: str = "napcat_fast_history") -> SourceChatSnapshot:
    return SourceChatSnapshot(
        chat_type="group",
        chat_id="922065597",
        chat_name="test",
        exported_at=datetime.now(EXPORT_TIMEZONE),
        metadata={"source": source},
        messages=messages,
    )


def test_collect_fast_history_tail_bulk_bridges_duplicate_anchor_boundary() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    payloads = iter(
        [
            {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
            {
                "messages": [_message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
        ]
    )

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        try:
            return next(payloads)
        except StopIteration:
            return None

    def fake_fetch_history_page(*args, **kwargs):
        return (
            _snapshot([_message("m3", "3")]),
            {
                "history_source": "napcat_fast_history",
                "page_duration_s": 0.01,
                "page_size": 1,
                "page_message_count": 1,
                "retry_count": 0,
            },
        )

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]
    provider._fetch_history_page = fake_fetch_history_page  # type: ignore[method-assign]

    state = provider._collect_fast_history_tail_bulk(
        _request(),
        data_count=3,
        page_size=200,
        progress_callback=None,
    )

    assert state is not None
    assert state["completed"] is True
    assert state["partial_fallback"] is False
    assert state["history_source"] == "napcat_fast_history_bulk+napcat_fast_history"
    assert [item["message_id"] for item in state["messages"]] == ["m1", "m2", "m3"]


def test_collect_fast_history_tail_bulk_boundary_bridge_keeps_fallback_when_no_progress() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    payloads = iter(
        [
            {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
            {
                "messages": [_message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
        ]
    )

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        try:
            return next(payloads)
        except StopIteration:
            return None

    def fake_fetch_history_page(*args, **kwargs):
        return (
            _snapshot([_message("m2", "2")]),
            {
                "history_source": "napcat_fast_history",
                "page_duration_s": 0.01,
                "page_size": 1,
                "page_message_count": 1,
                "retry_count": 0,
            },
        )

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]
    provider._fetch_history_page = fake_fetch_history_page  # type: ignore[method-assign]

    state = provider._collect_fast_history_tail_bulk(
        _request(),
        data_count=3,
        page_size=200,
        progress_callback=None,
    )

    assert state is not None
    assert state["completed"] is False
    assert state["partial_fallback"] is True
    assert [item["message_id"] for item in state["messages"]] == ["m1", "m2"]


def test_collect_fast_history_tail_bulk_boundary_bridge_uses_current_next_anchor() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    payloads = iter(
        [
            {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-1",
                "page_size": 200,
                "exhausted": False,
            },
            {
                "messages": [_message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
        ]
    )
    bridge_anchors: list[str | None] = []

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        try:
            return next(payloads)
        except StopIteration:
            return None

    def fake_fetch_history_page(request, *, before_message_seq: str | None, **kwargs):
        bridge_anchors.append(before_message_seq)
        return (
            _snapshot([_message("m3", "3")]),
            {
                "history_source": "napcat_fast_history",
                "page_duration_s": 0.01,
                "page_size": 1,
                "page_message_count": 1,
                "retry_count": 0,
            },
        )

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]
    provider._fetch_history_page = fake_fetch_history_page  # type: ignore[method-assign]

    state = provider._collect_fast_history_tail_bulk(
        _request(),
        data_count=3,
        page_size=200,
        progress_callback=None,
    )

    assert state is not None
    assert state["completed"] is True
    assert bridge_anchors == ["anchor-2"]
    assert [item["message_id"] for item in state["messages"]] == ["m1", "m2", "m3"]


def test_collect_fast_history_tail_bulk_boundary_bridge_does_not_overshoot_requested_count() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    payloads = iter(
        [
            {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
            {
                "messages": [_message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
        ]
    )

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        try:
            return next(payloads)
        except StopIteration:
            return None

    def fake_fetch_history_page(*args, **kwargs):
        return (
            _snapshot(
                [
                    _message("m3", "3"),
                    _message("m4", "4"),
                    _message("m5", "5"),
                ]
            ),
            {
                "history_source": "napcat_fast_history",
                "page_duration_s": 0.01,
                "page_size": 3,
                "page_message_count": 3,
                "retry_count": 0,
            },
        )

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]
    provider._fetch_history_page = fake_fetch_history_page  # type: ignore[method-assign]

    state = provider._collect_fast_history_tail_bulk(
        _request(),
        data_count=4,
        page_size=200,
        progress_callback=None,
    )

    assert state is not None
    assert state["completed"] is True
    assert len(state["messages"]) == 4
    assert [item["message_id"] for item in state["messages"][:2]] == ["m1", "m2"]
    assert {item["message_id"] for item in state["messages"][2:]} == {"m4", "m5"}


def test_fetch_full_snapshot_prefers_fast_full_bulk_until_exhausted() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    payloads = iter(
        [
            {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
            {
                "messages": [_message("m3", "3"), _message("m4", "4")],
                "pages_scanned": 1,
                "next_anchor": "anchor-4",
                "page_size": 200,
                "exhausted": True,
            },
        ]
    )
    history_page_calls = 0

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        try:
            return next(payloads)
        except StopIteration:
            return None

    def fake_fetch_history_page(*args, **kwargs):
        nonlocal history_page_calls
        history_page_calls += 1
        return _snapshot([]), {
            "history_source": "napcat_fast_history",
            "page_duration_s": 0.01,
            "page_size": 1,
            "page_message_count": 0,
            "retry_count": 0,
        }

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]
    provider._fetch_history_page = fake_fetch_history_page  # type: ignore[method-assign]
    provider._finalize_snapshot = lambda snapshot, progress_callback=None: snapshot  # type: ignore[method-assign]

    snapshot = provider.fetch_full_snapshot(_request(), page_size=500, progress_callback=None)

    assert history_page_calls == 0
    assert snapshot.metadata["source"] == "napcat_fast_history_bulk"
    assert [item["message_id"] for item in snapshot.messages] == ["m1", "m2", "m3", "m4"]


def test_fetch_full_snapshot_falls_back_to_history_page_after_partial_fast_full_bulk() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    payloads = iter(
        [
            {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 1,
                "next_anchor": "anchor-2",
                "page_size": 200,
                "exhausted": False,
            },
            None,
        ]
    )
    history_page_anchors: list[str | None] = []

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        return next(payloads)

    def fake_fetch_history_page(request, *, before_message_seq: str | None, **kwargs):
        history_page_anchors.append(before_message_seq)
        return _snapshot([_message("m3", "3")]), {
            "history_source": "napcat_fast_history",
            "page_duration_s": 0.01,
            "page_size": 1,
            "page_message_count": 1,
            "retry_count": 0,
        }

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]
    provider._fetch_history_page = fake_fetch_history_page  # type: ignore[method-assign]
    provider._finalize_snapshot = lambda snapshot, progress_callback=None: snapshot  # type: ignore[method-assign]

    snapshot = provider.fetch_full_snapshot(_request(), page_size=500, progress_callback=None)

    assert history_page_anchors == ["anchor-2", "3"]
    assert snapshot.metadata["source"] == "napcat_fast_history_bulk+napcat_fast_history"
    assert [item["message_id"] for item in snapshot.messages] == ["m1", "m2", "m3"]


def test_fetch_fast_history_tail_bulk_uses_seq_window_strategy() -> None:
    class _FastClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_history_tail_bulk(
            self,
            chat_type: str,
            chat_id: str,
            *,
            data_count: int,
            page_size: int,
            anchor_message_id: str | None = None,
            anchor_message_seq: str | None = None,
            history_fetch_strategy: str | None = None,
            include_debug_stats: bool = False,
            timeout=None,
        ):
            self.calls.append(
                {
                    "chat_type": chat_type,
                    "chat_id": chat_id,
                    "data_count": data_count,
                    "page_size": page_size,
                    "anchor_message_id": anchor_message_id,
                    "anchor_message_seq": anchor_message_seq,
                    "history_fetch_strategy": history_fetch_strategy,
                    "include_debug_stats": include_debug_stats,
                }
            )
            return {"messages": [], "pages_scanned": 0, "exhausted": True, "page_size": page_size}

    fast_client = _FastClient()
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=fast_client)

    provider._fetch_fast_history_tail_bulk(  # type: ignore[attr-defined]
        _request(),
        data_count=2000,
        page_size=500,
        anchor_message_id="anchor-msg",
        anchor_message_seq="7473",
    )

    assert fast_client.calls == [
        {
            "chat_type": "group",
            "chat_id": "922065597",
            "data_count": 2000,
            "page_size": 500,
            "anchor_message_id": "anchor-msg",
            "anchor_message_seq": "7473",
            "history_fetch_strategy": "seq_window",
            "include_debug_stats": False,
        }
    ]


def test_fetch_snapshot_tail_prefers_plugin_full_bulk_route_for_large_request() -> None:
    class _FastClient:
        def __init__(self) -> None:
            self.full_calls: list[dict[str, object]] = []
            self.tail_calls: list[dict[str, object]] = []

        def get_history_full_bulk(
            self,
            chat_type: str,
            chat_id: str,
            *,
            data_count: int,
            page_size: int,
            history_fetch_strategy: str | None = None,
            include_debug_stats: bool = False,
            timeout=None,
        ):
            self.full_calls.append(
                {
                    "chat_type": chat_type,
                    "chat_id": chat_id,
                    "data_count": data_count,
                    "page_size": page_size,
                    "history_fetch_strategy": history_fetch_strategy,
                    "include_debug_stats": include_debug_stats,
                }
            )
            return {
                "messages": [_message("m1", "1"), _message("m2", "2"), _message("m3", "3")],
                "pages_scanned": 3,
                "page_size": 200,
                "requested_data_count": data_count,
                "exhausted": True,
                "elapsed_ms": 222,
            }

        def get_history_tail_bulk(self, *args, **kwargs):
            self.tail_calls.append({"args": args, "kwargs": kwargs})
            return None

    fast_client = _FastClient()
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=fast_client)
    provider._finalize_snapshot = lambda snapshot, progress_callback=None: snapshot  # type: ignore[method-assign]

    snapshot = provider.fetch_snapshot_tail(
        ExportRequest(chat_type="group", chat_id="922065597", chat_name="test", limit=5000),
        data_count=5000,
        page_size=500,
        progress_callback=None,
    )

    assert [item["message_id"] for item in snapshot.messages] == ["m1", "m2", "m3"]
    assert snapshot.metadata["source"] == "napcat_fast_history_bulk"
    assert fast_client.tail_calls == []
    assert fast_client.full_calls == [
        {
            "chat_type": "group",
            "chat_id": "922065597",
            "data_count": 5000,
            "page_size": 200,
            "history_fetch_strategy": "seq_window",
            "include_debug_stats": False,
        }
    ]


def test_fetch_full_snapshot_prefers_plugin_full_bulk_route() -> None:
    class _FastClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_history_full_bulk(
            self,
            chat_type: str,
            chat_id: str,
            *,
            data_count: int,
            page_size: int,
            history_fetch_strategy: str | None = None,
            include_debug_stats: bool = False,
            timeout=None,
        ):
            self.calls.append(
                {
                    "chat_type": chat_type,
                    "chat_id": chat_id,
                    "data_count": data_count,
                    "page_size": page_size,
                    "history_fetch_strategy": history_fetch_strategy,
                    "include_debug_stats": include_debug_stats,
                }
            )
            return {
                "messages": [_message("m1", "1"), _message("m2", "2")],
                "pages_scanned": 2,
                "page_size": 200,
                "requested_data_count": data_count,
                "exhausted": True,
                "elapsed_ms": 123,
            }

    fast_client = _FastClient()
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=fast_client)
    provider._finalize_snapshot = lambda snapshot, progress_callback=None: snapshot  # type: ignore[method-assign]

    snapshot = provider.fetch_full_snapshot(
        ExportRequest(chat_type="group", chat_id="922065597", chat_name="test", limit=13000),
        page_size=500,
        progress_callback=None,
    )

    assert [item["message_id"] for item in snapshot.messages] == ["m1", "m2"]
    assert snapshot.metadata["source"] == "napcat_fast_history_bulk"
    assert fast_client.calls == [
        {
            "chat_type": "group",
            "chat_id": "922065597",
            "data_count": 13000,
            "page_size": 200,
            "history_fetch_strategy": "seq_window",
            "include_debug_stats": False,
        }
    ]


def test_enrich_forward_details_uses_history_as_last_chance_after_get_forward_msg_failure() -> None:
    class _ForwardFailClient:
        def get_forward_msg(self, message_id: str):
            raise NapCatApiError("找不到相关的聊天记录")

    provider = NapCatHistoryProvider(_ForwardFailClient())
    target_message = {
        "message_id": "m-forward",
        "message_seq": "23388",
        "message": [
            {
                "type": "forward",
                "data": {"id": "fwd-1"},
                "extra": {"forward_messages": [], "detailed_text": None},
            }
        ],
    }

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        message["message"][0]["extra"]["forward_messages"] = [{"message_id": "nested"}]  # type: ignore[index]
        message["message"][0]["extra"]["detailed_text"] = "nested text"  # type: ignore[index]
        return True, None

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    enriched, unavailable = provider._enrich_forward_details(
        [target_message],
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=True,
        progress_callback=None,
    )

    assert enriched == 1
    assert unavailable == 0
    assert target_message["message"][0]["extra"]["forward_messages"] == [{"message_id": "nested"}]  # type: ignore[index]


def test_enrich_forward_details_marks_unavailable_when_forward_and_history_both_fail() -> None:
    class _ForwardFailClient:
        def get_forward_msg(self, message_id: str):
            raise NapCatApiError("找不到相关的聊天记录")

    provider = NapCatHistoryProvider(_ForwardFailClient())
    target_message = {
        "message_id": "m-forward",
        "message_seq": "23388",
        "message": [
            {
                "type": "forward",
                "data": {"id": "fwd-1"},
                "extra": {"forward_messages": [], "detailed_text": None},
            }
        ],
    }

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        return False, "forward_structure_unavailable_via_history"

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    enriched, unavailable = provider._enrich_forward_details(
        [target_message],
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=True,
        progress_callback=None,
    )

    assert enriched == 0
    assert unavailable == 1


def test_finalize_snapshot_does_not_skip_history_hydration_just_because_fast_history_source() -> None:
    class _ForwardFailClient:
        def get_forward_msg(self, message_id: str):
            raise NapCatApiError("找不到相关的聊天记录")

    provider = NapCatHistoryProvider(_ForwardFailClient())
    target_message = {
        "message_id": "m-forward",
        "message_seq": "23388",
        "message": [
            {
                "type": "forward",
                "data": {"id": "fwd-1"},
                "extra": {"forward_messages": [], "detailed_text": None},
            }
        ],
    }

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        message["message"][0]["extra"]["forward_messages"] = [{"message_id": "nested"}]  # type: ignore[index]
        message["message"][0]["extra"]["detailed_text"] = "nested text"  # type: ignore[index]
        return True, None

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    finalized = provider._finalize_snapshot(
        _snapshot([target_message], source="napcat_fast_history"),
        progress_callback=None,
    )

    assert finalized.metadata.get("forward_detail_count") == 1
    assert target_message["message"][0]["extra"]["forward_messages"] == [{"message_id": "nested"}]  # type: ignore[index]


def test_enrich_forward_details_uses_fast_plugin_before_history_and_get_forward_msg() -> None:
    class _ForwardFailClient:
        def __init__(self) -> None:
            self.forward_calls: list[str] = []

        def get_forward_msg(self, message_id: str):
            self.forward_calls.append(message_id)
            raise NapCatApiError("找不到相关的聊天记录")

    class _FastPluginClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def hydrate_forward_detail(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "messages": [
                    {
                        "message_id": "nested-1",
                        "message_seq": "1",
                        "sender": {"uin": "42", "nickname": "Alice"},
                        "rawMessage": {
                            "msgId": "nested-1",
                            "msgSeq": "1",
                            "senderUin": "42",
                            "sendNickName": "Alice",
                            "peerUid": "922065597",
                            "chatType": 2,
                            "elements": [
                                {
                                    "elementType": 1,
                                    "textElement": {"content": "hello from plugin"},
                                }
                            ],
                        },
                    }
                ]
            }

    client = _ForwardFailClient()
    fast_client = _FastPluginClient()
    provider = NapCatHistoryProvider(client, fast_client=fast_client)
    target_message = {
        "message_id": "m-forward",
        "message_seq": "23388",
        "raw_message": {
            "msgId": "m-forward",
            "msgSeq": "23388",
            "peerUid": "922065597",
            "chatType": 2,
            "elements": [
                {
                    "elementType": FORWARD_ELEMENT_TYPE,
                    "elementId": "elem-forward",
                    "multiForwardMsgElement": {"resId": "fwd-1"},
                }
            ],
        },
    }
    progress: list[dict[str, object]] = []

    enriched, unavailable = provider._enrich_forward_details(
        [target_message],
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=progress.append,
    )

    assert enriched == 1
    assert unavailable == 0
    assert client.forward_calls == []
    assert len(fast_client.calls) == 1
    attached = target_message["raw_message"]["elements"][0]["multiForwardMsgElement"]["messages"]  # type: ignore[index]
    assert isinstance(attached, list)
    assert attached[0]["message_id"] == "nested-1"
    summary = next(row for row in progress if row.get("phase") == "forward_expand_summary")
    assert summary["fast_plugin_calls"] == 1
    assert summary["fast_plugin_hits"] == 1


def test_enrich_forward_details_prefetches_fast_plugin_concurrently() -> None:
    fast_client = _ConcurrentFastPluginClient()
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=fast_client)
    messages = [_plugin_forward_target(f"m-{index}", str(index)) for index in range(1, 7)]
    progress: list[dict[str, object]] = []

    enriched, unavailable = provider._enrich_forward_details(
        messages,
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=progress.append,
    )

    assert enriched == 6
    assert unavailable == 0
    assert len(fast_client.calls) == 6
    assert fast_client.max_active > 1
    summary = next(row for row in progress if row.get("phase") == "forward_expand_summary")
    assert summary["history_retry_calls"] == 0
    assert summary["get_forward_msg_calls"] == 0


def test_enrich_forward_details_prefers_fast_plugin_batch_route() -> None:
    class _ForwardFailClient:
        def __init__(self) -> None:
            self.forward_calls: list[str] = []

        def get_forward_msg(self, message_id: str):
            self.forward_calls.append(message_id)
            raise NapCatApiError("找不到相关的聊天记录")

    class _FastPluginBatchClient:
        def __init__(self) -> None:
            self.batch_calls: list[list[dict[str, object]]] = []
            self.single_calls: list[dict[str, object]] = []

        def hydrate_forward_detail_batch(self, items):
            self.batch_calls.append(list(items))
            results = []
            for index, item in enumerate(items, start=1):
                results.append(
                    {
                        "ok": True,
                        "data": {
                            "messages": [
                                {
                                    "message_id": f"nested-{index}",
                                    "message_seq": str(index),
                                    "sender": {"uin": "42", "nickname": "Alice"},
                                    "rawMessage": {
                                        "msgId": f"nested-{index}",
                                        "msgSeq": str(index),
                                        "senderUin": "42",
                                        "sendNickName": "Alice",
                                        "peerUid": str(item["peer_uid"]),
                                        "chatType": item["chat_type_raw"],
                                        "elements": [
                                            {
                                                "elementType": 1,
                                                "textElement": {"content": f"hello {index}"},
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                    }
                )
            return {"items": results}

        def hydrate_forward_detail(self, **kwargs):
            self.single_calls.append(kwargs)
            raise AssertionError("single forward-detail route should not be used when batch route is available")

    client = _ForwardFailClient()
    fast_client = _FastPluginBatchClient()
    provider = NapCatHistoryProvider(client, fast_client=fast_client)
    target_messages = [
        {
            "message_id": "m-forward-1",
            "message_seq": "23388",
            "raw_message": {
                "msgId": "m-forward-1",
                "msgSeq": "23388",
                "peerUid": "922065597",
                "chatType": 2,
                "elements": [
                    {
                        "elementType": FORWARD_ELEMENT_TYPE,
                        "elementId": "elem-forward-1",
                        "multiForwardMsgElement": {"resId": "fwd-1"},
                    }
                ],
            },
        },
        {
            "message_id": "m-forward-2",
            "message_seq": "23389",
            "raw_message": {
                "msgId": "m-forward-2",
                "msgSeq": "23389",
                "peerUid": "922065597",
                "chatType": 2,
                "elements": [
                    {
                        "elementType": FORWARD_ELEMENT_TYPE,
                        "elementId": "elem-forward-2",
                        "multiForwardMsgElement": {"resId": "fwd-2"},
                    }
                ],
            },
        },
    ]

    progress: list[dict[str, object]] = []
    enriched, unavailable = provider._enrich_forward_details(
        target_messages,
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=progress.append,
    )

    assert enriched == 2
    assert unavailable == 0
    assert client.forward_calls == []
    assert len(fast_client.batch_calls) == 1
    assert len(fast_client.batch_calls[0]) == 2
    assert fast_client.single_calls == []
    summary = next(row for row in progress if row.get("phase") == "forward_expand_summary")
    assert summary["fast_plugin_calls"] == 2
    assert summary["fast_plugin_hits"] == 2
    assert summary["history_retry_calls"] == 0
    assert summary["get_forward_msg_calls"] == 0


def test_enrich_forward_details_falls_back_to_single_fast_plugin_after_partial_batch_failure() -> None:
    class _ForwardFailClient:
        def __init__(self) -> None:
            self.forward_calls: list[str] = []

        def get_forward_msg(self, message_id: str):
            self.forward_calls.append(message_id)
            raise NapCatApiError("找不到相关的聊天记录")

    class _FastPluginBatchClient:
        def __init__(self) -> None:
            self.batch_calls: list[list[dict[str, object]]] = []
            self.single_calls: list[dict[str, object]] = []

        def hydrate_forward_detail_batch(self, items):
            self.batch_calls.append(list(items))
            return {
                "items": [
                    {
                        "ok": True,
                        "data": {
                            "messages": [
                                {
                                    "message_id": "nested-batch",
                                    "message_seq": "1",
                                    "sender": {"uin": "42", "nickname": "Alice"},
                                    "rawMessage": {
                                        "msgId": "nested-batch",
                                        "msgSeq": "1",
                                        "senderUin": "42",
                                        "sendNickName": "Alice",
                                        "peerUid": "922065597",
                                        "chatType": 2,
                                        "elements": [
                                            {
                                                "elementType": 1,
                                                "textElement": {"content": "hello batch"},
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "ok": False,
                        "error": "temporary batch miss",
                    },
                ]
            }

        def hydrate_forward_detail(self, **kwargs):
            self.single_calls.append(kwargs)
            return {
                "messages": [
                    {
                        "message_id": "nested-single",
                        "message_seq": "2",
                        "sender": {"uin": "42", "nickname": "Alice"},
                        "rawMessage": {
                            "msgId": "nested-single",
                            "msgSeq": "2",
                            "senderUin": "42",
                            "sendNickName": "Alice",
                            "peerUid": str(kwargs["peer_uid"]),
                            "chatType": kwargs["chat_type_raw"],
                            "elements": [
                                {
                                    "elementType": 1,
                                    "textElement": {"content": "hello single"},
                                }
                            ],
                        },
                    }
                ]
            }

    client = _ForwardFailClient()
    fast_client = _FastPluginBatchClient()
    provider = NapCatHistoryProvider(client, fast_client=fast_client)
    target_messages = [
        {
            "message_id": "m-forward-1",
            "message_seq": "23388",
            "raw_message": {
                "msgId": "m-forward-1",
                "msgSeq": "23388",
                "peerUid": "922065597",
                "chatType": 2,
                "elements": [
                    {
                        "elementType": FORWARD_ELEMENT_TYPE,
                        "elementId": "elem-forward-1",
                        "multiForwardMsgElement": {"resId": "fwd-1"},
                    }
                ],
            },
        },
        {
            "message_id": "m-forward-2",
            "message_seq": "23389",
            "raw_message": {
                "msgId": "m-forward-2",
                "msgSeq": "23389",
                "peerUid": "922065597",
                "chatType": 2,
                "elements": [
                    {
                        "elementType": FORWARD_ELEMENT_TYPE,
                        "elementId": "elem-forward-2",
                        "multiForwardMsgElement": {"resId": "fwd-2"},
                    }
                ],
            },
        },
    ]

    progress: list[dict[str, object]] = []
    enriched, unavailable = provider._enrich_forward_details(
        target_messages,
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=progress.append,
    )

    assert enriched == 2
    assert unavailable == 0
    assert client.forward_calls == []
    assert len(fast_client.batch_calls) == 1
    assert len(fast_client.batch_calls[0]) == 2
    assert len(fast_client.single_calls) == 1
    assert fast_client.single_calls[0]["message_id_raw"] == "m-forward-2"
    summary = next(row for row in progress if row.get("phase") == "forward_expand_summary")
    assert summary["fast_plugin_calls"] == 2
    assert summary["fast_plugin_hits"] == 2
    assert summary["history_retry_calls"] == 0
    assert summary["get_forward_msg_calls"] == 0


def test_enrich_forward_details_falls_back_to_history_when_fast_plugin_misses() -> None:
    class _ForwardFailClient:
        def get_forward_msg(self, message_id: str):
            raise NapCatApiError("找不到相关的聊天记录")

    class _FastPluginClient:
        def __init__(self) -> None:
            self.calls = 0

        def hydrate_forward_detail(self, **kwargs):
            self.calls += 1
            return {"messages": []}

    provider = NapCatHistoryProvider(_ForwardFailClient(), fast_client=_FastPluginClient())
    target_message = {
        "message_id": "m-forward",
        "message_seq": "23388",
        "raw_message": {
            "msgId": "m-forward",
            "msgSeq": "23388",
            "peerUid": "922065597",
            "chatType": 2,
            "elements": [
                {
                    "elementType": FORWARD_ELEMENT_TYPE,
                    "elementId": "elem-forward",
                    "multiForwardMsgElement": {"resId": "fwd-1"},
                }
            ],
        },
    }
    history_calls = 0
    progress: list[dict[str, object]] = []

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        nonlocal history_calls
        history_calls += 1
        message["message"] = [
            {
                "type": "forward",
                "data": {"id": "fwd-1", "content": [{"message_id": "nested"}]},
            }
        ]
        provider._record_forward_history_probe_outcome(
            message,
            has_content=True,
            route="history_retry",
        )
        return True, None

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    enriched, unavailable = provider._enrich_forward_details(
        [target_message],
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=progress.append,
    )

    assert enriched == 1
    assert unavailable == 0
    assert history_calls == 1
    summary = next(row for row in progress if row.get("phase") == "forward_expand_summary")
    assert summary["fast_plugin_calls"] == 1
    assert summary["fast_plugin_hits"] == 0
    assert summary["history_retry_calls"] == 1


def test_match_message_by_seq_does_not_blindly_accept_single_message_without_identity_proof() -> None:
    provider = NapCatHistoryProvider(_DummyClient())
    payload = {
        "messages": [
            {
                "message": [{"type": "forward", "data": {"content": [{"text": "nested"}]}}],
            }
        ]
    }

    matched = provider._match_message_by_seq(
        payload,
        "23388",
        target_message={"message_id": "target-msg", "message_seq": "23388"},
    )

    assert matched is None


def test_match_message_by_seq_accepts_single_message_when_message_id_matches() -> None:
    provider = NapCatHistoryProvider(_DummyClient())
    payload = {
        "messages": [
            {
                "message_id": "target-msg",
                "message": [{"type": "forward", "data": {"content": [{"text": "nested"}]}}],
            }
        ]
    }

    matched = provider._match_message_by_seq(
        payload,
        "23388",
        target_message={"message_id": "target-msg", "message_seq": "23388"},
    )

    assert matched is not None
    assert matched.get("message_id") == "target-msg"


def test_hydrate_fast_history_page_forwards_skips_already_resolved_messages() -> None:
    class _CountingClient:
        def __init__(self) -> None:
            self.calls = 0

        def get_group_msg_history(self, *args, **kwargs):
            self.calls += 1
            return {"messages": []}

    client = _CountingClient()
    provider = NapCatHistoryProvider(client)
    message = _forward_reference_message("resolved-forward", "42")
    message["message"] = [
        {
            "type": "forward",
            "data": {"content": [{"message_id": "nested"}]},
        }
    ]

    hydrated = provider._hydrate_fast_history_page_forwards(
        _request(),
        [message],
        before_message_seq=None,
        count=1,
        reverse_order=False,
    )

    assert hydrated == 0
    assert client.calls == 0


def test_hydrate_fast_history_tail_forwards_bulk_uses_sparse_history_retry_for_single_forward_window() -> None:
    provider = NapCatHistoryProvider(_DummyClient())
    messages = [_message(f"m{index}", str(index)) for index in range(1, 201)]
    messages[-1] = _forward_reference_message("forward-msg", "200")
    history_retry_calls: list[str] = []
    progress_events: list[dict[str, object]] = []

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        history_retry_calls.append(str(message.get("message_id")))
        message["message"] = [
            {
                "type": "forward",
                "data": {"content": [{"message_id": "nested"}]},
            }
        ]
        return True, None

    def progress_callback(event: dict[str, object]) -> None:
        progress_events.append(event)

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    hydrated = provider._hydrate_fast_history_tail_forwards_bulk(
        _request(),
        messages,
        page_size=200,
        progress_callback=progress_callback,
    )

    assert hydrated == 1
    assert history_retry_calls == ["forward-msg"]
    window_event = next(
        event
        for event in progress_events
        if event.get("phase") == "tail_forward_hydrate_window"
    )
    assert window_event["strategy"] == "history_retry_sparse_forward"
    assert window_event["forward_ref_count"] == 1
    assert window_event["resolved_forward_ref_count"] == 0
    assert window_event["unresolved_forward_ref_count"] == 1
    assert window_event["history_calls"] == 1


def test_enrich_forward_details_does_not_poison_later_forward_after_single_known_failure() -> None:
    class _MixedForwardClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_forward_msg(self, message_id: str):
            self.calls.append(message_id)
            if message_id == "bad-forward":
                raise NapCatApiError("找不到相关的聊天记录")
            return {"messages": [{"message_id": "resolved-good"}]}

    client = _MixedForwardClient()
    provider = NapCatHistoryProvider(client)
    messages = [
        {
            "message_id": "msg-1",
            "message_seq": "1001",
            "message": [
                {
                    "type": "forward",
                    "data": {"id": "bad-forward"},
                    "extra": {"forward_messages": [], "detailed_text": None},
                }
            ],
        },
        {
            "message_id": "msg-2",
            "message_seq": "1002",
            "message": [
                {
                    "type": "forward",
                    "data": {"id": "good-forward"},
                    "extra": {"forward_messages": [], "detailed_text": None},
                }
            ],
        },
    ]

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        return False, True

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    enriched, unavailable = provider._enrich_forward_details(
        messages,
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=True,
        progress_callback=None,
    )

    assert client.calls == ["bad-forward", "good-forward"]
    assert enriched == 1
    assert unavailable == 1
    assert messages[1]["message"][0]["data"]["content"] == [{"message_id": "resolved-good"}]  # type: ignore[index]


def test_enrich_forward_details_skips_duplicate_history_retry_after_bulk_parse_mult_miss() -> None:
    class _ForwardFailClient:
        def get_forward_msg(self, message_id: str):
            raise NapCatApiError("找不到相关的聊天记录")

    provider = NapCatHistoryProvider(_ForwardFailClient())
    target_message = {
        "message_id": "msg-forward",
        "message_seq": "23388",
        "message": [
            {
                "type": "forward",
                "data": {"id": "fwd-1"},
                "extra": {"forward_messages": [], "detailed_text": None},
            }
        ],
    }
    provider._record_forward_history_probe_outcome(
        target_message,
        has_content=False,
        route="bulk_parse_mult",
    )
    history_calls = 0

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        nonlocal history_calls
        history_calls += 1
        return False, "forward_structure_unavailable_via_history"

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    enriched, unavailable = provider._enrich_forward_details(
        [target_message],
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=None,
    )

    assert history_calls == 0
    assert enriched == 0
    assert unavailable == 1
    assert (
        target_message["message"][0]["data"]["_qq_data_forward_unavailable_reason"]  # type: ignore[index]
        == "forward_structure_unavailable_protocol_fallback"
    )


def test_hydrate_fast_history_tail_forwards_bulk_emits_window_progress() -> None:
    class _HydrateClient:
        def get_group_msg_history(
            self,
            chat_id: str,
            *,
            message_seq: str | None,
            count: int,
            reverse_order: bool,
            parse_mult_msg: bool,
        ):
            return {
                "messages": [
                    {
                        "message_id": "msg-forward",
                        "message": [
                            {
                                "type": "forward",
                                "data": {"id": "msg-forward", "content": [{"text": "nested"}]},
                            }
                        ],
                    }
                ]
            }

    provider = NapCatHistoryProvider(_HydrateClient())
    progress: list[dict[str, object]] = []
    messages = [
        {
            "message_id": "msg-forward",
            "message_seq": "23388",
            "timestamp_iso": "2026-03-24T12:00:00+08:00",
            "raw_message": {
                "msgId": "msg-forward",
                "msgSeq": "23388",
                "elements": [
                    {
                        "elementType": 16,
                        "multiForwardMsgElement": {"resId": "msg-forward"},
                    }
                ],
            },
        }
    ]

    hydrated = provider._hydrate_fast_history_tail_forwards_bulk(
        _request(),
        messages,
        page_size=200,
        progress_callback=progress.append,
    )

    assert hydrated == 1
    forward_events = [
        row for row in progress if row.get("phase") == "tail_forward_hydrate_window"
    ]
    assert len(forward_events) == 1
    assert forward_events[0]["status"] == "done"
    assert forward_events[0]["window_index"] == 1
    assert forward_events[0]["forward_ref_count"] == 1
    assert forward_events[0]["hydrated_count"] == 1
    assert forward_events[0]["strategy"] == "bulk_parse_mult_window"
    assert forward_events[0]["history_calls"] == 1


def test_hydrate_fast_history_tail_forwards_bulk_uses_sparse_history_strategy_for_low_density_window() -> None:
    class _SparseHydrateClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_group_msg_history(
            self,
            chat_id: str,
            *,
            message_seq: str | None,
            count: int,
            reverse_order: bool,
            parse_mult_msg: bool,
        ):
            self.calls.append(
                {
                    "chat_id": chat_id,
                    "message_seq": message_seq,
                    "count": count,
                    "reverse_order": reverse_order,
                    "parse_mult_msg": parse_mult_msg,
                }
            )
            return {
                "messages": [
                    {
                        "message_id": "msg-forward",
                        "message_seq": "23388",
                        "message": [
                            {
                                "type": "forward",
                                "data": {"id": "msg-forward", "content": [{"text": "nested"}]},
                            }
                        ],
                    }
                ]
            }

    client = _SparseHydrateClient()
    provider = NapCatHistoryProvider(client)
    progress: list[dict[str, object]] = []
    messages = [
        {
            "message_id": f"msg-{index}",
            "message_seq": str(23000 + index),
            "timestamp_iso": "2026-03-24T12:00:00+08:00",
            "raw_message": {
                "msgId": f"msg-{index}",
                "msgSeq": str(23000 + index),
                "elements": [],
            },
        }
        for index in range(200)
    ]
    messages[-1] = {
        "message_id": "msg-forward",
        "message_seq": "23388",
        "timestamp_iso": "2026-03-24T12:00:00+08:00",
        "raw_message": {
            "msgId": "msg-forward",
            "msgSeq": "23388",
            "elements": [
                {
                    "elementType": 16,
                    "multiForwardMsgElement": {"resId": "msg-forward"},
                }
            ],
        },
    }

    hydrated = provider._hydrate_fast_history_tail_forwards_bulk(
        _request(),
        messages,
        page_size=200,
        progress_callback=progress.append,
    )

    assert hydrated == 1
    assert client.calls == [
        {
            "chat_id": "922065597",
            "message_seq": "23388",
            "count": 1,
            "reverse_order": True,
            "parse_mult_msg": True,
        }
    ]
    forward_events = [
        row for row in progress if row.get("phase") == "tail_forward_hydrate_window"
    ]
    assert len(forward_events) == 1
    assert forward_events[0]["strategy"] == "history_retry_sparse_forward"
    assert forward_events[0]["history_calls"] == 1
    assert forward_events[0]["resolved_forward_ref_count"] == 0
    assert forward_events[0]["unresolved_forward_ref_count"] == 1


def test_hydrate_fast_history_tail_forwards_bulk_uses_sparse_history_strategy_for_three_forward_refs() -> None:
    class _SparseHydrateClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_group_msg_history(
            self,
            chat_id: str,
            *,
            message_seq: str | None,
            count: int,
            reverse_order: bool,
            parse_mult_msg: bool,
        ):
            self.calls.append(
                {
                    "chat_id": chat_id,
                    "message_seq": message_seq,
                    "count": count,
                    "reverse_order": reverse_order,
                    "parse_mult_msg": parse_mult_msg,
                }
            )
            return {
                "messages": [
                    {
                        "message_id": message_seq,
                        "message_seq": message_seq,
                        "message": [
                            {
                                "type": "forward",
                                "data": {"id": message_seq, "content": [{"text": "nested"}]},
                            }
                        ],
                    }
                ]
            }

    client = _SparseHydrateClient()
    provider = NapCatHistoryProvider(client)
    progress: list[dict[str, object]] = []
    messages = [
        {
            "message_id": f"msg-{index}",
            "message_seq": str(23000 + index),
            "timestamp_iso": "2026-03-24T12:00:00+08:00",
            "raw_message": {
                "msgId": f"msg-{index}",
                "msgSeq": str(23000 + index),
                "elements": [],
            },
        }
        for index in range(200)
    ]
    for offset in range(3):
        messages[-(offset + 1)] = {
            "message_id": f"msg-forward-{offset}",
            "message_seq": str(23388 + offset),
            "timestamp_iso": "2026-03-24T12:00:00+08:00",
            "raw_message": {
                "msgId": f"msg-forward-{offset}",
                "msgSeq": str(23388 + offset),
                "elements": [
                    {
                        "elementType": 16,
                        "multiForwardMsgElement": {"resId": f"msg-forward-{offset}"},
                    }
                ],
            },
        }

    hydrated = provider._hydrate_fast_history_tail_forwards_bulk(
        _request(),
        messages,
        page_size=200,
        progress_callback=progress.append,
    )

    assert hydrated == 3
    assert client.calls == [
        {
            "chat_id": "922065597",
            "message_seq": "23390",
            "count": 1,
            "reverse_order": True,
            "parse_mult_msg": True,
        },
        {
            "chat_id": "922065597",
            "message_seq": "23389",
            "count": 1,
            "reverse_order": True,
            "parse_mult_msg": True,
        },
        {
            "chat_id": "922065597",
            "message_seq": "23388",
            "count": 1,
            "reverse_order": True,
            "parse_mult_msg": True,
        },
    ]
    forward_events = [
        row for row in progress if row.get("phase") == "tail_forward_hydrate_window"
    ]
    assert len(forward_events) == 1
    assert forward_events[0]["strategy"] == "history_retry_sparse_forward"
    assert forward_events[0]["history_calls"] == 3
    assert forward_events[0]["forward_ref_count"] == 3
    assert forward_events[0]["hydrated_count"] == 3


def test_hydrate_fast_history_page_forwards_only_records_bulk_miss_for_exact_match() -> None:
    class _HydrateClient:
        def get_group_msg_history(
            self,
            chat_id: str,
            *,
            message_seq: str | None,
            count: int,
            reverse_order: bool,
            parse_mult_msg: bool,
        ):
            return {
                "messages": [
                    {
                        "message_id": "other-message",
                        "message_seq": "99999",
                        "message": [
                            {
                                "type": "forward",
                                "data": {"id": "other-message"},
                            }
                        ],
                    }
                ]
            }

    provider = NapCatHistoryProvider(_HydrateClient())
    messages = [
        {
            "message_id": "msg-forward",
            "message_seq": "23388",
            "raw_message": {
                "msgId": "msg-forward",
                "msgSeq": "23388",
                "elements": [
                    {
                        "elementType": 16,
                        "multiForwardMsgElement": {"resId": "msg-forward"},
                    }
                ],
            },
        }
    ]

    hydrated = provider._hydrate_fast_history_page_forwards(
        _request(),
        messages,
        before_message_seq=None,
        count=1,
        reverse_order=False,
    )

    assert hydrated == 0
    assert provider._get_forward_history_probe_outcome("23388") is None


def test_enrich_forward_details_does_not_retry_history_twice_after_initial_miss() -> None:
    class _ForwardFailClient:
        def get_forward_msg(self, message_id: str):
            raise NapCatApiError("找不到相关的聊天记录")

    provider = NapCatHistoryProvider(_ForwardFailClient())
    target_message = {
        "message_id": "msg-forward",
        "message_seq": "23388",
        "message": [
            {
                "type": "forward",
                "data": {"id": "fwd-1"},
                "extra": {"forward_messages": [], "detailed_text": None},
            }
        ],
    }
    history_calls = 0

    def fake_hydrate_forward_message_via_history(message: dict[str, object], *, chat_type: str, chat_id: str):
        nonlocal history_calls
        history_calls += 1
        provider._record_forward_history_probe_outcome(
            message,
            has_content=False,
            route="history_retry",
        )
        return False, None

    provider._hydrate_forward_message_via_history = fake_hydrate_forward_message_via_history  # type: ignore[method-assign]

    enriched, unavailable = provider._enrich_forward_details(
        [target_message],
        chat_type="group",
        chat_id="922065597",
        skip_history_retry=False,
        progress_callback=None,
    )

    assert history_calls == 1
    assert enriched == 0
    assert unavailable == 1
    assert (
        target_message["message"][0]["data"]["_qq_data_forward_unavailable_reason"]  # type: ignore[index]
        == "forward_structure_unavailable_protocol_fallback"
    )


def test_match_message_by_seq_does_not_accept_single_mismatched_message_with_seq() -> None:
    provider = NapCatHistoryProvider(_DummyClient())
    payload = [{"message_seq": "9999", "message": [{"type": "forward", "data": {"content": "x"}}]}]

    assert provider._match_message_by_seq(payload, "1000") is None


def test_collect_fast_history_tail_bulk_emits_history_page_done_for_bulk_chunks() -> None:
    provider = NapCatHistoryProvider(_DummyClient(), fast_client=object())
    progress: list[dict[str, object]] = []

    def fake_fetch_fast_history_tail_bulk(*args, **kwargs):
        return {
            "messages": [_message("m1", "1"), _message("m2", "2")],
            "pages_scanned": 2,
            "next_anchor": "anchor-2",
            "page_size": 200,
            "exhausted": True,
        }

    provider._fetch_fast_history_tail_bulk = fake_fetch_fast_history_tail_bulk  # type: ignore[method-assign]

    state = provider._collect_fast_history_tail_bulk(
        _request(),
        data_count=3,
        page_size=200,
        progress_callback=progress.append,
    )

    assert state is not None
    history_page_events = [row for row in progress if row.get("phase") == "history_page_done"]
    assert len(history_page_events) == 1
    assert history_page_events[0]["mode"] == "tail_scan"
    assert history_page_events[0]["history_source"] == "napcat_fast_history_bulk"
    assert history_page_events[0]["page_message_count"] == 2
    assert history_page_events[0]["requested_count"] == 3
