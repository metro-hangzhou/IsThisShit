from __future__ import annotations

import asyncio
import time
from pathlib import Path
import shutil
import uuid
from concurrent.futures import Future

from qq_data_integrations.napcat.fast_history_client import NapCatFastHistoryTimeoutError
from qq_data_integrations.napcat.media_downloader import NapCatMediaDownloader


class _DummyClient:
    pass


class _RemoteMediaDownloader(NapCatMediaDownloader):
    def __init__(self, remote_cache_dir: Path) -> None:
        super().__init__(_DummyClient(), remote_cache_dir=remote_cache_dir)

    async def _download_remote_payload_async(self, remote_url: str) -> bytes | None:  # type: ignore[override]
        return b"fake-bytes" if remote_url else None


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
    def hydrate_media_batch(self, _items):
        return {"items": []}


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
    downloader._call_public_action_with_token = lambda *args, **kwargs: {  # type: ignore[method-assign]
        "url": "https://gchat.qpic.cn/gchatpic_new/0/0-0-700B81F97B9D06E7999DF7504442D46C/0"
    }

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


def test_consume_remote_media_prefetch_peek_does_not_block_on_inflight_future() -> None:
    downloader = NapCatMediaDownloader(_DummyClient())
    cache_key = ("image", "https://example.invalid/test.png")
    downloader._remote_media_resolution_futures[cache_key] = Future()

    started = time.perf_counter()
    resolved = downloader._consume_remote_media_prefetch(cache_key)
    elapsed = time.perf_counter() - started

    assert resolved is ...
    assert elapsed < 0.5
