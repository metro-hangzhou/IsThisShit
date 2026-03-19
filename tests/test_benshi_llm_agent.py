from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from qq_data_analysis.benshi_llm_agent import BenshiMasterLlmAgent
from qq_data_analysis.llm_agent import LlmResponseBundle, LlmUsageSnapshot

from tests.test_benshi_master_agent import _FIXTURE_PATH, _TARGET_ID, _build_materials


def _new_workspace_tmp_dir(prefix: str) -> Path:
    tmp_root = Path(".tmp")
    tmp_root.mkdir(parents=True, exist_ok=True)
    path = tmp_root / f"{prefix}_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


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
    assert "group_consumption_layer" in output.compact_payload
    assert "joint_analysis_layer" in output.compact_payload
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
    assert output.compact_payload["group_consumption_layer"]["consumption_summary"]
    assert output.compact_payload["joint_analysis_layer"]["joint_verdict"]


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
    assert output.compact_payload["group_consumption_layer"]["consumption_summary"]
    assert output.compact_payload["joint_analysis_layer"]["joint_verdict"]
    assert "invalid_shi_component_analysis_shape" in output.warnings
    assert "invalid_shi_description_layer_shape" in output.warnings


def test_benshi_llm_agent_includes_prompt_reference_context_when_configured(
    monkeypatch,
) -> None:
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_reference_context",
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
  "shi_component_analysis": {},
  "shi_description_layer": {},
  "cultural_interpretation": {},
  "register_rendering": {
    "voice_profile": "cn_chonglang_benshi_v1",
    "style_constraints_followed": [],
    "rendered_commentary": "有例子库和分布基线兜着。"
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
        example_bank_manifest_path=Path(
            "dev/testdata/local/shi_group_751365230/benshi_example_bank_manifest.json"
        ),
        distribution_baseline_path=Path(
            "dev/testdata/local/shi_group_751365230/benshi_distribution_baseline.json"
        ),
    )
    output = agent.analyze(materials, agent.prepare(materials))

    prompt_refs = output.compact_payload["prompt_reference_context"]
    assert prompt_refs["example_bank_context"] is not None
    assert prompt_refs["distribution_baseline_context"] is not None
    assert "good_reply_probe_examples" not in (
        prompt_refs["example_bank_context"]["selected_counts"] or {}
    )
    assert "ExampleBankContext:" in output.human_report
    assert "DistributionBaseline:" in output.human_report


