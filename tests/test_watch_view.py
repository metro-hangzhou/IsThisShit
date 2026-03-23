from __future__ import annotations

from unittest.mock import Mock

from qq_data_cli.watch_view import WatchConversationView
from qq_data_cli.watch_view import _watch_content_width, _wrap_terminal_text


def test_watch_content_width_reserves_one_column_for_scrollbar() -> None:
    assert _watch_content_width(terminal_columns=30, reserve_scrollbar=True) == 29
    assert _watch_content_width(terminal_columns=30, reserve_scrollbar=False) == 30


def test_wrap_terminal_text_wraps_wide_cjk_before_scrollbar_boundary() -> None:
    line = ("x" * 18) + "吧"

    wrapped = _wrap_terminal_text(line, width=_watch_content_width(terminal_columns=20, reserve_scrollbar=True))

    assert wrapped == [("x" * 18), "吧"]


def test_refresh_message_area_for_resize_only_rewraps_when_width_changes() -> None:
    view = object.__new__(WatchConversationView)
    view._last_timeline_content_width = 40
    view._follow_tail = True
    view._scroll_top = 7
    view._timeline_content_width = Mock(return_value=40)
    view._refresh_message_area = Mock()
    view._clamp_scroll_top = Mock()
    view._sync_cursor_to_view = Mock()

    WatchConversationView._refresh_message_area_for_resize(view)

    view._refresh_message_area.assert_not_called()
    view._clamp_scroll_top.assert_not_called()
    view._sync_cursor_to_view.assert_not_called()


def test_refresh_message_area_for_resize_rewraps_and_restores_manual_scroll() -> None:
    view = object.__new__(WatchConversationView)
    view._last_timeline_content_width = 40
    view._follow_tail = False
    view._scroll_top = 7
    view._timeline_content_width = Mock(return_value=72)
    view._refresh_message_area = Mock()
    view._clamp_scroll_top = Mock()
    view._sync_cursor_to_view = Mock()

    WatchConversationView._refresh_message_area_for_resize(view)

    view._refresh_message_area.assert_called_once_with()
    assert view._follow_tail is False
    assert view._scroll_top == 7
    view._clamp_scroll_top.assert_called_once_with()
    view._sync_cursor_to_view.assert_called_once_with()


def test_before_render_refreshes_message_area_for_resize() -> None:
    view = object.__new__(WatchConversationView)
    view._refresh_message_area_for_resize = Mock()

    WatchConversationView._before_render(view, Mock())

    view._refresh_message_area_for_resize.assert_called_once_with()
