from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from qq_data_process.preprocess_models import PreprocessDirective

from ..interfaces import AnalyzerContext, DeterministicAnalyzer
from ..models import AnalysisEvidenceRef, DeterministicResult

NOISE_PATTERNS_DEFAULT = (
    "debug",
    "log",
    "traceback",
    "error",
    "rpc failed",
    "pull",
    "push",
    "branch",
    "commit",
    "start_cli",
    "start cli",
    "watch",
    "export",
    "login",
    "onebot",
    "napcat",
    "cli",
    "qr",
    "二维码",
    "代理",
    "节点",
    "配置",
    "脚本",
    "更新",
    "api",
    "llm",
    "rag",
    "prompt",
    "向量",
    "embedding",
    "数据库",
    "openai",
    "gpt",
)

SIGNAL_HINTS_DEFAULT = (
    "搬",
    "转发",
    "repost",
    "forward",
    "dump",
    "素材",
    "出处",
    "来源",
    "投稿",
    "群上传",
    "图片",
    "动图",
    "视频",
    "文件",
    "语音",
    "录音",
    "封面",
    "下载按钮",
    "资源过期",
    "素材包",
    "shi",
)

DEBUG_FILE_HINTS = (
    "log",
    "trace",
    "cli_",
    "startup",
    "state",
    "summary",
    "manifest",
    "jsonl",
)

WEAK_DEBUG_FILE_HINTS = (
    "export",
    "exports",
    "zip",
)

MEDIA_SEGMENT_TYPES = {"image", "gif", "video", "audio", "speech", "file", "forward"}


@dataclass(frozen=True)
class ContextFilterCluster:
    cluster_id: str
    source_message_ids: tuple[str, ...]
    summary: str
    confidence: float
    reason: str
    labels: tuple[str, ...]
    sample_texts: tuple[str, ...]
    preserved_neighbor_ids: tuple[str, ...]
    start_timestamp_iso: str | None
    end_timestamp_iso: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "cluster_id": self.cluster_id,
            "source_message_ids": list(self.source_message_ids),
            "summary": self.summary,
            "confidence": self.confidence,
            "reason": self.reason,
            "labels": list(self.labels),
            "sample_texts": list(self.sample_texts),
            "preserved_neighbor_ids": list(self.preserved_neighbor_ids),
            "start_timestamp_iso": self.start_timestamp_iso,
            "end_timestamp_iso": self.end_timestamp_iso,
        }


class ContextFilterPreprocessor(DeterministicAnalyzer):
    plugin_id = "context_filter_preprocessor"
    plugin_version = "0.2.0"
    scope_level = "message"
    supported_modalities = ("text", "image", "gif", "video", "audio", "file", "forward_bundle")
    requires = ()
    produces = ("context_filter_view",)

    def run(self, context: AnalyzerContext) -> list[DeterministicResult]:
        directive = _directive_from_context(context)
        messages = list(_messages_from_context(context))
        if not messages:
            return []

        relevant_indexes = {
            index
            for index, message in enumerate(messages)
            if _is_relevance_anchor(message, directive=directive)
        }
        preserve_window = max(int(directive.preserve_evidence_window), 0)
        preserved_indexes = _expand_preserve_window(
            message_count=len(messages),
            relevant_indexes=relevant_indexes,
            preserve_window=preserve_window,
        )
        clusters = _build_noise_clusters(
            messages,
            directive=directive,
            preserved_indexes=preserved_indexes,
        )
        findings: list[DeterministicResult] = []
        for cluster in clusters:
            verdict = _cluster_verdict(directive)
            findings.append(
                DeterministicResult(
                    plugin_id=self.plugin_id,
                    plugin_version=self.plugin_version,
                    status="resolved",
                    summary=cluster.summary,
                    confidence=cluster.confidence,
                    modality_targets=["text"],
                    details={
                        "view_kind": "context_filter",
                        "operation_type": _operation_type(directive),
                        "scope_level": "message",
                        "cluster_id": cluster.cluster_id,
                        "source_message_ids": list(cluster.source_message_ids),
                        "decision_summary": cluster.reason,
                        "derived_annotation": cluster.to_payload(),
                        "directive_id": directive.directive_id,
                        "directive_title": directive.title,
                        "analysis_goal": directive.analysis_goal,
                        "relevance_policy": directive.relevance_policy,
                        "noise_handling_mode": directive.noise_handling_mode,
                        "preserve_evidence_window": directive.preserve_evidence_window,
                        "labels": list(cluster.labels),
                    },
                    evidence_refs=[
                        *[
                            AnalysisEvidenceRef(kind="message", message_id=message_id)
                            for message_id in cluster.source_message_ids
                        ],
                        *[
                            AnalysisEvidenceRef(
                                kind="message",
                                message_id=message_id,
                                note="neighbor preserved as evidence window",
                            )
                            for message_id in cluster.preserved_neighbor_ids
                        ],
                    ],
                    tags=[
                        "context_filter",
                        "derived_view",
                        directive.relevance_policy,
                        *cluster.labels,
                    ],
                    verdict=verdict,
                )
            )
        return findings