def test_benshi_llm_agent_exports_joint_missing_and_overlay_context(monkeypatch) -> None:
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_joint_context",
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
  "shi_component_analysis": {},
  "shi_description_layer": {},
  "cultural_interpretation": {},
  "register_rendering": {
    "voice_profile": "cn_chonglang_benshi_v1",
    "style_constraints_followed": [],
    "rendered_commentary": "先看联合上下文。"
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

    payload = output.compact_payload
    assert "expired_inference_summary" in payload
    assert "expired_inference_items" in payload
    assert "crowd_reaction_summary" in payload
    assert "crowd_reaction_items" in payload
    assert "reaction_summary" in payload
    assert "reaction_patterns" in payload
    assert "missing_media_gaps" in payload
    assert "forward_degraded_asset_hints" in payload
    assert "preprocess_overlay_summary" in payload
    assert "selected_message_overview" in payload
    assert "asset_summary" in payload


def test_benshi_llm_agent_includes_reply_probe_examples_only_when_enabled(
    monkeypatch,
) -> None:
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_reply_probe_examples",
    )
    raw_text = """
{
  "contract_version": "benshi_master_v1",
  "analysis_mode": "benshi_master",
  "voice_profile": "cn_chonglang_benshi_v1",
  "evidence_layer": {},
  "shi_component_analysis": {},
  "shi_description_layer": {},
  "cultural_interpretation": {},
  "register_rendering": {},
  "reply_probe": {
    "enabled": true,
    "candidate_followups": ["这批是库存回放还是补档返场"],
    "followup_rationale": ["直接贴返场结构在接。"],
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
        example_bank_manifest_path=Path(
            "dev/testdata/local/shi_group_751365230/benshi_example_bank_manifest.json"
        ),
        max_good_judgment_examples=1,
        max_good_description_examples=1,
        max_good_reply_probe_examples=1,
    )
    output = agent.analyze(materials, agent.prepare(materials))

    prompt_refs = output.compact_payload["prompt_reference_context"]
    counts = prompt_refs["example_bank_context"]["selected_counts"]
    assert counts["good_judgment_examples"] == 1
    assert counts["good_description_examples"] == 1
    assert counts["good_reply_probe_examples"] == 1


def test_benshi_llm_agent_degrades_gracefully_when_reference_context_is_broken(
    monkeypatch,
) -> None:
    tmp_path = _new_workspace_tmp_dir("test_benshi_llm_agent_bad_reference_context")
    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_llm_agent_bad_reference_context",
    )
    raw_text = """
{
  "contract_version": "benshi_master_v1",
  "analysis_mode": "benshi_master",
  "voice_profile": "cn_chonglang_benshi_v1",
  "evidence_layer": {},
  "shi_component_analysis": {},
  "shi_description_layer": {},
  "cultural_interpretation": {},
  "register_rendering": {},
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

    broken_manifest = tmp_path / "broken_manifest.json"
    broken_manifest.write_text("{bad json", encoding="utf-8")

    agent = BenshiMasterLlmAgent(
        config_path=Path("state/config/llm.local.json"),
        prompt_version="benshi_master_v1",
        max_output_tokens=900,
        max_selected_messages=12,
        example_bank_manifest_path=broken_manifest,
        distribution_baseline_path=tmp_path / "missing_distribution.json",
    )
    output = agent.analyze(materials, agent.prepare(materials))

    prompt_refs = output.compact_payload["prompt_reference_context"]
    assert prompt_refs["example_bank_context"] is None
    assert prompt_refs["distribution_baseline_context"] is None
    assert "example_bank_context_load_failed" in output.warnings
    assert "distribution_baseline_path_missing" in output.warnings


def test_benshi_live_smoke_review_text_combines_missing_overlay_and_multimodal_sections() -> None:
    from scripts.run_benshi_live_llm_smoke import _build_review_text, _build_shi_review_text

    payload = {
        "agent_name": "benshi_master_llm",
        "agent_version": "v0",
        "warnings": [],
        "artifact_inputs": {
            "dataset_dir": "dev/testdata/local/shi_group_751365230",
            "example_bank_manifest_path": None,
            "distribution_baseline_path": None,
            "notes": [],
        },
        "compact_payload": {
            "evidence_layer": {
                "shi_presence": {"label": "clear"},
                "shi_type_candidates": [{"label": "二手史", "confidence": "high", "reasons": ["forward 套娃很重"]}],
                "transport_pattern": {"relay_shape": "forward_heavy", "recurrence_notes": ["同批内容存在返场重播。"]},
            },
            "shi_component_analysis_layer": {
                "definition": "史是包浆、回锅和二手转运一起成立的怪东西。",
                "dominant_components": ["二手史", "工业史"],
                "component_candidates": [
                    {
                        "label": "二手史",
                        "family": "provenance",
                        "score": 0.9,
                        "reasons": ["同一批转发再次出现"],
                    }
                ],
                "transport_components": ["补档返场", "套娃 forward"],
                "content_components": ["截图壳子"],
                "component_rationale": ["史点主要靠搬运结构成立。"],
            },
            "shi_description_layer": {
                "what_is_shi_definition": "史是抽象内容与二手搬运结构一起发酵后的成品。",
                "one_line_definition": "这窗像库存返场的二手搬史拼盘。",
                "descriptive_tags": ["二手史", "补档返场", "截图壳子"],
                "how_to_describe_this_shi": "先讲返场结构，再讲图串和缺失视频壳子。",
                "component_breakdown": [
                    {"label": "补档返场", "family": "transport", "why": "同批图串和 forward 再次出现"}
                ],
                "good_description_patterns": ["不要只说抽象，要点明库存回放。"],
                "bad_description_patterns": ["不要把缺失视频脑补成看过。"],
                "unknown_boundaries": ["视频只看到标题和上下文，不能硬猜画面。"],
            },
            "cultural_interpretation_layer": {
                "why_this_is_shi": ["旧库存返场让包浆感变重。"],
                "absurdity_mechanism": [],
                "packaging_notes": [],
                "resonance_notes": [],
                "classicness_potential": "medium",
            },
            "register_layer": {
                "voice_profile": "cn_chonglang_benshi_v1",
                "rendered_commentary": "这是库存返场，不是现场聊天。",
                "style_constraints_followed": ["不脑补缺失视频内容"],
            },
            "reply_probe_layer": {
                "enabled": True,
                "followup_confidence": "medium",
                "candidate_followups": ["这不是聊天，这是补档清库存。"],
                "followup_rationale": ["贴着返场和图串回放来接。"],
            },
            "llm_meta": {
                "provider": "openai_compatible",
                "model": "gpt-5.4",
                "prompt_version": "benshi_master_v1_reply_probe",
                "finish_reason": "completed",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "reasoning_tokens": 0,
                    "cached_tokens": 0,
                },
            },
            "image_cluster_summaries": [
                {
                    "cluster_id": "img_cluster_01",
                    "cluster_kind": "context_bundle_recurrent",
                    "member_count": 4,
                    "reference_count": 8,
                    "distinct_message_count": 2,
                    "representative_file_name": "sample_01.jpg",
                    "representative_context_excerpt": "同一组四图在窗口里返场。",
                    "file_name_examples": ["sample_01.jpg", "sample_02.jpg"],
                    "notes": ["同一图串重复出现 2 次。"],
                }
            ],
            "image_caption_samples": [
                {
                    "cluster_id": "img_cluster_01",
                    "cluster_kind": "context_bundle_recurrent",
                    "message_uid": "m_1",
                    "timestamp_iso": "2026-03-19T00:00:00+08:00",
                    "sender_id": "user_1",
                    "sender_name": "tester",
                    "file_name": "sample_01.jpg",
                    "context_excerpt": "四图图串",
                    "caption": "这是带大字说明的截图壳子图串。",
                    "model_name": "gpt-5.4",
                }
            ],
            "missing_media_gaps": [
                {
                    "gap_id": "gap_01",
                    "message_uid": "m_2",
                    "asset_type": "video",
                    "file_name": "missing_video.mp4",
                    "status": "missing_after_napcat",
                    "resolver": "napcat_context_only",
                    "context_excerpt": "只看到视频标题和补充说明。",
                    "reason": "resource expired",
                },
                {
                    "gap_id": "gap_02",
                    "message_uid": "m_3",
                    "asset_type": "file",
                    "file_name": "missing_file.zip",
                    "status": "expired",
                    "resolver": "napcat_public_token",
                    "context_excerpt": "文件壳子还在，但本体不可得。",
                    "reason": "resource expired",
                },
            ],
            "preprocess_overlay_summary": {
                "delivery_profile": "raw_plus_processed",
                "top_labels": {
                    "expired_asset_inference": 2,
                    "missing_media_context": 2,
                },
                "notes": ["overlay 已附着到 2 条消息。"],
                "representative_items": [
                    {
                        "message_uid": "m_2",
                        "labels": ["expired_asset_inference", "missing_media_context"],
                        "decision_summary": "失活视频需要更多上下文。",
                    }
                ],
            },
            "selected_message_overview": [
                {
                    "message_uid": "m_2",
                    "timestamp_iso": "2026-03-19T00:00:01+08:00",
                    "missing_media_count": 1,
                    "preprocess_labels": ["expired_asset_inference", "missing_media_context"],
                    "decision_summary": "失活视频需要更多上下文。",
                    "processed_text": "只能保守描述视频标题和周边文本。",
                }
            ],
            "asset_summary": {
                "asset_type_missing_counts": {"video": 1, "file": 1},
            },
            "prompt_reference_context": {
                "example_bank_context": {},
                "distribution_baseline_context": {},
            },
        },
    }

    review = _build_review_text(
        payload=payload,
        output_json_path=Path("dev/testdata/local/shi_group_751365230/fake_output.json"),
    )
    shi_review = _build_shi_review_text(
        payload=payload,
        output_json_path=Path("dev/testdata/local/shi_group_751365230/fake_output.json"),
    )

    assert "2.8 联合分析总览" in review
    assert "2.8.1 Shi本体:" in review
    assert "2.8.2 群友反应:" in review
    assert "2.8.3 图像模态:" in review
    assert "2.8.4 深层forward/退化媒体:" in review
    assert "2.8.5 UnknownBoundary:" in review
    assert "这窗像库存返场的二手搬史拼盘。" in review
    assert "formal 缺口: file=1 / video=1；状态=expired=1 / missing_after_napcat=1" in review
    assert "overlay: expired_asset_inference=2 / missing_media_context=2" in review
    assert "3.10 MissingMediaAndExpiredInference:" in review
    assert "gap_by_type:" in review
    assert "video=1" in review
    assert "file=1" in review
    assert "overlay_top_labels:" in review
    assert "expired_asset_inference=2" in review
    assert "joint_note: 图像簇/图像 caption 提供的是可见图像证据" in review

    assert "4.6 缺口/失活线索:" in shi_review
    assert "5.8 联合媒体描述约束:" in shi_review
    assert "当前仍有 2 个失活/缺失媒体位点" in shi_review
