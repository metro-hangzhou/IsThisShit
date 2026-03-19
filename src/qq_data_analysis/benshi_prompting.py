from __future__ import annotations

import json
from typing import Any

from qq_data_process.utils import preview_text

from .models import BenshiAnalysisPack

from pydantic import BaseModel, Field


DEFAULT_BENSHI_REASONING_EFFORT = "medium"
DEFAULT_BENSHI_TEMPERATURE = 0.0
DEFAULT_BENSHI_VOICE_PROFILE = "cn_chonglang_benshi_v1"
DEFAULT_BENSHI_REPLY_PROBE_ENABLED = False
_DEBUGISH_LABELS = {
    "runtime_debug",
    "cli_workflow",
    "dev_ops",
    "analysis_dev",
    "strict_focus_non_target",
    "low_signal_chatter",
}


class BenshiVoiceProfile(BaseModel):
    profile_id: str = DEFAULT_BENSHI_VOICE_PROFILE
    profile_label: str = "高强度冲浪群友旁白"
    register_summary: str = (
        "更像长期泡在中文互联网、QQ群和抽象梗语境里的普通网友，"
        "能说人话，也会说怪话，但不是装疯卖傻。"
    )
    tone_rules: list[str] = Field(
        default_factory=lambda: [
            "不要写成正经学术报告，也不要写成客服腔。",
            "允许使用中文互联网常见口癖、黑话、梗内简称，但不要为了口癖破坏可读性。",
            "可以点出荒诞、包浆、工业流水线、低智转运、典中典，但不要把未知说成已知。",
            "遇到证据不足时，先老实说不确定，再给上下文推断，不要编图像或媒体事实。",
            "语气可以损、可以阴阳，但不要把证据层污染成纯发癫输出。",
        ]
    )


class BenshiStructuredOutputContract(BaseModel):
    contract_version: str = "benshi_master_v1"
    required_top_level_keys: list[str] = Field(
        default_factory=lambda: [
            "contract_version",
            "analysis_mode",
            "voice_profile",
            "evidence_layer",
            "shi_component_analysis",
            "shi_description_layer",
            "cultural_interpretation",
            "register_rendering",
            "reply_probe",
        ]
    )
    shi_component_analysis_keys: list[str] = Field(
        default_factory=lambda: [
            "definition",
            "component_candidates",
            "dominant_components",
            "transport_components",
            "content_components",
            "component_rationale",
            "confidence",
        ]
    )
    shi_description_layer_keys: list[str] = Field(
        default_factory=lambda: [
            "what_is_shi_definition",
            "one_line_definition",
            "component_breakdown",
            "descriptive_tags",
            "how_to_describe_this_shi",
            "good_description_patterns",
            "bad_description_patterns",
            "unknown_boundaries",
        ]
    )
    evidence_layer_keys: list[str] = Field(
        default_factory=lambda: [
            "direct_observations",
            "context_inferences",
            "unknowns",
            "transport_pattern",
            "shi_presence",
            "shi_type_candidates",
            "confidence_notes",
        ]
    )
    cultural_interpretation_keys: list[str] = Field(
        default_factory=lambda: [
            "why_this_is_shi",
            "absurdity_mechanism",
            "packaging_notes",
            "resonance_notes",
            "classicness_potential",
        ]
    )
    register_rendering_keys: list[str] = Field(
        default_factory=lambda: [
            "voice_profile",
            "style_constraints_followed",
            "rendered_commentary",
        ]
    )
    reply_probe_keys: list[str] = Field(
        default_factory=lambda: [
            "enabled",
            "candidate_followups",
            "followup_rationale",
            "followup_confidence",
        ]
    )

    def contract_stub(self, *, reply_probe_enabled: bool) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "analysis_mode": "benshi_master",
            "voice_profile": DEFAULT_BENSHI_VOICE_PROFILE,
            "evidence_layer": {
                "direct_observations": [
                    "只写能从 pack 里直接看到的事实。",
                ],
                "context_inferences": [
                    {
                        "claim": "弱推断示例",
                        "confidence": "low|medium|high",
                        "basis": ["forward_structure", "reply_chain"],
                    }
                ],
                "unknowns": [
                    "媒体缺失、图像不可见、上下文不够时必须写 unknown。",
                ],
                "transport_pattern": {
                    "relay_shape": "native|forward_heavy|mixed|unclear",
                    "recurrence_notes": [],
                },
                "shi_presence": {
                    "label": "clear|possible|weak|none",
                    "confidence": "low|medium|high",
                    "reasons": [],
                },
                "shi_type_candidates": [
                    {
                        "label": "原生史|工业史|外源史|二手史|典中典史|反应史|配文史|不确定",
                        "confidence": "low|medium|high",
                        "reasons": [],
                    }
                ],
                "confidence_notes": [],
            },
            "shi_component_analysis": {
                "definition": "这里解释‘史’到底是什么，不要只会说抽象。",
                "component_candidates": [
                    {
                        "label": "外源史|二手史|工业史|配文史|截图壳子史|拼盘史|包浆史|补档返场史|图串重复回放|单人主导倾倒|视频壳缺本体|不确定",
                        "family": "provenance|transport|content|packaging|social|uncertainty",
                        "score": 0.0,
                        "reasons": [],
                        "evidence_message_uids": [],
                        "notes": [],
                    }
                ],
                "dominant_components": [],
                "transport_components": [],
                "content_components": [],
                "component_rationale": [],
                "confidence": "low|medium|high",
            },
            "shi_description_layer": {
                "what_is_shi_definition": "这里写对‘史’的定义，不要写得太学术。",
                "one_line_definition": "一句话定义这窗是什么路数的史。",
                "component_breakdown": [
                    {
                        "label": "成分名",
                        "family": "transport|content|packaging|provenance|social|uncertainty",
                        "why": "为什么有这个成分",
                    }
                ],
                "descriptive_tags": [],
                "how_to_describe_this_shi": "写给后续分析器或群友看的描述建议。",
                "good_description_patterns": [],
                "bad_description_patterns": [],
                "unknown_boundaries": [],
            },
            "cultural_interpretation": {
                "why_this_is_shi": [],
                "absurdity_mechanism": [],
                "packaging_notes": [],
                "resonance_notes": [],
                "classicness_potential": "low|medium|high|unclear",
            },
            "register_rendering": {
                "voice_profile": DEFAULT_BENSHI_VOICE_PROFILE,
                "style_constraints_followed": [],
                "rendered_commentary": "这里写更像群友会说的话，但不能篡改证据层。",
            },
            "reply_probe": {
                "enabled": reply_probe_enabled,
                "candidate_followups": [],
                "followup_rationale": [],
                "followup_confidence": "low|medium|high|n/a",
            },
        }


