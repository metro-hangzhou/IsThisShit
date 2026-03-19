from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from qq_data_process.utils import preview_text

from .models import AnalysisEvidenceItem, AnalysisMaterials, AnalysisMessageRecord


@dataclass(slots=True)
class MessageInputSemantics:
    delivery_profile: str
    raw_text: str | None
    processed_text: str | None
    decision_summary: str | None
    source_message_ids: tuple[str, ...]
    source_thread_ids: tuple[str, ...]
    labels: tuple[str, ...]
    annotation_count: int
    explicit_processed_overlay: bool
    processed_only: bool

    @property
    def has_raw(self) -> bool:
        return bool((self.raw_text or "").strip())

    @property
    def has_processed(self) -> bool:
        return bool(
            (self.processed_text or "").strip() or (self.decision_summary or "").strip()
        )


@dataclass(slots=True)
class MaterialInputSemantics:
    delivery_profile_guess: str
    raw_visible_messages: int
    processed_overlay_messages: int
    processed_only_messages: int
    raw_plus_processed_messages: int
    source_linked_messages: int
    annotation_messages: int
    annotation_count: int
    top_labels: list[tuple[str, int]]
    notes: list[str]


def build_material_input_semantics(materials: AnalysisMaterials) -> MaterialInputSemantics:
    explicit_profiles: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    raw_visible_messages = 0
    processed_overlay_messages = 0
    processed_only_messages = 0
    raw_plus_processed_messages = 0
    source_linked_messages = 0
    annotation_messages = 0
    annotation_count = 0

    for message in materials.messages:
        item = classify_message_input_semantics(message)
        explicit_profiles[item.delivery_profile] += 1
        if item.has_raw:
            raw_visible_messages += 1
        if item.explicit_processed_overlay:
            processed_overlay_messages += 1
        if item.processed_only:
            processed_only_messages += 1
        if item.has_raw and item.has_processed:
            raw_plus_processed_messages += 1
        if item.source_message_ids:
            source_linked_messages += 1
        if item.annotation_count > 0:
            annotation_messages += 1
        annotation_count += item.annotation_count
        label_counter.update(item.labels)

    delivery_profile_guess = _guess_delivery_profile(
        explicit_profiles=explicit_profiles,
        raw_plus_processed_messages=raw_plus_processed_messages,
        processed_only_messages=processed_only_messages,
    )
    notes: list[str] = []
    if delivery_profile_guess == "raw_plus_processed":
        notes.append("检测到 raw_plus_processed 语义，raw 文本与派生摘要必须分开展示。")
    if processed_only_messages:
        notes.append("存在 processed-only 记录，下游不得把其 summary 当成原始聊天原文引用。")
    if source_linked_messages:
        notes.append("部分记录带 source_message_ids/source_thread_ids，可追溯回原始证据。")
    if annotation_count:
        notes.append("存在预处理 annotation/summary 覆盖层，适合作为辅助线索而非真相层。")
    if not notes:
        notes.append("当前输入看起来接近 raw_only 语义。")

    return MaterialInputSemantics(
        delivery_profile_guess=delivery_profile_guess,
        raw_visible_messages=raw_visible_messages,
        processed_overlay_messages=processed_overlay_messages,
        processed_only_messages=processed_only_messages,
        raw_plus_processed_messages=raw_plus_processed_messages,
        source_linked_messages=source_linked_messages,
        annotation_messages=annotation_messages,
        annotation_count=annotation_count,
        top_labels=label_counter.most_common(5),
        notes=notes,
    )


