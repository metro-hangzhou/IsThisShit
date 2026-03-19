from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from qq_data_process.utils import preview_text, stable_digest

from .benshi_seed_artifacts import load_distribution_baseline_summary
from .models import (
    AnalysisMaterials,
    AnalysisMessageRecord,
    BenshiAnalysisPack,
    BenshiAssetAggregateSummary,
    BenshiAssetSummary,
    BenshiDistributionBaselineSummary,
    BenshiExpiredInferenceAggregateSummary,
    BenshiExpiredInferenceSummaryItem,
    BenshiForwardAggregateSummary,
    BenshiForwardDegradedAssetHint,
    BenshiForwardSummary,
    BenshiMissingMediaGap,
    BenshiOntologyDimension,
    BenshiOntologyPack,
    BenshiOntologyPopularForm,
    BenshiReactionAggregateSummary,
    BenshiReactionPatternSummary,
    BenshiOntologyTaxonomyItem,
    BenshiParticipantRoleCandidate,
    BenshiPreprocessOverlayItem,
    BenshiPreprocessOverlaySummary,
    BenshiRecurrenceAggregateSummary,
    BenshiRecurrenceSummary,
    BenshiSelectedMessage,
    BenshiShiComponentSummary,
    BenshiShiDescriptionProfile,
)
from .summary import build_material_input_semantics, classify_message_input_semantics

_MISSING_STATUS_HINTS = ("missing", "timeout", "failed", "expired", "unavailable")
_DEBUGISH_LABELS = {
    "runtime_debug",
    "cli_workflow",
    "dev_ops",
    "analysis_dev",
    "strict_focus_non_target",
    "low_signal_chatter",
}
_REACTION_MODE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "amused_break": (
        "绷",
        "绷不住",
        "蚌",
        "蚌埠住了",
        "笑死",
        "乐死",
        "草",
        "艹",
        "典中典",
    ),
    "mockery": (
        "小丑",
        "幽默",
        "逆天",
        "离谱",
        "抽象",
        "好似",
        "典",
        "节目效果",
        "贵物",
        "唐",
    ),
    "uniform_feedback": (
        "？？",
        "??",
        "。。。",
        "......",
        "哈哈",
        "哈哈哈",
    ),
    "meme_catch": (
        "补档",
        "返场",
        "回放",
        "库存",
        "又来了",
        "这下",
        "接上了",
        "串起来了",
        "典中典",
    ),
    "disgust": (
        "恶心",
        "臭",
        "有病",
        "病得不轻",
        "脑残",
        "nt",
        "真是屎",
        "想吐",
        "司马",
        "晦气",
    ),
    "spectator": (
        "围观",
        "这啥",
        "什么东西",
        "什么情况",
        "哪来的",
        "咋回事",
        "怎么回事",
        "谁发的",
        "这也行",
        "什么鬼",
        "真的假的",
    ),
}
_REACTION_PATTERN_LABELS: dict[str, str] = {
    "repeat_echo": "复读/回声",
    "amused_break": "绷/乐",
    "mockery": "嘲笑/阴阳",
    "uniform_feedback": "整齐反馈",
    "meme_catch": "接梗/顺嘴接",
    "disgust": "嫌弃/排斥",
    "spectator": "围观/惊诧",
}
_REACTION_SHORT_TEXT_MAX = 22
_REACTION_PUNCT_ONLY_PATTERN = re.compile(r"^[\s\?\!？！，。\.~～…、]+$")
_REACTION_SPLIT_PATTERN = re.compile(r"[:：]\s*", re.IGNORECASE)
_FORWARD_TOKEN_PATTERN = re.compile(r"\[(video|uploaded_file_name|uploaded_file|file):([^\]]+)\]")


class BenshiAnalysisPackBuilder:
    def __init__(
        self,
        *,
        max_forward_summaries: int = 24,
        max_recurrence_summaries: int = 24,
        max_missing_media_gaps: int = 32,
        max_expired_inference_items: int = 24,
        max_overlay_items: int = 24,
        distribution_baseline_path: str | Path | None = None,
    ) -> None:
        self.max_forward_summaries = max_forward_summaries
        self.max_recurrence_summaries = max_recurrence_summaries
        self.max_missing_media_gaps = max_missing_media_gaps
        self.max_expired_inference_items = max_expired_inference_items
        self.max_overlay_items = max_overlay_items
        self.distribution_baseline_path = (
            Path(distribution_baseline_path)
            if distribution_baseline_path is not None
            else None
        )

    def build(self, materials: AnalysisMaterials) -> BenshiAnalysisPack:
        return build_benshi_analysis_pack(
            materials,
            max_forward_summaries=self.max_forward_summaries,
            max_recurrence_summaries=self.max_recurrence_summaries,
            max_missing_media_gaps=self.max_missing_media_gaps,
            max_expired_inference_items=self.max_expired_inference_items,
            max_overlay_items=self.max_overlay_items,
            distribution_baseline_path=self.distribution_baseline_path,
        )


def build_benshi_analysis_pack(
    materials: AnalysisMaterials,
    *,
    max_forward_summaries: int = 24,
    max_recurrence_summaries: int = 24,
    max_missing_media_gaps: int = 32,
    max_expired_inference_items: int = 24,
    max_overlay_items: int = 24,
    distribution_baseline_path: str | Path | None = None,
) -> BenshiAnalysisPack:
    selected_messages = _build_selected_messages(materials.messages)
    overlay_summary = _build_preprocess_overlay_summary(
        materials,
        max_overlay_items=max_overlay_items,
    )
    forward_summaries = _build_forward_summaries(
        materials,
        max_items=max_forward_summaries,
    )
    recurrence_summaries = _build_recurrence_summaries(
        materials,
        max_items=max_recurrence_summaries,
    )
    participant_role_candidates = _build_participant_role_candidates(materials)
    reaction_summary, reaction_patterns = _build_reaction_summary(
        materials,
        participant_role_candidates=participant_role_candidates,
        forward_summaries=forward_summaries,
    )
    asset_summaries = _build_asset_summaries(materials)
    missing_media_gaps = _build_missing_media_gaps(
        materials,
        max_items=max_missing_media_gaps,
    )
    forward_degraded_asset_hints = _build_forward_degraded_asset_hints(
        forward_summaries,
        max_items=max_missing_media_gaps,
    )
    (
        expired_inference_summary,
        expired_inference_items,
    ) = _build_expired_inference_summary(
        materials,
        max_items=max_expired_inference_items,
    )
    forward_aggregate = _build_forward_aggregate_summary(
        materials,
        forward_summaries,
    )
    recurrence_aggregate = _build_recurrence_aggregate_summary(recurrence_summaries)
    asset_aggregate = _build_asset_aggregate_summary(asset_summaries)
    shi_component_summaries = _build_shi_component_summaries(
            materials=materials,
            selected_messages=selected_messages,
            participant_role_candidates=participant_role_candidates,
            forward_summary=forward_aggregate,
            recurrence_summary=recurrence_aggregate,
            asset_summary=asset_aggregate,
            missing_media_gaps=missing_media_gaps,
            reaction_summary=reaction_summary,
            forward_degraded_asset_hints=forward_degraded_asset_hints,
        )
    shi_description_profile = _build_shi_description_profile(
        materials=materials,
        component_summaries=shi_component_summaries,
        missing_media_gaps=missing_media_gaps,
        reaction_summary=reaction_summary,
        forward_degraded_asset_hints=forward_degraded_asset_hints,
    )
    ontology_pack = _build_benshi_ontology_pack()
    distribution_baseline_summary, distribution_warnings = _load_distribution_baseline_summary(
        distribution_baseline_path
    )
    warnings = list(materials.warnings) + distribution_warnings

    return BenshiAnalysisPack(
        run_id=materials.run_id,
        target=materials.target,
        chosen_time_window=materials.chosen_time_window,
        pack_summary=_build_pack_summary(
            materials=materials,
            forward_summaries=forward_summaries,
            recurrence_summaries=recurrence_summaries,
            missing_media_gaps=missing_media_gaps,
            forward_degraded_asset_hints=forward_degraded_asset_hints,
            expired_inference_summary=expired_inference_summary,
            overlay_summary=overlay_summary,
            reaction_summary=reaction_summary,
        ),
        stats=materials.stats,
        selected_messages=selected_messages,
        forward_summary=forward_aggregate,
        forward_summaries=forward_summaries,
        recurrence_summary=recurrence_aggregate,
        recurrence_summaries=recurrence_summaries,
        participant_role_candidates=participant_role_candidates,
        reaction_summary=reaction_summary,
        reaction_patterns=reaction_patterns,
        asset_summary=asset_aggregate,
        asset_summaries=asset_summaries,
        shi_component_summaries=shi_component_summaries,
        shi_description_profile=shi_description_profile,
        ontology_pack=ontology_pack,
        distribution_baseline_summary=distribution_baseline_summary,
        expired_inference_summary=expired_inference_summary,
        expired_inference_items=expired_inference_items,
        missing_media_gaps=missing_media_gaps,
        forward_degraded_asset_hints=forward_degraded_asset_hints,
        preprocess_overlay_summary=overlay_summary,
        warnings=warnings,
    )


def _load_distribution_baseline_summary(
    distribution_baseline_path: str | Path | None,
) -> tuple[BenshiDistributionBaselineSummary | None, list[str]]:
    if distribution_baseline_path is None:
        return None, []
    baseline_path = Path(distribution_baseline_path)
    if not baseline_path.exists():
        return None, [f"distribution_baseline_missing:{baseline_path}"]
    summary = load_distribution_baseline_summary(baseline_path)
    return summary, []


