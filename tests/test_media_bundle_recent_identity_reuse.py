from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from qq_data_core.media_bundle import materialize_snapshot_media
from qq_data_core.models import NormalizedMessage, NormalizedSegment, NormalizedSnapshot


class _MissingAssetManager:
    def __init__(
        self,
        *,
        missing_resolver: str = "missing_after_napcat",
        tracked_asset_types: set[str] | None = None,
    ) -> None:
        self.public_retry_calls = 0
        self.missing_resolver = missing_resolver
        self.tracked_asset_types = tracked_asset_types or {"image"}

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
        if str(request.get("asset_type") or "").strip() in self.tracked_asset_types:
            return None, self.missing_resolver
        return None, None

    def resolve_via_public_token_route(self, request):
        self.public_retry_calls += 1
        _ = request
        return None, None


class _RecoveringPublicRetryManager(_MissingAssetManager):
    def __init__(self, resolved_path: Path, *, tracked_asset_types: set[str] | None = None) -> None:
        super().__init__(
            missing_resolver="missing_after_napcat",
            tracked_asset_types=tracked_asset_types,
        )
        self.resolved_path = resolved_path

    def resolve_via_public_token_route(self, request):
        self.public_retry_calls += 1
        _ = request
        return self.resolved_path, "napcat_public_token_get_image_remote_url_prefetched"


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


def _forward_video_message(*, file_name: str, md5: str, timestamp_ms: int) -> NormalizedMessage:
    return NormalizedMessage(
        chat_type="group",
        chat_id="922065597",
        group_id="922065597",
        chat_name="蕾米二次元萌萌群",
        sender_id="10003",
        sender_name="forward-video-sender",
        message_id="forward-video-msg",
        message_seq="3",
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
                            "sender_id": "10003",
                            "sender_name": "forward-video-child",
                            "segments": [
                                {
                                    "type": "video",
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


def _top_level_video_message(
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
        sender_id="10004",
        sender_name="top-level-video-sender",
        message_id="top-level-video-msg",
        message_seq="4",
        timestamp_ms=timestamp_ms,
        timestamp_iso="2026-01-10T16:55:01+08:00",
        content=f"[video:{file_name}]",
        text_content="",
        segments=[
            NormalizedSegment(
                type="video",
                file_name=file_name,
                path=source_path,
                md5=md5,
                extra={},
            )
        ],
    )


def _run_recent_forward_reuse_case(
    *,
    root_name: str,
    first_missing_resolver: str,
    second_file_name: str,
    second_md5: str,
    expect_statuses: list[str],
    expect_public_retry_calls: int,
) -> list:
    temp_root = Path(".") / "state" / root_name
    try:
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        image_path = temp_root / second_file_name
        image_path.write_bytes(b"image-bytes")
        manager = _MissingAssetManager(missing_resolver=first_missing_resolver)
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
                    file_name=second_file_name,
                    md5=second_md5,
                    source_path=str(image_path),
                    timestamp_ms=1768035301000,
                ),
            ],
        )

        assets = materialize_snapshot_media(
            snapshot,
            temp_root / "assets",
            media_resolution_mode="napcat_only",
            media_download_manager=manager,
        )

        assert [item.status for item in assets] == expect_statuses
        assert manager.public_retry_calls == expect_public_retry_calls
        return assets
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_recent_forward_image_missing_is_reused_after_later_top_level_success() -> None:
    assets = _run_recent_forward_reuse_case(
        root_name="test_temp_recent_forward_reuse_success",
        first_missing_resolver="missing_after_napcat",
        second_file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
        second_md5="e23a4961d16c0004dbccb8884a8e427b",
        expect_statuses=["reused", "copied"],
        expect_public_retry_calls=0,
    )

    assert assets[0].exported_rel_path == assets[1].exported_rel_path
    assert assets[0].missing_kind is None
    assert assets[0].note is None


def test_recent_forward_image_missing_does_not_reuse_different_logical_image() -> None:
    assets = _run_recent_forward_reuse_case(
        root_name="test_temp_recent_forward_reuse_mismatch",
        first_missing_resolver="missing_after_napcat",
        second_file_name="DIFFERENT.jpg",
        second_md5="different-md5",
        expect_statuses=["missing", "copied"],
        expect_public_retry_calls=1,
    )

    assert assets[0].resolver == "missing_after_napcat"
    assert assets[0].missing_kind == "missing_after_napcat"


def test_recent_forward_background_missing_is_reused_after_later_top_level_success() -> None:
    assets = _run_recent_forward_reuse_case(
        root_name="test_temp_recent_forward_reuse_background",
        first_missing_resolver="qq_expired_after_napcat",
        second_file_name="E23A4961D16C0004DBCCB8884A8E427B.jpg",
        second_md5="e23a4961d16c0004dbccb8884a8e427b",
        expect_statuses=["reused", "copied"],
        expect_public_retry_calls=0,
    )

    assert assets[0].exported_rel_path == assets[1].exported_rel_path
    assert assets[0].missing_kind is None
    assert assets[0].note is None


def test_recent_forward_public_retry_clears_missing_kind_after_recovery() -> None:
    temp_root = Path(".") / "state" / "test_temp_public_retry"
    try:
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        image_path = temp_root / "recovered.jpg"
        image_path.write_bytes(b"image-bytes")
        manager = _RecoveringPublicRetryManager(image_path)
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
            ],
        )

        assets = materialize_snapshot_media(
            snapshot,
            temp_root / "assets",
            media_resolution_mode="napcat_only",
            media_download_manager=manager,
        )

        assert [item.status for item in assets] == ["copied"]
        assert assets[0].missing_kind is None
        assert assets[0].note is None
        assert manager.public_retry_calls == 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_recent_forward_video_background_missing_is_reused_after_later_top_level_success() -> None:
    temp_root = Path(".") / "state" / "test_temp_recent_forward_video_reuse"
    try:
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        video_path = temp_root / "shared-video.mp4"
        video_path.write_bytes(b"video-bytes")
        manager = _MissingAssetManager(
            missing_resolver="qq_expired_after_napcat",
            tracked_asset_types={"video"},
        )
        snapshot = NormalizedSnapshot(
            chat_type="group",
            chat_id="922065597",
            chat_name="蕾米二次元萌萌群",
            exported_at=datetime.now(timezone.utc),
            messages=[
                _forward_video_message(
                    file_name="shared-video.mp4",
                    md5="video-md5-shared",
                    timestamp_ms=1768035294000,
                ),
                _top_level_video_message(
                    file_name="shared-video.mp4",
                    md5="video-md5-shared",
                    source_path=str(video_path),
                    timestamp_ms=1768035301000,
                ),
            ],
        )

        assets = materialize_snapshot_media(
            snapshot,
            temp_root / "assets",
            media_resolution_mode="napcat_only",
            media_download_manager=manager,
        )

        assert [item.status for item in assets] == ["reused", "copied"]
        assert assets[0].exported_rel_path == assets[1].exported_rel_path
        assert assets[0].missing_kind is None
        assert assets[0].note is None
        assert manager.public_retry_calls == 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
