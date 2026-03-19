from __future__ import annotations

from qq_data_integrations.napcat.media_downloader import NapCatMediaDownloader


class _FakeClient:
    pass


def test_media_downloader_initializes_progress_snapshot() -> None:
    downloader = NapCatMediaDownloader(_FakeClient())  # type: ignore[arg-type]

    snapshot = downloader.export_download_progress_snapshot()

    assert snapshot["candidate_total"] == 0
    assert snapshot["queued"] == 0
    assert snapshot["active"] == 0
    assert snapshot["completed"] == 0
    assert snapshot["failed"] == 0
    assert snapshot["cached"] == 0
    assert snapshot["last_status"] is None


def test_media_downloader_progress_snapshot_tracks_remote_candidates() -> None:
    downloader = NapCatMediaDownloader(_FakeClient())  # type: ignore[arg-type]
    requests = [
        {
            "asset_type": "image",
            "file_name": "demo.jpg",
            "download_hint": {
                "message_id_raw": "1",
                "element_id": "2",
                "peer_uid": "u_1",
                "chat_type_raw": 2,
                "url": "http://127.0.0.1/demo.jpg",
            },
        },
        {
            "asset_type": "file",
            "file_name": "demo.zip",
            "public_file_token": "token-1",
            "download_hint": {
                "message_id_raw": "3",
                "element_id": "4",
                "peer_uid": "u_1",
                "chat_type_raw": 2,
            },
        },
    ]

    downloader._initialize_download_progress_for_requests(requests)
    downloader._update_download_progress(
        ("image", "http://127.0.0.1/demo.jpg"),
        asset_type="image",
        file_name="demo.jpg",
        next_state="queued",
    )
    downloader._update_download_progress(
        ("image", "http://127.0.0.1/demo.jpg"),
        asset_type="image",
        file_name="demo.jpg",
        next_state="completed",
    )

    snapshot = downloader.export_download_progress_snapshot()

    assert snapshot["candidate_total"] == 2
    assert snapshot["eager_remote_candidates"] == 1
    assert snapshot["public_token_candidates"] == 1
    assert snapshot["context_candidates"] == 2
    assert snapshot["queued"] == 0
    assert snapshot["completed"] == 1
    assert snapshot["last_asset_type"] == "image"
    assert snapshot["last_file_name"] == "demo.jpg"
    assert snapshot["last_status"] == "completed"