def _build_selected_messages(
    messages: Sequence[AnalysisMessageRecord],
) -> list[BenshiSelectedMessage]:
    selected: list[BenshiSelectedMessage] = []
    for message in messages:
        semantics = classify_message_input_semantics(message)
        asset_types = sorted(
            {
                str(item.get("asset_type") or item.get("type") or "").strip().lower()
                for item in message.assets
                if str(item.get("asset_type") or item.get("type") or "").strip()
            }
        )
        selected.append(
            BenshiSelectedMessage(
                message_uid=message.message_uid,
                timestamp_iso=message.timestamp_iso,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                message_id=message.message_id,
                message_seq=message.message_seq,
                content=message.content,
                text_content=message.text_content,
                processed_text=semantics.processed_text,
                decision_summary=semantics.decision_summary,
                delivery_profile=semantics.delivery_profile,
                preprocess_labels=list(semantics.labels),
                source_message_ids=list(semantics.source_message_ids),
                source_thread_ids=list(semantics.source_thread_ids),
                asset_count=len(message.assets),
                asset_types=asset_types,
                has_forward=message.features.has_forward,
                forward_depth=message.features.forward_depth,
                missing_media_count=message.features.missing_media_count,
                message_tags=list(message.features.message_tags),
            )
        )
    return selected


def _build_forward_summaries(
    materials: AnalysisMaterials,
    *,
    max_items: int,
) -> list[BenshiForwardSummary]:
    seen: set[str] = set()
    output: list[BenshiForwardSummary] = []
    message_by_id = {
        str(message.message_id): message
        for message in materials.messages
        if message.message_id is not None
    }

    for message in materials.messages:
        for annotation in _message_preprocess_annotations(message):
            if annotation.get("label") != "forward_bundle_expander":
                continue
            metadata = _as_mapping(annotation.get("metadata"))
            details = _as_mapping(metadata.get("details"))
            if not details:
                continue
            outer_message_id = _string_or_none(details.get("outer_message_id")) or message.message_id
            key = _string_or_none(annotation.get("annotation_id")) or _string_or_none(
                details.get("segment_id")
            )
            if not key:
                key = stable_digest(
                    "forward",
                    outer_message_id,
                    details.get("preview_text"),
                    details.get("inner_message_count"),
                    length=16,
                )
            if key in seen:
                continue
            seen.add(key)
            outer_message = message_by_id.get(str(outer_message_id or "")) or message
            inner_asset_refs = _list_of_mappings(details.get("inner_asset_refs"))
            inner_asset_type_counts = Counter(
                _string_or_none(item.get("asset_type")) or "unknown"
                for item in inner_asset_refs
            )
            output.append(
                BenshiForwardSummary(
                    summary_id=f"fwd_{key}",
                    outer_message_uid=outer_message.message_uid,
                    outer_message_id=outer_message.message_id,
                    outer_timestamp_iso=outer_message.timestamp_iso,
                    outer_sender_id=outer_message.sender_id,
                    outer_sender_name=outer_message.sender_name,
                    preview_text=_string_or_none(details.get("preview_text")),
                    detailed_text=_string_or_none(details.get("detailed_text")),
                    preview_lines=_string_list(details.get("preview_lines")),
                    segment_summary=_string_or_none(details.get("segment_summary")),
                    inner_message_count=_int_value(details.get("inner_message_count")),
                    inner_asset_count=len(inner_asset_refs),
                    inner_asset_type_counts=dict(sorted(inner_asset_type_counts.items())),
                    forward_depth_hint=_int_value(
                        _as_mapping(details.get("forward_meta")).get("forward_depth")
                    ),
                    evidence_message_uids=[outer_message.message_uid],
                )
            )
            if len(output) >= max_items:
                return output

    if output:
        return output

    for message in materials.messages:
        if not message.features.has_forward:
            continue
        output.append(
            BenshiForwardSummary(
                summary_id=f"fwd_{message.message_uid}",
                outer_message_uid=message.message_uid,
                outer_message_id=message.message_id,
                outer_timestamp_iso=message.timestamp_iso,
                outer_sender_id=message.sender_id,
                outer_sender_name=message.sender_name,
                preview_text=preview_text(message.content, 200),
                detailed_text=preview_text(message.content, 400),
                preview_lines=[],
                segment_summary="forward_bundle_fallback",
                inner_message_count=0,
                inner_asset_count=0,
                inner_asset_type_counts={},
                forward_depth_hint=message.features.forward_depth,
                evidence_message_uids=[message.message_uid],
            )
        )
        if len(output) >= max_items:
            break
    return output


def _build_recurrence_summaries(
    materials: AnalysisMaterials,
    *,
    max_items: int,
) -> list[BenshiRecurrenceSummary]:
    seen: set[str] = set()
    output: list[BenshiRecurrenceSummary] = []

    for message in materials.messages:
        for annotation in _message_preprocess_annotations(message):
            if annotation.get("label") != "asset_recurrence_preprocessor":
                continue
            metadata = _as_mapping(annotation.get("metadata"))
            details = _as_mapping(metadata.get("details"))
            recurrence_key = _string_or_none(details.get("recurrence_key"))
            if not recurrence_key:
                continue
            if recurrence_key in seen:
                continue
            seen.add(recurrence_key)
            output.append(
                BenshiRecurrenceSummary(
                    summary_id=f"rec_{stable_digest(recurrence_key, length=16)}",
                    recurrence_key=recurrence_key,
                    basis=_string_or_none(details.get("basis")) or "unknown",
                    asset_type=_string_or_none(details.get("asset_type")) or "unknown",
                    file_name=_string_or_none(details.get("file_name")),
                    occurrence_count=_int_value(details.get("occurrence_count")),
                    distinct_chat_ids=_string_list(details.get("distinct_chat_ids")),
                    resource_state_counts=_counter_mapping(details.get("resource_state_counts")),
                    materialization_status_counts=_counter_mapping(
                        details.get("materialization_status_counts")
                    ),
                    exported_rel_paths=_string_list(details.get("exported_rel_paths")),
                    evidence_message_ids=_string_list(details.get("message_ids")),
                    source_asset_ids=_string_list(details.get("asset_ids")),
                    confidence=_float_value(annotation.get("confidence")),
                )
            )
            if len(output) >= max_items:
                return output
    return output


def _build_participant_role_candidates(
    materials: AnalysisMaterials,
) -> list[BenshiParticipantRoleCandidate]:
    grouped: dict[str, list[AnalysisMessageRecord]] = defaultdict(list)
    for message in materials.messages:
        grouped[message.sender_id].append(message)

    top_message_count = max((len(items) for items in grouped.values()), default=0)
    top_forward_count = max(
        (
            sum(1 for message in items if message.features.has_forward)
            for items in grouped.values()
        ),
        default=0,
    )
    candidates: list[BenshiParticipantRoleCandidate] = []
    for sender_id, messages in grouped.items():
        sorted_messages = sorted(messages, key=lambda item: (item.timestamp_ms, item.message_uid))
        sender_name = next((item.sender_name for item in sorted_messages if item.sender_name), None)
        message_count = len(sorted_messages)
        forward_message_count = sum(1 for item in sorted_messages if item.features.has_forward)
        asset_message_count = sum(1 for item in sorted_messages if item.assets)
        reply_message_count = sum(1 for item in sorted_messages if item.features.has_reply)
        missing_media_message_count = sum(
            1 for item in sorted_messages if item.features.missing_media_count > 0
        )
        label_counter = Counter()
        for item in sorted_messages:
            semantics = classify_message_input_semantics(item)
            label_counter.update(semantics.labels)

        role_names: list[str] = []
        notes: list[str] = []
        if message_count == top_message_count and message_count >= 3:
            role_names.append("dominant_sender")
            notes.append(f"在当前窗口内发言数最高（{message_count} 条）。")
        if forward_message_count == top_forward_count and forward_message_count >= 3:
            role_names.append("forward_dumper")
            notes.append(f"forward 消息占比高（{forward_message_count}/{message_count}）。")
        if asset_message_count >= 3 and asset_message_count / max(message_count, 1) >= 0.4:
            role_names.append("media_shipper")
            notes.append(f"携带媒体的消息较多（{asset_message_count}/{message_count}）。")
        if reply_message_count >= 2 and reply_message_count / max(message_count, 1) >= 0.3:
            role_names.append("reactive_responder")
            notes.append(f"reply 链参与度较高（{reply_message_count}/{message_count}）。")
        if missing_media_message_count >= 1:
            role_names.append("gap_carrier")
            notes.append(f"该发送者关联 {missing_media_message_count} 条媒体缺口消息。")
        debug_hits = sum(label_counter.get(label, 0) for label in _DEBUGISH_LABELS)
        if debug_hits >= 2:
            role_names.append("dev_context_chatter")
            notes.append(f"预处理层判为 debug/dev 噪音的标签较多（{debug_hits}）。")
        if not role_names:
            role_names.append("ambient_participant")
            notes.append("当前窗口里更像背景参与者，而非集中搬运主导者。")

        candidates.append(
            BenshiParticipantRoleCandidate(
                sender_id=sender_id,
                sender_name=sender_name,
                message_count=message_count,
                forward_message_count=forward_message_count,
                asset_message_count=asset_message_count,
                reply_message_count=reply_message_count,
                missing_media_message_count=missing_media_message_count,
                candidate_roles=role_names,
                notes=notes,
                evidence_message_uids=[item.message_uid for item in sorted_messages[:8]],
            )
        )

    candidates.sort(key=lambda item: (-item.message_count, item.sender_id))
    return candidates


