from __future__ import annotations

from qq_data_core.normalize import normalize_message


def test_normalize_forward_nodes_accepts_fast_plugin_raw_messages() -> None:
    message = {
        "message_id": "outer-msg",
        "message_seq": "100",
        "time": 1773637977,
        "timestamp_iso": "2026-03-16T13:12:57+08:00",
        "raw_message": {
            "msgId": "outer-msg",
            "msgSeq": "100",
            "senderUin": "3956020260",
            "peerUid": "922065597",
            "chatType": 2,
            "elements": [
                {
                    "elementType": 16,
                    "elementId": "forward-elem",
                    "multiForwardMsgElement": {
                        "resId": "fwd-1",
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
                        ],
                    },
                }
            ],
        },
    }

    normalized = normalize_message(
        message,
        chat_type="group",
        chat_id="922065597",
        chat_name="test",
    )

    forward_segment = next(segment for segment in normalized.segments if segment.type == "forward")
    assert forward_segment.extra["forward_messages"][0]["text_content"] == "hello from plugin"
    assert "Alice: hello from plugin" in (forward_segment.extra.get("detailed_text") or "")