class BenshiPromptScaffold(BaseModel):
    scaffold_id: str = "benshi_master_v1"
    reasoning_effort_default: str = DEFAULT_BENSHI_REASONING_EFFORT
    temperature_default: float = DEFAULT_BENSHI_TEMPERATURE
    voice_profile: BenshiVoiceProfile = Field(default_factory=BenshiVoiceProfile)
    reply_probe_enabled: bool = DEFAULT_BENSHI_REPLY_PROBE_ENABLED
    structured_output: BenshiStructuredOutputContract = Field(
        default_factory=BenshiStructuredOutputContract
    )


def resolve_benshi_prompt_scaffold(
    prompt_version: str | None,
) -> BenshiPromptScaffold | None:
    normalized = (prompt_version or "").strip().lower()
    if not normalized.startswith("benshi_master_v1"):
        return None
    reply_probe_enabled = "reply_probe" in normalized
    return BenshiPromptScaffold(reply_probe_enabled=reply_probe_enabled)


def build_benshi_master_system_prompt(scaffold: BenshiPromptScaffold) -> str:
    reply_probe_note = (
        "当前启用了 reply probe，你需要额外给出可接这坨史下话茬的候选。"
        if scaffold.reply_probe_enabled
        else "当前没有启用 reply probe，不要额外生成接话茬候选。"
    )
    tone_rules = "\n".join(f"- {item}" for item in scaffold.voice_profile.tone_rules)
    return (
        "你是 BenshiMasterAgent 的提示词骨架层，负责把 analysis pack 变成第一份可复核的“吃史判断”。\n"
        "你不是普通总结器，也不是文绉绉的报告员。你要先稳住证据层，再拆史成分，再给描述策略，再解释这坨东西为什么是史，最后才把语气渲染成更像群友会说的话。\n"
        "你必须分清五层：\n"
        "1. 直接证据：pack 里明确可见的文本、forward、reply、系统/分享、caption、媒体覆盖信息。\n"
        "2. 上下文推断：可以推，但要写明是 context-only，不准装成看过媒体本体。\n"
        "3. 成分拆解：把内容成分、包装成分、搬运成分、不确定性成分拆开。\n"
        "4. 描述层：告诉后续系统应该怎么描述这坨史，哪些写法是空话或过界脑补。\n"
        "5. unknown：证据不够、媒体缺失、上下文断裂时必须保留 unknown。\n"
        "你要像高强度冲浪网友一样懂梗、懂抽象、懂搬史文化，但不能把装懂当真懂。\n"
        f"{reply_probe_note}\n"
        "最终输出必须是一个 JSON 对象，外面不要再包 Markdown 解释。\n"
        f"Voice profile: {scaffold.voice_profile.profile_id} / {scaffold.voice_profile.profile_label}\n"
        f"Voice summary: {scaffold.voice_profile.register_summary}\n"
        "Tone rules:\n"
        f"{tone_rules}"
    )