def classify_message_input_semantics(message: AnalysisMessageRecord) -> MessageInputSemantics:
    extra = _as_mapping(message.extra)
    delivery_profile = _first_non_empty_str(
        _nested(extra, "delivery_profile"),
        _nested(extra, "preprocess", "delivery_profile"),
        _nested(extra, "view", "delivery_profile"),
        _nested(extra, "preprocess_view", "delivery_profile"),
    )
    raw_text = _first_non_empty_str(
        _nested(extra, "raw_text"),
        _nested(extra, "raw_content"),
        _nested(extra, "original_text"),
        _nested(extra, "source_text"),
    )
    processed_text = _first_non_empty_str(
        _nested(extra, "processed_text"),
        _nested(extra, "processed_summary"),
        _nested(extra, "preprocess", "processed_text"),
        _nested(extra, "preprocess", "summary"),
    )
    decision_summary = _first_non_empty_str(
        _nested(extra, "decision_summary"),
        _nested(extra, "summary"),
        _nested(extra, "preprocess", "decision_summary"),
    )
    source_message_ids = _extract_string_list(
        _nested(extra, "source_message_ids"),
        _nested(extra, "preprocess", "source_message_ids"),
    )
    source_thread_ids = _extract_string_list(
        _nested(extra, "source_thread_ids"),
        _nested(extra, "preprocess", "source_thread_ids"),
    )
    labels = _extract_string_list(
        _nested(extra, "preprocess_labels"),
        _nested(extra, "labels"),
        _nested(extra, "preprocess", "labels"),
    )
    annotation_count = _count_annotations(
        _nested(extra, "annotations"),
        _nested(extra, "preprocess_annotations"),
        _nested(extra, "preprocess", "annotations"),
    )
    explicit_processed_overlay = any(
        (
            processed_text,
            decision_summary,
            source_message_ids,
            source_thread_ids,
            labels,
            annotation_count,
            delivery_profile in {"processed_only", "raw_plus_processed"},
        )
    )
    fallback_raw_text = (message.text_content or message.content or "").strip() or None
    if raw_text:
        pass
    elif delivery_profile != "processed_only":
        raw_text = fallback_raw_text
    processed_only = delivery_profile == "processed_only" or (
        explicit_processed_overlay and not raw_text and bool(processed_text or decision_summary)
    )
    if not delivery_profile:
        if processed_only:
            delivery_profile = "processed_only"
        elif explicit_processed_overlay and raw_text:
            delivery_profile = "raw_plus_processed"
        else:
            delivery_profile = "raw_only"
    return MessageInputSemantics(
        delivery_profile=delivery_profile,
        raw_text=raw_text,
        processed_text=processed_text,
        decision_summary=decision_summary,
        source_message_ids=source_message_ids,
        source_thread_ids=source_thread_ids,
        labels=labels,
        annotation_count=annotation_count,
        explicit_processed_overlay=explicit_processed_overlay,
        processed_only=processed_only,
    )


def build_input_semantics_lines(materials: AnalysisMaterials) -> list[str]:
    summary = build_material_input_semantics(materials)
    lines = [
        "## Input Semantics",
        f"- delivery_profile_guess: {summary.delivery_profile_guess}",
        f"- raw_visible_messages: {summary.raw_visible_messages}",
        f"- processed_overlay_messages: {summary.processed_overlay_messages}",
        f"- processed_only_messages: {summary.processed_only_messages}",
        f"- raw_plus_processed_messages: {summary.raw_plus_processed_messages}",
        f"- source_linked_messages: {summary.source_linked_messages}",
        f"- annotation_messages: {summary.annotation_messages}",
        f"- annotation_count: {summary.annotation_count}",
    ]
    if summary.top_labels:
        lines.append(
            "- top_preprocess_labels: "
            + ", ".join(f"{label}:{count}" for label, count in summary.top_labels)
        )
    for note in summary.notes:
        lines.append(f"- note: {note}")
    return lines


def build_processed_overlay_references(
    materials: AnalysisMaterials,
    *,
    limit: int,
) -> list[AnalysisEvidenceItem]:
    evidence: list[AnalysisEvidenceItem] = []
    for message in materials.messages:
        semantics = classify_message_input_semantics(message)
        if not semantics.explicit_processed_overlay:
            continue
        derived_text = _first_non_empty_str(
            semantics.processed_text,
            semantics.decision_summary,
        )
        if not derived_text:
            continue
        evidence.append(
            AnalysisEvidenceItem(
                message_uid=message.message_uid,
                timestamp_iso=message.timestamp_iso,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                content=_render_processed_overlay_reference(semantics, derived_text),
                reason="processed_overlay",
                tags=[
                    "processed_overlay",
                    semantics.delivery_profile,
                    *semantics.labels[:3],
                ],
            )
        )
        if len(evidence) >= limit:
            break
    return evidence


