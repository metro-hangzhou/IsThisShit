from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from qq_data_process.utils import preview_text

from .llm_agent import (
    DeepSeekAnalysisClient,
    DeepSeekRuntimeConfig,
    OpenAICompatibleAnalysisClient,
    LlmResponseBundle,
    load_deepseek_runtime_config,
    load_openai_compatible_runtime_config,
)
from .models import (
    AnalysisEvidenceItem,
    AnalysisMaterials,
    AnalysisMessageRecord,
    AnalysisPack,
    AnalysisPackMessageSample,
    ImageCaptionSample,
    LlmAnalysisJobConfig,
    LlmAnalysisResult,
    LlmRunArtifactSet,
    LlmUsageRecord,
    MediaEvidenceScaffoldItem,
    MediaInferenceScaffold,
    MediaCoverageSummary,
)

STRUCTURED_TOKEN_RE = re.compile(r"\[[^\]]+\]")
BENSHI_TEXT_TERMS = (
    "搬史",
    "运史",
    "工业史",
    "典中典",
    "外源",
    "二手",
    "史官",
    "抽象",
    "逆天",
    "弱智",
)
VISUAL_REFERENCE_TERMS = (
    "这图",
    "那图",
    "图里",
    "图上",
    "看图",
    "如图",
    "配图",
    "发图",
    "图片",
    "表情包",
    "梗图",
    "聊天记录",
    "截图",
)
SCREENSHOT_TEXT_TERMS = (
    "截图",
    "聊天记录",
    "原图",
    "原话",
    "原文",
    "证据",
    "出处",
    "来源",
    "转发",
)
REACTION_TEXT_TERMS = (
    "草",
    "哈哈",
    "笑死",
    "绷不住",
    "乐",
    "典",
    "逆天",
    "抽象",
    "离谱",
    "好似",
)
UNCERTAINTY_TEXT_TERMS = (
    "看不懂",
    "没看懂",
    "不知道",
    "啥意思",
    "什么意思",
    "不清楚",
)
STABLE_DIMENSION_GUIDE: tuple[tuple[str, str], ...] = (
    (
        "interaction_density",
        "how active the window is and how concentrated participation is",
    ),
    (
        "information_density",
        "how much of the window is low-information reactions versus self-explanatory content",
    ),
    (
        "content_provenance",
        "whether the window is mostly native discussion, relayed material, or mixed",
    ),
    (
        "narrative_coherence",
        "whether the window contains one clear storyline, several fragments, or mostly noise",
    ),
    (
        "media_dependence",
        "how much meaning depends on image/video/file payloads rather than visible text alone",
    ),
    (
        "uncertainty_load",
        "how much of the report must remain unknown because evidence is missing or weak",
    ),
    (
        "topic_type",
        "what kind of window this is: technical, relay/gossip, personal event, ambient joke/noise, or mixed",
    ),
    (
        "followup_value",
        "whether the best next step is media recovery, wider time window review, or user-history review",
    ),
)
SOFT_ROLE_GUIDE: tuple[tuple[str, str], ...] = (
    ("narrative_carrier", "carries the clearest text-native storyline in the window"),
    (
        "relay_forwarder",
        "mainly imports outside material through forwards, shares, or relayed context",
    ),
    ("topic_initiator", "visibly starts a topic branch or first anchor statement"),
    (
        "noise_broadcaster",
        "dominates the window with repeated low-information or repetitive media-heavy traffic",
    ),
    ("question_probe", "asks clarifying, provocative, or topic-revealing questions"),
    ("reaction_echoer", "mainly contributes short emotional or alignment responses"),
    (
        "resource_dropper",
        "moves discussion forward by dropping files, links, reference items, or useful media",
    ),
)


class WindowReportClient(Protocol):
    def analyze_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle: ...


@dataclass(slots=True)
class WindowReportPlan:
    pack: AnalysisPack
    prompt_version: str
    system_prompt: str
    user_prompt: str
    estimated_input_tokens: int
    max_output_tokens: int


@dataclass(slots=True)
class _TextGapReferencePattern:
    message_uid: str
    hypothesis_kind: str
    confidence_score: float
    support_signals: tuple[str, ...]


