from __future__ import annotations

from qq_data_integrations.napcat.fast_history_client import NapCatFastHistoryTimeoutError
from qq_data_integrations.napcat.media_downloader import NapCatMediaDownloader


class _DummyClient:
    pass


class _TimeoutForwardClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def hydrate_forward_media(self, **kwargs):
        self.calls.append(kwargs)
        raise NapCatFastHistoryTimeoutError("timed out")


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
