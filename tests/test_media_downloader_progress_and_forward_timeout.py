from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import uuid
from concurrent.futures import Future

from qq_data_integrations.napcat.fast_history_client import NapCatFastHistoryTimeoutError
from qq_data_integrations.napcat.fast_history_client import NapCatFastHistoryUnavailable
from qq_data_integrations.napcat.http_client import NapCatApiError
from qq_data_integrations.napcat.http_client import NapCatApiTimeoutError
from qq_data_integrations.napcat.media_downloader import NapCatMediaDownloader


class _DummyClient:
    pass


class _TimeoutPublicFileClient:
    def __init__(self) -> None:
        self.get_file_calls = 0
        self.timeouts: list[float | None] = []

    def get_file(self, *args, **kwargs):
        self.get_file_calls += 1
        self.timeouts.append(kwargs.get("timeout"))
        raise NapCatApiTimeoutError("NapCat action timed out: get_file")


class _TimeoutPublicRecordClient:
    def __init__(self) -> None:
        self.get_record_calls = 0
        self.timeouts: list[float | None] = []

    def get_record(self, *args, **kwargs):
        self.get_record_calls += 1
        self.timeouts.append(kwargs.get("timeout"))
        raise NapCatApiTimeoutError("NapCat action timed out: get_record")


class _MissingDirectFileClient:
    def __init__(self) -> None:
        self.get_file_calls = 0

    def get_file(self, *args, **kwargs):
        self.get_file_calls += 1
        raise NapCatApiError("file not found")


class _MissingPublicFileClient:
    def __init__(self) -> None:
        self.get_file_calls = 0

    def get_file(self, *args, **kwargs):
        self.get_file_calls += 1
        raise NapCatApiError("file not found")


class _MissingPublicRecordClient:
    def __init__(self) -> None:
        self.get_record_calls = 0

    def get_record(self, *args, **kwargs):
        self.get_record_calls += 1
        raise NapCatApiError("file not found")


class _BlankPublicFileClient:
    def __init__(self) -> None:
        self.get_file_calls = 0

    def get_file(self, *args, **kwargs):
        self.get_file_calls += 1
        return {"file": "", "url": ""}


class _RemoteMediaDownloader(NapCatMediaDownloader):
    def __init__(self, remote_cache_dir: Path) -> None:
        super().__init__(_DummyClient(), remote_cache_dir=remote_cache_dir)

    async def _download_remote_payload_async(self, remote_url: str) -> bytes | None:  # type: ignore[override]
        return b"fake-bytes" if remote_url else None


class _CleanupProbeDownloader(NapCatMediaDownloader):
    def __init__(self) -> None:
        super().__init__(_DummyClient())
        self.rebuild_calls: list[tuple[bool, bool]] = []

    def _rebuild_prefetch_executors(self, *, wait: bool, recreate: bool) -> None:  # type: ignore[override]
        self.rebuild_calls.append((wait, recreate))


class _BrokenRemoteRuntimeDownloader(NapCatMediaDownloader):
    def _start_remote_download_runtime(self) -> None:  # type: ignore[override]
        raise RuntimeError("remote media async runtime failed to start")


def _workspace_temp_dir() -> Path:
    root = Path(".tmp") / f"pytest_remote_cache_{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


class _TimeoutForwardClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        raise NapCatFastHistoryTimeoutError("timed out")


class _BatchFastClient:
    def __init__(self, *, raise_timeout: bool = False) -> None:
        self.raise_timeout = raise_timeout
        self.calls: list[list[dict[str, object]]] = []
        self.timeouts: list[object] = []

    def hydrate_media_batch(self, _items, *, timeout=None):
        self.calls.append(list(_items))
        self.timeouts.append(timeout)
        if self.raise_timeout:
            raise NapCatFastHistoryTimeoutError("batch timed out")
        return {"items": []}


class _EmptyForwardClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        return {"assets": []}


class _ErrorForwardClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("forward route exploded")


class _UnavailableForwardClient:
    def __init__(self) -> None:
        self.forward_calls: list[dict[str, object]] = []
        self.media_calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.forward_calls.append(kwargs)
        raise NapCatFastHistoryUnavailable("forward route missing")

    def hydrate_media(self, **kwargs):
        self.media_calls.append(kwargs)
        return {"file": str(Path(__file__).resolve())}


class _UnavailableContextClient:
    def __init__(self) -> None:
        self.forward_calls: list[dict[str, object]] = []
        self.media_calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.forward_calls.append(kwargs)
        return {
            "assets": [
                {
                    "asset_type": "image",
                    "asset_role": "forward_media",
                    "file_name": "forward-ok.jpg",
                    "file": str(Path(__file__).resolve()),
                }
            ]
        }

    def hydrate_media(self, **kwargs):
        self.media_calls.append(kwargs)
        raise NapCatFastHistoryUnavailable("context route missing")


class _SuccessForwardClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "targeted_mode": "metadata_only",
            "assets": [
                {
                    "asset_type": "image",
                    "asset_role": "forward_media",
                    "file_name": "2C167901425EF469C0B1F0BF859E4B2C.jpg",
                    "file": str(Path(__file__).resolve()),
                },
                {
                    "asset_type": "image",
                    "asset_role": "forward_media",
                    "file_name": "49D109C31C9FADA0A156408B75DC1620.png",
                    "file": str(Path(__file__).resolve()),
                },
            ],
        }


class _SlowMismatchedForwardClient:
    def __init__(self, delay_s: float = 0.02) -> None:
        self.delay_s = delay_s
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        time.sleep(self.delay_s)
        return {
            "targeted_mode": "single_target_download",
            "assets": [
                {
                    "asset_type": "video",
                    "asset_role": "forward_media",
                    "file_name": "not-the-requested-video.mp4",
                    "file": str(Path(__file__).resolve()),
                }
            ],
        }


class _RecordingForwardClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        return {"assets": []}


class _OldForwardMetadataTimeoutClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("materialize"):
            raise AssertionError("targeted materialize should be skipped for stale old forward video")
        raise NapCatFastHistoryTimeoutError("timed out")


class _OldForwardTokenOnlyClient:
    def __init__(self, stale_url: str) -> None:
        self.stale_url = stale_url
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("materialize"):
            raise AssertionError("targeted materialize should be skipped after old forward token timeout")
        return {
            "assets": [
                {
                    "asset_type": "video",
                    "asset_role": "forward_media",
                    "file_name": "old-forward-timeout.mp4",
                    "url": self.stale_url,
                    "public_action": "get_file",
                    "public_file_token": "old-forward-timeout-token",
                }
            ]
        }


class _OldForwardMaterializeOnlyTimeoutClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("materialize"):
            raise NapCatFastHistoryTimeoutError("timed out")
        return {"assets": []}


class _OldForwardEmptyClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        return {"assets": []}


class _OldForwardZeroLocalClient:
    def __init__(self, zero_path: str) -> None:
        self.zero_path = zero_path
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("materialize"):
            return {
                "asset_type": "video",
                "asset_role": "forward_media",
                "file_name": "old-forward-zero-local.mp4",
                "file": self.zero_path,
            }
        return {"assets": []}


def _build_forward_request(file_name: str) -> dict[str, object]:
    return {
        "asset_type": "image",
        "asset_role": "forward_media",
        "file_name": file_name,
        "md5": "",
        "download_hint": {
            "_forward_parent": {
                "message_id_raw": "7617760641125573795",
                "element_id": "7617760641125573794",
                "peer_uid": "u_example",
                "chat_type_raw": "2",
            }
        },
    }


def _build_forward_video_request(file_name: str) -> dict[str, object]:
    request = _build_forward_request(file_name)
    request["asset_type"] = "video"
    return request


def _build_forward_speech_request(file_name: str) -> dict[str, object]:
    request = _build_forward_request(file_name)
    request["asset_type"] = "speech"
    return request


def _mark_request_old(request: dict[str, object], *, days: int = 90) -> dict[str, object]:
    updated = dict(request)
    updated["timestamp_ms"] = int((time.time() - (days * 24 * 60 * 60)) * 1000)
    return updated


def _set_forward_parent_identity(
    request: dict[str, object],
    *,
    message_id_raw: str,
    element_id: str,
) -> dict[str, object]:
    updated = dict(request)
    hint = dict(updated.get("download_hint") or {})
    parent = dict(hint.get("_forward_parent") or {})
    parent["message_id_raw"] = message_id_raw
    parent["element_id"] = element_id
    hint["_forward_parent"] = parent
    updated["download_hint"] = hint
    return updated


def _set_forward_stale_local_path(
    request: dict[str, object],
    path: str,
) -> dict[str, object]:
    updated = dict(request)
    hint = dict(updated.get("download_hint") or {})
    hint["url"] = path
    updated["download_hint"] = hint
    updated["source_path"] = path
    return updated


def _build_context_hint_request(file_name: str) -> dict[str, object]:
    return {
        "asset_type": "image",
        "asset_role": "",
        "file_name": file_name,
        "download_hint": {
            "message_id_raw": "7610000000000000001",
            "element_id": "7610000000000000000",
            "peer_uid": "u_example",
            "chat_type_raw": "2",
        },
    }


def test_settle_export_download_progress_clears_pending_counts() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    downloader.begin_export_download_tracking([{"asset_type": "image", "download_hint": {}}])
    cache_key = ("image", "queued")
    downloader._download_operation_states[cache_key] = "queued"
    downloader._download_progress["queued"] = 1
    downloader._download_progress["active"] = 1
    downloader._download_operation_states[("image", "active")] = "active"

    settled = downloader.settle_export_download_progress()

    assert settled["queued"] == 0
    assert settled["active"] == 0


def test_remote_prefetch_runtime_startup_failure_degrades_without_breaking_downloader() -> None:
    downloader = _BrokenRemoteRuntimeDownloader(_DummyClient())

    assert downloader._remote_prefetch_runtime_disabled is True
    assert downloader._remote_prefetch_runtime_disable_reason == "remote media async runtime failed to start"
    assert downloader._public_token_executor is not None
    assert downloader._remote_loop is None
    assert downloader._remote_async_client is None


def test_remote_prefetch_runtime_disabled_process_still_rebuilds_safely() -> None:
    downloader = _BrokenRemoteRuntimeDownloader(_DummyClient())

    downloader._rebuild_prefetch_executors(wait=False, recreate=True)

    assert downloader._remote_prefetch_runtime_disabled is True
    assert downloader._public_token_executor is not None


def test_forward_metadata_timeout_is_short_circuited_for_sibling_assets() -> None:
    fast_client = _TimeoutForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    first = downloader._download_via_forward_context(
        _build_forward_request("2C167901425EF469C0B1F0BF859E4B2C.jpg"),
        materialize=False,
    )
    second = downloader._download_via_forward_context(
        _build_forward_request("49D109C31C9FADA0A156408B75DC1620.png"),
        materialize=False,
    )

    assert first is None
    assert second is None
    assert len(fast_client.calls) == 1


def test_forward_metadata_empty_result_is_short_circuited_for_sibling_assets() -> None:
    fast_client = _EmptyForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    first = downloader._download_via_forward_context(
        _build_forward_request("2C167901425EF469C0B1F0BF859E4B2C.jpg"),
        materialize=False,
    )
    second = downloader._download_via_forward_context(
        _build_forward_request("49D109C31C9FADA0A156408B75DC1620.png"),
        materialize=False,
    )

    assert first is None
    assert second is None
    assert len(fast_client.calls) == 1
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_context_empty_count"] == 1


def test_forward_metadata_error_is_short_circuited_for_sibling_assets() -> None:
    fast_client = _ErrorForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    first = downloader._download_via_forward_context(
        _build_forward_request("2C167901425EF469C0B1F0BF859E4B2C.jpg"),
        materialize=False,
    )
    second = downloader._download_via_forward_context(
        _build_forward_request("49D109C31C9FADA0A156408B75DC1620.png"),
        materialize=False,
    )

    assert first is None
    assert second is None
    assert len(fast_client.calls) == 1
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_context_error_count"] == 1


def test_forward_route_unavailable_does_not_disable_regular_context_hydration() -> None:
    fast_client = _UnavailableForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    forward_result = downloader._download_via_forward_context(
        _build_forward_request("forward-a.jpg"),
        materialize=False,
    )
    context_payload = downloader._download_via_context(
        _build_context_hint_request("context-a.jpg")["download_hint"],
        asset_type="image",
        asset_role=None,
        request=_build_context_hint_request("context-a.jpg"),
    )

    assert forward_result is None
    assert len(fast_client.forward_calls) == 1
    assert len(fast_client.media_calls) == 1
    assert context_payload is not None
    assert downloader._fast_context_route_disabled is False
    assert downloader._fast_forward_context_route_disabled is True