def _build_reaction_summary(
    materials: AnalysisMaterials,
    *,
    participant_role_candidates: Sequence[BenshiParticipantRoleCandidate],
    forward_summaries: Sequence[BenshiForwardSummary],
) -> tuple[BenshiReactionAggregateSummary, list[BenshiReactionPatternSummary]]:
    dominant_senders = {
        item.sender_id
        for item in participant_role_candidates
        if {"dominant_sender", "forward_dumper"} & set(item.candidate_roles)
    }
    reaction_records: list[dict[str, Any]] = []
    repeated_phrase_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reactor_ids: set[str] = set()
    reply_participation_count = 0
    short_reaction_count = 0

    for message in materials.messages:
        if not _is_reaction_candidate_message(message):
            continue
        if dominant_senders and message.sender_id in dominant_senders:
            continue
        normalized_text = _reaction_message_text(message)
        if not normalized_text:
            continue
        reaction_modes = _reaction_modes_for_text(normalized_text)
        if not reaction_modes and not _looks_like_short_reaction_text(normalized_text):
            continue
        reaction_records.append(
            {
                "scope": "top_level",
                "message_uid": message.message_uid,
                "message_id": message.message_id,
                "timestamp_iso": message.timestamp_iso,
                "sender_id": message.sender_id,
                "sender_name": message.sender_name,
                "forward_summary_id": None,
                "text": normalized_text,
                "normalized_text": _normalize_reaction_text(normalized_text),
                "pattern_ids": list(reaction_modes),
            }
        )
        reactor_ids.add(message.sender_id)
        if message.features.has_reply:
            reply_participation_count += 1
        if len(normalized_text) <= _REACTION_SHORT_TEXT_MAX:
            short_reaction_count += 1
        normalized_key = _normalize_reaction_text(normalized_text)
        if normalized_key:
            repeated_phrase_buckets[normalized_key].append(reaction_records[-1])

    for summary in forward_summaries:
        for reaction_line in _extract_forward_internal_reaction_lines(summary):
            text = reaction_line["text"]
            reaction_modes = _reaction_modes_for_text(text)
            if not reaction_modes and not _looks_like_short_reaction_text(text):
                continue
            normalized_key = _normalize_reaction_text(text)
            record = {
                "scope": "forward_internal",
                "message_uid": None,
                "message_id": None,
                "timestamp_iso": summary.outer_timestamp_iso,
                "sender_id": reaction_line.get("sender_key"),
                "sender_name": reaction_line.get("sender_name"),
                "forward_summary_id": summary.summary_id,
                "text": text,
                "normalized_text": normalized_key,
                "pattern_ids": list(reaction_modes),
            }
            reaction_records.append(record)
            if reaction_line.get("sender_key"):
                reactor_ids.add(str(reaction_line["sender_key"]))
            if len(text) <= _REACTION_SHORT_TEXT_MAX:
                short_reaction_count += 1
            if normalized_key:
                repeated_phrase_buckets[normalized_key].append(record)

    for repeated_records in repeated_phrase_buckets.values():
        if len(repeated_records) < 2:
            continue
        distinct_reactors = {
            str(item.get("sender_id") or item.get("sender_name") or "")
            for item in repeated_records
            if item.get("sender_id") or item.get("sender_name")
        }
        derived_mode = (
            "uniform_feedback"
            if len(repeated_records) >= 3 or len(distinct_reactors) >= 2
            else "repeat_echo"
        )
        for item in repeated_records:
            if derived_mode not in item["pattern_ids"]:
                item["pattern_ids"].append(derived_mode)

    mode_counter: Counter[str] = Counter()
    reactors_by_mode: dict[str, set[str]] = defaultdict(set)
    representative_by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scope_counter: Counter[str] = Counter()

    for record in reaction_records:
        if not record["pattern_ids"]:
            continue
        scope_counter.update([str(record.get("scope") or "unknown")])
        reactor_key = _reaction_actor_key(record)
        for mode in record["pattern_ids"]:
            mode_counter[mode] += 1
            if reactor_key:
                reactors_by_mode[mode].add(reactor_key)
            if len(representative_by_mode[mode]) < 4:
                representative_by_mode[mode].append(record)

    pattern_summaries: list[BenshiReactionPatternSummary] = []
    for label, count in mode_counter.most_common():
        representatives = representative_by_mode[label]
        top_level_count = sum(
            1 for item in representatives if item.get("scope") == "top_level"
        )
        forward_internal_count = sum(
            1 for item in representatives if item.get("scope") == "forward_internal"
        )
        representative_message_uids = [
            str(item.get("message_uid"))
            for item in representatives
            if item.get("message_uid")
        ]
        representative_forward_ids = [
            str(item.get("forward_summary_id"))
            for item in representatives
            if item.get("forward_summary_id")
        ]
        cue_texts = list(
            dict.fromkeys(
                preview_text(str(item.get("text") or ""), 80) or "<empty>"
                for item in representatives
            )
        )[:4]
        scope_label = "mixed"
        if top_level_count and not forward_internal_count:
            scope_label = "top_level"
        elif forward_internal_count and not top_level_count:
            scope_label = "forward_internal"
        pattern_summaries.append(
            BenshiReactionPatternSummary(
                pattern_id=label,
                pattern_label=_REACTION_PATTERN_LABELS.get(label, label),
                scope=scope_label,
                score=round(count + len(reactors_by_mode[label]) * 0.35, 3),
                message_count=count,
                reactor_count=len(reactors_by_mode[label]),
                top_level_count=sum(
                    1 for item in reaction_records
                    if label in item["pattern_ids"] and item.get("scope") == "top_level"
                ),
                forward_internal_count=sum(
                    1
                    for item in reaction_records
                    if label in item["pattern_ids"] and item.get("scope") == "forward_internal"
                ),
                representative_message_uids=representative_message_uids,
                representative_forward_ids=representative_forward_ids,
                representative_excerpts=cue_texts,
                cue_texts=cue_texts,
                notes=[
                    f"{_REACTION_PATTERN_LABELS.get(label, label)}出现 {count} 次。",
                    f"涉及 {len(reactors_by_mode[label])} 名参与者。",
                ],
            )
        )

    dominant_modes = [item.pattern_label for item in pattern_summaries[:4]]
    notes: list[str] = []
    if reaction_records:
        notes.append(
            f"窗口内识别出 {len(reaction_records)} 条疑似‘吃史反应’，参与者 {len(reactor_ids)} 人。"
        )
        if dominant_modes:
            notes.append("主导反应模式为：" + " / ".join(dominant_modes) + "。")
        if reply_participation_count:
            notes.append(f"其中 {reply_participation_count} 条带 reply 结构，说明存在显式接球/点评。")
        if scope_counter.get("forward_internal"):
            notes.append(
                f"其中 {scope_counter['forward_internal']} 条来自 forward 内层围观/点评片段。"
            )
    else:
        notes.append("当前窗口缺少明确的外围吃史反应，可能更偏单人倾倒或材料窗口。")

    summary = BenshiReactionAggregateSummary(
        reaction_message_count=len(reaction_records),
        reactor_count=len(reactor_ids),
        reply_participation_count=reply_participation_count,
        short_reaction_count=short_reaction_count,
        top_level_count=scope_counter.get("top_level", 0),
        forward_internal_count=scope_counter.get("forward_internal", 0),
        disbelief_count=mode_counter.get("amused_break", 0) + mode_counter.get("spectator", 0),
        ridicule_count=mode_counter.get("mockery", 0),
        disgust_count=mode_counter.get("disgust", 0),
        curiosity_count=mode_counter.get("spectator", 0),
        echo_count=mode_counter.get("repeat_echo", 0) + mode_counter.get("uniform_feedback", 0),
        amused_break_count=mode_counter.get("amused_break", 0),
        mockery_count=mode_counter.get("mockery", 0),
        uniform_feedback_count=mode_counter.get("uniform_feedback", 0),
        meme_catch_count=mode_counter.get("meme_catch", 0),
        spectator_count=mode_counter.get("spectator", 0),
        pattern_counts=dict(sorted(mode_counter.items())),
        scope_counts=dict(sorted(scope_counter.items())),
        dominant_modes=dominant_modes,
        representative_message_uids=[
            str(item.get("message_uid"))
            for item in reaction_records
            if item.get("message_uid")
        ][:8],
        representative_forward_ids=[
            str(item.get("forward_summary_id"))
            for item in reaction_records
            if item.get("forward_summary_id")
        ][:8],
        notes=notes,
    )
    return summary, pattern_summaries


def _build_forward_degraded_asset_hints(
    forward_summaries: Sequence[BenshiForwardSummary],
    *,
    max_items: int,
) -> list[BenshiForwardDegradedAssetHint]:
    grouped: dict[tuple[str, str | None], dict[str, Any]] = {}
    for summary in forward_summaries:
        text_pool = [*summary.preview_lines]
        if summary.detailed_text:
            text_pool.append(summary.detailed_text)
        if summary.preview_text:
            text_pool.append(summary.preview_text)
        for chunk in text_pool:
            for asset_type, file_name in _extract_forward_degraded_tokens(chunk):
                normalized_file_name = file_name.strip() or None
                key = (asset_type, normalized_file_name)
                bucket = grouped.setdefault(
                    key,
                    {
                        "asset_type": asset_type,
                        "file_name": normalized_file_name,
                        "occurrence_count": 0,
                        "outer_message_uids": set(),
                        "outer_message_ids": set(),
                        "preview_examples": [],
                        "timestamp_iso": summary.outer_timestamp_iso,
                        "sender_id": summary.outer_sender_id,
                        "sender_name": summary.outer_sender_name,
                        "context_excerpt": summary.preview_text or summary.detailed_text,
                    },
                )
                bucket["occurrence_count"] += 1
                if summary.outer_message_uid:
                    bucket["outer_message_uids"].add(summary.outer_message_uid)
                if summary.outer_message_id:
                    bucket["outer_message_ids"].add(summary.outer_message_id)
                if chunk and len(bucket["preview_examples"]) < 4:
                    bucket["preview_examples"].append(preview_text(chunk, 140) or chunk)

    output: list[BenshiForwardDegradedAssetHint] = []
    for (asset_type, file_name), item in sorted(
        grouped.items(),
        key=lambda pair: (-pair[1]["occurrence_count"], pair[0][0], pair[0][1] or ""),
    ):
        notes = ["该位点来自 deep/nested forward 预览文本，只能作为 context-only 证据。"]
        if item["occurrence_count"] >= 2:
            notes.append(f"该退化位点在窗口里重复出现 {item['occurrence_count']} 次。")
        output.append(
            BenshiForwardDegradedAssetHint(
                hint_id=f"fwdhint_{stable_digest(asset_type, file_name, item['occurrence_count'], length=16)}",
                asset_type=asset_type,
                file_name=file_name,
                evidence_state="inferred",
                confidence_label="context_only",
                occurrence_count=item["occurrence_count"],
                outer_message_count=len(item["outer_message_uids"]),
                outer_message_uids=sorted(item["outer_message_uids"]),
                outer_message_ids=sorted(item["outer_message_ids"]),
                representative_timestamp_iso=item["timestamp_iso"],
                representative_sender_id=item["sender_id"],
                representative_sender_name=item["sender_name"],
                representative_context_excerpt=preview_text(item["context_excerpt"] or "", 180) or None,
                preview_examples=list(item["preview_examples"]),
                notes=notes,
            )
        )
        if len(output) >= max_items:
            break
    return output


