from __future__ import annotations

from pathlib import Path

from qq_data_analysis.benshi_llm_agent import BenshiMasterLlmAgent
from qq_data_analysis.llm_agent import LlmResponseBundle, LlmUsageSnapshot

from tests.test_benshi_master_agent import _FIXTURE_PATH, _TARGET_ID, _build_materials


class _FakeBenshiTextClient:
    provider_name = "openai_compatible"
    model_name = "gpt-5.4"

    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text

    def analyze_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        stream_callback=None,
    ) -> LlmResponseBundle:
        assert system_prompt
        assert user_prompt
        assert max_output_tokens == 900
        if stream_callback is not None:
            stream_callback("content", self.raw_text[:32])
        return LlmResponseBundle(
            parsed_payload={},
            raw_text=self.raw_text,
            reasoning_text="",
            finish_reason="stop",
            usage=LlmUsageSnapshot(
                prompt_tokens=500,
                completion_tokens=200,
                total_tokens=700,
                reasoning_tokens=0,
                cached_tokens=0,
            ),
            raw_response={"provider": "fake"},
        )


def test_benshi_llm_agent_accepts_component_and_description_layers_from_raw_payload(
    monkeypatch,
) -> None:
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_components",
    )
    raw_text = """
{
  "contract_version": "benshi_master_v1",
  "analysis_mode": "benshi_master",
  "voice_profile": "cn_chonglang_benshi_v1",
  "evidence_layer": {
    "shi_presence": {"label": "clear", "confidence": "high", "reasons": []},
    "shi_type_candidates": []
  },
  "shi_component_analysis": {
    "definition": "史是被快速识别为值得围观和转运的荒诞内容单位。",
    "component_candidates": [
      {
        "label": "外源史",
        "family": "provenance",
        "score": 0.9,
        "reasons": ["forward 很重"],
        "evidence_message_uids": [],
        "notes": []
      }
    ],
    "dominant_components": ["外源史", "二手史"],
    "transport_components": ["外源史", "二手史"],
    "content_components": ["截图壳子史"],
    "component_rationale": ["这窗主体靠外部材料套娃转运成立。"],
    "confidence": "high"
  },
  "shi_description_layer": {
    "what_is_shi_definition": "史是抽象内容和转运包浆一起成立的东西。",
    "one_line_definition": "这是一窗外源二手搬运拼盘。",
    "component_breakdown": [
      {"label": "外源史", "family": "provenance", "why": "主要靠外部 forward。"}
    ],
    "descriptive_tags": ["外源史", "二手史"],
    "how_to_describe_this_shi": "先说外源，再说套娃和补档。",
    "good_description_patterns": ["不是单条神贴，而是一包库存倒货。"],
    "bad_description_patterns": ["不要只会说抽象。"],
    "unknown_boundaries": ["视频本体缺失，不能脑补。"]
  },
  "cultural_interpretation": {
    "why_this_is_shi": ["因为有包浆。"],
    "absurdity_mechanism": [],
    "packaging_notes": [],
    "resonance_notes": [],
    "classicness_potential": "medium"
  },
  "register_rendering": {
    "voice_profile": "cn_chonglang_benshi_v1",
    "style_constraints_followed": [],
    "rendered_commentary": "这窗就是典型的二手倒货。"
  },
  "reply_probe": {
    "enabled": true,
    "candidate_followups": ["这是进货还是清库存"],
    "followup_rationale": ["贴着补档结构在接"],
    "followup_confidence": "medium"
  }
}
""".strip()
    monkeypatch.setattr(
        "qq_data_analysis.benshi_llm_agent.load_text_analysis_client",
        lambda *args, **kwargs: _FakeBenshiTextClient(raw_text),
    )

    agent = BenshiMasterLlmAgent(
        config_path=Path("state/config/llm.local.json"),
        prompt_version="benshi_master_v1_reply_probe",
        max_output_tokens=900,
        max_selected_messages=12,
    )
    output = agent.analyze(materials, agent.prepare(materials))

    assert output.compact_payload["shi_component_analysis_layer"]["dominant_components"] == [
        "外源史",
        "二手史",
    ]
    assert output.compact_payload["shi_description_layer"]["one_line_definition"] == (
        "这是一窗外源二手搬运拼盘。"
    )
    assert "史成分" not in output.human_report or output.human_report


def test_benshi_llm_agent_backfills_new_layers_when_missing(monkeypatch) -> None:
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_missing_layers",
    )
    raw_text = """
{
  "contract_version": "benshi_master_v1",
  "analysis_mode": "benshi_master",
  "voice_profile": "cn_chonglang_benshi_v1",
  "evidence_layer": {
    "shi_presence": {"label": "weak", "confidence": "medium", "reasons": []},
    "shi_type_candidates": []
  },
  "cultural_interpretation": {
    "why_this_is_shi": [],
    "absurdity_mechanism": [],
    "packaging_notes": [],
    "resonance_notes": [],
    "classicness_potential": "unclear"
  },
  "register_rendering": {
    "voice_profile": "cn_chonglang_benshi_v1",
    "style_constraints_followed": [],
    "rendered_commentary": "先保守一点。"
  },
  "reply_probe": {
    "enabled": false,
    "candidate_followups": [],
    "followup_rationale": [],
    "followup_confidence": "n/a"
  }
}
""".strip()
    monkeypatch.setattr(
        "qq_data_analysis.benshi_llm_agent.load_text_analysis_client",
        lambda *args, **kwargs: _FakeBenshiTextClient(raw_text),
    )

    agent = BenshiMasterLlmAgent(
        config_path=Path("state/config/llm.local.json"),
        prompt_version="benshi_master_v1",
        max_output_tokens=900,
        max_selected_messages=12,
    )
    output = agent.analyze(materials, agent.prepare(materials))

    assert output.compact_payload["shi_component_analysis_layer"] == {}
    assert output.compact_payload["shi_description_layer"] == {}


def test_benshi_llm_agent_rejects_wrong_shape_for_new_layers_gracefully(
    monkeypatch,
) -> None:
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_invalid_layers",
    )
    raw_text = """
{
  "contract_version": "benshi_master_v1",
  "analysis_mode": "benshi_master",
  "voice_profile": "cn_chonglang_benshi_v1",
  "evidence_layer": {},
  "shi_component_analysis": "oops",
  "shi_description_layer": 123,
  "cultural_interpretation": {},
  "register_rendering": {},
  "reply_probe": {}
}
""".strip()
    monkeypatch.setattr(
        "qq_data_analysis.benshi_llm_agent.load_text_analysis_client",
        lambda *args, **kwargs: _FakeBenshiTextClient(raw_text),
    )

    agent = BenshiMasterLlmAgent(
        config_path=Path("state/config/llm.local.json"),
        prompt_version="benshi_master_v1",
        max_output_tokens=900,
        max_selected_messages=12,
    )
    output = agent.analyze(materials, agent.prepare(materials))

    assert output.compact_payload["shi_component_analysis_layer"] == {}
    assert output.compact_payload["shi_description_layer"] == {}
    assert "invalid_shi_component_analysis_shape" in output.warnings
    assert "invalid_shi_description_layer_shape" in output.warnings
