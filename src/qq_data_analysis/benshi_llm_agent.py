from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .benshi_pack import build_benshi_analysis_pack
from .benshi_prompting import (
    build_expired_inference_summary,
    build_benshi_master_system_prompt,
    build_benshi_master_user_prompt,
    resolve_benshi_prompt_scaffold,
)
from .benshi_seed_artifacts import (
    build_distribution_baseline_prompt_context_from_summary,
    build_example_bank_prompt_context,
    load_distribution_baseline_prompt_context,
)
from .llm_agent import OpenAICompatibleAnalysisClient, _extract_json_object
from .llm_window import _model_name_from_client, _provider_name_from_client, load_text_analysis_client
from .models import AnalysisAgentOutput, AnalysisMaterials, BenshiAnalysisPack


class BenshiMasterLlmAgent:
    agent_name = "benshi_master_llm"
    agent_version = "v0"

    def __init__(
        self,
        *,
        config_path: Path | str = Path("state/config/llm.local.json"),
        model: str | None = None,
        prompt_version: str = "benshi_master_v1",
        max_output_tokens: int = 2200,
        max_selected_messages: int = 32,
        stream_callback: Callable[[str, str], None] | None = None,
        example_bank_manifest_path: Path | str | None = None,
        distribution_baseline_path: Path | str | None = None,
        max_examples_per_group: int = 1,
        max_negative_templates: int = 2,
        max_good_judgment_examples: int | None = None,
        max_good_description_examples: int | None = None,
        max_good_reply_probe_examples: int | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.model = model
        self.prompt_version = prompt_version
        self.max_output_tokens = max_output_tokens
        self.max_selected_messages = max_selected_messages
        self.stream_callback = stream_callback
        self.example_bank_manifest_path = (
            Path(example_bank_manifest_path)
            if example_bank_manifest_path is not None
            else None
        )
        self.distribution_baseline_path = (
            Path(distribution_baseline_path)
            if distribution_baseline_path is not None
            else None
        )
        self.max_examples_per_group = max_examples_per_group
        self.max_negative_templates = max_negative_templates
        self.max_good_judgment_examples = max_good_judgment_examples
        self.max_good_description_examples = max_good_description_examples
        self.max_good_reply_probe_examples = max_good_reply_probe_examples

    def prepare(self, materials: AnalysisMaterials) -> BenshiAnalysisPack:
        return build_benshi_analysis_pack(
            materials,
            distribution_baseline_path=self.distribution_baseline_path,
        )

    def _load_prompt_reference_context(
        self,
        *,
        reply_probe_enabled: bool,
        load_distribution_baseline: bool = True,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
        example_bank_context = None
        distribution_baseline_context = None
        warnings: list[str] = []
        include_groups = [
            "good_judgment_examples",
            "good_description_examples",
        ]
        max_examples_by_group = {
            "good_judgment_examples": (
                self.max_good_judgment_examples
                if self.max_good_judgment_examples is not None
                else self.max_examples_per_group
            ),
            "good_description_examples": (
                self.max_good_description_examples
                if self.max_good_description_examples is not None
                else self.max_examples_per_group
            ),
        }
        if reply_probe_enabled:
            include_groups.append("good_reply_probe_examples")
            max_examples_by_group["good_reply_probe_examples"] = (
                self.max_good_reply_probe_examples
                if self.max_good_reply_probe_examples is not None
                else self.max_examples_per_group
            )

        if self.example_bank_manifest_path is not None:
            if self.example_bank_manifest_path.exists():
                try:
                    example_bank_context = build_example_bank_prompt_context(
                        self.example_bank_manifest_path,
                        max_examples_per_group=self.max_examples_per_group,
                        max_negative_templates=self.max_negative_templates,
                        include_groups=include_groups,
                        max_examples_by_group=max_examples_by_group,
                    )
                except Exception:
                    warnings.append("example_bank_context_load_failed")
            else:
                warnings.append("example_bank_manifest_missing")
        if load_distribution_baseline and self.distribution_baseline_path is not None:
            if self.distribution_baseline_path.exists():
                try:
                    distribution_baseline_context = load_distribution_baseline_prompt_context(
                        self.distribution_baseline_path
                    )
                except Exception:
                    warnings.append("distribution_baseline_context_load_failed")
            else:
                warnings.append("distribution_baseline_path_missing")
        return example_bank_context, distribution_baseline_context, warnings

    def analyze(
        self,
        materials: AnalysisMaterials,
        prepared: BenshiAnalysisPack | Any,
    ) -> AnalysisAgentOutput:
        pack = (
            prepared
            if isinstance(prepared, BenshiAnalysisPack)
            else build_benshi_analysis_pack(
                materials,
                distribution_baseline_path=self.distribution_baseline_path,
            )
        )
        scaffold = resolve_benshi_prompt_scaffold(self.prompt_version)
        if scaffold is None:
            raise RuntimeError(f"Unsupported benshi prompt version: {self.prompt_version}")

        pack_distribution_context = None
        if pack.distribution_baseline_summary is not None:
            pack_distribution_context = build_distribution_baseline_prompt_context_from_summary(
                pack.distribution_baseline_summary
            )
        example_bank_context, distribution_baseline_context, reference_context_warnings = (
            self._load_prompt_reference_context(
                reply_probe_enabled=scaffold.reply_probe_enabled,
                load_distribution_baseline=pack_distribution_context is None,
            )
        )
        if pack_distribution_context is not None:
            distribution_baseline_context = pack_distribution_context
        warnings: list[str] = list(reference_context_warnings)
        expired_inference_summary = build_expired_inference_summary(materials)
        system_prompt = build_benshi_master_system_prompt(scaffold)
        user_prompt = build_benshi_master_user_prompt(
            pack,
            scaffold=scaffold,
            max_selected_messages=self.max_selected_messages,
            expired_inference_summary=expired_inference_summary,
            example_bank_context=example_bank_context,
            distribution_baseline_context=distribution_baseline_context,
        )
        client = load_text_analysis_client(
            self.config_path,
            model=self.model,
            prompt_family=self.prompt_version,
        )
        bundle = client.analyze_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=self.max_output_tokens,
            stream_callback=self.stream_callback,
        )
        parsed = _extract_json_object(bundle.raw_text)
        evidence_layer = parsed.get("evidence_layer") or {}
        shi_component_layer = (
            parsed.get("shi_component_analysis")
            or parsed.get("shi_component_analysis_layer")
            or {}
        )
        group_consumption_layer = parsed.get("group_consumption_layer") or {}
        shi_description_layer = parsed.get("shi_description_layer") or {}
        joint_analysis_layer = parsed.get("joint_analysis_layer") or {}
        cultural_layer = parsed.get("cultural_interpretation") or parsed.get("cultural_interpretation_layer") or {}
        register_layer = parsed.get("register_rendering") or parsed.get("register_layer") or {}
        reply_probe_layer = parsed.get("reply_probe") or parsed.get("reply_probe_layer") or {}
        crowd_reaction_layer = parsed.get("crowd_reaction_layer") or {}

        if not isinstance(evidence_layer, dict):
            evidence_layer = {}
            warnings.append("invalid_evidence_layer_shape")
        if not isinstance(shi_component_layer, dict):
            shi_component_layer = {}
            warnings.append("invalid_shi_component_analysis_shape")
        if not isinstance(group_consumption_layer, dict):
            group_consumption_layer = {}
            warnings.append("invalid_group_consumption_layer_shape")
        if not isinstance(shi_description_layer, dict):
            shi_description_layer = {}
            warnings.append("invalid_shi_description_layer_shape")
        if not isinstance(joint_analysis_layer, dict):
            joint_analysis_layer = {}
            warnings.append("invalid_joint_analysis_layer_shape")
        if not isinstance(cultural_layer, dict):
            cultural_layer = {}
            warnings.append("invalid_cultural_interpretation_shape")
        if not isinstance(register_layer, dict):
            register_layer = {}
            warnings.append("invalid_register_layer_shape")
        if not isinstance(reply_probe_layer, dict):
            reply_probe_layer = {}
            warnings.append("invalid_reply_probe_layer_shape")
        if not isinstance(crowd_reaction_layer, dict):
            crowd_reaction_layer = {}
            warnings.append("invalid_crowd_reaction_layer_shape")

        pack_reaction_summary = (
            pack.reaction_summary.model_dump(mode="json")
            if getattr(pack, "reaction_summary", None) is not None
            else {}
        )
        pack_reaction_patterns = [
            item.model_dump(mode="json")
            for item in getattr(pack, "reaction_patterns", []) or []
        ]
        if not group_consumption_layer:
            group_consumption_layer = _build_fallback_group_consumption_layer(
                pack=pack,
                pack_reaction_summary=pack_reaction_summary,
                pack_reaction_patterns=pack_reaction_patterns,
                crowd_reaction_layer=crowd_reaction_layer,
            )
        if not joint_analysis_layer:
            joint_analysis_layer = _build_fallback_joint_analysis_layer(
                pack=pack,
                evidence_layer=evidence_layer,
                shi_component_layer=shi_component_layer,
                group_consumption_layer=group_consumption_layer,
            )

        report_lines = [
            "## Benshi Master LLM",
            f"- 分析对象: {pack.target.display_id}",
            f"- 时间窗口: {pack.chosen_time_window.start_timestamp_iso} -> {pack.chosen_time_window.end_timestamp_iso}",
            f"- Provider: {_provider_name_from_client(client)}",
            f"- Model: {_model_name_from_client(client)}",
            f"- PromptVersion: {self.prompt_version}",
            f"- FinishReason: {bundle.finish_reason}",
            f"- PromptTokens: {bundle.usage.prompt_tokens}",
            f"- CompletionTokens: {bundle.usage.completion_tokens}",
            f"- TotalTokens: {bundle.usage.total_tokens}",
        ]
        if example_bank_context is not None:
            report_lines.append(
                "- ExampleBankContext: "
                + ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(
                        (example_bank_context.get("selected_counts") or {}).items()
                    )
                )
            )
        if distribution_baseline_context is not None:
            report_lines.append(
                "- DistributionBaseline: "
                f"dataset={distribution_baseline_context.get('dataset_id')} "
                f"dominant={', '.join((distribution_baseline_context.get('current_window_distribution') or {}).get('dominant_components') or [])}"
            )
        if expired_inference_summary.get("present"):
            report_lines.append(
                "- ExpiredInference: "
                f"annotations={expired_inference_summary.get('annotation_count')} "
                f"resolved_hypotheses={expired_inference_summary.get('resolved_hypothesis_count')} "
                f"requested_context_rounds={expired_inference_summary.get('requested_context_rounds')}"
            )
            status_counts = expired_inference_summary.get("status_counts") or {}
            if status_counts:
                report_lines.append(
                    "  - statuses: "
                    + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
                )
            for item in (expired_inference_summary.get("top_records") or [])[:2]:
                label = item.get("file_name") or item.get("asset_type") or item.get("message_uid")
                degraded_note = " forward_degraded=true" if item.get("forward_degraded") else ""
                report_lines.append(
                    "  - "
                    f"{label}: status={item.get('status')} "
                    f"resource_state={item.get('resource_state')} "
                    f"reason={item.get('reason') or '<none>'}"
                    f"{degraded_note}"
                )
        if pack.reaction_summary.reaction_message_count:
            report_lines.append(
                "- GroupReaction: "
                f"messages={pack.reaction_summary.reaction_message_count} "
                f"reactors={pack.reaction_summary.reactor_count} "
                f"modes={', '.join(pack.reaction_summary.dominant_modes[:4]) or '<none>'}"
            )
            if pack.reaction_summary.forward_internal_count:
                report_lines.append(
                    "  - "
                    f"forward_internal={pack.reaction_summary.forward_internal_count}"
                )
            for item in pack_reaction_patterns[:3]:
                report_lines.append(
                    "  - "
                    f"{item.get('pattern_label') or item.get('pattern_id')}[{item.get('scope') or 'mixed'}] "
                    f"count={item.get('message_count')} reactors={item.get('reactor_count')}"
                )
                excerpt = (item.get("representative_excerpts") or [None])[0]
                if excerpt:
                    report_lines.append(f"    - {excerpt}")
        if pack.forward_degraded_asset_hints:
            report_lines.append(
                "- ForwardDegradedAssets: "
                f"hints={len(pack.forward_degraded_asset_hints)} "
                f"top={', '.join((item.file_name or item.asset_type) for item in pack.forward_degraded_asset_hints[:3])}"
            )
        if group_consumption_layer.get("consumption_summary"):
            report_lines.append("- 群友怎么吃:")
            report_lines.append(f"  - {group_consumption_layer.get('consumption_summary')}")
        if joint_analysis_layer.get("joint_verdict"):
            report_lines.append("- 联合总判断:")
            report_lines.append(f"  - {joint_analysis_layer.get('joint_verdict')}")
        rendered_commentary = register_layer.get("rendered_commentary")
        if isinstance(rendered_commentary, str) and rendered_commentary.strip():
            report_lines.append("- 口吻层输出:")
            report_lines.append(f"  - {rendered_commentary.strip()}")
        else:
            report_lines.append("- 原始返回:")
            report_lines.append(bundle.raw_text.strip() or "(empty)")

        compact_payload = {
            "contract_version": parsed.get("contract_version"),
            "analysis_mode": parsed.get("analysis_mode"),
            "voice_profile": parsed.get("voice_profile"),
            "evidence_layer": evidence_layer,
            "expired_inference_summary": expired_inference_summary,
            "expired_inference_items": list(
                expired_inference_summary.get("top_records") or []
            ),
            "shi_component_analysis_layer": shi_component_layer,
            "shi_component_analysis": shi_component_layer,
            "group_consumption_layer": group_consumption_layer,
            "shi_description_layer": shi_description_layer,
            "joint_analysis_layer": joint_analysis_layer,
            "cultural_interpretation_layer": cultural_layer,
            "register_layer": register_layer,
            "reply_probe_layer": reply_probe_layer,
            "crowd_reaction_layer": crowd_reaction_layer,
            "crowd_reaction_summary": pack_reaction_summary,
            "crowd_reaction_items": pack_reaction_patterns,
            "image_cluster_summaries": [
                {
                    "cluster_id": item.cluster_id,
                    "cluster_kind": item.cluster_kind,
                    "member_count": item.member_count,
                    "reference_count": item.reference_count,
                    "distinct_message_count": item.distinct_message_count,
                    "representative_file_name": item.representative_file_name,
                    "representative_context_excerpt": item.representative_context_excerpt,
                    "file_name_examples": list(item.file_name_examples),
                    "notes": list(item.notes),
                    "evidence_message_uids": list(item.evidence_message_uids),
                }
                for item in pack.image_cluster_summaries
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
                    "context_excerpt": item.context_excerpt,
                    "caption": item.caption,
                    "model_name": item.model_name,
                }
                for item in pack.image_caption_samples
            ],
            "reaction_summary": pack.reaction_summary.model_dump(mode="json"),
            "reaction_patterns": [
                item.model_dump(mode="json")
                for item in pack.reaction_patterns
            ],
            "missing_media_gaps": [
                {
                    **item.model_dump(mode="json"),
                    "forward_degraded": item.status == "forward_degraded_asset",
                }
                for item in pack.missing_media_gaps
            ],
            "forward_degraded_asset_hints": [
                item.model_dump(mode="json")
                for item in pack.forward_degraded_asset_hints
            ],
            "preprocess_overlay_summary": (
                pack.preprocess_overlay_summary.model_dump(mode="json")
                if pack.preprocess_overlay_summary is not None
                else None
            ),
            "selected_message_overview": [
                {
                    "message_uid": item.message_uid,
                    "timestamp_iso": item.timestamp_iso,
                    "missing_media_count": item.missing_media_count,
                    "preprocess_labels": list(item.preprocess_labels),
                    "decision_summary": item.decision_summary,
                    "processed_text": item.processed_text,
                }
                for item in pack.selected_messages
                if item.missing_media_count
                or item.preprocess_labels
                or item.decision_summary
                or item.processed_text
            ],
            "asset_summary": pack.asset_summary.model_dump(mode="json"),
            "llm_meta": {
                "provider": _provider_name_from_client(client),
                "model": _model_name_from_client(client),
                "prompt_version": self.prompt_version,
                "finish_reason": bundle.finish_reason,
                "usage": {
                    "prompt_tokens": bundle.usage.prompt_tokens,
                    "completion_tokens": bundle.usage.completion_tokens,
                    "total_tokens": bundle.usage.total_tokens,
                    "reasoning_tokens": bundle.usage.reasoning_tokens,
                    "cached_tokens": bundle.usage.cached_tokens,
                },
            },
            "pack_summary": {
                "distribution_baseline_summary": (
                    pack.distribution_baseline_summary.model_dump(mode="json")
                    if pack.distribution_baseline_summary is not None
                    else None
                ),
            },
            "prompt_reference_context": {
                "example_bank_context": example_bank_context,
                "distribution_baseline_context": distribution_baseline_context,
            },
            "raw_payload": parsed,
            "raw_text": bundle.raw_text,
        }
        if bundle.reasoning_text:
            compact_payload["reasoning_text"] = bundle.reasoning_text

        if not parsed:
            warnings.append("llm_response_did_not_parse_as_json")
        if isinstance(client, OpenAICompatibleAnalysisClient):
            pass
        return AnalysisAgentOutput(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            human_report="\n".join(report_lines),
            compact_payload=compact_payload,
            evidence=[],
            warnings=warnings,
        )


