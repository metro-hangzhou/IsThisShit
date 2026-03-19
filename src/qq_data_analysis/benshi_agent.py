from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .benshi_pack import build_benshi_analysis_pack
from .models import AnalysisAgentOutput, AnalysisEvidenceItem, AnalysisMaterials
from .models import BenshiAnalysisPack
from .summary import build_input_semantics_lines


@dataclass(slots=True)
class BenshiPreparedPack:
    target_id: str
    target_name: str | None
    start_iso: str
    end_iso: str
    message_count: int
    sender_count: int
    top_tags: list[tuple[str, int]] = field(default_factory=list)
    top_people: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[AnalysisEvidenceItem] = field(default_factory=list)
    input_semantics: Any = None
    delivery_profile: str | None = None
    annotation_count: int = 0
    missing_media_summary: dict[str, Any] = field(default_factory=dict)
    transport_signals: list[str] = field(default_factory=list)
    cultural_cues: list[str] = field(default_factory=list)
    participant_roles: list[dict[str, Any]] = field(default_factory=list)
    pack: BenshiAnalysisPack | None = None


class BenshiMasterAgent:
    agent_name = "benshi_master"
    agent_version = "v0"

    def serialize_result(self, output: AnalysisAgentOutput) -> dict[str, Any]:
        return output.compact_payload

    def prepare(self, materials: AnalysisMaterials) -> BenshiAnalysisPack:
        return build_benshi_analysis_pack(materials)

    def analyze(
        self, materials: AnalysisMaterials, prepared: BenshiPreparedPack | Any
    ) -> AnalysisAgentOutput:
        pack = self._coerce_pack(materials, prepared)
        shi_presence = self._judge_shi_presence(pack)
        shi_types = self._infer_shi_type_candidates(pack)
        quality_band = self._infer_quality_band(pack, shi_presence, shi_types)
        structured_evidence = self._build_structured_evidence(pack, shi_presence, shi_types, quality_band)
        shi_component_analysis = self._build_shi_component_analysis(
            pack,
            shi_presence,
            shi_types,
            quality_band,
        )
        shi_description_layer = self._build_shi_description_layer(
            pack,
            shi_presence,
            shi_types,
            quality_band,
            shi_component_analysis,
        )
        cultural_interpretation = self._build_cultural_interpretation(
            pack, shi_presence, shi_types, quality_band
        )
        register_layer = self._build_register_layer(pack, shi_presence, shi_types, quality_band)
        reply_probe = self._build_reply_probe_placeholder(pack, shi_presence, shi_types)

        report_lines = [
            "## Benshi Master",
            f"- 分析对象: {pack.target_name or pack.target_id}",
            f"- 时间窗口: {pack.start_iso} -> {pack.end_iso}",
            f"- 消息数: {pack.message_count}",
            f"- 参与者数: {pack.sender_count}",
            f"- 史存在判断: {shi_presence['label']} (score={shi_presence['score']:.2f})",
            "- 史类型候选: "
            + (" / ".join(f"{item['label']}({item['score']:.2f})" for item in shi_types) or "未定型"),
            f"- 史质量带: {quality_band['label']}",
        ]
        report_lines.extend(build_input_semantics_lines(materials))
        if structured_evidence["direct_observations"]:
            report_lines.append("- 直接观察:")
            for item in structured_evidence["direct_observations"]:
                report_lines.append(f"  - {item}")
        if structured_evidence["context_inferences"]:
            report_lines.append("- 语境推断:")
            for item in structured_evidence["context_inferences"]:
                report_lines.append(f"  - {item}")
        if cultural_interpretation["why_this_is_shi"]:
            report_lines.append("- 为什么它是史:")
            for item in cultural_interpretation["why_this_is_shi"]:
                report_lines.append(f"  - {item}")
        if shi_component_analysis["dominant_components"]:
            report_lines.append("- 史成分分析:")
            report_lines.append(
                "  - 主成分: "
                + " / ".join(shi_component_analysis["dominant_components"])
            )
            for item in shi_component_analysis["component_rationale"]:
                report_lines.append(f"  - {item}")
        if shi_description_layer["one_line_definition"]:
            report_lines.append("- 史描述层:")
            report_lines.append(f"  - 一句话定义: {shi_description_layer['one_line_definition']}")
            report_lines.append(
                f"  - 建议描述方式: {shi_description_layer['how_to_describe_this_shi']}"
            )
        if cultural_interpretation["resonance_notes"]:
            report_lines.append("- 共振/搬运机制:")
            for item in cultural_interpretation["resonance_notes"]:
                report_lines.append(f"  - {item}")
        report_lines.append("- 口吻层输出:")
        report_lines.append(f"  - {register_layer['rendered_commentary']}")
        report_lines.append("- 接茬探针:")
        report_lines.append(
            f"  - enabled={reply_probe['reply_probe_enabled']} | note={reply_probe['note']}"
        )

        return AnalysisAgentOutput(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            human_report="\n".join(report_lines),
            compact_payload={
                "evidence_layer": structured_evidence,
                "structured_evidence": structured_evidence,
                "shi_component_analysis_layer": shi_component_analysis,
                "shi_component_analysis": shi_component_analysis,
                "shi_description_layer": shi_description_layer,
                "cultural_interpretation_layer": cultural_interpretation,
                "cultural_interpretation": cultural_interpretation,
                "register_layer": register_layer,
                "reply_probe_layer": reply_probe,
                "reply_probe": reply_probe,
                "pack_summary": {
                    "target_id": pack.target_id,
                    "target_name": pack.target_name,
                    "start_iso": pack.start_iso,
                    "end_iso": pack.end_iso,
                    "message_count": pack.message_count,
                    "sender_count": pack.sender_count,
                    "delivery_profile": pack.delivery_profile,
                    "annotation_count": pack.annotation_count,
                    "top_tags": [
                        {"label": label, "count": count}
                        for label, count in pack.top_tags
                    ],
                    "transport_signals": pack.transport_signals,
                },
            },
            evidence=list(pack.evidence),
            warnings=[],
        )

    def _coerce_pack(
        self, materials: AnalysisMaterials, prepared: BenshiPreparedPack | Any
    ) -> BenshiPreparedPack:
        if isinstance(prepared, BenshiPreparedPack):
            return prepared
        if isinstance(prepared, BenshiAnalysisPack):
            return self._pack_to_prepared(prepared)
        # Future-compatible duck typing for a later shared BenshiAnalysisPack.
        top_tags = []
        for item in getattr(prepared, "top_tags", []) or []:
            if isinstance(item, tuple) and len(item) == 2:
                top_tags.append((str(item[0]), int(item[1])))
            elif isinstance(item, dict):
                top_tags.append((str(item.get("label", "")), int(item.get("count", 0))))
        return BenshiPreparedPack(
            target_id=str(getattr(prepared, "target_id", materials.target.display_id)),
            target_name=getattr(prepared, "target_name", materials.target.display_name),
            start_iso=str(getattr(prepared, "start_iso", materials.chosen_time_window.start_timestamp_iso)),
            end_iso=str(getattr(prepared, "end_iso", materials.chosen_time_window.end_timestamp_iso)),
            message_count=int(getattr(prepared, "message_count", materials.stats.message_count)),
            sender_count=int(getattr(prepared, "sender_count", materials.stats.sender_count)),
            top_tags=top_tags or [
                (item.tag, item.count)
                for item in materials.tag_summaries[:8]
                if item.count > 0
            ],
            top_people=list(getattr(prepared, "top_people", [])),
            evidence=list(getattr(prepared, "evidence", [])),
            input_semantics=getattr(prepared, "input_semantics", build_material_input_semantics(materials)),
            delivery_profile=getattr(prepared, "delivery_profile", None),
            annotation_count=int(getattr(prepared, "annotation_count", 0)),
            missing_media_summary=dict(getattr(prepared, "missing_media_summary", {})),
            transport_signals=list(getattr(prepared, "transport_signals", [])),
            cultural_cues=list(getattr(prepared, "cultural_cues", [])),
            participant_roles=list(getattr(prepared, "participant_roles", [])),
            pack=getattr(prepared, "pack", None),
        )

    def _pack_to_prepared(self, pack: BenshiAnalysisPack) -> BenshiPreparedPack:
        tag_counter = Counter()
        evidence: list[AnalysisEvidenceItem] = []
        seen_message_uids: set[str] = set()
        for item in pack.selected_messages:
            tag_counter.update(item.message_tags)
            if item.message_uid in seen_message_uids:
                continue
            if len(evidence) < 8 and (
                item.has_forward
                or item.asset_count
                or item.missing_media_count
                or item.message_tags
            ):
                evidence.append(
                    AnalysisEvidenceItem(
                        message_uid=item.message_uid,
                        timestamp_iso=item.timestamp_iso,
                        sender_id=item.sender_id,
                        sender_name=item.sender_name,
                        content=item.processed_text or item.content,
                        reason="benshi_pack_selected_message",
                        tags=list(item.message_tags),
                    )
                )
                seen_message_uids.add(item.message_uid)
        top_tags = tag_counter.most_common(8)
        participant_roles = [
            {
                "sender_id": item.sender_id,
                "sender_name": item.sender_name,
                "message_count": item.message_count,
                "candidate_roles": list(item.candidate_roles),
                "notes": list(item.notes),
                "evidence_message_uids": list(item.evidence_message_uids),
            }
            for item in pack.participant_role_candidates[:5]
        ]
        transport_signals = self._build_transport_signals_from_pack(pack)
        cultural_cues = self._build_cultural_cues_from_pack(pack, top_tags, transport_signals)
        overlay = pack.preprocess_overlay_summary
        return BenshiPreparedPack(
            target_id=pack.target.display_id,
            target_name=pack.target.display_name,
            start_iso=pack.chosen_time_window.start_timestamp_iso,
            end_iso=pack.chosen_time_window.end_timestamp_iso,
            message_count=pack.stats.message_count,
            sender_count=pack.stats.sender_count,
            top_tags=top_tags,
            top_people=participant_roles,
            evidence=evidence,
            input_semantics=overlay,
            delivery_profile=(overlay.delivery_profile if overlay else "raw_only"),
            annotation_count=(overlay.annotation_count if overlay else 0),
            missing_media_summary=self._build_missing_media_summary_from_pack(pack),
            transport_signals=transport_signals,
            cultural_cues=cultural_cues,
            participant_roles=participant_roles,
            pack=pack,
        )

    def _collect_evidence(
        self, materials: AnalysisMaterials, *, limit: int
    ) -> list[AnalysisEvidenceItem]:
        evidence: list[AnalysisEvidenceItem] = []
        seen: set[str] = set()
        for event in materials.candidate_events:
            for item in event.evidence:
                if item.message_uid in seen:
                    continue
                evidence.append(item)
                seen.add(item.message_uid)
                if len(evidence) >= limit:
                    return evidence
        for person in materials.participant_profiles:
            for item in person.evidence:
                if item.message_uid in seen:
                    continue
                evidence.append(item)
                seen.add(item.message_uid)
                if len(evidence) >= limit:
                    return evidence
        return evidence

    def _build_missing_media_summary(self, materials: AnalysisMaterials) -> dict[str, Any]:
        coverage = materials.manifest_media_coverage
        if coverage is None:
            return {"present": False}
        total_missing = (
            coverage.missing_image_count
            + coverage.missing_file_count
            + coverage.missing_sticker_count
            + coverage.missing_video_count
            + coverage.missing_speech_count
        )
        return {
            "present": True,
            "missing_total": total_missing,
            "missing_image_count": coverage.missing_image_count,
            "missing_file_count": coverage.missing_file_count,
            "missing_sticker_count": coverage.missing_sticker_count,
            "missing_video_count": coverage.missing_video_count,
            "missing_speech_count": coverage.missing_speech_count,
            "overall_missing_ratio": coverage.overall_media_missing_ratio,
        }

    def _build_missing_media_summary_from_pack(self, pack: BenshiAnalysisPack) -> dict[str, Any]:
        type_counter = Counter(item.asset_type for item in pack.missing_media_gaps)
        return {
            "present": True,
            "missing_total": len(pack.missing_media_gaps),
            "missing_by_type": dict(type_counter),
            "top_missing_files": [
                item.file_name
                for item in pack.missing_media_gaps
                if item.file_name
            ][:8],
        }

    def _build_transport_signals(
        self, materials: AnalysisMaterials, top_tags: list[tuple[str, int]]
    ) -> list[str]:
        tag_map = {label: count for label, count in top_tags}
        signals: list[str] = []
        if tag_map.get("forward_nested", 0):
            signals.append("套娃转发显著")
        if tag_map.get("forward_burst", 0):
            signals.append("存在集中倒史/批量转发")
        if tag_map.get("share_marker", 0):
            signals.append("夹带外源分享/卡片线索")
        if tag_map.get("repetitive_noise", 0):
            signals.append("存在复读式搬运或噪声扩散")
        if materials.theme_queries:
            signals.append("可继续围绕主题检索做二次吃史")
        return signals

    def _build_transport_signals_from_pack(self, pack: BenshiAnalysisPack) -> list[str]:
        signals: list[str] = []
        if pack.forward_summary.forward_message_count:
            signals.append(
                f"forward 消息密集（{pack.forward_summary.forward_message_count} 条）"
            )
        if pack.forward_summary.nested_forward_count:
            signals.append(
                f"存在套娃 forward（{pack.forward_summary.nested_forward_count} 条）"
            )
        if pack.recurrence_summary.repeated_asset_cluster_count:
            signals.append(
                "存在重复搬运/复现簇"
                f"（{pack.recurrence_summary.repeated_asset_cluster_count} 组）"
            )
        if pack.asset_summary.asset_type_reference_counts:
            rich_types = [
                f"{label}:{count}"
                for label, count in list(pack.asset_summary.asset_type_reference_counts.items())[:4]
            ]
            signals.append("媒体负载=" + " / ".join(rich_types))
        if pack.missing_media_gaps:
            signals.append(f"有 {len(pack.missing_media_gaps)} 个失活或缺口媒体位点")
        return signals

    def _build_cultural_cues(
        self, materials: AnalysisMaterials, top_tags: list[tuple[str, int]]
    ) -> list[str]:
        tag_map = {label: count for label, count in top_tags}
        cues: list[str] = []
        if tag_map.get("absurd_or_bizarre", 0):
            cues.append("认知落差明显")
        if tag_map.get("confusing_context", 0):
            cues.append("语境错位/脱水后仍有槽点")
        if tag_map.get("forward_nested", 0) or tag_map.get("forward_burst", 0):
            cues.append("二手转运/套娃包浆感较强")
        if tag_map.get("repetitive_noise", 0):
            cues.append("反馈整齐度与机械复读倾向存在")
        if materials.stats.image_ratio >= 0.35:
            cues.append("视觉载荷高，图像承担了大量笑点或冲击")
        return cues

    def _build_cultural_cues_from_pack(
        self,
        pack: BenshiAnalysisPack,
        top_tags: list[tuple[str, int]],
        transport_signals: list[str],
    ) -> list[str]:
        tag_map = {label: count for label, count in top_tags}
        cues: list[str] = []
        if tag_map.get("absurd_or_bizarre", 0):
            cues.append("认知落差明显")
        if tag_map.get("confusing_context", 0):
            cues.append("语境错位/脱水后仍有槽点")
        if pack.forward_summary.nested_forward_count or pack.recurrence_summary.repeated_asset_cluster_count:
            cues.append("二手转运/套娃包浆感较强")
        if tag_map.get("repetitive_noise", 0) or pack.recurrence_summary.repeated_transport_count >= 3:
            cues.append("反馈整齐度与机械复读倾向存在")
        if pack.asset_summary.asset_type_reference_counts.get("image", 0) >= max(1, pack.stats.message_count // 3):
            cues.append("视觉载荷高，图像承担了大量笑点或冲击")
        if not cues and transport_signals:
            cues.append("搬运结构明显，但文化解释还需后续 LLM 细化")
        return cues

    def _judge_shi_presence(self, pack: BenshiPreparedPack) -> dict[str, Any]:
        tag_map = {label: count for label, count in pack.top_tags}
        score = 0.0
        score += 2.2 if tag_map.get("forward_nested", 0) else 0.0
        score += 1.8 if tag_map.get("forward_burst", 0) else 0.0
        score += 1.2 if tag_map.get("absurd_or_bizarre", 0) else 0.0
        score += 1.0 if tag_map.get("confusing_context", 0) else 0.0
        score += 0.8 if tag_map.get("repetitive_noise", 0) else 0.0
        score += 0.6 if pack.message_count >= 20 else 0.0
        score += 0.4 if pack.sender_count <= 3 else 0.0
        label = "不确定"
        if score >= 5.0:
            label = "明显存在"
        elif score >= 2.5:
            label = "弱到中等存在"
        return {
            "label": label,
            "score": round(score, 2),
            "evidence_basis": list(pack.cultural_cues),
        }

    def _infer_shi_type_candidates(self, pack: BenshiPreparedPack) -> list[dict[str, Any]]:
        tag_map = {label: count for label, count in pack.top_tags}
        candidates: list[dict[str, Any]] = []
        if tag_map.get("forward_nested", 0):
            candidates.append(
                {"label": "二手史", "score": 0.86, "why": "套娃转发/二手转运痕迹明显"}
            )
        if tag_map.get("forward_burst", 0) or tag_map.get("share_marker", 0):
            candidates.append(
                {"label": "外源史", "score": 0.73, "why": "存在集中搬运和外源输入信号"}
            )
        if tag_map.get("repetitive_noise", 0) and tag_map.get("low_information", 0):
            candidates.append(
                {"label": "工业史", "score": 0.64, "why": "重复、低信息、流水线转运感较强"}
            )
        if tag_map.get("absurd_or_bizarre", 0) and not tag_map.get("forward_nested", 0):
            candidates.append(
                {"label": "原生史", "score": 0.55, "why": "怪诞感较强且未完全依赖二手套娃结构"}
            )
        if tag_map.get("forward_nested", 0) and tag_map.get("absurd_or_bizarre", 0):
            candidates.append(
                {"label": "混合/二阶史", "score": 0.69, "why": "原始怪诞感与二手转运结构叠加"}
            )
        if not candidates:
            candidates.append(
                {"label": "未定型", "score": 0.35, "why": "当前窗口更像普通噪声/混杂聊天"}
            )
        return candidates[:4]

    def _infer_quality_band(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
    ) -> dict[str, Any]:
        top_type = shi_types[0]["label"] if shi_types else "未定型"
        score = shi_presence["score"]
        if score >= 5.5 and top_type in {"二手史", "混合/二阶史", "外源史"}:
            label = "高价值"
        elif score >= 3.5:
            label = "中价值"
        elif score >= 2.0:
            label = "低价值"
        else:
            label = "不确定"
        if top_type == "工业史" and score >= 2.5:
            label = "工业废史"
        return {"label": label, "top_type": top_type, "score": round(score, 2)}

    def _build_structured_evidence(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
        quality_band: dict[str, Any],
    ) -> dict[str, Any]:
        direct_observations = [
            f"窗口内共有 {pack.message_count} 条消息，参与者 {pack.sender_count} 人",
            "高频标签: " + " / ".join(f"{label}({count})" for label, count in pack.top_tags[:5]),
        ]
        if pack.transport_signals:
            direct_observations.append("搬运信号: " + "；".join(pack.transport_signals))
        context_inferences = [
            f"当前更像 {quality_band['top_type']} 主导的窗口"
        ]
        if pack.cultural_cues:
            context_inferences.append("文化线索: " + "；".join(pack.cultural_cues))
        if pack.missing_media_summary.get("present") and pack.missing_media_summary.get("missing_total", 0):
            context_inferences.append(
                "存在缺失媒体，需要保留未知区，不把缺失内容硬推成事实"
            )
        return {
            "target": {
                "display_id": pack.target_id,
                "display_name": pack.target_name,
            },
            "shi_presence": shi_presence,
            "shi_type_candidates": shi_types,
            "shi_quality_band": quality_band,
            "direct_observations": direct_observations,
            "context_inferences": context_inferences,
            "missing_media_gaps": pack.missing_media_summary,
            "transport_pattern": pack.transport_signals,
            "participant_roles": pack.participant_roles or pack.top_people,
            "confidence": round(
                min(
                    1.0,
                    max(
                        shi_presence.get("score", 0.0) / 6.0,
                        (shi_types[0].get("score", 0.0) if shi_types else 0.0),
                    ),
                ),
                3,
            ),
        }

    def _build_shi_component_analysis(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
        quality_band: dict[str, Any],
    ) -> dict[str, Any]:
        pack_model = pack.pack
        component_candidates = []
        if pack_model is not None:
            component_candidates.extend(
                {
                    "label": item.component_label,
                    "family": item.component_family,
                    "score": round(float(item.score), 3),
                    "reasons": list(item.evidence_basis),
                    "evidence_message_uids": list(item.evidence_message_uids),
                    "notes": list(item.notes),
                }
                for item in pack_model.shi_component_summaries
            )
            if pack_model.image_cluster_summaries:
                recurrent_bundle_clusters = [
                    item
                    for item in pack_model.image_cluster_summaries
                    if item.cluster_kind in {"context_bundle_recurrent", "visual_recurrence"}
                    and item.distinct_message_count >= 2
                ]
                if recurrent_bundle_clusters:
                    component_candidates.append(
                        {
                            "label": "图串重复回放",
                            "family": "transport",
                            "score": 0.79,
                            "reasons": [
                                f"图像簇里有 {len(recurrent_bundle_clusters)} 组重复返场。",
                                "说明这窗不是一次性投喂，而是库存反复回放。",
                            ],
                            "evidence_message_uids": sorted(
                                {
                                    uid
                                    for item in recurrent_bundle_clusters
                                    for uid in item.evidence_message_uids
                                }
                            )[:8],
                            "notes": [
                                item.cluster_id for item in recurrent_bundle_clusters[:4]
                            ],
                        }
                    )
        deduped: dict[str, dict[str, Any]] = {}
        for item in component_candidates:
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            if label not in deduped or float(item.get("score") or 0.0) > float(deduped[label].get("score") or 0.0):
                deduped[label] = item

        ordered = sorted(
            deduped.values(),
            key=lambda item: (-float(item.get("score") or 0.0), str(item.get("family") or ""), str(item.get("label") or "")),
        )
        dominant_components = [str(item.get("label")) for item in ordered[:5]]
        transport_components = [
            str(item.get("label"))
            for item in ordered
            if str(item.get("family")) in {"transport", "provenance"}
        ]
        content_components = [
            str(item.get("label"))
            for item in ordered
            if str(item.get("family")) in {"content", "packaging", "social", "uncertainty"}
        ]
        component_rationale: list[str] = []
        top_type = shi_types[0]["label"] if shi_types else "未定型"
        if dominant_components:
            component_rationale.append(
                f"这窗最强的史成分不是单一爆点，而是 {', '.join(dominant_components[:4])} 叠在一起。"
            )
        if top_type != "未定型":
            component_rationale.append(
                f"类型判断上目前仍以 {top_type} 为主轴，成分层是在解释它为什么会往这个方向偏。"
            )
        if pack.missing_media_summary.get("missing_total", 0):
            component_rationale.append("窗口里有缺失媒体位点，所以成分层允许保留‘视频壳缺本体’这类未知项。")
        return {
            "definition": (
                "史不是单条离谱内容本身，而是内容、搬运、包装、群体回声和包浆一起作用后，"
                "在群聊里被快速识别成‘值得围观/值得搬运’的东西。"
            ),
            "component_candidates": ordered,
            "dominant_components": dominant_components,
            "transport_components": transport_components,
            "content_components": content_components,
            "component_rationale": component_rationale,
            "confidence": round(
                min(
                    1.0,
                    max(
                        float(shi_presence.get("score") or 0.0) / 6.0,
                        float(ordered[0].get("score") or 0.0) if ordered else 0.0,
                    ),
                ),
                3,
            ),
            "quality_band": quality_band["label"],
        }

    def _build_shi_description_layer(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
        quality_band: dict[str, Any],
        shi_component_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        pack_model = pack.pack
        profile = pack_model.shi_description_profile if pack_model is not None else None
        dominant_components = list(shi_component_analysis.get("dominant_components") or [])
        top_type = shi_types[0]["label"] if shi_types else "未定型"
        one_line_definition = (
            f"这窗更像一批以{top_type}为主轴、同时叠着{'、'.join(dominant_components[:3]) or '搬运包浆'}的集中倒货。"
        )
        component_breakdown = [
            {
                "label": item.get("label"),
                "family": item.get("family"),
                "score": item.get("score"),
                "why": (item.get("reasons") or [None])[0],
            }
            for item in (shi_component_analysis.get("component_candidates") or [])[:6]
        ]
        descriptive_tags = list(dict.fromkeys((profile.descriptive_tags if profile else []) + dominant_components))[:8]
        unknown_boundaries: list[str] = []
        if pack.missing_media_summary.get("missing_total", 0):
            unknown_boundaries.append(
                f"当前窗口还有 {pack.missing_media_summary['missing_total']} 个失活/缺失媒体位点，相关内容只能保守描述。"
            )
        if not pack.pack or not pack.pack.image_caption_samples:
            unknown_boundaries.append("并不是所有图片都被直接 caption 过，所以这里仍然保留一部分未知图片区。")
        if shi_presence.get("label") == "不确定":
            unknown_boundaries.append("这窗史感并不算压倒性明确，描述时要保留‘可能/偏向’而不是装成铁案。")

        how_to_describe = (
            "先说这是一批什么路数的史，再说它靠什么搬运结构成立，最后补一句包浆/返场/截图壳或未知边界。"
        )
        return {
            "what_is_shi_definition": profile.base_definition if profile else None,
            "one_line_definition": one_line_definition,
            "component_breakdown": component_breakdown,
            "descriptive_tags": descriptive_tags,
            "how_to_describe_this_shi": how_to_describe,
            "description_axes": list(profile.description_axes if profile else []),
            "good_description_patterns": list(profile.good_description_patterns if profile else []),
            "bad_description_patterns": list(profile.bad_description_patterns if profile else []),
            "unknown_boundaries": unknown_boundaries,
            "example_descriptors": list(profile.example_descriptors if profile else []),
            "quality_band": quality_band["label"],
        }

    def _build_cultural_interpretation(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
        quality_band: dict[str, Any],
    ) -> dict[str, Any]:
        why_this_is_shi: list[str] = []
        if "认知落差明显" in pack.cultural_cues:
            why_this_is_shi.append("内容本身有明显认知落差，容易让围观者第一时间进入“这也行？”状态")
        if "语境错位/脱水后仍有槽点" in pack.cultural_cues:
            why_this_is_shi.append("脱离原始语境后仍能成立，说明它的荒诞点不是小圈子内部梗，而是可搬运的公共槽点")
        if "二手转运/套娃包浆感较强" in pack.cultural_cues:
            why_this_is_shi.append("多层 forward 和二手转运结构本身就在给这坨史加包浆")
        if "反馈整齐度与机械复读倾向存在" in pack.cultural_cues:
            why_this_is_shi.append("它不只是被看见，还带起了重复扩散和机械复读，这说明搬运价值不低")
        if not why_this_is_shi:
            why_this_is_shi.append("这段材料目前更像混合噪声，史感存在但还不够到一眼封神")
        top_type = shi_types[0]["label"] if shi_types else "未定型"
        absurdity = {
            "原生史": "更像原生逆天，笑点集中在内容本身的离谱和自洽崩坏",
            "工业史": "笑点主要不在原创性，而在流水线搬运、低信息复读和审美疲劳",
            "典中典史": "这类东西如果能反复跨群成立，就会往典中典靠",
            "外源史": "看起来更像外部平台素材被运进群里再二次发酵",
            "二手史": "真正的劲儿来自二手转运和套娃围观，而不是某一条孤立原文",
            "混合/二阶史": "本体荒诞和搬运结构叠在一起，属于复合型史",
            "未定型": "当前还不足以强行定型，先保守处理",
        }.get(top_type, "当前类型尚不稳定")
        return {
            "why_this_is_shi": why_this_is_shi,
            "absurdity_mechanism": absurdity,
            "context_collapse_mechanism": "群聊语境被压缩后，仍能保留核心槽点",
            "packaging_or_patina_notes": pack.transport_signals or ["暂未看到显著包浆信号"],
            "resonance_notes": pack.cultural_cues or ["当前共振线索有限"],
            "quality_assessment": quality_band["label"],
            "classicness_potential": "中等" if quality_band["label"] in {"高价值", "中价值"} else "偏低/待观察",
        }

    def _build_register_layer(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
        quality_band: dict[str, Any],
    ) -> dict[str, Any]:
        top_type = shi_types[0]["label"] if shi_types else "未定型"
        commentary = (
            f"这窗东西整体上是{top_type}味儿偏重，史感判断是{shi_presence['label']}。"
            f"要是按群友视角说，就是这坨东西不只是抽象，主要还带着一股被人捞出来反复倒的包浆味。"
        )
        if quality_band["label"] == "工业废史":
            commentary = (
                "这窗更像工业流水线废史，量是有了，劲儿一般，属于会让人说“你先自己看完再转”的那种。"
            )
        elif quality_band["label"] == "高价值":
            commentary = (
                "这窗属于能端上桌细吃的史，不是单纯刷屏，而是本体、转运、围观反应都能咬出点东西。"
            )
        return {
            "voice_profile": "cn_high_context_benshi_commentator_v1",
            "register_constraints": [
                "允许抽象吐槽，但不能编造缺失媒体内容",
                "允许网友口吻，但证据层优先",
                "优先像懂梗的群友，不像写公文的分析师",
            ],
            "rendered_commentary": commentary,
        }

    def _build_reply_probe_placeholder(
        self,
        pack: BenshiPreparedPack,
        shi_presence: dict[str, Any],
        shi_types: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if shi_presence["score"] < 3.5:
            return {
                "enabled": False,
                "status": "disabled",
                "reply_probe_enabled": False,
                "candidate_followups": [],
                "followup_rationale": [],
                "followup_confidence": 0.0,
                "note": "当前窗口史感不够集中，先不做接茬探针。",
            }
        top_type = shi_types[0]["label"] if shi_types else "未定型"
        return {
            "enabled": False,
            "status": "placeholder",
            "reply_probe_enabled": False,
            "candidate_followups": [],
            "followup_rationale": [
                f"当前已经识别到 {top_type} 倾向，但接茬生成仍应放到后续独立 probe/prompt 阶段。"
            ],
            "followup_confidence": 0.0,
            "note": "reply_probe 先保留占位，不在 deterministic skeleton 阶段硬生成。",
        }