def test_regular_context_unavailable_does_not_disable_forward_hydration() -> None:
    fast_client = _UnavailableContextClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    context_payload = downloader._download_via_context(
        _build_context_hint_request("context-b.jpg")["download_hint"],
        asset_type="image",
        asset_role=None,
        request=_build_context_hint_request("context-b.jpg"),
    )
    forward_result = downloader._download_via_forward_context(
        _build_forward_request("forward-ok.jpg"),
        materialize=False,
    )

    assert context_payload is None
    assert len(fast_client.media_calls) == 1
    assert len(fast_client.forward_calls) == 1
    assert forward_result == (Path(__file__).resolve(), "napcat_forward_hydrated")
    assert downloader._fast_context_route_disabled is True
    assert downloader._fast_forward_context_route_disabled is False


def test_forward_metadata_success_payload_is_reused_for_sibling_assets() -> None:
    fast_client = _SuccessForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    first = downloader._download_via_forward_context(
        _build_forward_request("2C167901425EF469C0B1F0BF859E4B2C.jpg"),
        materialize=False,
    )
    second = downloader._download_via_forward_context(
        _build_forward_request("49D109C31C9FADA0A156408B75DC1620.png"),
        materialize=False,
    )

    assert len(fast_client.calls) == 1
    assert first == (Path(__file__).resolve(), "napcat_forward_hydrated")
    assert second == (Path(__file__).resolve(), "napcat_forward_hydrated")


def test_forward_video_public_token_timeout_skips_later_retry_even_with_new_token() -> None:
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client)
    request = _build_forward_video_request("slow-forward-video.mp4")

    first = downloader._call_public_action_with_token(
        "get_file",
        "first-token",
        request=request,
    )
    second = downloader._call_public_action_with_token(
        "get_file",
        "second-token",
        request=request,
    )

    assert first is None
    assert second is None
    assert client.get_file_calls == 2


def test_forward_video_materialize_timeout_skips_later_retry_for_sibling_assets() -> None:
    fast_client = _TimeoutForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    first = downloader._download_via_forward_context(
        _build_forward_video_request("slow-forward-video-a.mp4"),
        materialize=True,
    )
    second = downloader._download_via_forward_context(
        _build_forward_video_request("slow-forward-video-b.mp4"),
        materialize=True,
    )

    assert first is None
    assert second is None
    assert len(fast_client.calls) == 1


def test_forward_video_public_token_timeout_skips_later_retry_for_sibling_assets() -> None:
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client)

    first = downloader._call_public_action_with_token(
        "get_file",
        "first-token",
        request=_build_forward_video_request("slow-forward-video-a.mp4"),
    )
    second = downloader._call_public_action_with_token(
        "get_file",
        "second-token",
        request=_build_forward_video_request("slow-forward-video-b.mp4"),
    )

    assert first is None
    assert second is None
    assert client.get_file_calls == 2


def test_forward_speech_materialize_timeout_skips_later_retry_for_sibling_assets() -> None:
    fast_client = _TimeoutForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    first = downloader._download_via_forward_context(
        _build_forward_speech_request("slow-forward-audio-a.amr"),
        materialize=True,
    )
    second = downloader._download_via_forward_context(
        _build_forward_speech_request("slow-forward-audio-b.amr"),
        materialize=True,
    )

    assert first is None
    assert second is None
    assert len(fast_client.calls) == 1


def test_forward_speech_public_token_timeout_skips_later_retry_for_sibling_assets() -> None:
    client = _TimeoutPublicRecordClient()
    downloader = NapCatMediaDownloader(client)

    first = downloader._call_public_action_with_token(
        "get_record",
        "first-token",
        request=_build_forward_speech_request("slow-forward-audio-a.amr"),
    )
    second = downloader._call_public_action_with_token(
        "get_record",
        "second-token",
        request=_build_forward_speech_request("slow-forward-audio-b.amr"),
    )

    assert first is None
    assert second is None
    assert client.get_record_calls == 2


def test_old_forward_video_uses_shorter_public_token_timeout() -> None:
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-timeout.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-timeout.mp4",
    )

    assert downloader._call_public_action_with_token(
        "get_file",
        "old-forward-timeout-token",
        request=request,
    ) is None

    assert client.get_file_calls == 1
    assert client.timeouts == [downloader.OLD_FORWARD_EXPENSIVE_PUBLIC_TOKEN_TIMEOUT_S]


def test_old_forward_video_uses_shorter_forward_context_timeouts() -> None:
    fast_client = _RecordingForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-context.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-context.mp4",
    )

    assert downloader._download_via_forward_context(request, materialize=False) is None
    assert downloader._download_via_forward_context(request, materialize=True) is None

    assert [call.get("timeout") for call in fast_client.calls] == [
        downloader.OLD_FORWARD_EXPENSIVE_METADATA_TIMEOUT_S,
        downloader.OLD_FORWARD_EXPENSIVE_MATERIALIZE_TIMEOUT_S,
    ]