def build_benshi_master_user_tail(scaffold: BenshiPromptScaffold) -> list[str]:
    contract_stub = json.dumps(
        scaffold.structured_output.contract_stub(
            reply_probe_enabled=scaffold.reply_probe_enabled
        ),
        ensure_ascii=False,
        indent=2,
    )
    lines = [
        "请基于以上 analysis pack 输出一份 `BenshiMasterAgent` JSON 结果。",
        "输出必须先稳住证据层，再给史成分分析层、史描述层、文化解释层，最后才给更像群友的渲染层。",
        "在 cultural_interpretation 之前，先单独给出 `shi_component_analysis` 和 `shi_description_layer`。",
        "`shi_component_analysis` 负责回答：这坨东西为什么会被吃成史，具体有哪些成分，搬运结构和内容结构分别是什么。",
        "`shi_description_layer` 负责回答：应该怎么描述这坨史，哪些描述方式是对路的，哪些是空话或过界脑补。",
        "不要把 register_rendering 里的口吻污染到 evidence_layer。",
        "如果 pack 里没有直接证据支撑，就不要硬下“这是什么图/这是什么梗”的结论。",
        "如果媒体缺失或没有 caption，不能伪造 OCR、画面内容、配图文本或视频情节。",
        "如果你判断它是史，请说明是因为什么机制变成史，比如：认知落差、荒诞组合、工业流水线、外源套娃、二手转运、包浆、反馈整齐度。",
        "组件层里要尽量把‘内容成分 / 包装成分 / 搬运成分 / 不确定性成分’拆开，不要揉成一段空泛 prose。",
        "描述层里至少要给出：一句话定义、描述标签、建议怎么描述、哪些描述方式不对、未知边界。",
        "如果你判断它不是很成型的史，也可以写成弱史、半成品、工业废史、不足以判断。",
        "reply_probe 只有在 enabled=true 时才填写有效候选；否则保留空列表和 n/a。",
        "当 reply_probe 启用时，候选接话茬必须优先贴着当前 evidence_layer 里已经观察到的具体结构来接，比如：补档、库存回放、套娃 forward、题材拼盘、二手包浆、工业流水线、配图壳子、群内中转站气味。",
        "不要给太万能、放哪都能说的空泛吐槽句；宁可少给几条，也要更贴当前这坨史的具体结构。",
        "如果存在 image_cluster_summaries，它们是程序先做过的一层图像簇摘要。你可以把它们当成“这一窗图片大致分成了哪些簇、哪些是图串、哪些是重复回放”的结构证据。",
        "如果存在 image_caption_samples，它们属于直接可见媒体证据的一部分；可以拿来解释图像簇的画面类型、截图/梗图/界面/聊天记录属性，但不要把 caption 外推成看见了所有图片。",
        "不要输出额外解释文字，直接输出 JSON。",
        "JSON contract skeleton:",
        contract_stub,
    ]
    return lines