def _directive_from_context(context: AnalyzerContext) -> PreprocessDirective:
    raw_directive = context.options.get("directive")
    if isinstance(raw_directive, PreprocessDirective):
        return raw_directive
    if isinstance(raw_directive, Mapping):
        return PreprocessDirective.model_validate(dict(raw_directive))
    return PreprocessDirective(
        directive_id="context_filter_default",
        title="Default context filter",
        relevance_policy="meme_focus",
        noise_handling_mode="compact_cluster",
        preserve_evidence_window=2,
        suppress_non_target_chatter=True,
        suppress_message_patterns=list(NOISE_PATTERNS_DEFAULT),
        target_topics=list(SIGNAL_HINTS_DEFAULT),
        suppress_topics=["调试", "报错", "日志", "脚本", "更新", "代理", "配置"],
        retain_modalities=["image", "video", "file", "speech", "forward"],
    )


def _build_noise_clusters(
    messages: Sequence[Any],
    *,
    directive: PreprocessDirective,
    preserved_indexes: set[int],
) -> list[ContextFilterCluster]:
    clusters: list[list[tuple[int, Any, set[str]]]] = []
    current: list[tuple[int, Any, set[str]]] = []
    max_span = max(int(directive.max_compaction_span_messages), 1)
    max_gap_ms = max(int(directive.cluster_gap_seconds), 0) * 1000

    for index, message in enumerate(messages):
        reasons = _noise_labels(message, directive=directive)
        if index in preserved_indexes or not reasons:
            if current:
                clusters.append(current)
                current = []
            continue

        if not current:
            current = [(index, message, reasons)]
            continue

        prev_index, prev_message, _ = current[-1]
        gap_ms = max(_timestamp_ms(message) - _timestamp_ms(prev_message), 0)
        if index != prev_index + 1 or gap_ms > max_gap_ms or len(current) >= max_span:
            clusters.append(current)
            current = [(index, message, reasons)]
            continue
        current.append((index, message, reasons))

    if current:
        clusters.append(current)

    built: list[ContextFilterCluster] = []
    for cluster_index, cluster in enumerate(clusters, start=1):
        source_message_ids = tuple(_message_id(message) for _, message, _ in cluster if _message_id(message))
        labels = tuple(sorted({label for _, _, reasons in cluster for label in reasons}))
        preserved_neighbor_ids = _neighbor_ids(messages, cluster, preserved_indexes)
        sample_texts = tuple(_sample_texts(message for _, message, _ in cluster))
        reason_text = " / ".join(labels) if labels else "mixed_dev_chatter"
        built.append(
            ContextFilterCluster(
                cluster_id=f"context_filter_{cluster_index:04d}",
                source_message_ids=source_message_ids,
                summary=_cluster_summary(
                    cluster,
                    labels=labels,
                    sample_texts=sample_texts,
                    directive=directive,
                ),
                confidence=_cluster_confidence(cluster, labels=labels),
                reason=f"directive_suppressed_cluster:{reason_text}",
                labels=labels,
                sample_texts=sample_texts,
                preserved_neighbor_ids=preserved_neighbor_ids,
                start_timestamp_iso=_timestamp_iso(cluster[0][1]),
                end_timestamp_iso=_timestamp_iso(cluster[-1][1]),
            )
        )
    return built


def _cluster_summary(
    cluster: Sequence[tuple[int, Any, set[str]]],
    *,
    labels: Sequence[str],
    sample_texts: Sequence[str],
    directive: PreprocessDirective,
) -> str:
    label_hint = "、".join(labels[:3]) if labels else "开发/调试噪音"
    sample_hint = " | ".join(sample_texts[:3]) if sample_texts else "无代表样本"
    action = _summary_action_word(directive)
    return f"已{action} {len(cluster)} 条 mixed-purpose 群中的低相关开发/调试 chatter。 类别={label_hint}；样本={sample_hint}"


def _cluster_confidence(
    cluster: Sequence[tuple[int, Any, set[str]]],
    *,
    labels: Sequence[str],
) -> float:
    base = 0.72
    if len(cluster) >= 4:
        base += 0.08
    if any(label in {"dev_ops", "cli_workflow", "runtime_debug"} for label in labels):
        base += 0.05
    return min(base, 0.92)