def _build_asset_summaries(materials: AnalysisMaterials) -> list[BenshiAssetSummary]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    message_uids_by_type: dict[str, set[str]] = defaultdict(set)
    for message in materials.messages:
        for asset in message.assets:
            asset_type = _string_or_none(asset.get("asset_type") or asset.get("type")) or "unknown"
            grouped[asset_type].append(asset)
            if message.message_uid:
                message_uids_by_type[asset_type].add(message.message_uid)

    output: list[BenshiAssetSummary] = []
    for asset_type, assets in sorted(grouped.items()):
        status_counter = Counter(
            _asset_status(asset)
            for asset in assets
        )
        file_counter = Counter(
            file_name
            for file_name in (
                _string_or_none(asset.get("file_name"))
                for asset in assets
            )
            if file_name
        )
        output.append(
            BenshiAssetSummary(
                asset_type=asset_type,
                reference_count=len(assets),
                message_count=len(message_uids_by_type.get(asset_type, set())),
                materialized_count=sum(1 for asset in assets if _asset_is_materialized(asset)),
                missing_count=sum(1 for asset in assets if _asset_is_missing(asset)),
                status_counts=dict(sorted(status_counter.items())),
                top_file_names=[name for name, _ in file_counter.most_common(5)],
                representative_asset_ids=[
                    str(asset.get("asset_id"))
                    for asset in assets
                    if asset.get("asset_id")
                ][:8],
            )
        )
    return output


def _build_expired_inference_summary(
    materials: AnalysisMaterials,
    *,
    max_items: int,
) -> tuple[BenshiExpiredInferenceAggregateSummary, list[BenshiExpiredInferenceSummaryItem]]:
    annotation_records = _collect_expired_inference_annotations(materials)
    items: list[BenshiExpiredInferenceSummaryItem] = []
    final_status_counts = Counter()
    resource_state_counts = Counter()
    asset_type_counts = Counter()
    signal_reason_counts = Counter()
    request_kind_counts = Counter()
    total_round_count = 0
    same_asset_linked_count = 0
    with_hypothesis_count = 0

    for message, annotation, matched_assets in annotation_records:
        metadata = _as_mapping(annotation.get("metadata"))
        signal_summary = _as_mapping(metadata.get("signal_summary"))
        signal = _as_mapping(signal_summary.get("signal"))
        round_traces = _list_of_mappings(metadata.get("round_traces"))
        request_kinds = [
            request_kind
            for request_kind in (
                _string_or_none(item.get("request_kind")) for item in round_traces
            )
            if request_kind
        ]
        primary_asset = matched_assets[0] if matched_assets else None
        asset_type = (
            _string_or_none(
                (primary_asset or {}).get("asset_type") or (primary_asset or {}).get("type")
            )
            or _string_or_none(metadata.get("asset_type"))
            or _string_or_none(signal_summary.get("asset_type"))
            or "unknown"
        )
        file_name = (
            _string_or_none((primary_asset or {}).get("file_name"))
            or _string_or_none(metadata.get("file_name"))
            or _string_or_none(signal_summary.get("file_name"))
        )
        resource_state = (
            _string_or_none(signal_summary.get("resource_state"))
            or _string_or_none(metadata.get("resource_state"))
            or _value_from_prefixed_labels(annotation.get("tags"), "resource_state:")
            or "unknown"
        )
        final_status = (
            _string_or_none(metadata.get("status"))
            or _value_from_prefixed_labels(annotation.get("tags"), "status:")
            or "info"
        )
        hypothesis_text = _string_or_none(metadata.get("hypothesis_text"))
        signal_reason = _string_or_none(signal.get("reason"))
        forward_degraded = _bool_value(
            metadata.get("forward_degraded")
            if metadata.get("forward_degraded") is not None
            else signal_summary.get("forward_degraded")
        )
        forward_parent_message_id = (
            _string_or_none(metadata.get("forward_parent_message_id"))
            or _string_or_none(signal_summary.get("forward_parent_message_id"))
        )
        forward_depth = _int_value(
            metadata.get("forward_depth")
            if metadata.get("forward_depth") is not None
            else signal_summary.get("forward_depth")
        )
        context_excerpt = (
            _string_or_none(metadata.get("context_excerpt"))
            or _string_or_none(signal_summary.get("context_excerpt"))
        )
        same_asset_occurrence_count = _int_value(
            signal_summary.get("same_asset_occurrence_count")
            or len(_string_list(metadata.get("same_asset_occurrence_ids")))
        )
        if same_asset_occurrence_count > 0:
            same_asset_linked_count += 1
        if hypothesis_text:
            with_hypothesis_count += 1
        final_status_counts.update([final_status])
        resource_state_counts.update([resource_state])
        asset_type_counts.update([asset_type])
        if signal_reason:
            signal_reason_counts.update([signal_reason])
        request_kind_counts.update(request_kinds)
        total_round_count += len(round_traces)

        notes: list[str] = []
        if not matched_assets:
            notes.append("source_asset_not_located_in_message_assets")
        if file_name:
            notes.append(f"file_name:{file_name}")
        if forward_degraded:
            notes.append("forward_degraded:true")
        if forward_parent_message_id:
            notes.append(f"forward_parent_message_id:{forward_parent_message_id}")
        if forward_depth > 0:
            notes.append(f"forward_depth:{forward_depth}")
        if context_excerpt:
            notes.append(f"context_excerpt:{preview_text(context_excerpt, 180) or context_excerpt}")
        if _bool_value(signal.get("budget_exhausted")):
            notes.append("budget_exhausted")
        if round_traces and any(not _bool_value(item.get("granted")) for item in round_traces):
            notes.append("contains_rejected_context_round")

        items.append(
            BenshiExpiredInferenceSummaryItem(
                summary_id=_string_or_none(annotation.get("annotation_id"))
                or f"expinf_{stable_digest(message.message_uid, annotation.get('summary'), length=16)}",
                message_uid=message.message_uid,
                message_id=message.message_id,
                timestamp_iso=message.timestamp_iso,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                asset_id=_string_or_none(signal_summary.get("asset_id"))
                or _string_or_none((primary_asset or {}).get("asset_id")),
                processed_asset_ids=_string_list(annotation.get("target_ids")),
                asset_type=asset_type,
                resource_state=resource_state,
                final_status=final_status,
                confidence=_float_value(annotation.get("confidence")),
                hypothesis_text=hypothesis_text,
                decision_summary=_string_or_none(annotation.get("decision_summary"))
                or _string_or_none(annotation.get("summary")),
                signal_reason=signal_reason,
                snippet_count=_int_value(signal.get("snippet_count")),
                explicit_chars=_int_value(signal.get("explicit_chars")),
                same_asset_occurrence_count=same_asset_occurrence_count,
                round_count=len(round_traces),
                request_kinds=request_kinds,
                evidence_message_ids=_string_list(annotation.get("source_message_ids")),
                source_asset_ids=_string_list(annotation.get("source_asset_ids")),
                notes=notes,
            )
        )

    items.sort(
        key=lambda item: (
            _expired_inference_status_rank(item.final_status),
            -item.confidence,
            -item.same_asset_occurrence_count,
            item.timestamp_iso,
            item.summary_id,
        )
    )

    aggregate = BenshiExpiredInferenceAggregateSummary(
        inference_count=len(items),
        resolved_count=final_status_counts.get("resolved", 0),
        uncertain_count=final_status_counts.get("uncertain", 0),
        unrecoverable_count=final_status_counts.get("unrecoverable", 0),
        info_count=final_status_counts.get("info", 0),
        with_hypothesis_count=with_hypothesis_count,
        resource_state_counts=dict(sorted(resource_state_counts.items())),
        asset_type_counts=dict(sorted(asset_type_counts.items())),
        final_status_counts=dict(sorted(final_status_counts.items())),
        signal_reason_counts=dict(sorted(signal_reason_counts.items())),
        request_kind_counts=dict(sorted(request_kind_counts.items())),
        total_round_count=total_round_count,
        same_asset_linked_count=same_asset_linked_count,
        representative_summary_ids=[item.summary_id for item in items[:8]],
    )
    return aggregate, items[:max_items]


def _build_forward_aggregate_summary(
    materials: AnalysisMaterials,
    forward_summaries: Sequence[BenshiForwardSummary],
) -> BenshiForwardAggregateSummary:
    asset_type_counts = Counter()
    representative_ids: list[str] = []
    nested_forward_count = 0
    for item in forward_summaries:
        asset_type_counts.update(item.inner_asset_type_counts)
        if (item.forward_depth_hint or 0) >= 2:
            nested_forward_count += 1
        if item.summary_id and len(representative_ids) < 8:
            representative_ids.append(item.summary_id)
    return BenshiForwardAggregateSummary(
        forward_message_count=materials.stats.forward_message_count,
        nested_forward_count=nested_forward_count,
        expanded_bundle_count=len(forward_summaries),
        expanded_inner_message_count=sum(item.inner_message_count for item in forward_summaries),
        expanded_inner_asset_count=sum(item.inner_asset_count for item in forward_summaries),
        top_asset_type_counts=dict(asset_type_counts.most_common(8)),
        representative_forward_ids=representative_ids,
    )


def _build_recurrence_aggregate_summary(
    recurrence_summaries: Sequence[BenshiRecurrenceSummary],
) -> BenshiRecurrenceAggregateSummary:
    basis_counts = Counter()
    asset_type_counts = Counter()
    high_recurrence_keys: list[str] = []
    repeated_transport_count = 0
    for item in recurrence_summaries:
        basis_counts[item.basis] += 1
        asset_type_counts[item.asset_type] += item.occurrence_count or 1
        if item.occurrence_count >= 2:
            repeated_transport_count += item.occurrence_count
        if item.occurrence_count >= 3 and len(high_recurrence_keys) < 8:
            high_recurrence_keys.append(item.recurrence_key)
    return BenshiRecurrenceAggregateSummary(
        repeated_transport_count=repeated_transport_count,
        repeated_asset_cluster_count=len(recurrence_summaries),
        top_basis_counts=dict(basis_counts.most_common(8)),
        top_asset_type_counts=dict(asset_type_counts.most_common(8)),
        high_recurrence_keys=high_recurrence_keys,
    )


