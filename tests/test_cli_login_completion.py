from __future__ import annotations

from datetime import datetime

from prompt_toolkit.document import Document

from qq_data_cli.completion import SlashCommandCompleter
from qq_data_core.models import EXPORT_TIMEZONE
from qq_data_integrations.napcat.models import NapCatQuickLoginAccount


def _empty_target_lookup(_chat_type: str, _keyword: str | None, _limit: int):
    return []


def _quick_login_lookup(keyword: str | None, _limit: int):
    candidates = [
        NapCatQuickLoginAccount(uin="3956020260", nick_name="wiki"),
        NapCatQuickLoginAccount(uin="1507833383", nick_name="blank"),
    ]
    if not keyword:
        return candidates
    lowered = keyword.casefold()
    return [
        candidate
        for candidate in candidates
        if lowered in candidate.uin.casefold() or lowered in (candidate.nick_name or "").casefold()
    ]


def test_login_completion_suggests_quick_login_uins_after_command() -> None:
    completer = SlashCommandCompleter(
        target_lookup=_empty_target_lookup,
        quick_login_lookup=_quick_login_lookup,
        now_provider=lambda: datetime.now(EXPORT_TIMEZONE),
    )

    completions = list(
        completer.get_completions(Document("/login "), None)
    )

    completion_texts = {item.text for item in completions}
    assert "3956020260" in completion_texts
    assert "1507833383" in completion_texts
    assert "--refresh" in completion_texts


def test_login_completion_suggests_quick_login_uins_for_quick_uin_option() -> None:
    completer = SlashCommandCompleter(
        target_lookup=_empty_target_lookup,
        quick_login_lookup=_quick_login_lookup,
        now_provider=lambda: datetime.now(EXPORT_TIMEZONE),
    )

    completions = list(
        completer.get_completions(Document("/login --quick-uin "), None)
    )

    completion_texts = {item.text for item in completions}
    assert "3956020260" in completion_texts
    assert "1507833383" in completion_texts