def build_benshi_master_prompt_payload(
    pack: BenshiAnalysisPack,
    *,
    max_selected_messages: int = 32,
    max_forward_summaries: int = 8,
    max_recurrence_summaries: int = 8,
    max_missing_media_gaps: int = 8,
) -> dict[str, Any]:
    selected_messages = [
        _compact_selected_message(item)
        for item in _pick_prompt_selected_messages(
            pack.selected_messages,
            max_items=max_selected_messages,
        )
    ]
    return {
        "pack_version": "benshi_pack_v1",
        "target": {
            "display_id": pack.target.display_id,
            "display_name": pack.target.display_name,
        },
        "chosen_time_window": {
            "start_iso": pack.chosen_time_window.start_timestamp_iso,
            "end_iso": pack.chosen_time_window.end_timestamp_iso,
            "selected_message_count": pack.chosen_time_window.selected_message_count,
            "rationale": pack.chosen_time_window.rationale,
        },
        "pack_summary": pack.pack_summary,
        "stats": {
            "message_count": pack.stats.message_count,
            "sender_count": pack.stats.sender_count,
            "asset_count": pack.stats.asset_count,
            "image_message_count": pack.stats.image_message_count,
            "forward_message_count": pack.stats.forward_message_count,
            "reply_message_count": pack.stats.reply_message_count,
            "emoji_message_count": pack.stats.emoji_message_count,
            "low_information_count": pack.stats.low_information_count,
            "image_ratio": pack.stats.image_ratio,
            "forward_ratio": pack.stats.forward_ratio,
            "reply_ratio": pack.stats.reply_ratio,
            "emoji_ratio": pack.stats.emoji_ratio,
            "low_information_ratio": pack.stats.low_information_ratio,
        },
        "forward_summary": pack.forward_summary.model_dump(mode="json"),
        "forward_summaries": [
            _compact_forward_summary(item)
            for item in pack.forward_summaries[:max_forward_summaries]
        ],
        "recurrence_summary": pack.recurrence_summary.model_dump(mode="json"),
        "recurrence_summaries": [
            _compact_recurrence_summary(item)
            for item in pack.recurrence_summaries[:max_recurrence_summaries]
        ],
        "participant_role_candidates": [
            {
                "sender_id": item.sender_id,
                "sender_name": item.sender_name,
                "message_count": item.message_count,
                "forward_message_count": item.forward_message_count,
                "asset_message_count": item.asset_message_count,
                "reply_message_count": item.reply_message_count,
                "missing_media_message_count": item.missing_media_message_count,
                "candidate_roles": list(item.candidate_roles),
                "notes": [preview_text(note, 120) for note in item.notes[:3]],
            }
            for item in pack.participant_role_candidates[:8]
        ],
        "asset_summary": pack.asset_summary.model_dump(mode="json"),
        "asset_summaries": [
            {
                "asset_type": item.asset_type,
                "reference_count": item.reference_count,
                "message_count": item.message_count,
                "materialized_count": item.materialized_count,
                "missing_count": item.missing_count,
                "status_counts": item.status_counts,
                "top_file_names": item.top_file_names[:4],
            }
            for item in pack.asset_summaries[:6]
        ],
        "shi_component_summaries": [
            {
                "component_label": item.component_label,
                "component_family": item.component_family,
                "score": item.score,
                "evidence_basis": [preview_text(note, 120) for note in item.evidence_basis[:4]],
                "notes": [preview_text(note, 120) for note in item.notes[:4]],
            }
            for item in pack.shi_component_summaries[:10]
        ],
        "shi_description_profile": (
            pack.shi_description_profile.model_dump(mode="json")
            if pack.shi_description_profile is not None
            else None
        ),
        "image_cluster_summaries": [
            {
                "cluster_id": item.cluster_id,
                "cluster_kind": item.cluster_kind,
                "member_count": item.member_count,
                "reference_count": item.reference_count,
                "distinct_message_count": item.distinct_message_count,
                "representative_file_name": item.representative_file_name,
                "representative_context_excerpt": preview_text(
                    item.representative_context_excerpt or "",
                    120,
                ) or None,
                "file_name_examples": item.file_name_examples[:4],
                "notes": [preview_text(note, 120) for note in item.notes[:4]],
            }
            for item in pack.image_cluster_summaries[:8]
        ],
        "image_caption_samples": [
            {
                "cluster_id": item.cluster_id,
                "cluster_kind": item.cluster_kind,
                "message_uid": item.message_uid,
                "timestamp_iso": item.timestamp_iso,
                "sender_id": item.sender_id,
                "sender_name": item.sender_name,
                "file_name": item.file_name,
                "context_excerpt": preview_text(item.context_excerpt or "", 120),
                "caption": preview_text(item.caption, 180),
                "model_name": item.model_name,
            }
            for item in pack.image_caption_samples[:6]
        ],
        "missing_media_gaps": [
            {
                "gap_id": item.gap_id,
                "message_uid": item.message_uid,
                "timestamp_iso": item.timestamp_iso,
                "sender_id": item.sender_id,
                "sender_name": item.sender_name,
                "asset_type": item.asset_type,
                "file_name": item.file_name,
                "status": item.status,
                "resolver": item.resolver,
                "context_excerpt": preview_text(item.context_excerpt or "", 180),
                "reason": preview_text(item.reason or "", 120),
            }
            for item in pack.missing_media_gaps[:max_missing_media_gaps]
        ],
        "preprocess_overlay_summary": (
            pack.preprocess_overlay_summary.model_dump(mode="json")
            if pack.preprocess_overlay_summary is not None
            else None
        ),
        "selected_messages": selected_messages,
        "warnings": list(pack.warnings),
    }


