from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..interfaces import AnalyzerContext, DeterministicAnalyzer
from ..models import AnalysisEvidenceRef, DeterministicResult

MAX_WINDOW_MESSAGES = 24
WINDOW_GAP_MS = 3 * 60 * 1000


@dataclass(frozen=True)
class TopicWindowAnnotation:
    window_id: str
    source_message_ids: tuple[str, ...]
    summary: str
    confidence: float
    start_timestamp_iso: str | None
    end_timestamp_iso: str | None
    participant_ids: tuple[str, ...]
    thread_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "window_id": self.window_id,
            "source_message_ids": list(self.source_message_ids),
            "summary": self.summary,
            "confidence": self.confidence,
            "start_timestamp_iso": self.start_timestamp_iso,
            "end_timestamp_iso": self.end_timestamp_iso,
            "participant_ids": list(self.participant_ids),
            "thread_ids": list(self.thread_ids),
        }


class TopicWindowBuilder(DeterministicAnalyzer):
    plugin_id = "topic_window_builder"
    plugin_version = "0.1.0"
    scope_level = "topic"
    supported_modalities = ("text", "image", "gif", "video", "audio", "file", "forward_bundle")
    requires = ()
    produces = ("topic_windows",)

    def run(self, context: AnalyzerContext) -> list[DeterministicResult]:
        windows = _build_windows(context.corpus.messages)
        findings: list[DeterministicResult] = []
        for annotation in windows:
            findings.append(
                DeterministicResult(
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    status="resolved",
                    summary=annotation.summary,
                    confidence=annotation.confidence,
                    details={
                        "view_kind": "topic_window",
                        "operation_type": "group",
                        "scope_level": "topic",
                        "window_id": annotation.window_id,
                        "source_message_ids": list(annotation.source_message_ids),
                        "derived_annotation": annotation.to_payload(),
                    },
                    evidence_refs=[
                        AnalysisEvidenceRef(kind="message", message_id=message_id)
                        for message_id in annotation.source_message_ids
                    ],
                    tags=["topic_window", "deterministic", "derived_view"],
                    verdict="window_candidate",
                )
            )
        return findings


def _build_windows(messages: list[Any]) -> list[TopicWindowAnnotation]:
    ordered = sorted(
        messages,
        key=lambda item: (getattr(item, "timestamp_ms", 0), getattr(item, "message_seq", None) or "", getattr(item, "message_id", None) or ""),
    )
    raw_windows: list[list[Any]] = []
    current: list[Any] = []
    current_thread_ids: set[str] = set()
    thread_lookup = _thread_lookup(ordered)

    for message in ordered:
        message_key = message.message_id or f"seq:{message.message_seq}"
        thread_id = thread_lookup.get(message_key)
        if not current:
            current = [message]
            current_thread_ids = {thread_id} if thread_id else set()
            continue

        previous = current[-1]
        same_thread = bool(thread_id and thread_id in current_thread_ids)
        time_gap_ms = message.timestamp_ms - previous.timestamp_ms
        if len(current) >= MAX_WINDOW_MESSAGES or (time_gap_ms > WINDOW_GAP_MS and not same_thread):
            raw_windows.append(current)
            current = [message]
            current_thread_ids = {thread_id} if thread_id else set()
            continue

        current.append(message)
        if thread_id:
            current_thread_ids.add(thread_id)

    if current:
        raw_windows.append(current)

    annotations: list[TopicWindowAnnotation] = []
    for index, window in enumerate(raw_windows, start=1):
        if len(window) < 3:
            continue
        participant_ids = tuple(sorted({_sender_id(message) for message in window if _sender_id(message)}))
        if len(participant_ids) < 2:
            continue
        message_ids = tuple(_message_key(message) for message in window if _message_key(message))
        thread_ids = tuple(
            sorted(
                {
                    thread_lookup[message_id]
                    for message_id in message_ids
                    if message_id in thread_lookup and thread_lookup[message_id]
                }
            )
        )
        summary = _build_topic_summary(index, window)
        annotations.append(
            TopicWindowAnnotation(
                window_id=f"topic_window_{index:04d}",
                source_message_ids=message_ids,
                summary=summary,
                confidence=0.74,
                start_timestamp_iso=window[0].timestamp_iso,
                end_timestamp_iso=window[-1].timestamp_iso,
                participant_ids=participant_ids,
                thread_ids=thread_ids,
            )
        )
    return annotations


def _thread_lookup(messages: Iterable[Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for message in messages:
        message_key = _message_key(message)
        if not message_key:
            continue
        thread_id = None
        extra = getattr(message, "extra", None)
        raw_thread_id = extra.get("thread_id") if isinstance(extra, dict) else None
        if raw_thread_id:
            thread_id = str(raw_thread_id)
        if thread_id:
            lookup[message_key] = thread_id
    return lookup


def _build_topic_summary(index: int, window: list[Any]) -> str:
    samples = []
    for message in window:
        text = ((getattr(message, "text_content", None) or getattr(message, "content", None) or "").strip())
        if text:
            samples.append(text[:24])
        if len(samples) >= 3:
            break
    sample_text = " | ".join(samples) if samples else "多消息连续讨论"
    return f"topic_window_{index:04d}: {len(window)} 条连续消息，主题样本为 {sample_text}"


def _sender_id(message: Any) -> str | None:
    value = getattr(message, "sender_id", None) or getattr(message, "sender_id_raw", None)
    return str(value) if value else None


def _message_key(message: Any) -> str | None:
    message_id = getattr(message, "message_id", None)
    if message_id:
        return str(message_id)
    message_seq = getattr(message, "message_seq", None)
    if message_seq:
        return f"seq:{message_seq}"
    return None
