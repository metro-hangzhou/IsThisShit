from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from qq_data_process.utils import preview_text, stable_digest

from .models import (
    AnalysisMaterials,
    AnalysisMessageRecord,
    BenshiAnalysisPack,
    BenshiAssetAggregateSummary,
    BenshiAssetSummary,
    BenshiForwardAggregateSummary,
    BenshiForwardSummary,
    BenshiMissingMediaGap,
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


class BenshiAnalysisPackBuilder:
    def __init__(
        self,
        *,
        max_forward_summaries: int = 24,
        max_recurrence_summaries: int = 24,
        max_missing_media_gaps: int = 32,
        max_overlay_items: int = 24,
    ) -> None:
        self.max_forward_summaries = max_forward_summaries
        self.max_recurrence_summaries = max_recurrence_summaries
        self.max_missing_media_gaps = max_missing_media_gaps
        self.max_overlay_items = max_overlay_items

    def build(self, materials: AnalysisMaterials) -> BenshiAnalysisPack:
        return build_benshi_analysis_pack(
            materials,
            max_forward_summaries=self.max_forward_summaries,
            max_recurrence_summaries=self.max_recurrence_summaries,
            max_missing_media_gaps=self.max_missing_media_gaps,
            max_overlay_items=self.max_overlay_items,
        )


def build_benshi_analysis_pack(
    materials: AnalysisMaterials,
    *,
    max_forward_summaries: int = 24,
    max_recurrence_summaries: int = 24,
    max_missing_media_gaps: int = 32,
    max_overlay_items: int = 24,
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
    asset_summaries = _build_asset_summaries(materials)
    missing_media_gaps = _build_missing_media_gaps(
        materials,
        max_items=max_missing_media_gaps,
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
    )
    shi_description_profile = _build_shi_description_profile(
        materials=materials,
        component_summaries=shi_component_summaries,
        missing_media_gaps=missing_media_gaps,
    )

    return BenshiAnalysisPack(
        run_id=materials.run_id,
        target=materials.target,
        chosen_time_window=materials.chosen_time_window,
        pack_summary=_build_pack_summary(
            materials=materials,
            forward_summaries=forward_summaries,
            recurrence_summaries=recurrence_summaries,
            missing_media_gaps=missing_media_gaps,
            overlay_summary=overlay_summary,
        ),
        stats=materials.stats,
        selected_messages=selected_messages,
        forward_summary=forward_aggregate,
        forward_summaries=forward_summaries,
        recurrence_summary=recurrence_aggregate,
        recurrence_summaries=recurrence_summaries,
        participant_role_candidates=participant_role_candidates,
        asset_summary=asset_aggregate,
        asset_summaries=asset_summaries,
        shi_component_summaries=shi_component_summaries,
        shi_description_profile=shi_description_profile,
        missing_media_gaps=missing_media_gaps,
        preprocess_overlay_summary=overlay_summary,
        warnings=list(materials.warnings),
    )


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

    component_candidates.sort(
        key=lambda item: (-item.score, item.component_family, item.component_label)
    )
    return component_candidates[:12]


def _build_shi_description_profile(
    *,
    materials: AnalysisMaterials,
    component_summaries: Sequence[BenshiShiComponentSummary],
    missing_media_gaps: Sequence[BenshiMissingMediaGap],
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

    return BenshiShiDescriptionProfile(
        base_definition=(
            "史不是单纯离谱内容，而是在群聊/截图/转发语境里，因为抽象性、认知错位和搬运包浆，"
            "被围观者迅速识别为值得围观、值得转运的内容单位。"
        ),
        description_strategy=(
            "先交代这窗是原生还是外源/二手，再交代 forward、图串、返场、单人倾倒这些搬运结构，"
            "最后再说抽象点、包浆点和未知边界。"
        ),
        description_axes=[
            "来源路径：原生、外源、二手还是返场回放",
            "搬运结构：forward、套娃、图串、单人倾倒、中转站感",
            "史味机制：认知落差、包浆、工业复读、截图壳、配文壳",
            "媒体依赖：是靠文本立、靠图壳立，还是靠缺失媒体周边语境勉强成立",
            "未知边界：哪些媒体位点缺失，哪些结论只能保守说",
        ],
        descriptive_tags=dominant_labels,
        good_description_patterns=[
            f"这窗更像一批 {component_phrase} 叠在一起的搬运拼盘，不是单条神贴。",
            "真正的史味不只在内容本身，还在套娃转发、返场补档和群体回声形成的包浆。",
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
        ],
    )


def _build_missing_media_gaps(
    materials: AnalysisMaterials,
    *,
    max_items: int,
) -> list[BenshiMissingMediaGap]:
    output: list[BenshiMissingMediaGap] = []
    for message in materials.messages:
        context_excerpt = _message_context_excerpt(message)
        for asset in message.assets:
            if not _asset_is_missing(asset):
                continue
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
    return output


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
    overlay_summary: BenshiPreprocessOverlaySummary | None,
) -> str:
    parts = [
        f"窗口内共有 {len(materials.messages)} 条已选消息，发送者 {materials.stats.sender_count} 人。",
        f"forward 消息 {materials.stats.forward_message_count} 条，reply 消息 {materials.stats.reply_message_count} 条。",
    ]
    if forward_summaries:
        parts.append(f"预处理层整理出 {len(forward_summaries)} 个 forward 摘要。")
    if recurrence_summaries:
        parts.append(f"检测到 {len(recurrence_summaries)} 个保守 recurrence 摘要。")
    if missing_media_gaps:
        parts.append(f"当前 pack 仍有 {len(missing_media_gaps)} 个媒体缺口待解释。")
    if overlay_summary is not None and overlay_summary.delivery_profile:
        parts.append(
            "输入已叠加 preprocess overlay，"
            f"delivery_profile={overlay_summary.delivery_profile}。"
        )
    return " ".join(parts)


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


def _contains_any(text: str, needles: Sequence[str]) -> int:
    haystack = (text or "").lower()
    return int(any(needle.lower() in haystack for needle in needles))
