from __future__ import annotations

from qq_data_core.media_bundle import _iter_asset_candidates
from qq_data_core.normalize import normalize_message


def _base_message() -> dict[str, object]:
    return {
        "time": 1750000000,
        "sender": {"user_id": "10001", "nickname": "tester"},
    }


def test_onebot_mface_preserves_remote_sticker_hints() -> None:
    message = {
        **_base_message(),
        "message": [
            {
                "type": "mface",
                "data": {
                    "summary": "foo",
                    "emoji_id": "abcdef123456",
                    "emoji_package_id": 1,
                    "key": "market-key",
                },
            }
        ],
    }

    normalized = normalize_message(
        message,
        chat_type="group",
        chat_id="922065597",
    )

    segment = normalized.segments[0]
    assert segment.type == "sticker"
    assert segment.extra["remote_url"] == "https://gxh.vip.qq.com/club/item/parcel/item/ab/abcdef123456/raw300.gif"
    assert segment.extra["remote_file_name"] == "ab-abcdef123456.gif"


def test_remote_only_sticker_segment_still_produces_asset_candidate() -> None:
    message = {
        **_base_message(),
        "message": [
            {
                "type": "mface",
                "data": {
                    "summary": "foo",
                    "emoji_id": "abcdef123456",
                    "emoji_package_id": 1,
                },
            }
        ],
    }

    normalized = normalize_message(
        message,
        chat_type="group",
        chat_id="922065597",
    )

    candidates = list(_iter_asset_candidates(normalized))

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.asset_type == "sticker"
    assert candidate.file_name == "ab-abcdef123456.gif"
    assert candidate.source_path is None
    assert candidate.download_hint["remote_url"] == "https://gxh.vip.qq.com/club/item/parcel/item/ab/abcdef123456/raw300.gif"


def test_forward_remote_only_sticker_segment_produces_asset_candidate() -> None:
    message = {
        **_base_message(),
        "message": [
            {
                "type": "forward",
                "data": {
                    "content": [
                        {
                            "type": "node",
                            "data": {
                                "user_id": "10002",
                                "nickname": "nested",
                                "message": [
                                    {
                                        "type": "mface",
                                        "data": {
                                            "summary": "bar",
                                            "emoji_id": "fedcba654321",
                                            "emoji_package_id": 2,
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            }
        ],
    }

    normalized = normalize_message(
        message,
        chat_type="group",
        chat_id="922065597",
    )

    candidates = list(_iter_asset_candidates(normalized))

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.asset_type == "sticker"
    assert candidate.file_name == "fe-fedcba654321.gif"
    assert candidate.download_hint["remote_url"] == "https://gxh.vip.qq.com/club/item/parcel/item/fe/fedcba654321/raw300.gif"


def test_forward_file_segment_preserves_md5_and_file_biz_id() -> None:
    message = {
        **_base_message(),
        "message": [
            {
                "type": "forward",
                "data": {
                    "content": [
                        {
                            "type": "node",
                            "data": {
                                "user_id": "10002",
                                "nickname": "nested",
                                "message": [
                                    {
                                        "type": "file",
                                        "data": {
                                            "name": "sample.bin",
                                            "path": "C:/tmp/sample.bin",
                                            "file_id": "/test-file-id",
                                            "file_biz_id": "biz-42",
                                            "md5": "abcdefabcdefabcdefabcdefabcdefab",
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            }
        ],
    }

    normalized = normalize_message(
        message,
        chat_type="group",
        chat_id="922065597",
    )

    forward_segment = normalized.segments[0]
    nested_segment = forward_segment.extra["forward_messages"][0]["segments"][0]

    assert nested_segment["type"] == "file"
    assert nested_segment["md5"] == "abcdefabcdefabcdefabcdefabcdefab"
    assert nested_segment["extra"]["file_biz_id"] == "biz-42"
