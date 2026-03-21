from __future__ import annotations

from datetime import datetime

from qq_data_core.models import EXPORT_TIMEZONE, ExportRequest, SourceChatSnapshot
from qq_data_integrations.napcat.http_client import NapCatApiError
from qq_data_integrations.napcat.provider import NapCatHistoryProvider


class _DummyClient:
    def get_forward_msg(self, message_id: str):
        raise NotImplementedError


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
        return True, False

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
        return False, True

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
    assert (
        target_message["message"][0]["data"]["_qq_data_forward_unavailable_reason"]  # type: ignore[index]
        == "forward_structure_unavailable_via_history"
    )


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


def test_match_message_by_seq_does_not_accept_single_mismatched_message_with_seq() -> None:
    provider = NapCatHistoryProvider(_DummyClient())
    payload = [{"message_seq": "9999", "message": [{"type": "forward", "data": {"content": "x"}}]}]

    assert provider._match_message_by_seq(payload, "1000") is None