def test_old_forward_video_metadata_timeout_is_classified_before_targeted_materialize() -> None:
    fast_client = _OldForwardMetadataTimeoutClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-metadata-timeout.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-metadata-timeout.mp4",
    )

    resolved = downloader.resolve_for_export(request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert len(fast_client.calls) == 1
    assert fast_client.calls[0].get("materialize") is False


def test_old_forward_video_public_token_timeout_is_classified_before_targeted_materialize() -> None:
    stale_url = r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-timeout.mp4"
    fast_client = _OldForwardTokenOnlyClient(stale_url)
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client, fast_client=fast_client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-timeout.mp4"), days=240),
        stale_url,
    )

    resolved = downloader.resolve_for_export(request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert client.get_file_calls == 1
    assert client.timeouts == [downloader.OLD_FORWARD_EXPENSIVE_PUBLIC_TOKEN_TIMEOUT_S]
    assert len(fast_client.calls) == 1
    assert fast_client.calls[0].get("materialize") is False


def test_old_forward_video_materialize_timeout_is_classified_as_expired() -> None:
    fast_client = _OldForwardMaterializeOnlyTimeoutClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-materialize-timeout.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-materialize-timeout.mp4",
    )

    resolved = downloader.resolve_for_export(request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert len(fast_client.calls) == 2
    assert fast_client.calls[0].get("materialize") is False
    assert fast_client.calls[1].get("materialize") is True


def test_old_forward_video_materialize_empty_is_classified_as_expired() -> None:
    fast_client = _OldForwardEmptyClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-materialize-empty.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-materialize-empty.mp4",
    )

    resolved = downloader.resolve_for_export(request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert len(fast_client.calls) == 2
    assert fast_client.calls[0].get("materialize") is False
    assert fast_client.calls[1].get("materialize") is True


def test_old_forward_video_materialize_zero_local_is_classified_as_expired() -> None:
    temp_root = _workspace_temp_dir()
    try:
        zero_path = temp_root / "zero" / "old-forward-zero-local.mp4"
        zero_path.parent.mkdir(parents=True, exist_ok=True)
        zero_path.write_bytes(b"")
        fast_client = _OldForwardZeroLocalClient(str(zero_path))
        downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
        request = _set_forward_stale_local_path(
            _mark_request_old(_build_forward_video_request("old-forward-zero-local.mp4"), days=240),
            r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-zero-local.mp4",
        )

        resolved = downloader.resolve_for_export(request)

        assert resolved == (None, "qq_expired_after_napcat")
        assert len(fast_client.calls) == 2
        assert fast_client.calls[0].get("materialize") is False
        assert fast_client.calls[1].get("materialize") is True
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_old_forward_video_public_not_found_is_classified_as_expired() -> None:
    client = _MissingPublicFileClient()
    downloader = NapCatMediaDownloader(client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-public-not-found.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-public-not-found.mp4",
    )
    request["download_hint"]["file_id"] = "/fileid/old-forward-public-not-found"
    payload = {
        "public_action": "get_file",
        "public_file_token": "old-forward-public-not-found-token",
        "file_name": "old-forward-public-not-found.mp4",
        "asset_type": "video",
        "file_id": "/fileid/old-forward-public-not-found",
    }

    resolved = downloader._resolve_from_public_token(payload, request=request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert client.get_file_calls == 1


def test_old_forward_speech_public_not_found_is_classified_as_expired() -> None:
    client = _MissingPublicRecordClient()
    downloader = NapCatMediaDownloader(client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_request("old-forward-public-not-found.mp3"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Audio\2025-05\Ori\old-forward-public-not-found.mp3",
    )
    request["asset_type"] = "speech"
    payload = {
        "public_action": "get_record",
        "public_file_token": "old-forward-public-not-found-token",
        "file_name": "old-forward-public-not-found.mp3",
        "asset_type": "speech",
    }

    resolved = downloader._resolve_from_public_token(payload, request=request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert client.get_record_calls == 1


def test_old_forward_video_route_unavailable_is_classified_as_expired() -> None:
    fast_client = _UnavailableForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-unavailable.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-unavailable.mp4",
    )

    resolved = downloader.resolve_for_export(request)

    assert resolved == (None, "qq_expired_after_napcat")
    assert len(fast_client.forward_calls) == 1


def test_old_forward_video_direct_file_not_found_is_classified_as_expired() -> None:
    downloader = NapCatMediaDownloader(_MissingDirectFileClient())
    request = _set_forward_stale_local_path(
        _mark_request_old(_build_forward_video_request("old-forward-direct-not-found.mp4"), days=240),
        r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\old-forward-direct-not-found.mp4",
    )
    request["download_hint"]["file_id"] = "/fileid/old-forward-direct-not-found"

    resolved = downloader._resolve_via_direct_file_id(request)

    assert resolved == (None, "qq_expired_after_napcat")


def test_malformed_forward_parent_with_live_remote_url_still_recovers() -> None:
    remote_root = _workspace_temp_dir()
    try:
        downloader = _RemoteMediaDownloader(remote_root)
        request = _set_forward_stale_local_path(
            _mark_request_old(_build_forward_video_request("malformed-forward-live-remote.mp4"), days=240),
            r"D:\QQHOT\Tencent Files\2141129832\nt_qq\nt_data\Video\2025-05\Ori\malformed-forward-live-remote.mp4",
        )
        hint = dict(request.get("download_hint") or {})
        hint["_forward_parent"] = {
            "message_id_raw": "7617760641125573795",
            "element_id": "",
            "peer_uid": "u_example",
            "chat_type_raw": "2",
        }
        hint["remote_url"] = "https://assets.example.invalid/malformed-forward-live-remote.mp4"
        request["download_hint"] = hint

        resolved_path, resolver = downloader.resolve_for_export(request)

        assert resolver == "napcat_forward_remote_url"
        assert resolved_path is not None
        assert Path(resolved_path).exists()
    finally:
        shutil.rmtree(remote_root, ignore_errors=True)


def test_forward_video_public_token_timeout_breaker_skips_distinct_old_parents_after_limit() -> None:
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client)

    for index in range(downloader.FORWARD_TIMEOUT_STORM_LIMIT):
        request = _mark_request_old(
            _build_forward_video_request(f"storm-video-{index}.mp4"),
            days=90,
        )
        parent = request["download_hint"]["_forward_parent"]  # type: ignore[index]
        parent["message_id_raw"] = f"7618{index:012d}"  # type: ignore[index]
        parent["element_id"] = f"7618{index:012d}"  # type: ignore[index]
        assert downloader._call_public_action_with_token(
            "get_file",
            f"storm-token-{index}",
            request=request,
        ) is None

    skipped_request = _mark_request_old(
        _build_forward_video_request("storm-video-skip.mp4"),
        days=90,
    )
    skipped_parent = skipped_request["download_hint"]["_forward_parent"]  # type: ignore[index]
    skipped_parent["message_id_raw"] = "7618999999999999"  # type: ignore[index]
    skipped_parent["element_id"] = "7618999999999999"  # type: ignore[index]
    assert downloader._call_public_action_with_token(
        "get_file",
        "storm-token-skip",
        request=skipped_request,
    ) is None

    assert client.get_file_calls == downloader.FORWARD_TIMEOUT_STORM_LIMIT
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_timeout_storm_skip_count"] == 1


def test_forward_video_materialize_timeout_breaker_skips_distinct_old_parents_after_limit() -> None:
    fast_client = _TimeoutForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    for index in range(downloader.FORWARD_TIMEOUT_STORM_LIMIT):
        request = _mark_request_old(
            _build_forward_video_request(f"storm-mat-{index}.mp4"),
            days=90,
        )
        parent = request["download_hint"]["_forward_parent"]  # type: ignore[index]
        parent["message_id_raw"] = f"7628{index:012d}"  # type: ignore[index]
        parent["element_id"] = f"7628{index:012d}"  # type: ignore[index]
        assert downloader._download_via_forward_context(
            request,
            materialize=True,
        ) is None

    skipped_request = _mark_request_old(
        _build_forward_video_request("storm-mat-skip.mp4"),
        days=90,
    )
    skipped_parent = skipped_request["download_hint"]["_forward_parent"]  # type: ignore[index]
    skipped_parent["message_id_raw"] = "7628999999999999"  # type: ignore[index]
    skipped_parent["element_id"] = "7628999999999999"  # type: ignore[index]
    assert downloader._download_via_forward_context(
        skipped_request,
        materialize=True,
    ) is None

    assert len(fast_client.calls) == downloader.FORWARD_TIMEOUT_STORM_LIMIT
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_timeout_storm_skip_count"] == 1


def test_forward_video_direct_file_id_timeout_breaker_skips_distinct_old_parents_after_limit() -> None:
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client)

    for index in range(downloader.FORWARD_TIMEOUT_STORM_LIMIT):
        request = _mark_request_old(
            _build_forward_video_request(f"storm-direct-{index}.mp4"),
            days=90,
        )
        request["download_hint"]["file_id"] = f"/storm/{index}"  # type: ignore[index]
        parent = request["download_hint"]["_forward_parent"]  # type: ignore[index]
        parent["message_id_raw"] = f"7638{index:012d}"  # type: ignore[index]
        parent["element_id"] = f"7638{index:012d}"  # type: ignore[index]
        assert downloader._resolve_via_direct_file_id(request) is None

    skipped_request = _mark_request_old(
        _build_forward_video_request("storm-direct-skip.mp4"),
        days=90,
    )
    skipped_request["download_hint"]["file_id"] = "/storm/skip"  # type: ignore[index]
    skipped_parent = skipped_request["download_hint"]["_forward_parent"]  # type: ignore[index]
    skipped_parent["message_id_raw"] = "7638999999999999"  # type: ignore[index]
    skipped_parent["element_id"] = "7638999999999999"  # type: ignore[index]
    assert downloader._resolve_via_direct_file_id(skipped_request) is None

    assert client.get_file_calls == downloader.FORWARD_TIMEOUT_STORM_LIMIT
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_timeout_storm_skip_count"] == 1


def test_forward_video_public_token_timeout_breaker_groups_very_old_months_together() -> None:
    client = _TimeoutPublicFileClient()
    downloader = NapCatMediaDownloader(client)
    downloader.FORWARD_TIMEOUT_STORM_LIMIT = 2

    first = _set_forward_parent_identity(
        _mark_request_old(_build_forward_video_request("old-1.mp4"), days=240),
        message_id_raw="8618000000000001",
        element_id="8618000000000001",
    )
    second = _set_forward_parent_identity(
        _mark_request_old(_build_forward_video_request("old-2.mp4"), days=300),
        message_id_raw="8618000000000002",
        element_id="8618000000000002",
    )
    third = _set_forward_parent_identity(
        _mark_request_old(_build_forward_video_request("old-3.mp4"), days=330),
        message_id_raw="8618000000000003",
        element_id="8618000000000003",
    )

    assert downloader._call_public_action_with_token("get_file", "old-token-1", request=first) is None
    assert downloader._call_public_action_with_token("get_file", "old-token-2", request=second) is None
    assert downloader._call_public_action_with_token("get_file", "old-token-3", request=third) is None

    assert client.get_file_calls == 2
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_timeout_storm_skip_count"] == 1


def test_forward_video_materialize_slow_noop_contributes_to_breaker_for_very_old_assets() -> None:
    fast_client = _SlowMismatchedForwardClient(delay_s=0.02)
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    downloader.FORWARD_TIMEOUT_STORM_LIMIT = 2
    downloader.FORWARD_TIMEOUT_STORM_SLOW_NOOP_ELAPSED_S = 0.01

    first = _set_forward_parent_identity(
        _mark_request_old(_build_forward_video_request("noop-1.mp4"), days=240),
        message_id_raw="8718000000000001",
        element_id="8718000000000001",
    )
    second = _set_forward_parent_identity(
        _mark_request_old(_build_forward_video_request("noop-2.mp4"), days=300),
        message_id_raw="8718000000000002",
        element_id="8718000000000002",
    )
    third = _set_forward_parent_identity(
        _mark_request_old(_build_forward_video_request("noop-3.mp4"), days=330),
        message_id_raw="8718000000000003",
        element_id="8718000000000003",
    )

    assert downloader._download_via_forward_context(first, materialize=True) in {None, (None, None)}
    assert downloader._download_via_forward_context(second, materialize=True) in {None, (None, None)}
    assert downloader._download_via_forward_context(third, materialize=True) in {None, (None, None)}

    assert len(fast_client.calls) == 2
    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["forward_timeout_storm_skip_count"] == 1


def test_prefetched_forward_remote_payload_is_used_before_metadata_requery() -> None:
    temp_root = _workspace_temp_dir()
    downloader = _RemoteMediaDownloader(temp_root / "remote_cache")
    request = _build_forward_request("prefetched-forward.jpg")
    key = downloader._request_key(request)
    downloader._prefetched_forward_media_payloads[key] = {
        "asset_type": "image",
        "file_name": "prefetched-forward.jpg",
        "remote_url": "https://example.invalid/prefetched-forward.jpg",
    }

    def _unexpected_forward_context(*args, **kwargs):
        raise AssertionError("forward metadata hydration should not re-run when a prefetched payload exists")

    downloader._download_via_forward_context = _unexpected_forward_context  # type: ignore[method-assign]

    try:
        resolved, resolver = downloader.resolve_for_export(request)
        assert resolved is not None
        assert resolver == "napcat_forward_remote_url"
        assert resolved.exists()
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_prefetched_forward_public_token_is_used_before_metadata_requery() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    request = _build_forward_request("prefetched-forward-token.jpg")
    key = downloader._request_key(request)
    downloader._prefetched_forward_media_payloads[key] = {
        "asset_type": "image",
        "file_name": "prefetched-forward-token.jpg",
        "public_file_token": "public-token",
    }

    def _unexpected_forward_context(*args, **kwargs):
        raise AssertionError("forward metadata hydration should not re-run when a prefetched payload exists")

    downloader._download_via_forward_context = _unexpected_forward_context  # type: ignore[method-assign]
    downloader._resolve_from_public_token = (  # type: ignore[method-assign]
        lambda payload, **kwargs: (Path(__file__).resolve(), "napcat_get_image")
    )

    resolved, resolver = downloader.resolve_for_export(request)

    assert resolved == Path(__file__).resolve()
    assert resolver == "napcat_get_image"


def test_forward_match_prefers_remote_url_before_public_token() -> None:
    temp_root = _workspace_temp_dir()
    downloader = _RemoteMediaDownloader(temp_root / "remote_cache")
    request = _build_forward_request("forward-remote-first.jpg")
    public_token_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _unexpected_public_token(*args, **kwargs):
        public_token_calls.append((args, kwargs))
        raise AssertionError("public token action should not run when forward remote URL already succeeds")

    downloader._resolve_from_public_token = _unexpected_public_token  # type: ignore[method-assign]

    try:
        resolved, matched = downloader._pick_forward_asset_match(
            request,
            [
                {
                    "asset_type": "image",
                    "asset_role": "forward_media",
                    "file_name": "forward-remote-first.jpg",
                    "remote_url": "https://example.invalid/forward-remote-first.jpg",
                    "public_action": "get_image",
                    "public_file_token": "public-token",
                }
            ],
        )
        assert matched is not None
        assert resolved[0] is not None
        assert resolved[1] == "napcat_forward_remote_url"
        assert public_token_calls == []
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_forward_match_prefers_local_path_before_public_token() -> None:
    temp_root = _workspace_temp_dir()
    downloader = NapCatMediaDownloader(_DummyClient())
    local_path = temp_root / "forward-local-first.jpg"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(b"local")
    request = _build_forward_request("forward-local-first.jpg")

    try:
        resolved, matched = downloader._pick_forward_asset_match(
            request,
            [
                {
                    "asset_type": "image",
                    "asset_role": "forward_media",
                    "file_name": "forward-local-first.jpg",
                    "public_action": "get_image",
                    "public_file_token": "public-token",
                },
                {
                    "asset_type": "image",
                    "asset_role": "forward_media",
                    "file_name": "forward-local-first.jpg",
                    "file": str(local_path),
                },
            ],
        )
        assert matched is not None
        assert resolved[0] == local_path.resolve()
        assert resolved[1] == "napcat_forward_hydrated"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_recent_forward_video_missing_is_not_shared_without_terminal_expired_resolver() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    request = _build_forward_video_request("recent-forward-video.mp4")
    request["timestamp_ms"] = int(
        (datetime.now(timezone.utc) - timedelta(days=20)).timestamp() * 1000
    )

    assert downloader._should_share_missing_outcome(request, resolver=None) is False
    assert downloader._should_share_missing_outcome(
        request,
        resolver="missing_after_napcat",
    ) is False
    assert downloader._should_share_missing_outcome(
        request,
        resolver="qq_expired_after_napcat",
    ) is True


def test_recent_forward_speech_missing_is_not_shared_without_terminal_expired_resolver() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    request = _build_forward_speech_request("recent-forward-speech.mp3")
    request["timestamp_ms"] = int(
        (datetime.now(timezone.utc) - timedelta(days=20)).timestamp() * 1000
    )

    assert downloader._should_share_missing_outcome(request, resolver=None) is False
    assert downloader._should_share_missing_outcome(
        request,
        resolver="missing_after_napcat",
    ) is False
    assert downloader._should_share_missing_outcome(
        request,
        resolver="qq_expired_after_napcat",
    ) is True


def test_forward_file_shared_request_key_requires_strong_identity() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    request = _build_forward_video_request("generic-name.mp4")

    assert downloader._shared_request_key(request) is None

    request["md5"] = "abcd1234"
    assert downloader._shared_request_key(request) is not None


def test_request_scoped_public_timeout_key_is_candidate_aware() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    request = _build_forward_video_request("candidate-a.mp4")
    key_a = downloader._request_scoped_public_action_timeout_key(
        request,
        action="get_file",
        token="token-a",
    )
    request_b = _build_forward_video_request("candidate-b.mp4")
    key_b = downloader._request_scoped_public_action_timeout_key(
        request_b,
        action="get_file",
        token="token-b",
    )

    assert key_a is not None
    assert key_b is not None
    assert key_a != key_b


def test_remote_media_download_prepares_cache_dir_on_first_use() -> None:
    temp_root = _workspace_temp_dir()
    downloader = _RemoteMediaDownloader(temp_root / "remote_cache")

    try:
        resolved, used_cached = asyncio.run(
            downloader._download_remote_media_async(
                asset_type="image",
                file_name="example.jpg",
                hint={"url": "https://example.invalid/example.jpg"},
            )
        )
        assert resolved is not None
        assert used_cached is False
        resolved_path = Path(resolved)
        assert resolved_path.exists()
        assert resolved_path.read_bytes() == b"fake-bytes"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_remote_sticker_download_prepares_cache_dir_on_first_use() -> None:
    temp_root = _workspace_temp_dir()
    downloader = _RemoteMediaDownloader(temp_root / "remote_cache")
    downloader._download_remote_payload = lambda remote_url: b"gif-bytes"  # type: ignore[method-assign]

    try:
        resolved = downloader._download_remote_sticker(
            {"remote_url": "https://example.invalid/example.gif", "remote_file_name": "example.gif"},
            asset_role="dynamic",
            file_name="example.gif",
        )

        assert resolved is not None
        resolved_path = Path(resolved)
        assert resolved_path.exists()
        assert resolved_path.read_bytes() == b"gif-bytes"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_public_token_placeholder_missing_is_classified_before_remote_attempt() -> None:
    temp_root = _workspace_temp_dir()
    source_path = temp_root / "Pic" / "2025-09" / "Ori" / "700B81F97B9D06E7999DF7504442D46C.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"")
    sibling_placeholder = source_path.parent.parent / "OriTemp" / source_path.name
    sibling_placeholder.parent.mkdir(parents=True, exist_ok=True)
    sibling_placeholder.write_bytes(b"")

    downloader = NapCatMediaDownloader(_DummyClient())
    public_token_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _unexpected_public_token(*args, **kwargs):
        public_token_calls.append((args, kwargs))
        return {
            "url": "https://gchat.qpic.cn/gchatpic_new/0/0-0-700B81F97B9D06E7999DF7504442D46C/0"
        }

    downloader._call_public_action_with_token = _unexpected_public_token  # type: ignore[method-assign]

    def _unexpected_remote_download(*args, **kwargs):
        raise AssertionError("remote URL download should not run when placeholder missing is already classified")

    downloader._download_remote_media = _unexpected_remote_download  # type: ignore[method-assign]

    try:
        resolved, resolver = downloader._resolve_from_public_token(
            {
                "asset_type": "image",
                "public_action": "get_image",
                "public_file_token": "public-token",
                "file_name": source_path.name,
            },
            old_bucket=("image", "2025-09"),
            request={
                "asset_type": "image",
                "file_name": source_path.name,
                "source_path": str(source_path),
            },
        )
        assert resolved is None
        assert resolver == "qq_not_downloaded_local_placeholder"
        assert public_token_calls == []
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_prepare_for_export_skips_remote_prefetch_for_old_placeholder_image() -> None:
    temp_root = _workspace_temp_dir()
    source_path = temp_root / "Pic" / "2025-09" / "Ori" / "PLACEHOLDER_B.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    sibling_placeholder = source_path.parent.parent / "OriTemp" / source_path.name
    sibling_placeholder.parent.mkdir(parents=True, exist_ok=True)
    sibling_placeholder.write_bytes(b"")

    class _CountingDownloader(NapCatMediaDownloader):
        def __init__(self) -> None:
            super().__init__(_DummyClient(), fast_client=_BatchFastClient())
            self.scheduled_requests: list[str] = []

        def _schedule_request_remote_prefetch(self, request):  # type: ignore[override]
            self.scheduled_requests.append(str(request.get("file_name") or ""))

    downloader = _CountingDownloader()
    request = {
        "asset_type": "image",
        "file_name": source_path.name,
        "source_path": str(source_path),
        "timestamp_ms": 1750000000000,
        "download_hint": {
            "message_id_raw": "7610000000000000003",
            "element_id": "7610000000000000002",
            "peer_uid": "u_example",
            "chat_type_raw": "2",
            "url": "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=dummy&spec=0",
        },
    }

    try:
        downloader.prepare_for_export([request])
        assert downloader.scheduled_requests == []
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_resolve_via_context_only_skips_old_placeholder_image_before_context_hydration() -> None:
    temp_root = _workspace_temp_dir()
    source_path = temp_root / "Pic" / "2025-09" / "Ori" / "PLACEHOLDER_CONTEXT_SKIP.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"")
    sibling_placeholder = source_path.parent.parent / "OriTemp" / source_path.name
    sibling_placeholder.parent.mkdir(parents=True, exist_ok=True)
    sibling_placeholder.write_bytes(b"")
    downloader = NapCatMediaDownloader(_DummyClient())
    request = {
        "asset_type": "image",
        "file_name": source_path.name,
        "source_path": str(source_path),
        "timestamp_ms": 1750000000000,
        "download_hint": {
            "message_id_raw": "7610000000000000401",
            "element_id": "7610000000000000400",
            "peer_uid": "u_example",
            "chat_type_raw": "2",
        },
    }

    def _unexpected_context(*args, **kwargs):
        raise AssertionError("old placeholder image should be classified before context hydration")

    downloader._download_via_context = _unexpected_context  # type: ignore[method-assign]

    try:
        resolved, resolver = downloader._resolve_via_context_only(request)
        assert resolved is None
        assert resolver == "qq_not_downloaded_local_placeholder"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_resolve_for_export_prefers_existing_source_path_for_non_image_assets() -> None:
    temp_root = _workspace_temp_dir()
    downloader = NapCatMediaDownloader(_DummyClient())
    try:
        for asset_type, suffix in (
            ("video", "mp4"),
            ("file", "bin"),
            ("speech", "mp3"),
        ):
            source_path = temp_root / asset_type / f"existing-source.{suffix}"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(f"{asset_type}-bytes".encode("utf-8"))

            resolved, resolver = downloader.resolve_for_export(
                {
                    "asset_type": asset_type,
                    "file_name": source_path.name,
                    "source_path": str(source_path),
                    "download_hint": {},
                }
            )

            assert resolved == source_path.resolve()
            assert resolver == "source_local_path"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_stale_image_neighbor_does_not_accept_zero_byte_source_self() -> None:
    temp_root = _workspace_temp_dir()
    source_path = temp_root / "nt_qq" / "nt_data" / "Pic" / "2025-09" / "Ori" / "ZERO_SELF.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"")
    downloader = NapCatMediaDownloader(_DummyClient())
    try:
        resolved = downloader._resolve_from_stale_local_neighbors(
            {
                "asset_type": "image",
                "file_name": source_path.name,
                "source_path": str(source_path),
            }
        )
        assert resolved == (None, None)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_prepare_for_export_uses_metadata_only_batch_prefetch_with_timeout() -> None:
    fast_client = _BatchFastClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    request = _build_context_hint_request("sample-image.png")

    downloader.prepare_for_export([request])

    assert fast_client.calls
    assert fast_client.timeouts == [downloader.PREFETCH_BATCH_TIMEOUT_S]
    first_item = fast_client.calls[0][0]
    assert first_item["metadata_only"] is True


def test_prepare_for_export_emits_prepare_progress_events() -> None:
    fast_client = _BatchFastClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    requests = [
        _build_context_hint_request("sample-image-1.png"),
        _build_context_hint_request("sample-image-2.png"),
    ]
    progress_events: list[dict[str, object]] = []

    downloader.prepare_for_export(requests, progress_callback=progress_events.append)

    prepare_events = [
        event
        for event in progress_events
        if str(event.get("phase") or "") == "prefetch_media_prepare"
    ]
    assert prepare_events
    assert str(prepare_events[0].get("stage") or "") == "start"
    assert str(prepare_events[-1].get("stage") or "") == "done"
    assert int(prepare_events[-1].get("scanned_request_count") or 0) == 2
    assert int(prepare_events[-1].get("context_request_count") or 0) == 2
    assert "elapsed_s" in prepare_events[-1]


def test_prepare_for_export_stops_after_prefetch_budget_exceeded() -> None:
    fast_client = _BatchFastClient(raise_timeout=True)
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    downloader.PREFETCH_BATCH_TIMEOUT_STRIKE_LIMIT = 99
    downloader.PREFETCH_TOTAL_BUDGET_S = 0.0
    request = _build_context_hint_request("sample-image.png")

    try:
        downloader.prepare_for_export([request])
    except RuntimeError as exc:
        assert "exceeding total budget" in str(exc)
    else:
        raise AssertionError("expected prefetch budget guard to stop the batch prefetch")


def test_prepare_for_export_skips_old_bucket_requests_in_metadata_batch_prefetch() -> None:
    fast_client = _BatchFastClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    downloader.PREFETCH_LARGE_REQUEST_THRESHOLD = 1
    request = {
        "asset_type": "image",
        "file_name": "old-prefetch-skip.jpg",
        "timestamp_ms": 1750000000000,
        "download_hint": {
            "message_id_raw": "7610000000000000301",
            "element_id": "7610000000000000300",
            "peer_uid": "u_example",
            "chat_type_raw": "2",
        },
    }

    downloader.prepare_for_export([request])

    assert fast_client.calls == []


def test_prepare_for_export_uses_smaller_batches_and_explicit_timeout_for_large_runs() -> None:
    fast_client = _BatchFastClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    downloader.PREFETCH_LARGE_REQUEST_THRESHOLD = 50
    downloader.PREFETCH_LARGE_BATCH_SIZE = 10
    downloader.PREFETCH_BATCH_TIMEOUT_S = 12.5
    requests = []
    for index in range(0, 51):
        request = _build_context_hint_request(f"context-{index}.jpg")
        request["timestamp_ms"] = 1770000000000
        requests.append(request)

    downloader.prepare_for_export(requests)

    assert [len(batch) for batch in fast_client.calls] == [10, 10, 10, 10, 10, 1]
    assert fast_client.timeouts == [12.5, 12.5, 12.5, 12.5, 12.5, 12.5]


def test_prepare_for_export_degrades_after_repeated_batch_timeouts() -> None:
    fast_client = _BatchFastClient(raise_timeout=True)
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)
    downloader.PREFETCH_BATCH_SIZE = 5
    downloader.PREFETCH_BATCH_TIMEOUT_STRIKE_LIMIT = 2
    requests = []
    for index in range(0, 15):
        request = _build_context_hint_request(f"timeout-{index}.jpg")
        request["timestamp_ms"] = 1770000000000
        requests.append(request)
    progress_events: list[dict[str, object]] = []

    try:
        downloader.prepare_for_export(
            requests,
            progress_callback=progress_events.append,
        )
    except RuntimeError as exc:
        assert "repeated batch hydrate timeouts" in str(exc)
    else:
        raise AssertionError("prepare_for_export should degrade after repeated batch timeouts")

    assert len(fast_client.calls) == 2
    error_events = [
        event for event in progress_events
        if str(event.get("phase") or "") == "prefetch_media_chunk"
        and str(event.get("stage") or "") == "error"
    ]
    assert len(error_events) == 2
    assert all(str(event.get("reason") or "") == "chunk_timeout" for event in error_events)


