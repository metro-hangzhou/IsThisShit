from __future__ import annotations

from qq_data_cli.status_display import build_rich_status_text, colorize_status_fields_for_ansi


def test_colorize_status_fields_for_ansi_colors_only_exact_status_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "qq_data_cli.status_display._supports_ansi_status_color",
        lambda stream=None: True,
    )
    rendered = colorize_status_fields_for_ansi(
        "status=success status=failed status=in progress login_status=failed status=timeout"
    )

    assert "status=\x1b[32msuccess\x1b[0m" in rendered
    assert "status=\x1b[31mfailed\x1b[0m" in rendered
    assert "status=\x1b[33min progress\x1b[0m" in rendered
    assert "login_status=failed" in rendered
    assert "status=timeout" in rendered


def test_build_rich_status_text_styles_only_exact_status_values() -> None:
    rendered = build_rich_status_text(
        "status=success login_status=failed status=failed status=in progress"
    )

    assert rendered.plain == "status=success login_status=failed status=failed status=in progress"
    styled_segments = {(span.start, span.end, span.style) for span in rendered.spans}
    assert (7, 14, "green") in styled_segments
    assert (42, 48, "red") in styled_segments
    assert (56, 67, "yellow") in styled_segments