def _build_asset_aggregate_summary(
    asset_summaries: Sequence[BenshiAssetSummary],
) -> BenshiAssetAggregateSummary:
    reference_counts = {
        item.asset_type: item.reference_count for item in asset_summaries
    }
    missing_counts = {
        item.asset_type: item.missing_count for item in asset_summaries if item.missing_count
    }
    materialized_counts = {
        item.asset_type: item.materialized_count
        for item in asset_summaries
        if item.materialized_count
    }
    top_file_names: list[str] = []
    for item in asset_summaries:
        for file_name in item.top_file_names:
            if file_name in top_file_names:
                continue
            top_file_names.append(file_name)
            if len(top_file_names) >= 10:
                break
        if len(top_file_names) >= 10:
            break
    return BenshiAssetAggregateSummary(
        total_asset_reference_count=sum(item.reference_count for item in asset_summaries),
        materialized_asset_count=sum(item.materialized_count for item in asset_summaries),
        missing_asset_count=sum(item.missing_count for item in asset_summaries),
        asset_type_reference_counts=reference_counts,
        asset_type_missing_counts=missing_counts,
        asset_type_materialized_counts=materialized_counts,
        top_file_names=top_file_names,
    )


def _build_shi_component_summaries(
    *,
    materials: AnalysisMaterials,
    selected_messages: Sequence[BenshiSelectedMessage],
    participant_role_candidates: Sequence[BenshiParticipantRoleCandidate],
    forward_summary: BenshiForwardAggregateSummary,
    recurrence_summary: BenshiRecurrenceAggregateSummary,
    asset_summary: BenshiAssetAggregateSummary,
    missing_media_gaps: Sequence[BenshiMissingMediaGap],
    reaction_summary: BenshiReactionAggregateSummary,
    forward_degraded_asset_hints: Sequence[BenshiForwardDegradedAssetHint],
) -> list[BenshiShiComponentSummary]:
    short_asset_message_count = 0
    content_blob_parts: list[str] = []
    for item in selected_messages:
        effective_text = (item.processed_text or item.text_content or item.content or "").strip()
        if effective_text:
            content_blob_parts.append(effective_text)
        if item.asset_count and (not effective_text or len(effective_text) <= 24):
            short_asset_message_count += 1
    content_blob = "\n".join(content_blob_parts)
    topic_bucket_hits = sum(
        [
            _contains_any(
                content_blob,
                ("中东", "德黑兰", "川普", "特朗普", "美国", "苏联", "俄", "以色列", "哈马斯", "vps"),
            ),
            _contains_any(
                content_blob,
                ("巨根", "药娘", "萝莉", "成人视频", "性神经", "前置科技", "鸡巴", "搞黄"),
            ),
            _contains_any(
                content_blob,
                ("彩礼", "停车位", "充电桩", "地锁", "老婆", "老公", "相亲", "互联网"),
            ),
            _contains_any(
                content_blob,
                ("开盒", "爆破", "od", "自杀", "翻车", "偷拍视频", "学校", "未成年"),
            ),
        ]
    )
    top_sender_messages = max(
        (item.message_count for item in participant_role_candidates),
        default=0,
    )
    dominant_sender_ratio = top_sender_messages / max(1, materials.stats.message_count)
    missing_types = {item.asset_type for item in missing_media_gaps}
    degraded_types = {item.asset_type for item in forward_degraded_asset_hints}
    image_reference_count = asset_summary.asset_type_reference_counts.get("image", 0)
    component_candidates: list[BenshiShiComponentSummary] = []

    def add_component(
        label: str,
        family: str,
        score: float,
        reasons: list[str],
        *,
        evidence_message_uids: list[str] | None = None,
        notes: list[str] | None = None,
    ) -> None:
        component_candidates.append(
            BenshiShiComponentSummary(
                component_label=label,
                component_family=family,
                score=round(score, 3),
                evidence_basis=reasons,
                evidence_message_uids=list(evidence_message_uids or []),
                notes=list(notes or []),
            )
        )

    if forward_summary.forward_message_count >= max(3, materials.stats.message_count // 4):
        add_component(
            "外源史",
            "provenance",
            0.9,
            [
                f"窗口内 forward 密度高（{forward_summary.forward_message_count}/{materials.stats.message_count}）",
                "主体更像外部材料被搬进群再分发，而不是群内自然长出来。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.has_forward][:6],
        )
    if forward_summary.nested_forward_count >= 1:
        add_component(
            "二手史",
            "provenance",
            0.92,
            [
                f"存在套娃 forward（{forward_summary.nested_forward_count} 条）",
                "史味不只在内容本体，更在层层转手和二次围观结构里。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.forward_depth >= 2][:6],
        )
    if recurrence_summary.repeated_transport_count >= 2 or recurrence_summary.repeated_asset_cluster_count >= 1:
        add_component(
            "补档返场史",
            "transport",
            0.84,
            [
                "窗口内存在重复搬运或返场回放信号。",
                f"复现簇={recurrence_summary.repeated_asset_cluster_count}，重复转运={recurrence_summary.repeated_transport_count}。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.has_forward or item.asset_count][:6],
        )
    if reaction_summary.reaction_message_count >= 2 or reaction_summary.reply_participation_count >= 1:
        add_component(
            "反应史",
            "social",
            0.76,
            [
                f"窗口内有 {reaction_summary.reaction_message_count} 条外围吃史反应。",
                "群友的问号、复读、阴阳和接球已经参与到这坨史的成立过程里。",
            ],
            evidence_message_uids=list(reaction_summary.representative_message_uids[:6]),
            notes=list(reaction_summary.dominant_modes[:4]),
        )
    if dominant_sender_ratio >= 0.65 and forward_summary.forward_message_count >= max(3, materials.stats.message_count // 4):
        add_component(
            "单人主导倾倒",
            "transport",
            0.82,
            [
                f"单个发送者占窗口消息的 {dominant_sender_ratio:.0%} 左右。",
                "更像中转站卸货，而不是多人围绕一条史展开讨论。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages[:6]],
        )
    if image_reference_count >= max(12, materials.stats.message_count // 2):
        add_component(
            "截图壳子史",
            "packaging",
            0.76,
            [
                f"图片引用量高（{image_reference_count}）",
                "很多史味不是靠单段正文，而是靠截图壳、图串壳和界面壳来承载。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if "image" in item.asset_types][:6],
        )
    if short_asset_message_count >= max(4, materials.stats.message_count // 8):
        add_component(
            "配文史",
            "packaging",
            0.7,
            [
                f"有 {short_asset_message_count} 条消息属于“短文本 + 多媒体壳子”结构。",
                "很多内容更像靠标题、截图和一两句配文成立。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.asset_count][:6],
        )
    if forward_summary.nested_forward_count >= 1 and forward_summary.expanded_inner_message_count >= 8:
        add_component(
            "群聊切片史",
            "packaging",
            0.72,
            [
                f"forward 内层消息多（{forward_summary.expanded_inner_message_count}）",
                "更像把别处群聊切片、接话和回声片段整包搬进来。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.has_forward][:6],
        )
    if materials.stats.low_information_ratio >= 0.12 and recurrence_summary.repeated_transport_count >= 1:
        add_component(
            "工业史",
            "content",
            0.68,
            [
                f"低信息消息占比偏高（{materials.stats.low_information_ratio:.0%}）",
                "重复搬运和低信息回声叠在一起，工业流水线气味明显。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if "low_information" in item.message_tags][:6],
        )
    if topic_bucket_hits >= 3:
        add_component(
            "拼盘史",
            "content",
            0.66,
            [
                "文本里同时命中多个异质题材桶。",
                "更像乱炖式倒货，不像单主题深聊。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages[:6]],
        )
    if _contains_any(content_blob, ("巨根", "药娘", "萝莉", "成人视频", "偷拍", "开盒", "od")):
        add_component(
            "低俗猎奇史",
            "content",
            0.61,
            [
                "窗口内有明显高刺激、低事实密度的猎奇词汇或叙述。",
                "这种成分会抬高冲击性，但不一定抬高信息质量。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages[:6]],
        )
    if forward_summary.nested_forward_count >= 1 and recurrence_summary.repeated_transport_count >= 1:
        add_component(
            "包浆史",
            "social",
            0.74,
            [
                "套娃转运和返场回放同时存在。",
                "重点不只是这条内容本身，而是它被人反复搬、反复看之后形成的包浆感。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.has_forward][:6],
        )
    if image_reference_count >= 16:
        add_component(
            "多图串搬运",
            "transport",
            0.78,
            [
                f"图片总量高（{image_reference_count}）",
                "不是零散单图，而是偏整串、整包地往群里倒。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if "image" in item.asset_types][:6],
        )
    if "video" in missing_types or "file" in missing_types:
        add_component(
            "视频壳缺本体",
            "uncertainty",
            0.58,
            [
                "窗口里有视频/文件位点，但本体仍缺失。",
                "这意味着有一部分史味只能靠上下文和壳子去判断，不能把媒体内容硬编进去。",
            ],
            evidence_message_uids=[item.message_uid for item in selected_messages if item.missing_media_count][:6],
        )
    elif {"video", "file"} & degraded_types:
        add_component(
            "视频壳缺本体",
            "uncertainty",
            0.66,
            [
                f"deep forward 预览里有 {len(forward_degraded_asset_hints)} 个视频/文件壳子位点。",
                "本体没被直接看见，但上下文已经说明这些媒体在整坨史里占了位置。",
            ],
            evidence_message_uids=[
                message_uid
                for item in forward_degraded_asset_hints[:6]
                for message_uid in item.outer_message_uids[:2]
            ][:6],
            notes=["context_only", "deep_forward_preview"],
        )

    component_candidates.sort(
        key=lambda item: (-item.score, item.component_family, item.component_label)
    )
    return component_candidates[:12]


def _build_shi_description_profile(
    *,
    materials: AnalysisMaterials,
    component_summaries: Sequence[BenshiShiComponentSummary],
    missing_media_gaps: Sequence[BenshiMissingMediaGap],
    reaction_summary: BenshiReactionAggregateSummary,
    forward_degraded_asset_hints: Sequence[BenshiForwardDegradedAssetHint],
) -> BenshiShiDescriptionProfile:
    dominant_labels = [item.component_label for item in component_summaries[:6]]
    component_phrase = "、".join(dominant_labels[:4]) or "搬运结构"
    taboo_notes = [
        "不要把缺失视频/文件的内容硬写成已经看见的事实。",
        "不要只会说‘抽象’，要说清抽象到底来自外源套娃、截图壳、工业流水线还是认知落差。",
        "不要把单窗搬运现象直接写成所有参与者的稳定人格结论。",
    ]
    if missing_media_gaps:
        taboo_notes.append("这窗存在失活媒体位点，描述时必须保留未知区。")
    if forward_degraded_asset_hints:
        taboo_notes.append("deep forward 里有只能靠 preview 看到的退化媒体位点，不能把 preview 直接当成看过本体。")

    return BenshiShiDescriptionProfile(
        base_definition=(
            "史不是单纯离谱内容，而是在群聊/截图/转发语境里，因为抽象性、认知错位和搬运包浆，"
            "被围观者迅速识别为值得围观、值得转运的内容单位。"
        ),
        description_strategy=(
            "先交代这窗是原生还是外源/二手，再交代 forward、图串、返场、单人倾倒这些搬运结构，"
            "然后补上群友是怎么吃这坨史的，最后再说抽象点、包浆点和未知边界。"
        ),
        description_axes=[
            "来源路径：原生、外源、二手还是返场回放",
            "搬运结构：forward、套娃、图串、单人倾倒、中转站感",
            "吃史反应：群友是在问号、复读、阴阳还是嫌恶式共振",
            "史味机制：认知落差、包浆、工业复读、截图壳、配文壳",
            "媒体依赖：是靠文本立、靠图壳立，还是靠缺失媒体周边语境勉强成立",
            "未知边界：哪些媒体位点缺失，哪些结论只能保守说",
        ],
        descriptive_tags=dominant_labels,
        good_description_patterns=[
            f"这窗更像一批 {component_phrase} 叠在一起的搬运拼盘，不是单条神贴。",
            "真正的史味不只在内容本身，还在套娃转发、返场补档和群体回声形成的包浆。",
            "描述时最好把‘这坨史是什么’和‘群友怎么吃这坨史’并排说，不要只盯内容壳子。",
            "先说结构，再说气味，再说未知区，这样描述才不会把史写成空洞吐槽。",
        ],
        bad_description_patterns=[
            "只会说‘抽象’、‘逆天’，但说不清抽象点到底在哪。",
            "把缺失媒体脑补成完整视频剧情或完整图片文字。",
            "把一窗搬运现象直接写成全局动机判断。",
        ],
        taboo_or_risk_notes=taboo_notes,
        example_descriptors=[
            "单人主导的高密度外源搬运拼盘",
            "套娃 forward 和图串返场味儿很重的二手史",
            "不是单条爆点，而是中转站式库存清仓",
            "群友反应主要靠问号、短吐槽和接球回声来完成吃史动作",
        ],
    )


def _build_benshi_ontology_pack() -> BenshiOntologyPack:
    return BenshiOntologyPack(
        source_documents=[
            "dev/documents/Q群群友史.docx",
            "dev/documents/benshi_calibration_rubric.md",
            "dev/documents/benshi_report_review_20260312.md",
        ],
        origin_definition=(
            "‘史’不是普通垃圾内容的同义词，而是当内容抽象性、认知错位感和传播外壳包浆共同成立后，"
            "在群聊里被迅速识别成值得围观、值得搬运、值得复读的一类赛博审美对象。"
        ),
        propagation_paradox=(
            "史的传播动力并不来自认可，而常常来自厌恶、围观、吐槽、复读和再搬运。"
            "也就是说，嫌弃感本身往往会转化成传播燃料。"
        ),
        formation_dimensions=[
            BenshiOntologyDimension(
                label="内容抽象性",
                summary="表达或行为明显脱离常识与社会规范，形成荒诞奇点。",
                cues=["逻辑崩坏", "表达离谱", "行为失衡"],
            ),
            BenshiOntologyDimension(
                label="认知错位感",
                summary="当事人往往自洽甚至自我感动，而旁观者体验到强烈的尴尬、震惊或滑稽。",
                cues=["当事人无自觉", "围观者 cringe", "双方认知不在一个平面"],
            ),
            BenshiOntologyDimension(
                label="视觉符号化/赛博包浆",
                summary="长截图、高糊录屏、多层水印、套娃 forward、截图壳与返场回放等外壳，会增强其被识别和搬运的身份。",
                cues=["截图壳", "套娃 forward", "水印/画质劣化", "图串返场"],
            ),
        ],
        taxonomy=[
            BenshiOntologyTaxonomyItem(
                label="原生史",
                definition="在即时通讯环境中自然生成的原始史料，重点在突发性、原始感和无修饰的荒诞张力。",
                positive_cues=["现场聊天自然生长", "原始记录", "不用额外包装就有冲击力"],
                caution="不要把所有群内原生争吵都抬成原生史，必须仍有明显荒诞张力。",
            ),
            BenshiOntologyTaxonomyItem(
                label="工业史",
                definition="机械化、大规模、低门槛重复搬运的平庸内容，常常更像电子噪声而不是高质量史料。",
                positive_cues=["低信息密度", "机械复读", "过时旧梗", "工业流水线感"],
                caution="工业史可以成立，但成色通常偏低，不要和典中典或高价值原生史混为一谈。",
            ),
            BenshiOntologyTaxonomyItem(
                label="典中典史",
                definition="经时间和跨群传播检验后沉淀成共同模因记忆的经典史料。",
                positive_cues=["跨语境成立", "时间沉淀", "群友无需解释就能接"],
                caution="不要因为窗口里有人反应整齐，就过早封成典中典。",
            ),
            BenshiOntologyTaxonomyItem(
                label="外源史",
                definition="源自外部平台，经截图或转运移植进 QQ 群的史料。",
                positive_cues=["外部平台 UI", "外部新闻/帖文/短视频截图", "群外材料搬入"],
                caution="外源史强调来源路径，不等于自动高质量。",
            ),
            BenshiOntologyTaxonomyItem(
                label="二手史",
                definition="经多轮跨群转发、被群友评论和套娃结构包裹后的二手史料。",
                positive_cues=["多层 forward", "群友点评包裹", "套娃感", "二手转运"],
                caution="二手史的重点可能转移到群体反应，而不是原事件本体。",
            ),
            BenshiOntologyTaxonomyItem(
                label="二阶史",
                definition="多种类型叠加形成的复合史，例如外源史和二手史叠加，或原生史沿传播链演化成典中典。",
                positive_cues=["复合类型", "原义与 popular 形态混合", "沿传播链演化"],
                caution="二阶史是混合解释，不应成为偷懒兜底标签。",
            ),
        ],
        quality_rubric=[
            BenshiOntologyDimension(
                label="认知落差",
                summary="是否存在明显超出常规认知的戏剧张力。",
                cues=["荒诞奇点", "这也行？", "强烈反转/错位"],
            ),
            BenshiOntologyDimension(
                label="语境跨度/脱水性",
                summary="脱离原始语境后，别人是否仍能迅速看懂槽点。",
                cues=["跨群可理解", "无需大量背景说明", "公共槽点"],
            ),
            BenshiOntologyDimension(
                label="视觉包浆/真实性",
                summary="合理的截图壳、UI 锚点、水印和套娃结构会增强证言感，但过度摆拍会削弱原生震撼力。",
                cues=["截图壳", "平台 UI", "多层水印", "赛博包浆"],
            ),
            BenshiOntologyDimension(
                label="反馈整齐度",
                summary="能否稳定激起问号、复读、尖锐点评或机械情绪共振。",
                cues=["整齐反馈", "复读", "回声", "群体共振"],
            ),
        ],
        transport_theory=[
            BenshiOntologyDimension(
                label="运史官不是机械转发器",
                summary="搬运者是筛选器、过滤器和审美裁判者，不是任何垃圾都无脑转。",
                cues=["会筛", "看后不转", "投放到特定受众群"],
            ),
            BenshiOntologyDimension(
                label="搬运行为本身是一种再生产",
                summary="史不是简单复制，而是在新群里被重新包装、赋予新立场和新反馈结构。",
                cues=["再投放", "二次包装", "社交筹码"],
            ),
        ],
        popular_forms=[
            BenshiOntologyPopularForm(
                label="外源截图史",
                summary="来自外部平台的截图被直接当作可围观史料搬入群里。",
                common_carriers=["平台 UI 截图", "新闻截图", "社媒评论区截图"],
                relation_to_origin="通常更接近外源史，而不是纯原生史。",
            ),
            BenshiOntologyPopularForm(
                label="套娃 forward 史",
                summary="靠多层 forward 和群友包裹评论来增加包浆和二手感。",
                common_carriers=["合并转发", "群聊切片", "套娃截图"],
                relation_to_origin="popular 形态上常常是二手史或二阶史。",
            ),
            BenshiOntologyPopularForm(
                label="图串返场史",
                summary="同一批图片/图串在窗口前后重复回放，形成库存清仓或补档返场感。",
                common_carriers=["图串 bundle", "重复引用", "补档回放"],
                relation_to_origin="popular 形态上常和补档返场史、包浆史耦合。",
            ),
            BenshiOntologyPopularForm(
                label="拼盘混装史",
                summary="不同题材的抽象料被集中倾倒，形成库存货架全倒出来的乱炖感。",
                common_carriers=["单人高密度投喂", "题材异质混装", "多图多 forward 混合"],
                relation_to_origin="popular 形态上不一定最纯，但非常符合集中式搬史窗口。",
                cautions=["popular 不等于高质量，拼盘感强不自动代表成色高。"],
            ),
        ],
        hard_guidance=[
            "史不等于普通低俗内容。",
            "史不等于单纯截图壳，也不等于任何复读。",
            "判断史时必须同时考虑内容抽象性、认知错位和传播外壳/包浆。",
            "必须区分史的原义、popular 形态、搬运机制和成色高低。",
            "缺失媒体不能被脑补成直接证据。",
        ],
        soft_guidance=[
            "当前 popular shi 常常比原义更偏外源、二手、套娃、图串返场和拼盘混装。",
            "单人高密度倾倒常会增强中转站感和库存清仓感。",
            "低俗猎奇会抬高冲击性，但不自动抬高史价值。",
        ],
        anti_patterns=[
            "看到低俗内容就自动判成史。",
            "看到截图就自动判成史。",
            "看到多人复读就自动判成高价值史。",
            "把当前 popular shi 的常见载体误当成史的本义。",
            "把缺失视频/图片脑补成完整剧情。",
        ],
    )


def _build_missing_media_gaps(
    materials: AnalysisMaterials,
    *,
    max_items: int,
) -> list[BenshiMissingMediaGap]:
    output: list[BenshiMissingMediaGap] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for message in materials.messages:
        context_excerpt = _message_context_excerpt(message)
        for asset in message.assets:
            if not _asset_is_missing(asset):
                continue
            dedupe_key = (
                message.message_uid,
                _string_or_none(asset.get("asset_type") or asset.get("type")) or "unknown",
                _string_or_none(asset.get("file_name")) or "",
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            reason = _asset_missing_reason(asset)
            output.append(
                BenshiMissingMediaGap(
                    gap_id=f"gap_{stable_digest(message.message_uid, asset.get('asset_id'), asset.get('file_name'), length=16)}",
                    message_uid=message.message_uid,
                    message_id=message.message_id,
                    timestamp_iso=message.timestamp_iso,
                    sender_id=message.sender_id,
                    sender_name=message.sender_name,
                    asset_id=_string_or_none(asset.get("asset_id")),
                    asset_type=_string_or_none(asset.get("asset_type") or asset.get("type")) or "unknown",
                    file_name=_string_or_none(asset.get("file_name")),
                    status=_asset_status(asset),
                    resolver=_string_or_none(asset.get("resolver")),
                    exported_rel_path=_string_or_none(asset.get("exported_rel_path")),
                    context_excerpt=context_excerpt,
                    reason=reason,
                )
            )
            if len(output) >= max_items:
                return output
        for gap in _forward_degraded_missing_media_gaps(message):
            dedupe_key = (
                gap.message_uid,
                gap.asset_type,
                gap.file_name or "",
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            output.append(gap)
            if len(output) >= max_items:
                return output
    return output


def _forward_degraded_missing_media_gaps(
    message: AnalysisMessageRecord,
) -> list[BenshiMissingMediaGap]:
    output: list[BenshiMissingMediaGap] = []
    for annotation in _message_preprocess_annotations(message):
        if annotation.get("label") != "forward_bundle_expander":
            continue
        metadata = _as_mapping(annotation.get("metadata"))
        details = _as_mapping(metadata.get("details"))
        inner_asset_refs = _list_of_mappings(details.get("inner_asset_refs"))
        preview_text_value = _string_or_none(details.get("preview_text"))
        detailed_text = _string_or_none(details.get("detailed_text"))
        preview_lines = _string_list(details.get("preview_lines"))
        token_refs = list(inner_asset_refs)
        if not token_refs:
            for value in [*preview_lines, preview_text_value, detailed_text]:
                for asset_type, file_name in _extract_forward_degraded_tokens(value):
                    token_refs.append(
                        {
                            "asset_type": asset_type,
                            "file_name": file_name,
                            "resource_state": "missing",
                            "resolver": "forward_bundle_expander",
                            "forward_degraded": True,
                        }
                    )
        for item in token_refs:
            asset_type = _string_or_none(item.get("asset_type") or item.get("type"))
            if asset_type not in {"video", "file"}:
                continue
            if not _bool_value(item.get("forward_degraded")) and _string_or_none(item.get("resolver")) != "forward_token_only":
                continue
            file_name = _string_or_none(item.get("file_name"))
            reason_parts = ["deep_forward_token_only"]
            source_hint = _string_or_none(item.get("source_hint"))
            if source_hint:
                reason_parts.append(source_hint)
            output.append(
                BenshiMissingMediaGap(
                    gap_id=f"gap_{stable_digest(message.message_uid, asset_type, file_name, 'forward_degraded', length=16)}",
                    message_uid=message.message_uid,
                    message_id=message.message_id,
                    timestamp_iso=message.timestamp_iso,
                    sender_id=message.sender_id,
                    sender_name=message.sender_name,
                    asset_id=None,
                    asset_type=asset_type,
                    file_name=file_name,
                    status="forward_degraded_asset",
                    resolver=_string_or_none(item.get("resolver")) or "forward_bundle_expander",
                    exported_rel_path=None,
                    context_excerpt=preview_text(
                        preview_text_value
                        or detailed_text
                        or " / ".join(preview_lines),
                        220,
                    ),
                    reason=";".join(reason_parts),
                )
            )
    return output


def _collect_expired_inference_annotations(
    materials: AnalysisMaterials,
) -> list[tuple[AnalysisMessageRecord, dict[str, Any], list[dict[str, Any]]]]:
    best_by_annotation_id: dict[
        str,
        tuple[int, int, AnalysisMessageRecord, dict[str, Any], list[dict[str, Any]]],
    ] = {}

    for message in materials.messages:
        for annotation in _message_preprocess_annotations(message):
            if annotation.get("label") != "expired_asset_inference_preprocessor":
                continue
            annotation_id = _string_or_none(annotation.get("annotation_id")) or stable_digest(
                message.message_uid,
                annotation.get("summary"),
                annotation.get("source_asset_ids"),
                length=16,
            )
            matched_assets = _match_annotation_assets(message.assets, annotation)
            rank = (1 if matched_assets else 0, len(matched_assets))
            current = best_by_annotation_id.get(annotation_id)
            if current is None or rank > (current[0], current[1]):
                best_by_annotation_id[annotation_id] = (
                    rank[0],
                    rank[1],
                    message,
                    annotation,
                    matched_assets,
                )

    output = [
        (message, annotation, matched_assets)
        for _, _, message, annotation, matched_assets in best_by_annotation_id.values()
    ]
    output.sort(key=lambda item: (item[0].timestamp_ms, item[0].message_uid))
    return output


def _match_annotation_assets(
    assets: Sequence[dict[str, Any]],
    annotation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source_asset_ids = _string_list(annotation.get("source_asset_ids"))
    if not source_asset_ids:
        return []
    assets_by_id = {
        asset_id: asset
        for asset in assets
        if (asset_id := _string_or_none(asset.get("asset_id")))
    }
    return [assets_by_id[asset_id] for asset_id in source_asset_ids if asset_id in assets_by_id]


def _build_preprocess_overlay_summary(
    materials: AnalysisMaterials,
    *,
    max_overlay_items: int,
) -> BenshiPreprocessOverlaySummary | None:
    overlay_context = _as_mapping((materials.input_context or {}).get("preprocess_overlay"))
    analysis_input = _as_mapping((materials.input_context or {}).get("analysis_input"))
    input_semantics = build_material_input_semantics(materials)
    top_labels = Counter()
    representative_items: list[BenshiPreprocessOverlayItem] = []

    for message in materials.messages:
        semantics = classify_message_input_semantics(message)
        top_labels.update(semantics.labels)
        if not semantics.explicit_processed_overlay:
            continue
        if len(representative_items) >= max_overlay_items:
            continue
        representative_items.append(
            BenshiPreprocessOverlayItem(
                message_uid=message.message_uid,
                delivery_profile=semantics.delivery_profile,
                processed_text=semantics.processed_text,
                decision_summary=semantics.decision_summary,
                labels=list(semantics.labels),
                source_message_ids=list(semantics.source_message_ids),
            )
        )

    if not overlay_context and not representative_items:
        return BenshiPreprocessOverlaySummary(
            overlayed_message_count=0,
            processed_message_view_count=0,
            processed_thread_view_count=0,
            processed_asset_view_count=0,
            annotation_count=0,
            source_linked_message_count=input_semantics.source_linked_messages,
            top_labels=dict(top_labels.most_common(8)),
            representative_items=[],
            notes=list(input_semantics.notes),
        )

    directive = _as_mapping(overlay_context.get("directive")) or _as_mapping(
        analysis_input.get("directive")
    )
    notes = list(input_semantics.notes)
    if overlay_context.get("overlayed_message_count"):
        notes.append(
            f"overlay 已附着到 {overlay_context.get('overlayed_message_count')} 条消息。"
        )
    return BenshiPreprocessOverlaySummary(
        view_id=_string_or_none(overlay_context.get("view_id")) or _string_or_none(
            analysis_input.get("view_id")
        ),
        delivery_profile=_string_or_none(overlay_context.get("delivery_profile")) or _string_or_none(
            analysis_input.get("delivery_profile")
        ),
        overlayed_message_count=_int_value(overlay_context.get("overlayed_message_count")),
        processed_message_view_count=_int_value(
            overlay_context.get("processed_message_view_count")
            or analysis_input.get("processed_message_count")
        ),
        processed_thread_view_count=_int_value(
            overlay_context.get("processed_thread_view_count")
            or analysis_input.get("processed_thread_count")
        ),
        processed_asset_view_count=_int_value(
            overlay_context.get("processed_asset_view_count")
            or analysis_input.get("processed_asset_count")
        ),
        annotation_count=_int_value(
            overlay_context.get("annotation_count") or analysis_input.get("annotation_count")
        ),
        source_linked_message_count=input_semantics.source_linked_messages,
        directive_id=_string_or_none(directive.get("directive_id")),
        directive_title=_string_or_none(directive.get("title")),
        relevance_policy=_string_or_none(directive.get("relevance_policy")),
        top_labels=dict(top_labels.most_common(8)),
        representative_items=representative_items,
        notes=notes,
    )


def _build_pack_summary(
    *,
    materials: AnalysisMaterials,
    forward_summaries: Sequence[BenshiForwardSummary],
    recurrence_summaries: Sequence[BenshiRecurrenceSummary],
    missing_media_gaps: Sequence[BenshiMissingMediaGap],
    forward_degraded_asset_hints: Sequence[BenshiForwardDegradedAssetHint],
    expired_inference_summary: BenshiExpiredInferenceAggregateSummary,
    overlay_summary: BenshiPreprocessOverlaySummary | None,
    reaction_summary: BenshiReactionAggregateSummary,
) -> str:
    parts = [
        f"窗口内共有 {len(materials.messages)} 条已选消息，发送者 {materials.stats.sender_count} 人。",
        f"forward 消息 {materials.stats.forward_message_count} 条，reply 消息 {materials.stats.reply_message_count} 条。",
    ]
    if forward_summaries:
        parts.append(f"预处理层整理出 {len(forward_summaries)} 个 forward 摘要。")
    if recurrence_summaries:
        parts.append(f"检测到 {len(recurrence_summaries)} 个保守 recurrence 摘要。")
    if reaction_summary.reaction_message_count:
        parts.append(
            "群友吃史反应约 "
            f"{reaction_summary.reaction_message_count} 条，主模式="
            f"{'/'.join(reaction_summary.dominant_modes[:3]) or 'unclear'}。"
        )
    if missing_media_gaps:
        parts.append(f"当前 pack 仍有 {len(missing_media_gaps)} 个媒体缺口待解释。")
    if forward_degraded_asset_hints:
        parts.append(
            "deep forward 里还有 "
            f"{len(forward_degraded_asset_hints)} 个只能靠 preview 保守判断的退化媒体位点。"
        )
    if expired_inference_summary.inference_count:
        parts.append(
            "expired inference 已汇总 "
            f"{expired_inference_summary.inference_count} 条结果，"
            f"resolved={expired_inference_summary.resolved_count}，"
            f"uncertain={expired_inference_summary.uncertain_count}，"
            f"unrecoverable={expired_inference_summary.unrecoverable_count}。"
        )
    if overlay_summary is not None and overlay_summary.delivery_profile:
        parts.append(
            "输入已叠加 preprocess overlay，"
            f"delivery_profile={overlay_summary.delivery_profile}。"
        )
    return " ".join(parts)


def _is_reaction_candidate_message(message: AnalysisMessageRecord) -> bool:
    semantics = classify_message_input_semantics(message)
    if any(label in _DEBUGISH_LABELS for label in semantics.labels):
        return False
    if message.features.has_forward:
        return False
    text = (semantics.processed_text or message.text_content or message.content or "").strip()
    if not text:
        return False
    if len(text) <= 40:
        return True
    if message.features.has_reply and len(text) <= 120:
        return True
    return False


def _reaction_modes_for_text(text: str) -> list[str]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return []
    modes: list[str] = []
    for label, keywords in _REACTION_MODE_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            modes.append(label)
    if not modes and ("?" in normalized or "？" in normalized):
        modes.append("curiosity")
    return modes


def _extract_forward_degraded_tokens(text: str | None) -> list[tuple[str, str]]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    tokens: list[tuple[str, str]] = []
    for token_type, raw_value in _FORWARD_TOKEN_PATTERN.findall(normalized):
        asset_type = _normalize_forward_token_type(token_type)
        if asset_type not in {"video", "file"}:
            continue
        tokens.append((asset_type, raw_value.strip()))
    return tokens


def _normalize_forward_token_type(token_type: str) -> str:
    lowered = (token_type or "").strip().lower()
    if lowered == "video":
        return "video"
    if lowered in {"uploaded_file_name", "uploaded_file", "file"}:
        return "file"
    return lowered or "unknown"


def _message_preprocess_annotations(message: AnalysisMessageRecord) -> list[dict[str, Any]]:
    preprocess = _as_mapping(message.extra.get("preprocess"))
    raw = preprocess.get("annotations")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _message_context_excerpt(message: AnalysisMessageRecord) -> str | None:
    semantics = classify_message_input_semantics(message)
    candidate = (
        (semantics.processed_text or "").strip()
        or (semantics.decision_summary or "").strip()
        or (message.text_content or "").strip()
        or (message.content or "").strip()
    )
    if not candidate:
        return None
    return preview_text(candidate, 220)


def _asset_is_missing(asset: Mapping[str, Any]) -> bool:
    status = _asset_status(asset)
    if any(hint in status for hint in _MISSING_STATUS_HINTS):
        return True
    materialized = asset.get("materialized")
    if materialized is False:
        path = _string_or_none(asset.get("path"))
        exported_rel_path = _string_or_none(asset.get("exported_rel_path"))
        if not path and not exported_rel_path:
            return True
    return False


def _asset_is_materialized(asset: Mapping[str, Any]) -> bool:
    if _asset_is_missing(asset):
        return False
    materialized = asset.get("materialized")
    if materialized is None:
        return bool(_string_or_none(asset.get("path")) or _string_or_none(asset.get("exported_rel_path")))
    return bool(materialized)


def _asset_status(asset: Mapping[str, Any]) -> str:
    return (_string_or_none(asset.get("status")) or "observed").lower()


def _asset_missing_reason(asset: Mapping[str, Any]) -> str:
    status = _asset_status(asset)
    resolver = _string_or_none(asset.get("resolver"))
    file_name = _string_or_none(asset.get("file_name"))
    parts = [status]
    if resolver:
        parts.append(f"resolver={resolver}")
    if file_name:
        parts.append(f"file={file_name}")
    return "; ".join(parts)


def _counter_mapping(value: Any) -> dict[str, int]:
    mapping = _as_mapping(value)
    output: dict[str, int] = {}
    for key, item in mapping.items():
        text_key = _string_or_none(key)
        if not text_key:
            continue
        output[text_key] = _int_value(item)
    return dict(sorted(output.items()))


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = _string_or_none(item)
        if text:
            output.append(text)
    return output


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _value_from_prefixed_labels(labels: Any, prefix: str) -> str | None:
    for item in _string_list(labels):
        if item.startswith(prefix):
            return item[len(prefix) :].strip() or None
    return None


def _expired_inference_status_rank(status: str) -> int:
    order = {
        "resolved": 0,
        "uncertain": 1,
        "unrecoverable": 2,
        "info": 3,
    }
    return order.get((status or "").strip().lower(), 9)


def _is_reaction_candidate_message(message: AnalysisMessageRecord) -> bool:
    text = _reaction_message_text(message)
    if not text:
        return False
    if len(text) <= _REACTION_SHORT_TEXT_MAX:
        return True
    if message.features.has_reply and len(text) <= 64:
        return True
    if _reaction_modes_for_text(text):
        return True
    return False


def _reaction_message_text(message: AnalysisMessageRecord) -> str:
    semantics = classify_message_input_semantics(message)
    text = (
        semantics.processed_text
        or message.text_content
        or message.content
        or ""
    ).strip()
    if not text:
        return ""
    return preview_text(text, 160) or ""


def _extract_forward_internal_reaction_lines(
    summary: BenshiForwardSummary,
) -> list[dict[str, Any]]:
    source_lines = [
        line.strip()
        for line in summary.preview_lines
        if isinstance(line, str) and line.strip()
    ]
    if not source_lines and summary.detailed_text:
        source_lines = [
            line.strip()
            for line in str(summary.detailed_text).splitlines()
            if line.strip()
        ]

    output: list[dict[str, Any]] = []
    for line in source_lines:
        sender_name: str | None = None
        text = line
        if "：" in line or ":" in line:
            parts = _REACTION_SPLIT_PATTERN.split(line, maxsplit=1)
            if len(parts) == 2:
                sender_name = parts[0].strip() or None
                text = parts[1].strip()
        if not text or _FORWARD_TOKEN_PATTERN.search(text):
            continue
        if len(text) > 64 and not _reaction_modes_for_text(text):
            continue
        output.append(
            {
                "sender_name": sender_name,
                "sender_key": sender_name or stable_digest(summary.summary_id, line, length=12),
                "text": preview_text(text, 120) or text,
            }
        )
    return output


def _reaction_modes_for_text(text: str) -> list[str]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return []

    matches: list[str] = []
    for mode, keywords in _REACTION_MODE_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            matches.append(mode)
    if _REACTION_PUNCT_ONLY_PATTERN.match(normalized):
        matches.append("uniform_feedback")
    if "?" in normalized or "？" in normalized:
        matches.append("spectator")
    if len(normalized) <= 8 and any(token in normalized for token in ("典", "绷", "蚌", "草", "艹")):
        matches.append("amused_break")
    if "接" in normalized and any(token in normalized for token in ("梗", "上", "住", "续")):
        matches.append("meme_catch")
    return list(dict.fromkeys(matches))


def _normalize_reaction_text(text: str) -> str:
    normalized = (text or "").strip().lower()
    if not normalized:
        return ""
    normalized = re.sub(r"\s+", "", normalized)
    if _REACTION_PUNCT_ONLY_PATTERN.match(normalized):
        return normalized
    normalized = re.sub(r"[，。、“”\"'‘’·,\.!！~～…\-_=]+", "", normalized)
    return normalized[:48]


def _looks_like_short_reaction_text(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    if len(normalized) <= _REACTION_SHORT_TEXT_MAX:
        return True
    if _REACTION_PUNCT_ONLY_PATTERN.match(normalized):
        return True
    return False


def _reaction_actor_key(record: Mapping[str, Any]) -> str | None:
    sender_id = _string_or_none(record.get("sender_id"))
    sender_name = _string_or_none(record.get("sender_name"))
    forward_summary_id = _string_or_none(record.get("forward_summary_id"))
    if sender_id:
        return sender_id
    if sender_name:
        return f"name:{sender_name}"
    if forward_summary_id:
        return f"forward:{forward_summary_id}"
    return None


def _contains_any(text: str, needles: Sequence[str]) -> int:
    haystack = (text or "").lower()
    return int(any(needle.lower() in haystack for needle in needles))
