from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "probe_asset_routes.py"
    spec = importlib.util.spec_from_file_location("probe_asset_routes", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_derive_projected_localhost_download_url_projects_multimedia_download() -> None:
    module = _load_script_module()
    projected = module._derive_projected_localhost_download_url(  # type: ignore[attr-defined]
        "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=dead-token&spec=0",
        "http://127.0.0.1:3000",
    )
    assert projected == "http://127.0.0.1:3000/download?appid=1407&fileid=dead-token&spec=0"


def test_derive_projected_localhost_download_url_joins_relative_download_path() -> None:
    module = _load_script_module()
    projected = module._derive_projected_localhost_download_url(  # type: ignore[attr-defined]
        "/download?appid=1407&fileid=abc&spec=0",
        "http://127.0.0.1:3000",
    )
    assert projected == "http://127.0.0.1:3000/download?appid=1407&fileid=abc&spec=0"


def test_summarize_hydrate_payload_surfaces_first_asset_and_local_path_probe() -> None:
    module = _load_script_module()
    summary = module._summarize_hydrate_payload(  # type: ignore[attr-defined]
        {
            "targeted": True,
            "targeted_mode": "hydrated",
            "assets": [
                {
                    "asset_type": "image",
                    "file_name": "demo.png",
                    "file": r"C:\QQ\demo.png",
                    "remote_url": "/download?appid=1407&fileid=abc&spec=0",
                    "public_action": "get_image",
                    "public_file_token": "token-1",
                }
            ],
        }
    )
    assert summary["targeted"] is True
    assert summary["assets_count"] == 1
    assert summary["first_asset"]["file_name"] == "demo.png"
    assert summary["first_asset"]["public_file_token"] == "token-1"
    assert summary["first_asset"]["local_path_probe"]["path"] == r"C:\QQ\demo.png"
