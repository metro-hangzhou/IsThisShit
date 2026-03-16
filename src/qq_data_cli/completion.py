from __future__ import annotations

import shlex
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from prompt_toolkit.completion import CompleteEvent, Completer, Completion

from qq_data_core import EXPORT_TIME_FORMAT, SPECIAL_TIME_EXPRESSIONS, is_explicit_datetime_literal
from qq_data_core.models import EXPORT_TIMEZONE
from qq_data_cli.export_commands import EXPORT_COMMAND_PROFILES, FORMAT_MARKERS
from qq_data_cli.export_input import render_export_date_literal_display
from qq_data_cli.logging_utils import get_cli_logger
from qq_data_cli.target_display import format_target_label, format_target_remark, is_blank_like_text
from qq_data_integrations.napcat import ChatTarget

COMMANDS = [
    "/doctor",
    "/help",
    "/login",
    "/quit",
    "/status",
    "/terminal-doctor",
    "/groups",
    "/friends",
    "/watch",
    "/export",
    "/export_onlyText",
    "/export_TextImage",
    "/export_TextImageEmoji",
    "/fixture-export",
]

CHAT_KINDS = ["group", "friend"]
EXPORT_TARGET_MODES = ["group", "friend", "group_asBatch=", "friend_asBatch="]
LIST_OPTIONS = ["--refresh", "--limit"]
EXPORT_OPTIONS = ["--format", "--out", "--limit", "--data-count", "--refresh", "--include-raw"]
WATCH_OPTIONS = ["--refresh"]
LOGIN_OPTIONS = ["--refresh", "--timeout", "--poll"]
FORMAT_VALUES = ["jsonl", "txt"]
DATE_FUNCTIONS = list(SPECIAL_TIME_EXPRESSIONS)
DATA_COUNT_INLINE = "data_count="
WATCH_COMMANDS = [
    "/exit",
    "/export",
    "/export_onlyText",
    "/export_TextImage",
    "/export_TextImageEmoji",
    "/help",
]
WATCH_EXPORT_OPTIONS = ["--format", "--out", "--limit", "--data-count", "--include-raw"]
FORMAT_ALIASES = ["asTXT", "asJSONL"]