def _build_fallback_group_consumption_layer(
    *,
    pack: BenshiAnalysisPack,
    pack_reaction_summary: dict[str, Any],
    pack_reaction_patterns: list[dict[str, Any]],
    crowd_reaction_layer: dict[str, Any],
) -> dict[str, Any]:
    dominant_modes = list(
        crowd_reaction_layer.get("dominant_patterns")
        or pack_reaction_summary.get("dominant_modes")
        or []
    )
    reaction_count = int(pack_reaction_summary.get("reaction_message_count") or 0)
    forward_internal = int(pack_reaction_summary.get("forward_internal_count") or 0)
    style = "反应稀薄或未成型"
    if reaction_count >= 40 and forward_internal >= 10:
        style = "围观接球+forward内层回声混合型"
    elif reaction_count >= 40:
        style = "短平快围观接球型"
    elif dominant_modes:
        style = "零散围观型"
    how_group_ate_it: list[str] = []
    if reaction_count:
        how_group_ate_it.append(
            f"窗口内约有 {reaction_count} 条吃史反应，说明这些材料被即时消费。"
        )
    if forward_internal:
        how_group_ate_it.append(
            f"其中约 {forward_internal} 条发生在 forward 内层，说明转运壳内部也在接球。"
        )
    if dominant_modes:
        how_group_ate_it.append(
            "主导吃法偏向 " + " / ".join(dominant_modes[:4]) + "。"
        )
    return {
        "consumption_summary": (
            "群友对这坨料的吃法不是深聊考据，而更像短平快接球、问号、复读、绷乐和阴阳，把搬进来的料进一步做成史。"
        ),
        "dominant_reaction_modes": dominant_modes,
        "consumption_style": style,
        "how_group_ate_it": how_group_ate_it,
        "social_fuel_notes": list(pack_reaction_summary.get("notes") or []),
        "unknown_boundaries": [
            "反应层解释的是群友怎么吃，不等于能补完原始事件或缺失媒体本体。"
        ],
    }