def _is_relevance_anchor(message: Any, *, directive: PreprocessDirective) -> bool:
    text = _message_text(message)
    lowered = text.lower()
    suppress_tokens = _lowered_tokens(directive.suppress_message_patterns, NOISE_PATTERNS_DEFAULT)

    if directive.preserve_reply_context and _has_reply_structure(message):
        return True
    if _has_forward_structure(message):
        return True
    if _participant_matches(message, directive.suppress_participants):
        return False
    if _has_signal_media(message, directive=directive) and not _looks_like_debug_attachment(message, suppress_tokens=suppress_tokens):
        return True
    if any(token in lowered for token in _lowered_tokens(directive.target_topics, SIGNAL_HINTS_DEFAULT)):
        return True
    if any(token in lowered for token in ("转发", "forward", "repost", "搬运", "出处", "来源", "dump")):
        return True
    if directive.target_participants and _participant_matches(message, directive.target_participants):
        return True
    return False


def _noise_labels(message: Any, *, directive: PreprocessDirective) -> set[str]:
    text = _message_text(message)
    lowered = text.lower()

    if _is_relevance_anchor(message, directive=directive):
        return set()
    if directive.target_participants and _participant_matches(message, directive.target_participants):
        return set()
    if any(token in lowered for token in _lowered_tokens(directive.target_topics, ())):
        return set()

    labels: set[str] = set()
    suppress_tokens = _lowered_tokens(directive.suppress_message_patterns, NOISE_PATTERNS_DEFAULT)
    suppress_topics = _lowered_tokens(directive.suppress_topics, ())
    examples = _lowered_tokens(directive.suppress_message_examples, ())

    if _participant_matches(message, directive.suppress_participants):
        labels.add("suppressed_participant")
    if any(token in lowered for token in suppress_topics):
        labels.add("suppressed_topic")
    if any(token in lowered for token in examples):
        labels.add("suppressed_example")
    if any(token in lowered for token in suppress_tokens):
        labels.update(_categorize_text_noise(lowered))
    if _looks_like_debug_attachment(message, suppress_tokens=suppress_tokens):
        labels.add("debug_attachment")
    if directive.suppress_non_target_chatter and _looks_like_short_chatter(lowered):
        labels.add("low_signal_chatter")
    if _should_force_strict_focus_compaction(
        message,
        directive=directive,
        lowered_text=lowered,
    ):
        labels.add("strict_focus_non_target")
    return labels


def _categorize_text_noise(lowered: str) -> set[str]:
    labels: set[str] = set()
    if any(token in lowered for token in ("napcat", "onebot", "qr", "二维码", "代理", "rpc failed", "traceback", "报错", "日志")):
        labels.add("runtime_debug")
    if any(token in lowered for token in ("start cli", "start_cli", "/watch", "/export", "/login", "cli", "watch", "export")):
        labels.add("cli_workflow")
    if any(token in lowered for token in ("git", "pull", "push", "branch", "commit", "更新", "脚本", "配置")):
        labels.add("dev_ops")
    if any(token in lowered for token in ("llm", "rag", "api", "embedding", "向量", "prompt", "数据库", "gpt", "openai")):
        labels.add("analysis_dev")
    if not labels:
        labels.add("suppressed_pattern")
    return labels


def _has_reply_structure(message: Any) -> bool:
    if getattr(message, "reply_to", None) is not None:
        return True
    for segment in _segments(message):
        if _segment_type(segment) == "reply":
            return True
    return False


def _has_forward_structure(message: Any) -> bool:
    for segment in _segments(message):
        if _segment_type(segment) == "forward":
            return True
    return False


def _has_signal_media(message: Any, *, directive: PreprocessDirective) -> bool:
    retain_modalities = {item.strip().lower() for item in directive.retain_modalities if str(item).strip()}
    for segment in _segments(message):
        segment_type = _segment_type(segment)
        if segment_type in {"forward", "image", "gif", "video", "audio", "speech"}:
            return True
        if segment_type == "file" and ("file" in retain_modalities or not retain_modalities):
            return True
    if getattr(message, "image_file_names", None):
        return True
    return False


def _looks_like_debug_attachment(message: Any, *, suppress_tokens: Sequence[str]) -> bool:
    file_names = list(getattr(message, "uploaded_file_names", None) or [])
    for segment in _segments(message):
        if _segment_type(segment) == "file":
            file_name = _string_or_none(getattr(segment, "file_name", None))
            if file_name:
                file_names.append(file_name)
    lowered_text = _message_text(message).lower()
    for file_name in file_names:
        lowered = file_name.lower()
        if any(token in lowered for token in DEBUG_FILE_HINTS):
            return True
        if any(token in lowered for token in WEAK_DEBUG_FILE_HINTS) and any(
            token in lowered_text for token in suppress_tokens
        ):
            return True
    return False


def _expand_preserve_window(
    *,
    message_count: int,
    relevant_indexes: Iterable[int],
    preserve_window: int,
) -> set[int]:
    preserved: set[int] = set()
    for index in relevant_indexes:
        start = max(index - preserve_window, 0)
        end = min(index + preserve_window + 1, message_count)
        preserved.update(range(start, end))
    return preserved


