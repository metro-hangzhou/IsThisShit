from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qq_data_core.media_bundle import materialize_snapshot_media
from qq_data_core.models import NormalizedMessage, NormalizedSegment, NormalizedSnapshot


class _MissingImageManager:
    def __init__(self, *, missing_resolver: str = "missing_after_napcat") -> None:
        self.public_retry_calls = 0
        self.missing_resolver = missing_resolver

    def begin_export_download_tracking(self, _requests):
        return {}

    def prepare_for_export(self, _requests, *, progress_callback=None):
        _ = progress_callback
        return None

    def export_download_progress_snapshot(self):
        return {}

    def settle_export_download_progress(self):
        return {}

    def resolve_for_export(self, request, *, trace_callback=None):
        _ = trace_callback
        if str(request.get("asset_type") or "").strip() == "image":
            return None, self.missing_resolver
        return None, None

    def resolve_via_public_token_route(self, request):
        self.public_retry_calls += 1
        _ = request
        return None, None


def _forward_image_message(*, file_name: str, md5: str, timestamp_ms: int) -> NormalizedMessage:
    return NormalizedMessage(
        chat_type="group",
        chat_id="922065597",
        group_id="922065597",
        chat_name="蕾米二次元萌萌群",
        sender_id="10001",
        sender_name="forward-sender",
        message_id="forward-msg",
        message_seq="1",
        timestamp_ms=timestamp_ms,
        timestamp_iso="2026-01-10T16:54:54+08:00",
        content="[forward message]",
        text_content="",
        segments=[
            NormalizedSegment(
                type="forward",
                token="[forward message]",
                extra={
                    "message_id_raw": "7616396026189795566",
                    "element_id": "7616396026189795565",
                    "peer_uid": "922065597",
                    "chat_type_raw": 2,
                    "forward_messages": [
                        {
                            "sender_id": "10001",
                            "sender_name": "forward-child",
                            "segments": [
                                {
                                    "type": "image",
                                    "file_name": file_name,
                                    "md5": md5,
                                    "extra": {},
                                }
                            ],
                        }
                    ],
                },
            )
        ],
    )


def _top_level_image_message(
    *,
    file_name: str,
    md5: str,
    source_path: str,
    timestamp_ms: int,
) -> NormalizedMessage:
    return NormalizedMessage(
        chat_type="group",
        chat_id="922065597",
        group_id="922065597",
        chat_name="蕾米二次元萌萌群",
        sender_id="10002",
        sender_name="top-level-sender",
        message_id="top-level-msg",
        message_seq="2",
        timestamp_ms=timestamp_ms,
        timestamp_iso="2026-01-10T16:55:01+08:00",
        content=f"[image:{file_name}]",
        text_content="",
        image_file_names=[file_name],
        segments=[
            NormalizedSegment(
                type="image",
                file_name=file_name,
                path=source_path,
                md5=md5,
                extra={},
            )
        ],
    )


def test_recent_forward_image_missing_is_reused_after_later_top_level_success(tmp_path: Path) -> None:
    image_path = tmp_path / "E23A4961D16C0004DBCCB8884A8E427B.jpg"
    image_path.write_bytes(b"image-bytes")
    manager = _MissingImageManager()
    snapshot = NormalizedSnapshot(
        chat_type="group",
        chat_id="922065597",
        chat_name="蕾米二次元萌萌群",
        exported_at=datetime.now(timezone.utc),
        messages=[
            _forward_image_message(
                file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
                md5="e23a4961d16c0004dbccb8884a8e427b",
                timestamp_ms=1768035294000,
            ),
            _top_level_image_message(
                file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
                md5="e23a4961d16c0004dbccb8884a8e427b",
                source_path=str(image_path),
                timestamp_ms=1768035301000,
            ),
        ],
    )

    assets = materialize_snapshot_media(
        snapshot,
        tmp_path / "assets",
        media_resolution_mode="napcat_only",
        media_download_manager=manager,
    )

    assert [item.status for item in assets] == ["reused", "copied"]
    assert assets[0].exported_rel_path == assets[1].exported_rel_path
    assert assets[0].missing_kind is None
    assert assets[0].note is None
    assert manager.public_retry_calls == 0


def test_recent_forward_image_missing_does_not_reuse_different_logical_image(tmp_path: Path) -> None:
    image_path = tmp_path / "DIFFERENT.jpg"
    image_path.write_bytes(b"image-bytes")
    manager = _MissingImageManager()
    snapshot = NormalizedSnapshot(
        chat_type="group",
        chat_id="922065597",
        chat_name="蕾米二次元萌萌群",
        exported_at=datetime.now(timezone.utc),
        messages=[
            _forward_image_message(
                file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
                md5="e23a4961d16c0004dbccb8884a8e427b",
                timestamp_ms=1768035294000,
            ),
            _top_level_image_message(
                file_name="DIFFERENT.jpg",
                md5="different-md5",
                source_path=str(image_path),
                timestamp_ms=1768035301000,
            ),
        ],
    )

    assets = materialize_snapshot_media(
        snapshot,
        tmp_path / "assets",
        media_resolution_mode="napcat_only",
        media_download_manager=manager,
    )

    assert [item.status for item in assets] == ["missing", "copied"]
    assert assets[0].resolver == "missing_after_napcat"
    assert assets[0].missing_kind == "missing_after_napcat"
    assert manager.public_retry_calls == 1


def test_recent_forward_background_missing_is_reused_after_later_top_level_success(tmp_path: Path) -> None:
    image_path = tmp_path / "E23A4961D16C0004DBCCB8884A8E427B.jpg"
    image_path.write_bytes(b"image-bytes")
    manager = _MissingImageManager(missing_resolver="qq_expired_after_napcat")
    snapshot = NormalizedSnapshot(
        chat_type="group",
        chat_id="922065597",
        chat_name="蕾米二次元萌萌群",
        exported_at=datetime.now(timezone.utc),
        messages=[
            _forward_image_message(
                file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
                md5="e23a4961d16c0004dbccb8884a8e427b",
                timestamp_ms=1768035294000,
            ),
            _top_level_image_message(
                file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
                md5="e23a4961d16c0004dbccb8884a8e427b",
                source_path=str(image_path),
                timestamp_ms=1768035301000,
            ),
        ],
    )

    assets = materialize_snapshot_media(
        snapshot,
        tmp_path / "assets",
        media_resolution_mode="napcat_only",
        media_download_manager=manager,
    )

    assert [item.status for item in assets] == ["reused", "copied"]
    assert assets[0].exported_rel_path == assets[1].exported_rel_path
    assert assets[0].missing_kind is None
    assert assets[0].note is None
    assert manager.public_retry_calls == 0
