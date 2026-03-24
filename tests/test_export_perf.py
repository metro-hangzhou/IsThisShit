from __future__ import annotations

import json

from qq_data_core.export_perf import ExportPerfTraceWriter


def test_export_perf_report_includes_stage_page_and_materialize_breakdown(tmp_path):
    writer = ExportPerfTraceWriter(
        tmp_path,
        chat_type="group",
        chat_id="922065597",
        mode="test_export",
    )
    with writer.timed_stage("app.fetch_snapshot", payload={"limit": 20}) as stage:
        stage.add(history_source="napcat_fast_history", message_count=20)
    writer.write_event(
        "history_page_done",
        {
            "mode": "tail_scan",
            "before_message_seq": "123",
            "requested_count": 200,
            "history_source": "napcat_fast_history_bulk",
            "page_duration_s": 0.1234,
            "page_message_count": 200,
            "retry_count": 0,
            "status": "done",
        },
    )
    writer.write_event(
        "scan_summary",
        {
            "scan_phase": "tail_scan",
            "elapsed_s": 1.234,
            "exit_reason": "target_reached",
            "pages_scanned": 4,
            "matched_messages": 500,
        },
    )
    writer.write_event(
        "tail_scan",
        {
            "pages_scanned": 4,
            "matched_messages": 500,
            "requested_data_count": 500,
            "history_source": "napcat_fast_history_bulk",
            "page_duration_s": 0.2222,
            "page_message_count": 200,
        },
    )
    writer.write_event(
        "materialize_asset_step",
        {
            "stage": "done",
            "current": 1,
            "total": 1,
            "asset_type": "image",
            "file_name": "A.png",
            "step_elapsed_s": 0.456,
            "status": "copied",
            "resolver": "napcat_public_token_get_image",
        },
    )
    writer.write_event(
        "materialize_asset_substep",
        {
            "stage": "done",
            "substep": "public_token_get_image",
            "status": "ok",
            "asset_type": "image",
            "file_name": "A.png",
            "elapsed_s": 0.078,
            "message_id_raw": "1",
            "element_id": "2",
        },
    )

    report = writer.build_report(record_count=20)

    assert report["record_count"] == 20
    assert report["total_elapsed_s"] >= 0
    assert report["stage_breakdown"][0]["name"] == "app.fetch_snapshot"
    assert report["history_page_breakdown"][0]["name"] == "tail_scan:napcat_fast_history_bulk"
    assert report["fetch_stage_breakdown"][0]["name"] == "app.fetch_snapshot"
    assert report["materialize_asset_breakdown"][0]["asset_type"] == "image"
    assert report["materialize_asset_breakdown"][0]["resolver"] == "napcat_public_token_get_image"
    assert report["materialize_stage_breakdown"][0]["substep"] == "public_token_get_image"
    assert report["scan_phase_breakdown"][0]["name"] == "tail_scan"
    assert report["scan_summaries"][0]["scan_phase"] == "tail_scan"
    assert report["top_materialize_steps"][0]["file_name"] == "A.png"
    assert report["top_materialize_substeps"][0]["substep"] == "public_token_get_image"

    writer.close()
    report_path = writer.persist_report(record_count=20)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["record_count"] == 20
    assert saved["trace_path"].endswith(".jsonl")


def test_materialize_asset_step_only_persists_done_rows(tmp_path):
    writer = ExportPerfTraceWriter(
        tmp_path,
        chat_type="private",
        chat_id="1507833383",
        mode="test_export",
    )
    writer.write_event(
        "materialize_asset_step",
        {
            "stage": "start",
            "current": 1,
            "total": 2,
            "asset_type": "image",
            "file_name": "ignore.png",
        },
    )
    writer.write_event(
        "materialize_asset_step",
        {
            "stage": "done",
            "current": 1,
            "total": 2,
            "asset_type": "image",
            "file_name": "keep.png",
            "step_elapsed_s": 0.111,
            "status": "copied",
            "resolver": "direct_local_precheck",
        },
    )
    writer.close()
    lines = writer.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "keep.png" in lines[0]
    assert "ignore.png" not in lines[0]