class SlashCommandCompleter(Completer):
    def __init__(
        self,
        *,
        target_lookup: Callable[[str, str | None, int], Iterable[ChatTarget]],
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._target_lookup = target_lookup
        self._now_provider = now_provider or (lambda: datetime.now(EXPORT_TIMEZONE).replace(microsecond=0))
        self._logger = get_cli_logger("completion")
        self._reported_lookup_failures: set[tuple[str, str, str, str, str]] = set()

    def get_completions(self, document, complete_event):
        before_cursor = document.text_before_cursor
        if not before_cursor.startswith("/"):
            return

        previous_tokens, current_token = _split_tokens(before_cursor)
        ends_with_space = before_cursor.endswith(" ")
        start_position = -len(current_token)

        if not previous_tokens:
            yield from _complete_words(COMMANDS, current_token, start_position=start_position)
            return

        command = previous_tokens[0].lower()

        if command == "/watch" or command in EXPORT_COMMAND_PROFILES:
            yield from self._complete_chat_command(
                command,
                previous_tokens,
                current_token,
                ends_with_space=ends_with_space,
                start_position=start_position,
            )
            return

        if command == "/login":
            yield from _complete_words(LOGIN_OPTIONS, current_token, start_position=start_position)
            return

        if command in {"/groups", "/friends"}:
            chat_type = "group" if command == "/groups" else "private"
            options = LIST_OPTIONS
            if current_token.startswith("--"):
                yield from _complete_words(options, current_token, start_position=start_position)
                return
            keyword = None if ends_with_space else current_token
            yield from self._complete_targets(chat_type, keyword, start_position=start_position)
            yield from _complete_words(options, current_token, start_position=start_position)
            return

        if command == "/fixture-export" and len(previous_tokens) >= 3:
            yield from _complete_words(FORMAT_VALUES, current_token, start_position=start_position)
            return

        if len(previous_tokens) == 1 and not ends_with_space:
            yield from _complete_words(COMMANDS, current_token, start_position=start_position)

    def _complete_chat_command(
        self,
        command: str,
        previous_tokens: list[str],
        current_token: str,
        *,
        ends_with_space: bool,
        start_position: int,
    ):
        if len(previous_tokens) == 1:
            batch_spec = _parse_batch_target_token(current_token)
            if batch_spec is not None:
                chat_type, prefix, selected_targets, fragment = batch_spec
                batch_start = -len(fragment)
                yield from self._complete_batch_targets(
                    chat_type,
                    prefix=prefix,
                    selected_targets=selected_targets,
                    fragment=fragment,
                    start_position=batch_start,
                )
                return
            yield from _complete_words(EXPORT_TARGET_MODES if command in EXPORT_COMMAND_PROFILES else CHAT_KINDS, current_token, start_position=start_position)
            return

        if command in EXPORT_COMMAND_PROFILES:
            batch_spec = _parse_batch_target_token(previous_tokens[1])
            if batch_spec is not None:
                if previous_tokens[-1] == "--format":
                    yield from _complete_words(FORMAT_VALUES, current_token, start_position=start_position)
                    return
                if current_token.startswith("--"):
                    yield from _complete_words(EXPORT_OPTIONS, current_token, start_position=start_position)
                    return
                date_args = len(_positional_tokens_without_format_alias(previous_tokens[2:]))
                if _looks_like_data_count_prefix(current_token):
                    yield from _complete_data_count_inline(current_token, start_position=start_position)
                    return
                if _looks_like_format_alias_prefix(current_token) or date_args >= 2:
                    yield from _complete_data_count_inline(current_token, start_position=start_position)
                    yield from _complete_words(FORMAT_ALIASES, current_token, start_position=start_position)
                    return
                if date_args < 2 and not current_token.startswith("--"):
                    yield from self._complete_time_expressions(
                        current_token,
                        slot_index=date_args,
                        previous_date_tokens=_positional_tokens_without_format_alias(previous_tokens[2:]),
                        start_position=start_position,
                    )
                    yield from _complete_data_count_inline(current_token, start_position=start_position)
                    return
                yield from _complete_words(EXPORT_OPTIONS, current_token, start_position=start_position)
                return

        chat_kind = previous_tokens[1].lower()
        if chat_kind not in {"group", "friend"}:
            yield from _complete_words(CHAT_KINDS, current_token, start_position=start_position)
            return

        if previous_tokens[-1] == "--format":
            yield from _complete_words(FORMAT_VALUES, current_token, start_position=start_position)
            return

        if current_token.startswith("--"):
            options = WATCH_OPTIONS if command == "/watch" else EXPORT_OPTIONS
            yield from _complete_words(options, current_token, start_position=start_position)
            return

        if command in EXPORT_COMMAND_PROFILES:
            yield from self._complete_export_command(
                chat_kind,
                previous_tokens,
                current_token,
                ends_with_space=ends_with_space,
                start_position=start_position,
            )
            return

        target_position = len(previous_tokens) == 2 or (
            len(previous_tokens) == 3
            and (
                ends_with_space
                or (bool(current_token) and not before_cursor_ends_with_option_value(previous_tokens))
            )
        )
        if target_position:
            chat_type = "group" if chat_kind == "group" else "private"
            keyword = None if current_token.startswith("--") else current_token or None
            yield from self._complete_targets(chat_type, keyword, start_position=start_position)
            if current_token:
                options = WATCH_OPTIONS if command == "/watch" else EXPORT_OPTIONS
                yield from _complete_words(options, current_token, start_position=start_position)
            return

        options = WATCH_OPTIONS if command == "/watch" else EXPORT_OPTIONS
        yield from _complete_words(options, current_token, start_position=start_position)

    def _complete_export_command(
        self,
        chat_kind: str,
        previous_tokens: list[str],
        current_token: str,
        *,
        ends_with_space: bool,
        start_position: int,
    ):
        if len(previous_tokens) == 2:
            chat_type = "group" if chat_kind == "group" else "private"
            keyword = current_token or None
            yield from self._complete_targets(chat_type, keyword, start_position=start_position)
            return

        if previous_tokens[-1] == "--format":
            yield from _complete_words(FORMAT_VALUES, current_token, start_position=start_position)
            return

        date_args = len(_positional_tokens_without_format_alias(previous_tokens[3:]))
        if _looks_like_data_count_prefix(current_token):
            yield from _complete_data_count_inline(current_token, start_position=start_position)
            return
        if _looks_like_format_alias_prefix(current_token) or date_args >= 2:
            yield from _complete_data_count_inline(current_token, start_position=start_position)
            yield from _complete_words(FORMAT_ALIASES, current_token, start_position=start_position)
            return

        if date_args < 2 and not current_token.startswith("--"):
            yield from self._complete_time_expressions(
                current_token,
                slot_index=date_args,
                previous_date_tokens=_positional_tokens_without_format_alias(previous_tokens[3:]),
                start_position=start_position,
            )
            yield from _complete_data_count_inline(current_token, start_position=start_position)
            return

        yield from _complete_words(EXPORT_OPTIONS, current_token, start_position=start_position)

    def _complete_targets(
        self,
        chat_type: str,
        keyword: str | None,
        *,
        start_position: int,
    ):
        try:
            targets = list(self._target_lookup(chat_type, keyword, 6))
        except Exception as exc:
            self._report_target_lookup_failure("single", chat_type, keyword, exc)
            return

        for target in targets:
            details = []
            if target.remark and target.remark != target.name:
                details.append(f"remark={format_target_remark(target)}")
            if target.member_count is not None:
                details.append(f"members={target.member_count}")
            completion_text = _target_completion_text(target)
            yield Completion(
                text=completion_text,
                start_position=start_position,
                display=format_target_label(target),
                display_meta=", ".join(details) if details else target.chat_type,
            )

    def _complete_batch_targets(
        self,
        chat_type: str,
        *,
        prefix: str,
        selected_targets: set[str],
        fragment: str,
        start_position: int,
    ):
        normalized_chat_type = "group" if chat_type == "group" else "private"
        try:
            targets = list(self._target_lookup(normalized_chat_type, fragment or None, 6))
        except Exception as exc:
            self._report_target_lookup_failure("batch", normalized_chat_type, fragment or None, exc)
            return

        for target in targets:
            completion_text = _target_completion_text(target)
            if completion_text in selected_targets:
                continue
            details = []
            if target.remark and target.remark != target.name:
                details.append(f"remark={format_target_remark(target)}")
            if target.member_count is not None:
                details.append(f"members={target.member_count}")
            yield Completion(
                text=completion_text,
                start_position=start_position,
                display=format_target_label(target),
                display_meta=", ".join(details) if details else target.chat_type,
            )

    def _report_target_lookup_failure(
        self,
        scope: str,
        chat_type: str,
        keyword: str | None,
        exc: Exception,
    ) -> None:
        message = str(exc or "").strip() or exc.__class__.__name__
        failure_key = (
            scope,
            chat_type,
            keyword or "",
            exc.__class__.__name__,
            message,
        )
        if failure_key in self._reported_lookup_failures:
            return
        self._reported_lookup_failures.add(failure_key)
        self._logger.warning(
            "completion_lookup_failed scope=%s chat_type=%s keyword=%r error=%s",
            scope,
            chat_type,
            keyword,
            message,
        )

    def _complete_time_expressions(
        self,
        current_token: str,
        *,
        slot_index: int,
        previous_date_tokens: list[str],
        start_position: int,
    ):
        yield from _complete_time_expressions(
            current_token,
            slot_index=slot_index,
            previous_date_tokens=previous_date_tokens,
            start_position=start_position,
            now_provider=self._now_provider,
        )


class WatchCommandCompleter(Completer):
    def __init__(self, *, now_provider: Callable[[], datetime] | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(EXPORT_TIMEZONE).replace(microsecond=0))

    def get_completions(self, document, complete_event):
        before_cursor = document.text_before_cursor
        if not before_cursor.startswith("/"):
            return

        previous_tokens, current_token = _split_tokens(before_cursor)
        ends_with_space = before_cursor.endswith(" ")
        start_position = -len(current_token)

        if not previous_tokens:
            yield from _complete_words(WATCH_COMMANDS, current_token, start_position=start_position)
            return

        command = previous_tokens[0].lower()
        if command in EXPORT_COMMAND_PROFILES:
            if previous_tokens[-1] == "--format":
                yield from _complete_words(FORMAT_VALUES, current_token, start_position=start_position)
                return

            if current_token.startswith("--"):
                yield from _complete_words(WATCH_EXPORT_OPTIONS, current_token, start_position=start_position)
                return

            date_args = len(_positional_tokens_without_format_alias(previous_tokens[1:]))
            if _looks_like_data_count_prefix(current_token):
                yield from _complete_data_count_inline(current_token, start_position=start_position)
                return
            if _looks_like_format_alias_prefix(current_token) or date_args >= 2:
                yield from _complete_data_count_inline(current_token, start_position=start_position)
                yield from _complete_words(FORMAT_ALIASES, current_token, start_position=start_position)
                return

            if len(previous_tokens) <= 2:
                yield from _complete_time_expressions(
                    current_token,
                    slot_index=date_args,
                    previous_date_tokens=_positional_tokens_without_format_alias(previous_tokens[1:]),
                    start_position=start_position,
                    now_provider=self._now_provider,
                )
                yield from _complete_data_count_inline(current_token, start_position=start_position)
                return

            if ends_with_space and len(previous_tokens) <= 2:
                yield from _complete_time_expressions(
                    "",
                    slot_index=date_args,
                    previous_date_tokens=_positional_tokens_without_format_alias(previous_tokens[1:]),
                    start_position=0,
                    now_provider=self._now_provider,
                )
                return

            yield from _complete_data_count_inline(current_token, start_position=start_position)
            yield from _complete_words(FORMAT_ALIASES, current_token, start_position=start_position)
            return

        if len(previous_tokens) == 1 and not ends_with_space:
            yield from _complete_words(WATCH_COMMANDS, current_token, start_position=start_position)


def _complete_words(words: Iterable[str], current_token: str, *, start_position: int):
    normalized = current_token.casefold()
    for word in words:
        if not normalized or word.casefold().startswith(normalized):
            yield Completion(text=word, start_position=start_position)


def _complete_time_expressions(
    current_token: str,
    *,
    slot_index: int,
    previous_date_tokens: list[str],
    start_position: int,
    now_provider: Callable[[], datetime],
):
    if is_explicit_datetime_literal(current_token):
        time_candidate = _build_time_stage_candidate(
            current_token,
            slot_index=slot_index,
            previous_date_tokens=previous_date_tokens,
            now_provider=now_provider,
        )
        if time_candidate is not None and time_candidate != current_token:
            yield Completion(
                text=time_candidate,
                start_position=start_position,
                display=_display_time_only(time_candidate),
                display_meta=render_export_date_literal_display(time_candidate),
            )
        return

    if current_token and current_token.startswith("@"):
        yield from _complete_words(DATE_FUNCTIONS, current_token, start_position=start_position)
        return

    if not current_token:
        date_candidate = _build_date_stage_candidate(
            slot_index,
            previous_date_tokens=previous_date_tokens,
            now_provider=now_provider,
        )
        yield Completion(
            text=date_candidate,
            start_position=start_position,
            display=render_export_date_literal_display(date_candidate),
            display_meta="explicit datetime",
        )
        yield from _complete_words(DATE_FUNCTIONS, current_token, start_position=start_position)
        return

    if current_token[:1].isdigit():
        candidate = _build_date_stage_candidate(
            slot_index,
            previous_date_tokens=previous_date_tokens,
            now_provider=now_provider,
        )
        if candidate.startswith(current_token):
            yield Completion(
                text=candidate,
                start_position=start_position,
                display=render_export_date_literal_display(candidate),
                display_meta="explicit datetime",
            )


def _complete_data_count_inline(current_token: str, *, start_position: int):
    normalized = current_token.casefold()
    if normalized and DATA_COUNT_INLINE.startswith(normalized):
        yield Completion(
            text=DATA_COUNT_INLINE,
            start_position=start_position,
            display=DATA_COUNT_INLINE,
            display_meta="limit exported messages",
        )


def _build_date_stage_candidate(
    slot_index: int,
    *,
    previous_date_tokens: list[str],
    now_provider: Callable[[], datetime],
) -> str:
    anchor = _resolve_anchor_datetime(
        slot_index,
        previous_date_tokens=previous_date_tokens,
        now_provider=now_provider,
    )
    if slot_index <= 0:
        candidate = anchor
    else:
        candidate = anchor - timedelta(days=1)
    return candidate.replace(hour=0, minute=0, second=0, microsecond=0).strftime(EXPORT_TIME_FORMAT)


def _build_time_stage_candidate(
    current_token: str,
    *,
    slot_index: int,
    previous_date_tokens: list[str],
    now_provider: Callable[[], datetime],
) -> str | None:
    if not current_token.endswith("_00-00-00"):
        return None
    current_dt = datetime.strptime(current_token, EXPORT_TIME_FORMAT).replace(tzinfo=EXPORT_TIMEZONE)
    anchor = _resolve_anchor_datetime(
        slot_index,
        previous_date_tokens=previous_date_tokens,
        now_provider=now_provider,
    )
    resolved = current_dt.replace(
        hour=anchor.hour,
        minute=anchor.minute,
        second=anchor.second,
        microsecond=0,
    )
    return resolved.strftime(EXPORT_TIME_FORMAT)


def _resolve_anchor_datetime(
    slot_index: int,
    *,
    previous_date_tokens: list[str],
    now_provider: Callable[[], datetime],
) -> datetime:
    now = now_provider().astimezone(EXPORT_TIMEZONE).replace(microsecond=0)
    if slot_index <= 0:
        return now
    if previous_date_tokens and is_explicit_datetime_literal(previous_date_tokens[0]):
        return datetime.strptime(previous_date_tokens[0], EXPORT_TIME_FORMAT).replace(tzinfo=EXPORT_TIMEZONE)
    return now


def _display_time_only(value: str) -> str:
    return f"{value[11:13]}h_{value[14:16]}m_{value[17:19]}s"


def _positional_tokens_without_format_alias(tokens: list[str]) -> list[str]:
    if tokens and tokens[-1].casefold() in FORMAT_MARKERS:
        return tokens[:-1]
    return tokens


def _looks_like_format_alias_prefix(value: str) -> bool:
    if not value:
        return False
    normalized = value.casefold()
    return any(alias.casefold().startswith(normalized) for alias in FORMAT_ALIASES)


def _looks_like_data_count_prefix(value: str) -> bool:
    if not value:
        return False
    normalized = value.casefold()
    return DATA_COUNT_INLINE.startswith(normalized)


def _parse_batch_target_token(token: str) -> tuple[str, str, set[str], str] | None:
    stripped = token.strip()
    lowered = stripped.casefold()
    if lowered.startswith("group_asbatch="):
        value = stripped[len("group_asBatch="):]
        return _split_batch_target_value("group", "group_asBatch=", value)
    if lowered.startswith("friend_asbatch="):
        value = stripped[len("friend_asBatch="):]
        return _split_batch_target_value("friend", "friend_asBatch=", value)
    return None


def _split_batch_target_value(chat_type: str, prefix_token: str, value: str) -> tuple[str, str, set[str], str]:
    parts = value.split(",")
    if len(parts) <= 1:
        return chat_type, prefix_token, set(), parts[0].strip()
    selected_parts = [_normalize_batch_target_part(part) for part in parts[:-1] if part.strip()]
    prefix = prefix_token + ",".join(part for part in selected_parts if part)
    if not prefix.endswith(","):
        prefix += ","
    return chat_type, prefix, {part for part in selected_parts if part}, parts[-1].strip()


def _normalize_batch_target_part(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        parsed = shlex.split(stripped)
    except ValueError:
        return stripped.strip("'\"")
    if parsed:
        return parsed[0]
    return stripped.strip("'\"")


def _split_tokens(text: str) -> tuple[list[str], str]:
    ends_with_space = text.endswith(" ")
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    if ends_with_space:
        return tokens, ""
    if not tokens:
        return [], ""
    return tokens[:-1], tokens[-1]


def before_cursor_ends_with_option_value(tokens: list[str]) -> bool:
    if len(tokens) < 3:
        return False
    return tokens[-2] in {"--out", "--limit", "--data-count", "--format", "--timeout", "--poll"}


def _target_completion_text(target: ChatTarget) -> str:
    value = target.remark or target.name or target.chat_id
    if is_blank_like_text(value):
        return target.chat_id
    if any(char.isspace() for char in value):
        return shlex.quote(value)
    return value