def build_benshi_master_user_prompt(
    pack: BenshiAnalysisPack,
    *,
    scaffold: BenshiPromptScaffold,
    max_selected_messages: int = 32,
    max_forward_summaries: int = 8,
    max_recurrence_summaries: int = 8,
    max_missing_media_gaps: int = 8,
) -> str:
    payload = build_benshi_master_prompt_payload(
        pack,
        max_selected_messages=max_selected_messages,
        max_forward_summaries=max_forward_summaries,
        max_recurrence_summaries=max_recurrence_summaries,
        max_missing_media_gaps=max_missing_media_gaps,
    )
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    tail_lines = build_benshi_master_user_tail(scaffold)
    return (
        "以下是 BenshiAnalysisPack，请基于它做分析。\n"
        "注意：selected_messages 是从窗口中抽出来的高信号证据池，不一定等于完整原始聊天；processed_text/decision_summary 是派生层，只能辅助解释。\n\n"
        f"{payload_json}\n\n"
        + "\n".join(tail_lines)
    )


def _pick_prompt_selected_messages(
    selected_messages: list[Any],
    *,
    max_items: int,
) -> list[Any]:
    if len(selected_messages) <= max_items:
        return list(selected_messages)
    scored = sorted(
        selected_messages,
        key=lambda item: (
            -_selected_message_prompt_score(item),
            item.timestamp_iso,
            item.message_uid,
        ),
    )
    chosen = scored[:max_items]
    return sorted(chosen, key=lambda item: (item.timestamp_iso, item.message_uid))


def _selected_message_prompt_score(item: Any) -> int:
    score = 0
    if item.has_forward:
        score += 40
    score += min(int(item.forward_depth or 0), 3) * 10
    score += min(int(item.missing_media_count or 0), 3) * 8
    score += min(int(item.asset_count or 0), 6) * 3
    score += min(len(item.asset_types or []), 4) * 2
    score += min(len(item.message_tags or []), 5) * 2
    score += min(len(item.preprocess_labels or []), 4)
    if item.delivery_profile != "raw_only":
        score += 3
    debug_hits = sum(1 for label in item.preprocess_labels if label in _DEBUGISH_LABELS)
    score -= debug_hits * 6
    if item.text_content and len(item.text_content) >= 24:
        score += 2
    return score


def _compact_selected_message(item: Any) -> dict[str, Any]:
    return {
        "message_uid": item.message_uid,
        "timestamp_iso": item.timestamp_iso,
        "sender_id": item.sender_id,
        "sender_name": item.sender_name,
        "content": preview_text(item.content, 280),
        "processed_text": preview_text(item.processed_text or "", 200) or None,
        "decision_summary": preview_text(item.decision_summary or "", 140) or None,
        "delivery_profile": item.delivery_profile,
        "preprocess_labels": list(item.preprocess_labels[:6]),
        "asset_types": list(item.asset_types[:6]),
        "has_forward": item.has_forward,
        "forward_depth": item.forward_depth,
        "missing_media_count": item.missing_media_count,
        "message_tags": list(item.message_tags[:8]),
    }


def _compact_forward_summary(item: Any) -> dict[str, Any]:
    return {
        "summary_id": item.summary_id,
        "outer_timestamp_iso": item.outer_timestamp_iso,
        "outer_sender_id": item.outer_sender_id,
        "outer_sender_name": item.outer_sender_name,
        "preview_text": preview_text(item.preview_text or "", 180) or None,
        "detailed_text": preview_text(item.detailed_text or "", 220) or None,
        "preview_lines": [preview_text(line, 120) for line in item.preview_lines[:4]],
        "segment_summary": item.segment_summary,
        "inner_message_count": item.inner_message_count,
        "inner_asset_count": item.inner_asset_count,
        "inner_asset_type_counts": item.inner_asset_type_counts,
        "forward_depth_hint": item.forward_depth_hint,
    }


def _compact_recurrence_summary(item: Any) -> dict[str, Any]:
    return {
        "summary_id": item.summary_id,
        "recurrence_key": preview_text(item.recurrence_key, 80),
        "basis": item.basis,
        "asset_type": item.asset_type,
        "file_name": item.file_name,
        "occurrence_count": item.occurrence_count,
        "resource_state_counts": item.resource_state_counts,
        "materialization_status_counts": item.materialization_status_counts,
        "exported_rel_paths": list(item.exported_rel_paths[:4]),
    }
