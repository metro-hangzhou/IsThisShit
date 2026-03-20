from __future__ import annotations

from pathlib import Path

from qq_data_cli.status_display import (
    build_rich_status_text,
    colorize_status_fields_for_ansi,
    format_export_result_lines,
)
from qq_data_core.models import ExportBundleResult


def test_colorize_status_fields_for_ansi_colors_only_exact_status_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "qq_data_cli.status_display._supports_ansi_status_color",
        lambda stream=None: True,
    )
    rendered = colorize_status_fields_for_ansi(
        "status=success export_status=failed status=in progress login_status=failed status=timeout"
    )

    assert "status=\x1b[32msuccess\x1b[0m" in rendered
    assert "export_status=\x1b[31mfailed\x1b[0m" in rendered
    assert "status=\x1b[33min progress\x1b[0m" in rendered
    assert "login_status=failed" in rendered
    assert "status=timeout" in rendered


def test_build_rich_status_text_styles_only_exact_status_values() -> None:
    rendered = build_rich_status_text(
        "status=success login_status=failed export_status=failed status=in progress"
    )

    assert rendered.plain == "status=success login_status=failed export_status=failed status=in progress"
    styled_segments = {(span.start, span.end, span.style) for span in rendered.spans}
    assert (7, 14, "green") in styled_segments
    assert (49, 55, "red") in styled_segments
    assert (63, 74, "yellow") in styled_segments


def test_format_export_result_lines_builds_human_friendly_sections() -> None:
    bundle = ExportBundleResult(
        data_path=Path("exports/test.jsonl"),
        manifest_path=Path("exports/test.manifest.json"),
        assets_dir=Path("exports/test_assets"),
        record_count=2000,
        copied_asset_count=341,
        reused_asset_count=100,
        missing_asset_count=129,
    )
    summary = {
        "oldest_timestamp_iso": "2025-09-23T16:40:52+08:00",
        "latest_timestamp_iso": "2026-03-17T17:01:33+08:00",
        "history_source": "napcat_fast_history_bulk",
        "bulk_partial_fallback": False,
        "forward_detail_count": 5,
        "forward_structure_unavailable_count": 1,
        "expected_assets": {"image": 570},
        "actual_assets": {"image": 441},
        "missing_assets": {"image": 129},
        "actionable_missing_count": 0,
        "background_missing_count": 129,
        "missing_breakdown": {
            "qq_expired_after_napcat": 5,
            "qq_not_downloaded_local_placeholder": 124,
        },
        "actionable_missing_breakdown": {},
        "background_missing_breakdown": {
            "qq_expired_after_napcat": 5,
            "qq_not_downloaded_local_placeholder": 124,
        },
    }
    trace_summary = {"elapsed_s": 23.832, "pages_scanned": 11, "retry_events": 0}

    lines = format_export_result_lines(
        session_line="export_session: uin=3956020260 nick=wiki online=True",
        content_summary=summary,
        bundle=bundle,
        trace_summary=trace_summary,
        trace_path=Path("state/export_perf/run.jsonl"),
    )

    rendered = "\n".join(lines)
    assert "export_result:" in rendered
    assert "export_status=success export_verdict=success_with_background_missing" in rendered
    assert "session=uin=3956020260 nick=wiki online=True" in rendered
    assert "files:" in rendered
    assert "summary:" in rendered
    assert "assets:" in rendered
    assert "final_assets=441/570 copied=341 reused=100 missing=129" in rendered
    assert "background_missing_reason=[qq_expired_after_napcat:5, qq_not_downloaded_local_placeholder:124]" in rendered
    assert "当前剩余 missing 均为背景缺失" in rendered
