from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable

from ..interfaces import AnalyzerContext, DeterministicAnalyzer
from ..models import AnalysisEvidenceRef, DeterministicResult


@dataclass(frozen=True)
class ThreadCompactionAnnotation:
    thread_id: str
    source_message_ids: tuple[str, ...]
    summary: str
    confidence: float
    reason: str
    compacted_message_count: int
    participant_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "thread_id": self.thread_id,
            "source_message_ids": list(self.source_message_ids),
            "summary": self.summary,
            "confidence": self.confidence,
            "reason": self.reason,
            "compacted_message_count": self.compacted_message_count,
            "participant_ids": list(self.participant_ids),
        }


class ThreadCompactionPreprocessor(DeterministicAnalyzer):
    plugin_id = "thread_compaction_preprocessor"
    plugin_version = "0.1.0"
    scope_level = "thread"
    supported_modalities = ("text",)
    requires = ()
    produces = ("compact_thread_view",)

    def run(self, context: AnalyzerContext) -> list[DeterministicResult]:
        corpus = context.corpus
        messages_by_id = {
            _message_key(message): message
            for message in getattr(corpus, "messages", []) or []
            if _message_key(message)
        }
        threads = list(getattr(corpus, "threads", []) or [])

        findings: list[DeterministicResult] = []
        for thread in threads:
            annotation = _maybe_compact_thread(thread, messages_by_id=messages_by_id)
            if annotation is None:
                continue
            findings.append(
                DeterministicResult(
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    status="resolved",
                    summary=annotation.summary,
                    confidence=annotation.confidence,
                    modality_targets=["text"],
                    details={
                        "view_kind": "thread_compaction",
                        "operation_type": "compact",
                        "scope_level": "thread",
                        "thread_id": annotation.thread_id,
                        "source_message_ids": list(annotation.source_message_ids),
                        "derived_annotation": annotation.to_payload(),
                    },
                    evidence_refs=[
                        AnalysisEvidenceRef(
                            kind="thread",
                            thread_id=annotation.thread_id,
                            note=annotation.reason,
                        ),
                        *[
                            AnalysisEvidenceRef(kind="message", message_id=message_id)
                            for message_id in annotation.source_message_ids
                        ],
                    ],
                    tags=["compact", "thread", "deterministic", "derived_view"],
                    verdict="compact_candidate",
                )
            )
        return findings


def _maybe_compact_thread(
    thread: Any,
    *,
    messages_by_id: dict[str, Any],
) -> ThreadCompactionAnnotation | None:
    ordered_messages = [
        messages_by_id[message_id]
        for message_id in getattr(thread, "message_ids", []) or []
        if message_id in messages_by_id
    ]
    if len(ordered_messages) < 5:
        return None
    if any(_has_nontrivial_structure(message) for message in ordered_messages):
        return None

    normalized_texts = [_normalize_text(message.text_content or message.content) for message in ordered_messages]
    if any(not text for text in normalized_texts):
        return None

    average_length = mean(len(text) for text in normalized_texts)
    unique_ratio = len(set(normalized_texts)) / len(normalized_texts)
    repeated_short_ratio = sum(1 for text in normalized_texts if len(text) <= 8) / len(normalized_texts)

    if average_length > 10:
        return None
    if unique_ratio > 0.7:
        return None
    if repeated_short_ratio < 0.7:
        return None

    summary = _build_compaction_summary(thread, normalized_texts)
    return ThreadCompactionAnnotation(
        thread_id=str(getattr(thread, "thread_id", "unknown_thread")),
        source_message_ids=tuple(_message_key(message) for message in ordered_messages if _message_key(message)),
        summary=summary,
        confidence=0.82,
        reason="short_repetitive_text_only_thread",
        compacted_message_count=len(ordered_messages),
        participant_ids=tuple(getattr(thread, "participant_ids", []) or []),
    )


def _has_nontrivial_structure(message: Any) -> bool:
    if getattr(message, "reply_to", None) is not None:
        return True
    if (
        getattr(message, "image_file_names", None)
        or getattr(message, "uploaded_file_names", None)
        or getattr(message, "emoji_tokens", None)
    ):
        return True
    for segment in getattr(message, "segments", []) or []:
        if getattr(segment, "type", None) != "text":
            return True
    return False


def _normalize_text(text: str) -> str:
    filtered = "".join(ch.lower() for ch in text if ch.isalnum())
    return filtered.strip()


def _build_compaction_summary(thread: Any, normalized_texts: Iterable[str]) -> str:
    samples = list(dict.fromkeys(text for text in normalized_texts if text))[:3]
    hint = "、".join(samples) if samples else "短句重复"
    return (
        f"thread {getattr(thread, 'thread_id', 'unknown_thread')} 可压缩为低信息密度片段："
        f"{len(getattr(thread, 'message_ids', []) or [])} 条短句重复消息，核心模式为 {hint}。"
    )


def _message_key(message: Any) -> str | None:
    message_id = getattr(message, "message_id", None)
    if message_id:
        return str(message_id)
    message_seq = getattr(message, "message_seq", None)
    if message_seq:
        return f"seq:{message_seq}"
    return None