def build_llm_result_summary_payload(*, result: Any, plan: Any) -> dict[str, Any]:
    pack = result.pack
    special = pack.special_content_types
    input_semantics = {
        "delivery_profile_guess": special.get("delivery_profile_guess", "raw_only"),
        "raw_visible_messages": special.get("raw_visible_messages", 0),
        "processed_overlay_messages": special.get("processed_overlay_messages", 0),
        "processed_only_messages": special.get("processed_only_messages", 0),
        "raw_plus_processed_messages": special.get("raw_plus_processed_messages", 0),
        "source_linked_messages": special.get("source_linked_messages", 0),
        "annotation_messages": special.get("annotation_messages", 0),
        "annotation_count": special.get("annotation_count", 0),
        "processed_overlay_reference_count": special.get(
            "processed_overlay_reference_count", 0
        ),
    }
    return {
        "prompt_version": result.prompt_version,
        "provider_name": result.provider_name,
        "model_name": result.model_name,
        "estimated_input_tokens": plan.estimated_input_tokens,
        "max_output_tokens": plan.max_output_tokens,
        "usage": result.usage.model_dump(mode="json"),
        "target": pack.target.model_dump(mode="json"),
        "chosen_time_window": pack.chosen_time_window.model_dump(mode="json"),
        "pack_summary": pack.pack_summary,
        "warnings": list(result.warnings),
        "message_count": pack.stats.message_count,
        "sender_count": pack.stats.sender_count,
        "candidate_event_count": len(pack.candidate_events),
        "representative_message_count": len(pack.representative_messages),
        "reference_pool_count": len(pack.message_reference_pool),
        "input_semantics": input_semantics,
        "media_coverage": pack.media_coverage.model_dump(mode="json"),
        "special_content_types": dict(pack.special_content_types),
    }


def format_message_for_display(
    message: AnalysisMessageRecord,
    *,
    max_chars: int,
) -> tuple[str, list[str]]:
    semantics = classify_message_input_semantics(message)
    tags = list(message.features.message_tags[:4])
    if semantics.processed_only:
        text = _first_non_empty_str(
            semantics.processed_text,
            semantics.decision_summary,
            semantics.raw_text,
        ) or ""
        tags.append("processed_only")
        return f"[processed-only summary] {preview_text(text, max_chars)}", tags
    text = semantics.raw_text or ""
    if semantics.explicit_processed_overlay:
        tags.append("processed_overlay_available")
    return preview_text(text.replace("\n", " / "), max_chars), tags


def _render_processed_overlay_reference(
    semantics: MessageInputSemantics, processed_text: str
) -> str:
    parts = [f"[processed {semantics.delivery_profile}] {preview_text(processed_text, 220)}"]
    if semantics.source_message_ids:
        parts.append("source_messages=" + ",".join(semantics.source_message_ids[:4]))
    if semantics.source_thread_ids:
        parts.append("source_threads=" + ",".join(semantics.source_thread_ids[:3]))
    return " | ".join(parts)


def _guess_delivery_profile(
    *,
    explicit_profiles: Counter[str],
    raw_plus_processed_messages: int,
    processed_only_messages: int,
) -> str:
    explicit_profiles.pop("", None)
    if explicit_profiles:
        return explicit_profiles.most_common(1)[0][0]
    if raw_plus_processed_messages > 0:
        return "raw_plus_processed"
    if processed_only_messages > 0:
        return "processed_only"
    return "raw_only"


def _extract_string_list(*values: Any) -> tuple[str, ...]:
    for value in values:
        if isinstance(value, (list, tuple)):
            normalized = [str(item).strip() for item in value if str(item).strip()]
            if normalized:
                return tuple(normalized)
    return ()


def _count_annotations(*values: Any) -> int:
    for value in values:
        if isinstance(value, (list, tuple)):
            return len(value)
    return 0


def _first_non_empty_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return None


def _nested(mapping: Mapping[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
