from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .benshi_pack import build_benshi_analysis_pack
from .benshi_prompting import (
    build_benshi_master_system_prompt,
    build_benshi_master_user_prompt,
    resolve_benshi_prompt_scaffold,
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
    ) -> None:
        self.config_path = Path(config_path)
        self.model = model
        self.prompt_version = prompt_version
        self.max_output_tokens = max_output_tokens
        self.max_selected_messages = max_selected_messages
        self.stream_callback = stream_callback

    def prepare(self, materials: AnalysisMaterials) -> BenshiAnalysisPack:
        return build_benshi_analysis_pack(materials)

    def analyze(
        self,
        materials: AnalysisMaterials,
        prepared: BenshiAnalysisPack | Any,
    ) -> AnalysisAgentOutput:
        pack = prepared if isinstance(prepared, BenshiAnalysisPack) else build_benshi_analysis_pack(materials)
        scaffold = resolve_benshi_prompt_scaffold(self.prompt_version)
        if scaffold is None:
            raise RuntimeError(f"Unsupported benshi prompt version: {self.prompt_version}")

        system_prompt = build_benshi_master_system_prompt(scaffold)
        user_prompt = build_benshi_master_user_prompt(
            pack,
            scaffold=scaffold,
            max_selected_messages=self.max_selected_messages,
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
        shi_description_layer = parsed.get("shi_description_layer") or {}
        cultural_layer = parsed.get("cultural_interpretation") or parsed.get("cultural_interpretation_layer") or {}
        register_layer = parsed.get("register_rendering") or parsed.get("register_layer") or {}
        reply_probe_layer = parsed.get("reply_probe") or parsed.get("reply_probe_layer") or {}

        warnings: list[str] = []
        if not isinstance(evidence_layer, dict):
            evidence_layer = {}
            warnings.append("invalid_evidence_layer_shape")
        if not isinstance(shi_component_layer, dict):
            shi_component_layer = {}
            warnings.append("invalid_shi_component_analysis_shape")
        if not isinstance(shi_description_layer, dict):
            shi_description_layer = {}
            warnings.append("invalid_shi_description_layer_shape")
        if not isinstance(cultural_layer, dict):
            cultural_layer = {}
            warnings.append("invalid_cultural_interpretation_shape")
        if not isinstance(register_layer, dict):
            register_layer = {}
            warnings.append("invalid_register_layer_shape")
        if not isinstance(reply_probe_layer, dict):
            reply_probe_layer = {}
            warnings.append("invalid_reply_probe_layer_shape")

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
            "shi_component_analysis_layer": shi_component_layer,
            "shi_component_analysis": shi_component_layer,
            "shi_description_layer": shi_description_layer,
            "cultural_interpretation_layer": cultural_layer,
            "register_layer": register_layer,
            "reply_probe_layer": reply_probe_layer,
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
