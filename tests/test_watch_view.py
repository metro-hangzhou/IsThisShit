from __future__ import annotations

from qq_data_cli.watch_view import _watch_content_width, _wrap_terminal_text


def test_watch_content_width_reserves_one_column_for_scrollbar() -> None:
    assert _watch_content_width(terminal_columns=30, reserve_scrollbar=True) == 29
    assert _watch_content_width(terminal_columns=30, reserve_scrollbar=False) == 30


def test_wrap_terminal_text_wraps_wide_cjk_before_scrollbar_boundary() -> None:
    line = ("x" * 18) + "吧"

    wrapped = _wrap_terminal_text(line, width=_watch_content_width(terminal_columns=20, reserve_scrollbar=True))

    assert wrapped == [("x" * 18), "吧"]