def test_classify_missing_from_public_payload_marks_old_file_without_path_or_url_as_background() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())

    classification = downloader._classify_missing_from_public_payload(
        {
            "asset_type": "file",
            "public_action": "get_file",
            "file": "",
            "url": "",
            "file_name": "old-uploaded.jpg",
        },
        old_bucket=("file", "2025-09"),
        request={
            "asset_type": "file",
            "file_name": "old-uploaded.jpg",
        },
    )

    assert classification == "qq_expired_after_napcat"


def test_resolve_via_direct_file_id_marks_old_file_not_found_as_background() -> None:
    downloader = NapCatMediaDownloader(_MissingDirectFileClient())
    request = {
        "asset_type": "file",
        "file_name": "old-uploaded.jpg",
        "timestamp_ms": 1757268507000,
        "download_hint": {
            "file_id": "/494603f2-038f-4fd0-bffa-934b4553f019",
        },
    }

    resolved = downloader._resolve_via_direct_file_id(request)

    assert resolved == (None, "qq_expired_after_napcat")


def test_resolve_from_public_token_marks_old_video_blank_payload_as_background() -> None:
    downloader = NapCatMediaDownloader(_BlankPublicFileClient())
    request = {
        "asset_type": "video",
        "file_name": "old-video.mp4",
        "timestamp_ms": 1757142395000,
        "download_hint": {},
    }

    resolved = downloader._resolve_from_public_token(
        {
            "asset_type": "video",
            "public_action": "get_file",
            "public_file_token": "old-video-token",
            "file_name": "old-video.mp4",
        },
        old_bucket=("video", "2025-09"),
        request=request,
    )

    assert resolved == (None, "qq_expired_after_napcat")