def _neighbor_ids(
    messages: Sequence[Any],
    cluster: Sequence[tuple[int, Any, set[str]]],
    preserved_indexes: set[int],
) -> tuple[str, ...]:
    if not cluster:
        return ()
    first = cluster[0][0]
    last = cluster[-1][0]
    neighbor_ids: list[str] = []
    for index in range(first - 2, last + 3):
        if index < 0 or index >= len(messages) or index not in preserved_indexes:
            continue
        if first <= index <= last:
            continue
        message_id = _message_id(messages[index])
        if message_id:
            neighbor_ids.append(message_id)
    return tuple(dict.fromkeys(neighbor_ids))


def _sample_texts(messages: Iterable[Any]) -> list[str]:
    samples: list[str] = []
    for message in messages:
        text = _message_text(message)
        if not text:
            continue
        samples.append(text[:64])
        if len(samples) >= 3:
            break
    return samples


def _messages_from_context(context: AnalyzerContext) -> Sequence[Any]:
    direct = getattr(context, "messages", None)
    if direct is not None:
        return list(direct)
    corpus = getattr(context, "corpus", None)
    nested = getattr(corpus, "messages", None)
    if nested is not None:
        return list(nested)
    return []


def _segments(message: Any) -> list[Any]:
    return list(getattr(message, "segments", None) or [])


def _segment_type(segment: Any) -> str:
    return _string_or_none(getattr(segment, "type", None)) or "text"


def _participant_matches(message: Any, participants: Sequence[str]) -> bool:
    haystack = {
        _string_or_none(getattr(message, "sender_id", None)) or "",
        _string_or_none(getattr(message, "sender_name", None)) or "",
        _string_or_none(getattr(message, "sender_card", None)) or "",
    }
    needles = {str(item).strip().lower() for item in participants if str(item).strip()}
    return bool({item.lower() for item in haystack if item} & needles)


def _lowered_tokens(values: Sequence[str], fallback: Sequence[str]) -> tuple[str, ...]:
    tokens = [str(item).strip().lower() for item in values if str(item).strip()]
    if tokens:
        return tuple(tokens)
    return tuple(str(item).strip().lower() for item in fallback if str(item).strip())


def _looks_like_short_chatter(lowered_text: str) -> bool:
    compact = lowered_text.strip()
    if len(compact) <= 4:
        return True
    chatty_markers = (
        "哈哈",
        "hhh",
        "草",
        "6",
        "哦",
        "啊",
        "行",
        "ok",
        "收到",
        "牛",
        "确实",
        "笑死",
        "在吗",
        "来了",
    )
    return any(token in compact for token in chatty_markers)


def _should_force_strict_focus_compaction(
    message: Any,
    *,
    directive: PreprocessDirective,
    lowered_text: str,
) -> bool:
    if str(directive.relevance_policy).strip().lower() != "strict_focus":
        return False
    if _has_forward_structure(message) or _has_reply_structure(message):
        return False
    if _has_signal_media(message, directive=directive):
        return False
    if any(token in lowered_text for token in _lowered_tokens(directive.target_topics, SIGNAL_HINTS_DEFAULT)):
        return False
    if directive.target_participants and _participant_matches(message, directive.target_participants):
        return False
    return bool(lowered_text)


def _operation_type(directive: PreprocessDirective) -> str:
    if directive.noise_handling_mode == "annotate_only":
        return "annotate"
    if directive.noise_handling_mode == "suppress_message":
        return "suppress"
    return "compact"


def _summary_action_word(directive: PreprocessDirective) -> str:
    if directive.noise_handling_mode == "annotate_only":
        return "标注"
    if directive.noise_handling_mode == "suppress_message":
        return "抑制"
    return "压缩"


def _cluster_verdict(directive: PreprocessDirective) -> str:
    if directive.noise_handling_mode == "annotate_only":
        return "annotated_cluster"
    if directive.noise_handling_mode == "suppress_message":
        return "suppressed_cluster"
    return "compact_candidate"


def _message_id(message: Any) -> str | None:
    value = _string_or_none(getattr(message, "message_id", None))
    if value:
        return value
    seq = _string_or_none(getattr(message, "message_seq", None))
    return f"seq:{seq}" if seq else None


def _message_text(message: Any) -> str:
    return (_string_or_none(getattr(message, "text_content", None)) or _string_or_none(getattr(message, "content", None)) or "").strip()


def _timestamp_ms(message: Any) -> int:
    value = getattr(message, "timestamp_ms", None)
    if isinstance(value, int):
        return value
    return 0


def _timestamp_iso(message: Any) -> str | None:
    return _string_or_none(getattr(message, "timestamp_iso", None))


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
