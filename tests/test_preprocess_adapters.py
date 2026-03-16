from __future__ import annotations

from pathlib import Path

from qq_data_process.adapters import (
    ExporterJsonlAdapter,
    QceJsonAdapter,
    TxtTranscriptAdapter,
)


def test_exporter_jsonl_adapter_loads_high_fidelity_fixture() -> None:
    adapter = ExporterJsonlAdapter()
    bundle = adapter.load(Path("tests/fixtures/smoke.jsonl"))

    assert bundle.source_type == "exporter_jsonl"
    assert bundle.fidelity == "high"
    assert bundle.chat_name == "示例私聊"
    assert len(bundle.messages) == 6
    assert bundle.messages[1].assets[0].asset_type == "image"


def test_qce_json_adapter_loads_compat_fixture() -> None:
    adapter = QceJsonAdapter()
    bundle = adapter.load(Path("tests/fixtures/private_fixture.json"))

    assert bundle.source_type == "qce_json"
    assert bundle.fidelity == "compat"
    assert bundle.chat_name == "示例私聊"
    assert len(bundle.messages) == 6
    assert any(message.assets for message in bundle.messages)


def test_txt_adapter_loads_lossy_fixture() -> None:
    adapter = TxtTranscriptAdapter()
    bundle = adapter.load(Path("tests/fixtures/smoke.txt"))

    assert bundle.source_type == "qq_txt"
    assert bundle.fidelity == "lossy"
    assert bundle.chat_name == "示例私聊"
    assert len(bundle.messages) == 6
    assert bundle.messages[1].assets[0].asset_type == "image"
    assert bundle.messages[1].sender_id_raw == "1585729597"
