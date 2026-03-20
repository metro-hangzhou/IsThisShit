from __future__ import annotations

import re
from typing import TextIO

from rich.text import Text

from qq_data_cli.terminal_compat import probe_terminal_environment


_STATUS_FIELD_RE = re.compile(
    r"(?P<prefix>(?<![\w])status=)(?P<value>success|failed|in progress)\b",
    flags=re.IGNORECASE,
)

_ANSI_STATUS_COLORS = {
    "success": "\x1b[32m",
    "failed": "\x1b[31m",
    "in progress": "\x1b[33m",
}

_RICH_STATUS_STYLES = {
    "success": "green",
    "failed": "red",
    "in progress": "yellow",
}

_ANSI_RESET = "\x1b[0m"


def colorize_status_fields_for_ansi(
    text: str,
    *,
    stream: TextIO | None = None,
) -> str:
    if not text or not _supports_ansi_status_color(stream=stream):
        return text
    return _STATUS_FIELD_RE.sub(_ansi_status_replacement, text)


def build_rich_status_text(text: str) -> Text:
    result = Text()
    if not text:
        return result
    cursor = 0
    for match in _STATUS_FIELD_RE.finditer(text):
        value = match.group("value")
        style = _RICH_STATUS_STYLES.get(value.casefold())
        if cursor < match.start("value"):
            result.append(text[cursor : match.start("value")])
        result.append(value, style=style)
        cursor = match.end("value")
    if cursor < len(text):
        result.append(text[cursor:])
    if not result:
        result.append(text)
    return result


def _ansi_status_replacement(match: re.Match[str]) -> str:
    value = match.group("value")
    color = _ANSI_STATUS_COLORS.get(value.casefold())
    if not color:
        return match.group(0)
    return f"{match.group('prefix')}{color}{value}{_ANSI_RESET}"


def _supports_ansi_status_color(*, stream: TextIO | None = None) -> bool:
    target_stream = stream
    if target_stream is not None and not bool(getattr(target_stream, "isatty", lambda: False)()):
        return False
    probe = probe_terminal_environment(stdout=target_stream)
    if not probe.stdout_tty:
        return False
    if probe.platform_system != "Windows":
        return True
    if probe.virtual_terminal_enabled:
        return True
    return probe.wt_session or probe.vscode_terminal or probe.ansicon_present