class WholeWindowPackBuilder:
    def __init__(self, config: LlmAnalysisJobConfig) -> None:
        self.config = config

    def build(self, materials: AnalysisMaterials) -> AnalysisPack:
        representative_messages = self._representative_messages(materials)
        reference_pool = self._reference_pool(materials, representative_messages)
        retrieval_snippets = self._retrieval_snippets(materials)
        media_coverage = materials.manifest_media_coverage or self._media_coverage(
            materials.messages
        )
        media_inference_scaffold = self._media_inference_scaffold(
            materials.messages,
            media_coverage,
        )
        special_content_types = self._special_content_types(materials.messages)
        special_content_types["text_gap_inferred_items"] = len(
            media_inference_scaffold.inferred
        )
        special_content_types["text_gap_unknown_items"] = len(
            media_inference_scaffold.unknown
        )
        warnings = list(materials.warnings)

        if self.config.include_retrieval_snippets and not retrieval_snippets:
            warnings.append(
                "Retrieval snippets were requested, but this first-phase pack builder "
                "did not include any additional retrieval snippets."
            )

        if media_coverage.overall_media_missing_ratio > 0.5:
            warnings.append(
                f"High media missing ratio: {media_coverage.overall_media_missing_ratio:.1%} "
                f"of media references are unavailable. Analysis may be based on incomplete evidence."
            )
        elif media_coverage.overall_media_missing_ratio > 0.1:
            warnings.append(
                f"Moderate media missing ratio: {media_coverage.overall_media_missing_ratio:.1%} "
                f"of media references are unavailable."
            )

        if media_inference_scaffold.inferred:
            warnings.append(
                f"Text-only gap inference added {len(media_inference_scaffold.inferred)} "
                "context-only hypotheses; keep them secondary to direct evidence."
            )

        return AnalysisPack(
            run_id=materials.run_id,
            target=materials.target,
            chosen_time_window=materials.chosen_time_window,
            pack_summary=self._pack_summary(materials),
            stats=materials.stats,
            tag_summaries=materials.tag_summaries[: self.config.max_candidate_events],
            candidate_events=materials.candidate_events[
                : self.config.max_candidate_events
            ],
            participant_profiles=materials.participant_profiles[
                : self.config.max_people
            ],
            representative_messages=representative_messages,
            special_content_types=special_content_types,
            retrieval_snippets=retrieval_snippets,
            message_reference_pool=reference_pool,
            media_coverage=media_coverage,
            media_inference_scaffold=media_inference_scaffold,
            warnings=warnings,
        )

    def _representative_messages(
        self, materials: AnalysisMaterials
    ) -> list[AnalysisPackMessageSample]:
        limit = self.config.max_representative_messages
        selected: list[AnalysisPackMessageSample] = []
        seen: set[str] = set()

        def add_message(message: AnalysisMessageRecord) -> None:
            if message.message_uid in seen or len(selected) >= limit:
                return
            selected.append(
                AnalysisPackMessageSample(
                    message_uid=message.message_uid,
                    timestamp_iso=message.timestamp_iso,
                    sender_id=message.sender_id,
                    sender_name=message.sender_name,
                    content=preview_text(message.content.replace("\n", " / "), 220),
                    tags=message.features.message_tags[:4],
                )
            )
            seen.add(message.message_uid)

        message_map = {item.message_uid: item for item in materials.messages}
        for event in materials.candidate_events[: self.config.max_candidate_events]:
            for evidence in event.evidence:
                message = message_map.get(evidence.message_uid)
                if message is not None:
                    add_message(message)

        for profile in materials.participant_profiles[: self.config.max_people]:
            for evidence in profile.evidence:
                message = message_map.get(evidence.message_uid)
                if message is not None:
                    add_message(message)

        if len(selected) < limit and materials.messages:
            stride = max(1, len(materials.messages) // max(1, limit - len(selected)))
            for message in materials.messages[::stride]:
                add_message(message)
                if len(selected) >= limit:
                    break

        return selected

    def _reference_pool(
        self,
        materials: AnalysisMaterials,
        representative_messages: list[AnalysisPackMessageSample],
    ) -> list[AnalysisEvidenceItem]:
        selected: list[AnalysisEvidenceItem] = []
        seen: set[str] = set()

        def add(item: AnalysisEvidenceItem) -> None:
            if (
                item.message_uid in seen
                or len(selected) >= self.config.max_reference_messages
            ):
                return
            selected.append(item)
            seen.add(item.message_uid)

        for event in materials.candidate_events[: self.config.max_candidate_events]:
            for evidence in event.evidence:
                add(evidence)

        for profile in materials.participant_profiles[: self.config.max_people]:
            for evidence in profile.evidence:
                add(evidence)

        for sample in representative_messages:
            if (
                sample.message_uid in seen
                or len(selected) >= self.config.max_reference_messages
            ):
                continue
            selected.append(
                AnalysisEvidenceItem(
                    message_uid=sample.message_uid,
                    timestamp_iso=sample.timestamp_iso,
                    sender_id=sample.sender_id,
                    sender_name=sample.sender_name,
                    content=sample.content,
                    reason="representative_sample",
                    tags=sample.tags,
                )
            )
            seen.add(sample.message_uid)

        return selected

    def _special_content_types(
        self, messages: list[AnalysisMessageRecord]
    ) -> dict[str, int]:
        counts = {
            "image_messages": sum(
                1 for item in messages if item.features.image_count > 0
            ),
            "file_messages": sum(
                1 for item in messages if item.features.file_count > 0
            ),
            "emoji_messages": sum(
                1 for item in messages if item.features.emoji_count > 0
            ),
            "reply_messages": sum(1 for item in messages if item.features.has_reply),
            "forward_messages": sum(
                1 for item in messages if item.features.has_forward
            ),
            "nested_forward_messages": sum(
                1 for item in messages if item.features.forward_depth >= 2
            ),
            "low_information_messages": sum(
                1 for item in messages if item.features.low_information
            ),
            "repetitive_noise_messages": sum(
                1 for item in messages if item.features.repeated_noise
            ),
            "missing_media_messages": sum(
                1 for item in messages if item.features.missing_media_count > 0
            ),
            "unsupported_markers": sum(
                item.features.unsupported_count for item in messages
            ),
        }
        counts["share_like_messages"] = sum(
            1
            for item in messages
            if _contains_keyword_marker(
                item.extra.get("source_payload", item.extra), ("share", "ark")
            )
        )
        counts["system_like_messages"] = sum(
            1
            for item in messages
            if _contains_keyword_marker(
                item.extra.get("source_payload", item.extra),
                ("system", "graytip", "tip"),
            )
        )
        return counts

    def _retrieval_snippets(self, materials: AnalysisMaterials) -> list[str]:
        if not self.config.include_retrieval_snippets:
            return []
        snippets: list[str] = []
        for event in materials.candidate_events[: self.config.max_retrieval_snippets]:
            snippets.append(
                f"{event.start_timestamp_iso} -> {event.end_timestamp_iso} | "
                f"{event.message_count} msgs | {event.summary}"
            )
        return snippets[: self.config.max_retrieval_snippets]

    def _pack_summary(self, materials: AnalysisMaterials) -> str:
        top_tags = (
            ", ".join(
                f"{item.tag}:{item.count}" for item in materials.tag_summaries[:5]
            )
            or "none"
        )
        top_people = (
            ", ".join(
                f"{item.sender_id}:{item.message_count}"
                for item in materials.participant_profiles[:3]
            )
            or "none"
        )
        return (
            f"Target={materials.target.display_name or materials.target.display_id}; "
            f"Window={materials.chosen_time_window.start_timestamp_iso} -> "
            f"{materials.chosen_time_window.end_timestamp_iso}; "
            f"Messages={materials.stats.message_count}; "
            f"Senders={materials.stats.sender_count}; "
            f"TopTags={top_tags}; "
            f"TopPeople={top_people}"
        )

    def _media_coverage(
        self, messages: list[AnalysisMessageRecord]
    ) -> MediaCoverageSummary:
        total_image = 0
        total_file = 0
        total_sticker = 0
        total_video = 0
        total_speech = 0
        missing_image = 0
        missing_file = 0
        missing_sticker = 0
        missing_video = 0
        missing_speech = 0

        for message in messages:
            for asset in message.assets:
                asset_type = asset.get("asset_type") or asset.get("type") or ""
                is_missing = asset.get("materialized", True) is False

                if asset_type == "image":
                    total_image += 1
                    if is_missing:
                        missing_image += 1
                elif asset_type == "file":
                    total_file += 1
                    if is_missing:
                        missing_file += 1
                elif asset_type == "sticker":
                    total_sticker += 1
                    if is_missing:
                        missing_sticker += 1
                elif asset_type == "video":
                    total_video += 1
                    if is_missing:
                        missing_video += 1
                elif asset_type == "speech":
                    total_speech += 1
                    if is_missing:
                        missing_speech += 1

        def _ratio(missing: int, total: int) -> float:
            return missing / total if total > 0 else 0.0

        total_media = (
            total_image + total_file + total_sticker + total_video + total_speech
        )
        total_missing = (
            missing_image
            + missing_file
            + missing_sticker
            + missing_video
            + missing_speech
        )

        return MediaCoverageSummary(
            total_image_references=total_image,
            total_file_references=total_file,
            total_sticker_references=total_sticker,
            total_video_references=total_video,
            total_speech_references=total_speech,
            missing_image_count=missing_image,
            missing_file_count=missing_file,
            missing_sticker_count=missing_sticker,
            missing_video_count=missing_video,
            missing_speech_count=missing_speech,
            image_missing_ratio=_ratio(missing_image, total_image),
            file_missing_ratio=_ratio(missing_file, total_file),
            sticker_missing_ratio=_ratio(missing_sticker, total_sticker),
            video_missing_ratio=_ratio(missing_video, total_video),
            speech_missing_ratio=_ratio(missing_speech, total_speech),
            overall_media_missing_ratio=_ratio(total_missing, total_media),
            media_availability_flags={
                "has_image": total_image > 0,
                "has_file": total_file > 0,
                "has_sticker": total_sticker > 0,
                "has_video": total_video > 0,
                "has_speech": total_speech > 0,
                "all_media_available": total_missing == 0 if total_media > 0 else True,
                "has_missing_media": total_missing > 0,
            },
        )

    def _media_inference_scaffold(
        self,
        messages: list[AnalysisMessageRecord],
        media_coverage: MediaCoverageSummary,
    ) -> MediaInferenceScaffold:
        observed: list[MediaEvidenceScaffoldItem] = []
        missing: list[MediaEvidenceScaffoldItem] = []
        future_reference_pool: list[str] = []
        observed_image_indexes: list[int] = []
        missing_image_targets: list[tuple[int, AnalysisMessageRecord]] = []
        seen_observed_image_messages: set[str] = set()
        seen_missing_image_messages: set[str] = set()

        for index, message in enumerate(messages):
            context_excerpt = preview_text(message.content.replace("\n", " / "), 120)
            for asset in message.assets:
                asset_type = asset.get("asset_type") or asset.get("type") or "unknown"
                is_missing = (
                    asset.get(
                        "materialized", asset.get("extra", {}).get("materialized", True)
                    )
                    is False
                )
                item = MediaEvidenceScaffoldItem(
                    asset_type=asset_type,
                    state="missing" if is_missing else "observed",
                    confidence_label="unknown" if is_missing else "direct",
                    confidence_score=0.0 if is_missing else 1.0,
                    source_message_uid=message.message_uid,
                    source_timestamp_iso=message.timestamp_iso,
                    source_sender_id=message.sender_id,
                    context_excerpt=context_excerpt,
                    support_message_uids=[message.message_uid],
                    notes=[
                        "missing_asset_reference"
                        if is_missing
                        else "direct_asset_reference"
                    ],
                )
                if is_missing:
                    missing.append(item)
                    if (
                        asset_type == "image"
                        and message.message_uid not in seen_missing_image_messages
                    ):
                        missing_image_targets.append((index, message))
                        seen_missing_image_messages.add(message.message_uid)
                else:
                    observed.append(item)
                    future_reference_pool.append(message.message_uid)
                    if (
                        asset_type == "image"
                        and message.message_uid not in seen_observed_image_messages
                    ):
                        observed_image_indexes.append(index)
                        seen_observed_image_messages.add(message.message_uid)

        inferred, unknown = self._text_gap_inference(
            messages=messages,
            observed_image_indexes=observed_image_indexes,
            missing_image_targets=missing_image_targets,
        )

        def _append_placeholder_missing(asset_type: str, count: int) -> None:
            for _ in range(
                max(
                    0,
                    count - sum(1 for item in missing if item.asset_type == asset_type),
                )
            ):
                missing.append(
                    MediaEvidenceScaffoldItem(
                        asset_type=asset_type,
                        state="missing",
                        confidence_label="unknown",
                        confidence_score=0.0,
                        notes=[
                            "aggregate_missing_reference_without_local_asset_payload"
                        ],
                    )
                )

        _append_placeholder_missing("image", media_coverage.missing_image_count)
        _append_placeholder_missing("file", media_coverage.missing_file_count)
        _append_placeholder_missing("sticker", media_coverage.missing_sticker_count)
        _append_placeholder_missing("video", media_coverage.missing_video_count)
        _append_placeholder_missing("speech", media_coverage.missing_speech_count)

        return MediaInferenceScaffold(
            observed=observed,
            missing=missing,
            inferred=inferred,
            unknown=unknown,
            future_reference_pool_message_uids=list(
                dict.fromkeys(future_reference_pool)
            ),
        )

    def _text_gap_inference(
        self,
        *,
        messages: list[AnalysisMessageRecord],
        observed_image_indexes: list[int],
        missing_image_targets: list[tuple[int, AnalysisMessageRecord]],
    ) -> tuple[list[MediaEvidenceScaffoldItem], list[MediaEvidenceScaffoldItem]]:
        if not self.config.enable_text_gap_inference or not missing_image_targets:
            return [], []

        reference_patterns = self._build_observed_image_reference_patterns(
            messages,
            observed_image_indexes,
        )
        inferred: list[MediaEvidenceScaffoldItem] = []
        unknown: list[MediaEvidenceScaffoldItem] = []

        for index, message in missing_image_targets[
            : self.config.max_text_gap_hypotheses
        ]:
            signature = self._text_gap_context_signature(messages, index)
            hypothesis_kind, confidence_score, reference_message_uids = (
                self._classify_missing_image_signature(signature, reference_patterns)
            )
            if hypothesis_kind is None:
                unknown.append(
                    MediaEvidenceScaffoldItem(
                        asset_type="image",
                        state="unknown",
                        confidence_label="unknown",
                        confidence_score=confidence_score,
                        confidence_band=(
                            _confidence_band(confidence_score)
                            if confidence_score > 0
                            else None
                        ),
                        source_message_uid=message.message_uid,
                        source_timestamp_iso=message.timestamp_iso,
                        source_sender_id=message.sender_id,
                        context_excerpt=signature["context_excerpt"],
                        hypothesis_text=(
                            "仅能确认这里引用了缺失图片，但当前文本上下文不足以做稳妥推断。"
                        ),
                        support_message_uids=signature["support_message_uids"],
                        reference_message_uids=reference_message_uids,
                        support_signals=signature["support_signals"],
                        contradiction_signals=signature["contradiction_signals"],
                        notes=[
                            "text_only_context_inference_v1",
                            "insufficient_text_context",
                        ],
                    )
                )
                continue

            inferred.append(
                MediaEvidenceScaffoldItem(
                    asset_type="image",
                    state="inferred",
                    confidence_label="context_only",
                    confidence_score=confidence_score,
                    confidence_band=_confidence_band(confidence_score),
                    source_message_uid=message.message_uid,
                    source_timestamp_iso=message.timestamp_iso,
                    source_sender_id=message.sender_id,
                    context_excerpt=signature["context_excerpt"],
                    hypothesis_kind=hypothesis_kind,
                    hypothesis_text=self._hypothesis_text(
                        hypothesis_kind,
                        signature["support_signals"],
                    ),
                    support_message_uids=signature["support_message_uids"],
                    reference_message_uids=reference_message_uids,
                    support_signals=signature["support_signals"],
                    contradiction_signals=signature["contradiction_signals"],
                    notes=[
                        "text_only_context_inference_v1",
                        "secondary_to_direct_evidence",
                    ],
                )
            )

        return inferred, unknown

    def _build_observed_image_reference_patterns(
        self,
        messages: list[AnalysisMessageRecord],
        observed_image_indexes: list[int],
    ) -> list[_TextGapReferencePattern]:
        patterns: list[_TextGapReferencePattern] = []
        for index in observed_image_indexes:
            signature = self._text_gap_context_signature(messages, index)
            hypothesis_kind, confidence_score, _ = (
                self._classify_missing_image_signature(
                    signature,
                    (),
                )
            )
            if hypothesis_kind is None:
                continue
            patterns.append(
                _TextGapReferencePattern(
                    message_uid=messages[index].message_uid,
                    hypothesis_kind=hypothesis_kind,
                    confidence_score=confidence_score,
                    support_signals=tuple(signature["support_signals"]),
                )
            )
        patterns.sort(key=lambda item: item.confidence_score, reverse=True)
        return patterns[: self.config.max_text_gap_hypotheses]

    def _text_gap_context_signature(
        self,
        messages: list[AnalysisMessageRecord],
        index: int,
    ) -> dict[str, Any]:
        start = max(0, index - self.config.text_gap_context_radius)
        end = min(len(messages), index + self.config.text_gap_context_radius + 1)
        window = messages[start:end]
        current = messages[index]
        support_signals: set[str] = set()
        contradiction_signals: set[str] = set()
        support_message_uids: list[str] = []
        context_parts: list[str] = []

        for item in window:
            text = _analysis_text(item)
            if text:
                support_message_uids.append(item.message_uid)
                context_parts.append(f"{item.sender_id}:{text}")
            if _contains_any_term(text, BENSHI_TEXT_TERMS):
                support_signals.add("benshi_lexicon")
            if _contains_any_term(text, VISUAL_REFERENCE_TERMS):
                support_signals.add("visual_reference")
            if _contains_any_term(text, SCREENSHOT_TEXT_TERMS):
                support_signals.add("screenshot_marker")
            if _contains_any_term(text, REACTION_TEXT_TERMS):
                support_signals.add("reaction_context")
            if _contains_any_term(text, UNCERTAINTY_TEXT_TERMS):
                contradiction_signals.add("context_unclear")
            if item.features.has_forward:
                support_signals.add("forward_structure")
            if item.features.has_reply:
                support_signals.add("reply_chain")
            if item.features.repeated_noise:
                contradiction_signals.add("repetitive_noise_window")

        current_text = _analysis_text(current)
        if len(current_text.strip()) <= 4:
            support_signals.add("short_caption")
        if current.features.low_information:
            support_signals.add("low_information_caption")
        if not current_text.strip():
            contradiction_signals.add("no_text_caption")
        if len(support_message_uids) <= 1:
            contradiction_signals.add("sparse_context")

        return {
            "current_text": current_text,
            "context_excerpt": preview_text(" | ".join(context_parts), 180),
            "support_message_uids": support_message_uids[:6],
            "support_signals": sorted(support_signals),
            "contradiction_signals": sorted(contradiction_signals),
        }

    def _classify_missing_image_signature(
        self,
        signature: dict[str, Any],
        reference_patterns: tuple[_TextGapReferencePattern, ...]
        | list[_TextGapReferencePattern],
    ) -> tuple[str | None, float, list[str]]:
        support_signals = set(signature["support_signals"])
        contradiction_signals = set(signature["contradiction_signals"])
        kind_scores: dict[str, float] = {}

        if "benshi_lexicon" in support_signals:
            score = 0.56
            if "screenshot_marker" in support_signals:
                score += 0.12
            if "visual_reference" in support_signals:
                score += 0.08
            if "forward_structure" in support_signals:
                score += 0.08
            if "reply_chain" in support_signals:
                score += 0.05
            kind_scores["benshi_candidate"] = score

        if "reaction_context" in support_signals:
            score = 0.44
            if (
                "short_caption" in support_signals
                or "low_information_caption" in support_signals
            ):
                score += 0.10
            if "visual_reference" in support_signals:
                score += 0.04
            kind_scores["reaction_meme"] = max(
                kind_scores.get("reaction_meme", 0.0),
                score,
            )

        if support_signals.intersection(
            {"visual_reference", "screenshot_marker", "reply_chain"}
        ):
            score = 0.38
            if "screenshot_marker" in support_signals:
                score += 0.12
            if "reply_chain" in support_signals:
                score += 0.08
            if "forward_structure" in support_signals:
                score += 0.05
            kind_scores["context_supporting_image"] = max(
                kind_scores.get("context_supporting_image", 0.0),
                score,
            )

        if not kind_scores:
            return None, 0.0, []

        hypothesis_kind = max(kind_scores, key=kind_scores.get)
        reference_message_uids = self._matching_reference_patterns(
            hypothesis_kind,
            support_signals,
            reference_patterns,
        )
        confidence_score = kind_scores[hypothesis_kind] + min(
            0.08,
            0.03 * len(reference_message_uids),
        )
        if "context_unclear" in contradiction_signals:
            confidence_score -= 0.18
        if "sparse_context" in contradiction_signals:
            confidence_score -= 0.12
        if "no_text_caption" in contradiction_signals:
            confidence_score -= 0.08
        if (
            "repetitive_noise_window" in contradiction_signals
            and hypothesis_kind != "reaction_meme"
        ):
            confidence_score -= 0.05
        confidence_score = _clamp_score(confidence_score)
        if confidence_score < 0.48:
            return None, confidence_score, reference_message_uids
        return hypothesis_kind, confidence_score, reference_message_uids

    def _matching_reference_patterns(
        self,
        hypothesis_kind: str,
        support_signals: set[str],
        reference_patterns: tuple[_TextGapReferencePattern, ...]
        | list[_TextGapReferencePattern],
    ) -> list[str]:
        scored: list[tuple[int, float, str]] = []
        for item in reference_patterns:
            if item.hypothesis_kind != hypothesis_kind:
                continue
            overlap = len(support_signals.intersection(item.support_signals))
            if overlap <= 0:
                continue
            scored.append((overlap, item.confidence_score, item.message_uid))
        scored.sort(reverse=True)
        return [message_uid for _, _, message_uid in scored[:2]]

    def _hypothesis_text(
        self,
        hypothesis_kind: str,
        support_signals: list[str],
    ) -> str:
        if hypothesis_kind == "benshi_candidate":
            if "screenshot_marker" in support_signals:
                return (
                    "文本上下文更像在围绕一条截图/聊天记录式材料展开，这张缺失图片可能承担了"
                    "搬shi语境里的主要触发物或证据载体作用。"
                )
            return (
                "文本上下文更像在围绕一条可被评价、转发或玩梗的图像材料展开，"
                "这张缺失图片可能承担了搬shi链路里的主要触发物作用。"
            )
        if hypothesis_kind == "reaction_meme":
            return "上下文更像在用图片承接短促反应、调侃或玩梗，缺失图片更可能是反应图/梗图式载体。"
        return "当前只能从文本上下文确认这里有一张配合讨论的图片，但不足以进一步判断其更细语义。"


class WholeWindowLlmAnalyzer:
    def __init__(
        self,
        *,
        client: WindowReportClient,
        config: LlmAnalysisJobConfig | None = None,
    ) -> None:
        self.client = client
        self.config = config or LlmAnalysisJobConfig()
        self.pack_builder = WholeWindowPackBuilder(self.config)

    def prepare(self, materials: AnalysisMaterials) -> WindowReportPlan:
        pack = self.pack_builder.build(materials)
        return self.build_plan_from_pack(pack)

    def build_plan_from_pack(self, pack: AnalysisPack) -> WindowReportPlan:
        system_prompt = self._system_prompt()
        user_prompt = self._user_prompt(pack)
        estimated_input_tokens = _estimate_text_tokens(
            system_prompt
        ) + _estimate_text_tokens(user_prompt)
        return WindowReportPlan(
            pack=pack,
            prompt_version=self.config.prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            estimated_input_tokens=estimated_input_tokens,
            max_output_tokens=self.config.max_output_tokens,
        )

    def analyze(
        self,
        plan: WindowReportPlan,
        *,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmAnalysisResult:
        kwargs = {
            "system_prompt": plan.system_prompt,
            "user_prompt": plan.user_prompt,
            "max_output_tokens": plan.max_output_tokens,
        }
        if stream_callback is not None:
            kwargs["stream_callback"] = stream_callback
        bundle = self.client.analyze_text(**kwargs)
        usage = LlmUsageRecord(
            prompt_tokens=bundle.usage.prompt_tokens,
            completion_tokens=bundle.usage.completion_tokens,
            total_tokens=bundle.usage.total_tokens,
            reasoning_tokens=bundle.usage.reasoning_tokens,
            cached_tokens=bundle.usage.cached_tokens,
        )
        warnings = list(plan.pack.warnings)
        if not bundle.raw_text:
            warnings.append("LLM returned an empty report body.")
        return LlmAnalysisResult(
            pack=plan.pack,
            prompt_version=plan.prompt_version,
            provider_name=_provider_name_from_client(self.client),
            model_name=_model_name_from_client(self.client),
            report_body=bundle.raw_text.strip(),
            usage=usage,
            warnings=warnings,
        )

    def _system_prompt(self) -> str:
        if self.config.prompt_version == "benshi_window_v2":
            return (
                "你是QQ群/好友聊天记录的文本优先分析员，正在为 Benshi 工作流生成第二轮报告。\n"
                "输入是已经压缩好的 analysis pack，不是完整聊天全文。\n"
                "你的任务仍然不是给出最终低层 taxonomy，而是输出一份可复核的长报告，并额外收敛出稳定的软维度与软角色。\n"
                "请先区分：直接观察到的证据、由上下文支持的弱推测、以及必须保持 unknown 的部分。\n"
                "当前如果提供缺失媒体推断，它们也只是 text-only context inference，不代表已经看到了图片本体。\n"
                "只有在 Missing Media Text-Only Inference 小节里明确列出的 inferred hypothesis，才允许被当成上下文弱推测引用。\n"
                "如果 InferredItems 为 0，则你不得自行补做缺失媒体语义推断；这类内容必须保持 unknown。\n"
                "如果 InferredItems 为 0，你也不得把话题跳跃、事件触发、用户动机归因到某张缺失图片；最多只能说时间邻近，但触发原因未知。\n"
                "不要把缺失图片/视频当成已经看过，不要伪造 OCR、图像内容或动机。\n"
                "本轮报告必须包含两个新增块：\n"
                "1. Stable Dimension Block：对稳定维度逐项给出 soft label、1句解释、证据等级。\n"
                "2. Soft Participant Roles：只在证据足够时给角色；证据不足就写 unclear。\n"
                "这些 soft labels 只是收敛中的中间层，不是最终 Benshi taxonomy。\n"
                "输出为 Markdown 长报告，建议包含：总体概览、Stable Dimension Block、Soft Participant Roles、关键线索与证据、媒体完整性与 unknown、后续细化方向。"
            )
        if self.config.prompt_version == "benshi_window_v1":
            return (
                "你是QQ群/好友聊天记录的文本优先分析员，正在为 Benshi 工作流生成报告优先的观察结果。\n"
                "输入是已经筛选和压缩好的 analysis pack，不是完整聊天全文。\n"
                "你的目标是基于文本、回复关系、转发结构、分享/系统提示、媒体缺失情况，输出高层、诚实、可复核的 Markdown 报告。\n"
                "请明确区分：直接观察到的证据、由上下文支持的弱推测、以及因为媒体缺失而无法确定的部分。\n"
                "当前如果提供缺失媒体推断，它们也只是 text-only context inference，不代表已经看到了图片本体。\n"
                "只有在 Missing Media Text-Only Inference 小节里明确列出的 inferred hypothesis，才允许被当成上下文弱推测引用。\n"
                "如果 InferredItems 为 0，则你不得自行补做缺失媒体语义推断；这类内容必须保持 unknown。\n"
                "如果 InferredItems 为 0，你也不得把话题跳跃、事件触发、用户动机归因到某张缺失图片；最多只能说时间邻近，但触发原因未知。\n"
                "不要把缺失图片/视频当成已经看过，不要伪造 OCR、图像内容或动机。\n"
                "优先回答：\n"
                "1. 这一时间窗内最值得注意的文本/上下文模式；\n"
                "2. 哪些异常或 Benshi 线索有明确证据支持；\n"
                "3. 哪些判断受媒体缺失或上下文不足限制；\n"
                "4. 后续最值得继续细化的候选方向。\n"
                "输出为 Markdown 长报告，建议包含：总体概览、关键线索、证据与反证、媒体完整性与不确定性、后续细化方向。"
            )
        return (
            "你是QQ群/好友聊天记录的上层内容分析员。\n"
            "你的当前任务不是做细粒度搬shi定罪，而是先输出一份高层、抽象、开放式的长报告。\n"
            "输入是已经筛选和压缩好的 analysis pack，不是完整聊天全文。\n"
            "请重点分析：\n"
            "1. 这段时间窗里主要都在聊什么；\n"
            "2. 整体互动氛围是什么样；\n"
            "3. 有哪些异常、怪异、低信息、套娃转发、图文主导、情绪或抽象内容模式；\n"
            "4. 哪些维度值得后续进一步细化成更具体的标签或子分析器；\n"
            "5. 哪些结论目前仍然只是观察，不应被当成最终定性。\n"
            "不要做强动机推断，不要把当前报告写成最终裁决。\n"
            "输出为 Markdown 长报告，建议包含：总体概览、主要主题、互动氛围、异常/特殊内容、候选细化方向、不确定性。"
        )

    def _user_prompt(self, pack: AnalysisPack) -> str:
        lines = [
            "# Analysis Pack",
            f"- Target: {pack.target.display_name or pack.target.display_id}",
            f"- TimeWindow: {pack.chosen_time_window.start_timestamp_iso} -> {pack.chosen_time_window.end_timestamp_iso}",
            f"- Rationale: {pack.chosen_time_window.rationale}",
            f"- PackSummary: {pack.pack_summary}",
            "",
            "## Basic Stats",
            f"- Messages: {pack.stats.message_count}",
            f"- Senders: {pack.stats.sender_count}",
            f"- ImageRatio: {pack.stats.image_ratio:.2%}",
            f"- ForwardRatio: {pack.stats.forward_ratio:.2%}",
            f"- ReplyRatio: {pack.stats.reply_ratio:.2%}",
            f"- EmojiRatio: {pack.stats.emoji_ratio:.2%}",
            f"- LowInformationRatio: {pack.stats.low_information_ratio:.2%}",
            "",
            "## Stable Review Dimensions",
        ]
        for name, desc in STABLE_DIMENSION_GUIDE:
            lines.append(f"- {name}: {desc}")

        lines.extend(
            [
                "",
                "## Allowed Soft Participant Roles",
            ]
        )
        for name, desc in SOFT_ROLE_GUIDE:
            lines.append(f"- {name}: {desc}")

        lines.extend(
            [
                "",
                "## Media Coverage",
                f"- OverallMissingRatio: {pack.media_coverage.overall_media_missing_ratio:.2%}",
                f"- ImageMissingRatio: {pack.media_coverage.image_missing_ratio:.2%}",
                f"- FileMissingRatio: {pack.media_coverage.file_missing_ratio:.2%}",
                f"- StickerMissingRatio: {pack.media_coverage.sticker_missing_ratio:.2%}",
                f"- VideoMissingRatio: {pack.media_coverage.video_missing_ratio:.2%}",
                f"- SpeechMissingRatio: {pack.media_coverage.speech_missing_ratio:.2%}",
                f"- AvailabilityFlags: {json.dumps(pack.media_coverage.media_availability_flags, ensure_ascii=False)}",
                "",
                "## Missing Media Text-Only Inference",
                "- InferenceMode: text_only_context_v1",
                f"- InferredItems: {len(pack.media_inference_scaffold.inferred)}",
                f"- UnknownItems: {len(pack.media_inference_scaffold.unknown)}",
                "- Rule: hypotheses below are context-only and must not be treated as observed image content.",
            ]
        )
        if pack.media_inference_scaffold.inferred:
            for item in pack.media_inference_scaffold.inferred[
                : self.config.max_text_gap_hypotheses
            ]:
                lines.append(
                    f"- {item.source_timestamp_iso or 'unknown'} | {item.source_sender_id or 'unknown'} | "
                    f"kind={item.hypothesis_kind or 'unknown'} | conf={item.confidence_score:.2f} | "
                    f"support={','.join(item.support_signals) or 'none'} | {item.hypothesis_text or ''}"
                )
        else:
            lines.append("- inferred: none")
            lines.append(
                "- Rule: no approved context-only missing-media hypotheses were produced for this pack; "
                "missing-media semantics must stay unknown unless directly visible in text."
            )
            lines.append(
                "- Rule: with InferredItems=0, do not attribute topic jumps, event triggers, or user intent to any missing image/video; causal links remain unknown unless explicit in text."
            )

        if pack.media_inference_scaffold.unknown:
            lines.append("- unresolved_samples:")
            for item in pack.media_inference_scaffold.unknown[
                : min(4, self.config.max_text_gap_hypotheses)
            ]:
                lines.append(
                    f"  - {item.source_timestamp_iso or 'unknown'} | {item.source_sender_id or 'unknown'} | "
                    f"support={','.join(item.support_signals) or 'none'} | "
                    f"contradictions={','.join(item.contradiction_signals) or 'none'}"
                )

        lines.extend(["", "## Image Caption Evidence"])
        if pack.image_caption_samples:
            lines.append(
                "- Rule: captions below come from direct multimodal model inspection of available exported image files, not from text-only guessing."
            )
            for item in pack.image_caption_samples:
                lines.append(
                    f"- {item.timestamp_iso} | {item.sender_id} | file={item.file_name or 'unknown'} | "
                    f"ctx={item.context_excerpt or '<none>'} | caption={item.caption}"
                )
        else:
            lines.append("- none")

        lines.extend(
            [
                "",
                "## Special Content Types",
            ]
        )
        for key, value in pack.special_content_types.items():
            lines.append(f"- {key}: {value}")

        lines.extend(["", "## Top Tags"])
        if pack.tag_summaries:
            for item in pack.tag_summaries:
                lines.append(f"- {item.tag}: {item.count} ({item.rate:.2%})")
        else:
            lines.append("- none")

        lines.extend(["", "## Candidate Events"])
        if pack.candidate_events:
            for item in pack.candidate_events:
                lines.append(
                    f"- {item.start_timestamp_iso} -> {item.end_timestamp_iso} | "
                    f"{item.message_count} msgs | {item.participant_count} senders | "
                    f"tags={','.join(item.dominant_tags) or 'none'} | {item.summary}"
                )
        else:
            lines.append("- none")

        lines.extend(["", "## Key People"])
        if pack.participant_profiles:
            for item in pack.participant_profiles:
                lines.append(
                    f"- {item.sender_id} ({item.sender_name or 'unknown'}): "
                    f"{item.message_count} msgs | tags={','.join(item.tag_counts.keys()) or 'none'}"
                )
        else:
            lines.append("- none")

        lines.extend(["", "## Representative Messages"])
        for item in pack.representative_messages:
            lines.append(
                f"- {item.timestamp_iso} | {item.sender_id} | "
                f"tags={','.join(item.tags) or 'none'} | {item.content}"
            )

        if pack.retrieval_snippets:
            lines.extend(["", "## Retrieval Snippets"])
            for item in pack.retrieval_snippets:
                lines.append(f"- {item}")

        lines.extend(["", "## Message Reference Pool"])
        for item in pack.message_reference_pool:
            lines.append(
                f"- {item.timestamp_iso} | {item.sender_id} | {item.reason} | {item.content}"
            )

        lines.append("")
        if self.config.prompt_version == "benshi_window_v2":
            lines.extend(
                [
                    "请基于以上 analysis pack 输出一份 Benshi v2 长报告。",
                    "报告中必须包含 `Stable Dimension Block`，并逐项覆盖：interaction_density, information_density, content_provenance, narrative_coherence, media_dependence, uncertainty_load, topic_type, followup_value。",
                    "每个维度都要给出：soft label、1句解释、evidence_tier（direct/context_only/unknown）。",
                    "报告中必须包含 `Soft Participant Roles`，只允许使用给定的 soft role labels；若证据不足请写 `unclear`，不要硬贴标签。",
                    "如果存在 `Image Caption Evidence`，可将其视为直接可见媒体证据的一部分，但要与纯文本证据一起交叉核对。",
                    "明确指出哪些线索来自文本/回复/转发/分享/系统提示，哪些部分受到媒体缺失限制。",
                    "如果引用了 Missing Media Text-Only Inference，请明确标注它只是上下文推断，不是图像事实。",
                    "如果 InferredItems=0 或该小节没有列出某条假设，你不得自行补做缺失媒体语义推断，只能写 unknown/不确定。",
                    "如果 InferredItems=0，你不得写出'由缺失图片触发'、'几乎肯定是某张缺图引发'、'图片说明了动机'这类因果判断；只能写时间相邻或原因未知。",
                    "soft roles 和 stable dimensions 都是中间层，不是最终 Benshi taxonomy。",
                    "输出重点是帮助人类决定下一步该继续看哪些维度，并为后续 schema 收敛提供稳定候选。",
                ]
            )
        elif self.config.prompt_version == "benshi_window_v1":
            lines.extend(
                [
                    "请基于以上 analysis pack 输出一份 Benshi 报告优先的长报告。",
                    "如果存在 `Image Caption Evidence`，可将其视为直接可见媒体证据的一部分，但要与文本上下文交叉核对。",
                    "明确指出哪些线索来自文本/回复/转发/分享/系统提示，哪些部分受到媒体缺失限制。",
                    "如果引用了 Missing Media Text-Only Inference，请明确标注它只是上下文推断，不是图像事实。",
                    "如果 InferredItems=0 或该小节没有列出某条假设，你不得自行补做缺失媒体语义推断，只能写 unknown/不确定。",
                    "如果 InferredItems=0，你不得写出'由缺失图片触发'、'几乎肯定是某张缺图引发'、'图片说明了动机'这类因果判断；只能写时间相邻或原因未知。",
                    "如果媒体缺失影响判断，请直接写出不确定性，不要伪造图像或视频内容。",
                    "输出重点是帮助人类决定下一步该继续看哪些维度，而不是直接给出最终裁决。",
                ]
            )
        else:
            lines.extend(
                [
                    "请基于以上 analysis pack 输出一份高层长报告。",
                    "重点是帮助人类观察这段时间窗里最值得后续继续结构化的方向，而不是直接给出最终搬shi裁决。",
                ]
            )
        return "\n".join(lines)


def save_llm_analysis_result(
    *,
    result: LlmAnalysisResult,
    plan: WindowReportPlan,
    out_dir: Path,
    prefix: str,
) -> LlmAnalysisResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    analysis_pack_path = out_dir / f"{prefix}.analysis_pack.json"
    llm_run_meta_path = out_dir / f"{prefix}.llm_run_meta.json"
    report_path = out_dir / f"{prefix}.report.md"
    usage_path = out_dir / f"{prefix}.usage.json"
    prompt_path = out_dir / f"{prefix}.prompt.txt"

    analysis_pack_path.write_text(
        json.dumps(result.pack.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    llm_run_meta_path.write_text(
        json.dumps(
            {
                "prompt_version": result.prompt_version,
                "provider_name": result.provider_name,
                "model_name": result.model_name,
                "warnings": result.warnings,
                "estimated_input_tokens": plan.estimated_input_tokens,
                "max_output_tokens": plan.max_output_tokens,
                "target": result.pack.target.model_dump(mode="json"),
                "chosen_time_window": result.pack.chosen_time_window.model_dump(
                    mode="json"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path.write_text(result.report_body, encoding="utf-8")
    usage_path.write_text(
        json.dumps(result.usage.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    prompt_path.write_text(
        "\n\n--- USER PROMPT ---\n\n".join([plan.system_prompt, plan.user_prompt]),
        encoding="utf-8",
    )

    result.artifacts = LlmRunArtifactSet(
        analysis_pack_path=str(analysis_pack_path),
        llm_run_meta_path=str(llm_run_meta_path),
        report_path=str(report_path),
        usage_path=str(usage_path),
        prompt_path=str(prompt_path),
    )
    return result


def load_saved_analysis_pack(path: Path) -> AnalysisPack:
    return AnalysisPack.model_validate_json(path.read_text(encoding="utf-8"))


def load_text_analysis_client(
    config_path: Path,
    *,
    model: str | None = None,
) -> WindowReportClient:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    provider = str(raw.get("provider", "")).strip().lower()
    if provider == "openai_compatible" or (
        not provider and "openai_compatible" in raw and "deepseek" not in raw
    ):
        runtime = load_openai_compatible_runtime_config(config_path)
        if model:
            runtime.model = model
        return OpenAICompatibleAnalysisClient(runtime)
    runtime = load_deepseek_runtime_config(config_path)
    if model:
        runtime.model = model
    return DeepSeekAnalysisClient(runtime)


def _analysis_text(message: AnalysisMessageRecord) -> str:
    text = (message.text_content or "").strip()
    if text:
        return text
    content = STRUCTURED_TOKEN_RE.sub(" ", message.content or "")
    return " ".join(content.split())


def _contains_any_term(text: str, terms: tuple[str, ...]) -> bool:
    if not text:
        return False
    return any(term in text for term in terms)


def _confidence_band(score: float) -> str:
    if score >= 0.74:
        return "high"
    if score >= 0.58:
        return "medium"
    return "low"


def _clamp_score(score: float) -> float:
    return max(0.0, min(0.95, round(score, 3)))


def _provider_name_from_client(client: Any) -> str:
    if isinstance(client, DeepSeekAnalysisClient):
        return "deepseek"
    if isinstance(client, OpenAICompatibleAnalysisClient):
        return "openai_compatible"
    return getattr(client, "provider_name", "unknown")


def _model_name_from_client(client: Any) -> str:
    if isinstance(client, DeepSeekAnalysisClient):
        return client.config.model
    return getattr(client, "model_name", "unknown")


def _estimate_text_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _contains_keyword_marker(value: Any, keywords: tuple[str, ...]) -> bool:
    lowered = tuple(item.lower() for item in keywords)
    if isinstance(value, dict):
        for key, item in value.items():
            if any(word in str(key).lower() for word in lowered):
                return True
            if _contains_keyword_marker(item, keywords):
                return True
        value_type = str(value.get("type", "")).lower()
        return any(word in value_type for word in lowered)
    if isinstance(value, list):
        return any(_contains_keyword_marker(item, keywords) for item in value)
    if isinstance(value, str):
        text = value.lower()
        return any(word in text for word in lowered)
    return False