def test_classify_missing_from_public_payload_marks_old_video_with_stale_local_url_as_background() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())

    classification = downloader._classify_missing_from_public_payload(
        {
            "asset_type": "video",
            "public_action": "get_file",
            "public_file_token": "old-video-token",
            "file": "",
            "url": r"C:\QQ\3956020260\nt_qq\nt_data\Video\2025-09\Ori\missing-old-video.mp4",
            "file_name": "missing-old-video.mp4",
            "file_id": "old-file-id",
        },
        old_bucket=("video", "2025-09"),
        request={
            "asset_type": "video",
            "file_name": "missing-old-video.mp4",
        },
    )

    assert classification == "qq_expired_after_napcat"


def test_consume_remote_media_prefetch_peek_does_not_block_on_inflight_future() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    cache_key = ("image", "https://example.invalid/test.png")
    downloader._remote_media_resolution_futures[cache_key] = Future()

    started = time.perf_counter()
    resolved = downloader._consume_remote_media_prefetch(cache_key)
    elapsed = time.perf_counter() - started

    assert resolved is ...
    assert elapsed < 0.5


def test_cleanup_remote_cache_rebuilds_prefetch_runtime_without_waiting() -> None:
    downloader = _CleanupProbeDownloader()

    stats = downloader.cleanup_remote_cache()

    assert downloader.rebuild_calls == [(False, True)]
    assert stats["cache_cleared"] is False


def test_forward_timeout_updates_download_progress_counters() -> None:
    fast_client = _TimeoutForwardClient()
    downloader = NapCatMediaDownloader(_DummyClient(), fast_client=fast_client)

    downloader._download_via_forward_context(
        _build_forward_request("2C167901425EF469C0B1F0BF859E4B2C.jpg"),
        materialize=False,
    )

    snapshot = downloader.export_download_progress_snapshot()
    assert snapshot["timeout_count"] == 1
    assert snapshot["forward_context_timeout_count"] == 1