def _build_fallback_joint_analysis_layer(
    *,
    pack: BenshiAnalysisPack,
    evidence_layer: dict[str, Any],
    shi_component_layer: dict[str, Any],
    group_consumption_layer: dict[str, Any],
) -> dict[str, Any]:
    dominant_components = list(shi_component_layer.get("dominant_components") or [])
    shi_presence = (evidence_layer.get("shi_presence") or {}).get("label") or "unclear"
    modality_coordination: list[str] = []
    if pack.image_cluster_summaries:
        modality_coordination.append(
            f"图像侧有 {len(pack.image_cluster_summaries)} 个图像簇，说明图片壳和图串返场参与了这窗成形。"
        )
    if pack.reaction_summary.reaction_message_count:
        modality_coordination.append(
            f"群友反应约 {pack.reaction_summary.reaction_message_count} 条，说明群体吃法也是核心证据。"
        )
    if pack.forward_degraded_asset_hints:
        modality_coordination.append(
            f"deep forward 中还有 {len(pack.forward_degraded_asset_hints)} 个退化媒体位点，只能 context-only 纳入联合判断。"
        )
    integrated_findings = []
    if dominant_components:
        integrated_findings.append(
            "联合主成分为：" + " / ".join(dominant_components[:5]) + "。"
        )
    if group_consumption_layer.get("consumption_style"):
        integrated_findings.append(
            "群友吃法更像 " + str(group_consumption_layer.get("consumption_style")) + "。"
        )
    integrated_findings.append(
        "整窗真正的史味来自搬运结构、图像壳、群友接球和返场包浆叠加，而不是单条内容孤立封神。"
    )
    return {
        "joint_verdict": (
            f"这是一个 {shi_presence} 的联合史窗口：要把文本、图像、forward 结构、群友反应和退化媒体线索放在一起，"
            "才看得出它为什么成立。"
        ),
        "shi_object_summary": "搬来的更像外源二手混装料，图片壳、截图壳和 forward 套娃都很重。",
        "group_consumption_summary": group_consumption_layer.get("consumption_summary"),
        "modality_coordination": modality_coordination,
        "integrated_findings": integrated_findings,
        "unknown_boundaries": [
            "联合分析不等于忽略边界；deep forward 预览视频、未 caption 图串和失活媒体仍然只能保守处理。"
        ],
    }
