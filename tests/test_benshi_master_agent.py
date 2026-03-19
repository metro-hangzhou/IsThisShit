from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from qq_data_analysis import AnalysisJobConfig, AnalysisSubstrate, AnalysisTarget
from qq_data_process import (
    ChunkPolicySpec,
    DeterministicEmbeddingProvider,
    EmbeddingPolicy,
    PreprocessJobConfig,
    PreprocessService,
)

_FIXTURE_PATH = Path("tests/fixtures/analysis_seed.jsonl")
_TARGET_ID = "20001"
_DISTRIBUTION_BASELINE_PATH = Path(
    "dev/testdata/local/shi_group_751365230/benshi_distribution_baseline.json"
)


def _new_tmp_path(prefix: str) -> Path:
    tmp_root = Path(".tmp")
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_root / f"{prefix}_{uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    return tmp_path


def _build_analysis_state(
    *,
    tmp_name: str,
    fixture_path: Path,
    target_id: str,
    skip_image_embeddings: bool = False,
) -> tuple[Path, Path, str]:
    tmp_path = _new_tmp_path(tmp_name)
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=fixture_path,
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        skip_image_embeddings=skip_image_embeddings,
        chunk_policy_specs=[
            ChunkPolicySpec(
                name="window",
                params={"window_size": 5, "overlap": 2},
            )
        ],
    )
    result = service.run(config)
    return result.sqlite_path, result.qdrant_location, target_id


def _build_materials(
    *,
    fixture_path: Path,
    target_id: str,
    tmp_name: str,
    skip_image_embeddings: bool = False,
):
    sqlite_path, qdrant_path, resolved_target_id = _build_analysis_state(
        tmp_name=tmp_name,
        fixture_path=fixture_path,
        target_id=target_id,
        skip_image_embeddings=skip_image_embeddings,
    )
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        return substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id=resolved_target_id),
            )
        )
    finally:
        substrate.close()


def _build_forward_degraded_materials():
    from qq_data_analysis.models import (
        AnalysisMaterials,
        AnalysisMessageFeatures,
        AnalysisMessageRecord,
        AnalysisStatsSnapshot,
        ResolvedAnalysisTarget,
        ResolvedTimeWindow,
    )

    annotations = [
        {
            "annotation_id": "annotation_forward_expander_01",
            "label": "forward_bundle_expander",
            "tags": ["preprocess", "forward", "expanded"],
            "metadata": {
                "details": {
                    "outer_message_id": "msg_forward_01",
                    "preview_text": "甲: [video:lost_clip.mp4] / 乙: [uploaded_file_name:lost_bundle.zip]",
                    "detailed_text": "甲: [video:lost_clip.mp4]\n乙: [uploaded_file_name:lost_bundle.zip]",
                    "preview_lines": [
                        "甲: [video:lost_clip.mp4]",
                        "乙: [uploaded_file_name:lost_bundle.zip]",
                    ],
                    "forward_meta": {"forward_depth": 3},
                    "inner_asset_refs": [
                        {
                            "asset_type": "video",
                            "file_name": "lost_clip.mp4",
                            "resource_state": "missing",
                            "resolver": "forward_token_only",
                            "forward_degraded": True,
                            "source_hint": "preview_line:0",
                        },
                        {
                            "asset_type": "file",
                            "file_name": "lost_bundle.zip",
                            "resource_state": "missing",
                            "resolver": "forward_token_only",
                            "forward_degraded": True,
                            "source_hint": "preview_line:1",
                        },
                    ],
                }
            },
        },
        {
            "annotation_id": "annotation_expired_forward_01",
            "label": "expired_asset_inference_preprocessor",
            "summary": "Context-supported inference only for deep forward lost video.",
            "decision_summary": "Deep forward video token stayed degraded, but surrounding text supports a conservative inference.",
            "confidence": 0.72,
            "source_message_ids": ["msg_forward_01"],
            "source_asset_ids": ["forward_degraded_asset_01"],
            "target_ids": ["processed_asset_forward_degraded_01"],
            "tags": [
                "expired_asset_inference",
                "status:resolved",
                "resource_state:missing",
            ],
            "metadata": {
                "status": "resolved",
                "asset_type": "video",
                "file_name": "lost_clip.mp4",
                "resource_state": "missing",
                "forward_degraded": True,
                "forward_parent_message_id": "msg_forward_01",
                "forward_depth": 3,
                "context_excerpt": "甲: [video:lost_clip.mp4]",
                "hypothesis_text": "Context-supported inference only; this looks like a forwarded lost video shell.",
                "signal_summary": {
                    "asset_id": "forward_degraded_asset_01",
                    "asset_type": "video",
                    "file_name": "lost_clip.mp4",
                    "resource_state": "missing",
                    "forward_degraded": True,
                    "forward_parent_message_id": "msg_forward_01",
                    "forward_depth": 3,
                    "context_excerpt": "甲: [video:lost_clip.mp4]",
                    "same_asset_occurrence_count": 1,
                    "signal": {
                        "reason": "sufficient_contextual_signal",
                        "snippet_count": 2,
                        "explicit_chars": 64,
                    },
                },
                "round_traces": [],
                "same_asset_occurrence_ids": [],
            },
        },
    ]

    message = AnalysisMessageRecord(
        message_uid="m_forward_01",
        run_id="run_forward_degraded",
        chat_type="group",
        chat_id="chat_751365230",
        chat_name="shi_focus",
        sender_id="user_forward",
        sender_name="forward_dumper",
        timestamp_ms=1760000000000,
        timestamp_iso="2026-03-06T01:05:30+08:00",
        message_id="msg_forward_01",
        message_seq="seq_forward_01",
        content="[forward message] 甲: [video:lost_clip.mp4] / 乙: [uploaded_file_name:lost_bundle.zip]",
        text_content="甲: [video:lost_clip.mp4] / 乙: [uploaded_file_name:lost_bundle.zip]",
        assets=[],
        extra={"preprocess": {"annotations": annotations}},
        features=AnalysisMessageFeatures(
            file_count=1,
            missing_media_count=2,
            has_forward=True,
            forward_depth=3,
            message_tags=["forward_nested", "forward_burst"],
        ),
    )
    return AnalysisMaterials(
        run_id="run_forward_degraded",
        target=ResolvedAnalysisTarget(
            target_type="group",
            raw_id="751365230",
            alias_id="chat_751365230",
            display_id="chat_751365230",
            display_name="shi_focus",
            run_id="run_forward_degraded",
        ),
        chosen_time_window=ResolvedTimeWindow(
            mode="auto_adaptive",
            start_timestamp_ms=1760000000000,
            end_timestamp_ms=1760000100000,
            start_timestamp_iso="2026-03-06T01:05:30+08:00",
            end_timestamp_iso="2026-03-06T01:07:10+08:00",
            rationale="synthetic forward degraded window",
            selected_message_count=1,
        ),
        messages=[message],
        stats=AnalysisStatsSnapshot(
            message_count=1,
            sender_count=1,
            asset_count=0,
            image_message_count=0,
            forward_message_count=1,
            reply_message_count=0,
            emoji_message_count=0,
            low_information_count=0,
            image_ratio=0.0,
            forward_ratio=1.0,
            reply_ratio=0.0,
            emoji_ratio=0.0,
            low_information_ratio=0.0,
            hourly_distribution={"01": 1},
            daily_distribution={"2026-03-06": 1},
        ),
    )


def test_benshi_analysis_pack_builder_is_alias_safe_and_structured() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPack, BenshiAnalysisPackBuilder

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_pack_builder_shape",
    )
    builder = BenshiAnalysisPackBuilder()
    pack = builder.build(materials)

    assert isinstance(pack, BenshiAnalysisPack)
    assert pack.target.display_id.startswith("chat_")
    assert pack.chosen_time_window.selected_message_count > 0
    assert pack.selected_messages
    assert pack.forward_summary is not None
    assert pack.reaction_summary is not None
    assert pack.asset_summary is not None
    assert pack.missing_media_gaps is not None
    assert pack.forward_degraded_asset_hints is not None
    assert pack.preprocess_overlay_summary is not None
    assert pack.ontology_pack is not None
    assert "史" in pack.ontology_pack.origin_definition
    assert pack.ontology_pack.taxonomy
    for item in pack.selected_messages[:20]:
        sender_id = getattr(item, "sender_id", None)
        if sender_id:
            assert not str(sender_id).isdigit(), (
                f"Raw sender id leaked into Benshi pack: {sender_id}"
            )


def test_benshi_analysis_pack_builder_can_attach_distribution_baseline_summary() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_pack_distribution_baseline",
    )
    pack = BenshiAnalysisPackBuilder(
        distribution_baseline_path=_DISTRIBUTION_BASELINE_PATH,
    ).build(materials)

    assert pack.distribution_baseline_summary is not None
    assert pack.distribution_baseline_summary.dataset_id == "shi_group_751365230"
    assert pack.distribution_baseline_summary.canonical_messages == 49
    assert pack.distribution_baseline_summary.all_occurrences == 147
    assert pack.distribution_baseline_summary.dominant_components
    assert pack.distribution_baseline_summary.cluster_count >= 1


def test_benshi_analysis_pack_builder_carries_forward_and_recurrence_signals() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_pack_forward_recurrence",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)

    assert pack.forward_summary.forward_message_count >= 1
    assert pack.forward_summary.nested_forward_count >= 1
    assert pack.recurrence_summary is not None
    assert pack.recurrence_summary.repeated_transport_count >= 0
    assert pack.recurrence_summary.repeated_asset_cluster_count >= 0


def test_benshi_analysis_pack_builder_exposes_expired_inference_summary() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_pack_expired_inference",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)

    assert pack.expired_inference_summary is not None
    assert pack.expired_inference_summary.inference_count >= 0
    assert isinstance(pack.expired_inference_summary.final_status_counts, dict)
    assert isinstance(pack.expired_inference_summary.request_kind_counts, dict)
    assert isinstance(pack.expired_inference_items, list)
    assert pack.reaction_summary is not None
    assert isinstance(pack.reaction_summary.pattern_counts, dict)
    assert isinstance(pack.reaction_patterns, list)


def test_benshi_master_agent_emits_layered_output_without_llm() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_master_agent_output",
    )
    agent = BenshiMasterAgent()
    prepared = agent.prepare(materials)
    output = agent.analyze(materials, prepared)

    assert output.agent_name == "benshi_master"
    assert output.human_report
    assert output.compact_payload
    assert "evidence_layer" in output.compact_payload
    assert "shi_component_analysis_layer" in output.compact_payload
    assert "group_consumption_layer" in output.compact_payload
    assert "shi_description_layer" in output.compact_payload
    assert "joint_analysis_layer" in output.compact_payload
    assert "cultural_interpretation_layer" in output.compact_payload
    assert "register_layer" in output.compact_payload
    assert "reply_probe_layer" in output.compact_payload
    assert "expired_inference_summary" in output.compact_payload
    assert "crowd_reaction_layer" in output.compact_payload
    assert "crowd_reaction_summary" in output.compact_payload
    assert "crowd_reaction_items" in output.compact_payload
    assert "reaction_summary" in output.compact_payload
    assert "reaction_patterns" in output.compact_payload
    assert "forward_degraded_asset_hints" in output.compact_payload
    assert output.compact_payload["pack_summary"]["ontology_summary"] is not None

    evidence_layer = output.compact_payload["evidence_layer"]
    assert "shi_presence" in evidence_layer
    assert "shi_type_candidates" in evidence_layer
    assert "transport_pattern" in evidence_layer
    assert "expired_inference_summary" in evidence_layer
    assert "crowd_reaction_summary" in evidence_layer
    assert "crowd_reaction_patterns" in evidence_layer
    assert "confidence" in evidence_layer
    component_layer = output.compact_payload["shi_component_analysis_layer"]
    assert "component_candidates" in component_layer
    assert "dominant_components" in component_layer
    assert "transport_components" in component_layer
    assert "content_components" in component_layer
    assert "component_rationale" in component_layer
    description_layer = output.compact_payload["shi_description_layer"]
    group_consumption_layer = output.compact_payload["group_consumption_layer"]
    joint_analysis_layer = output.compact_payload["joint_analysis_layer"]
    assert "one_line_definition" in description_layer
    assert "component_breakdown" in description_layer
    assert "descriptive_tags" in description_layer
    assert "how_to_describe_this_shi" in description_layer
    assert "unknown_boundaries" in description_layer
    assert "consumption_summary" in group_consumption_layer
    assert "dominant_reaction_modes" in group_consumption_layer
    assert "how_group_ate_it" in group_consumption_layer
    assert "joint_verdict" in joint_analysis_layer
    assert "modality_coordination" in joint_analysis_layer
    assert "integrated_findings" in joint_analysis_layer
    ontology_summary = output.compact_payload["pack_summary"]["ontology_summary"]
    assert "origin_definition" in ontology_summary
    assert ontology_summary["taxonomy_labels"]
    assert ontology_summary["popular_form_labels"]
    crowd_reaction = output.compact_payload["crowd_reaction_layer"]
    assert "reaction_message_count" in crowd_reaction
    assert "dominant_patterns" in crowd_reaction
    assert "representative_reactions" in crowd_reaction


def test_benshi_master_agent_keeps_alias_safe_defaults() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_master_agent_alias",
    )
    agent = BenshiMasterAgent()
    output = agent.analyze(materials, agent.prepare(materials))

    evidence_layer = output.compact_payload["evidence_layer"]
    target = evidence_layer.get("target", {})
    display_id = str(target.get("display_id", "") or "")
    assert display_id.startswith("chat_")

    for item in evidence_layer.get("participant_roles", []):
        sender_id = str(item.get("sender_id", "") or "")
        if sender_id:
            assert not sender_id.isdigit(), (
                f"Raw sender id leaked into participant role payload: {sender_id}"
            )
    serialized = str(output.compact_payload["shi_component_analysis_layer"]) + str(
        output.compact_payload["shi_description_layer"]
    )
    assert "20001" not in serialized


def test_benshi_master_agent_surfaces_distribution_baseline_summary_when_provided() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_distribution_summary_output",
    )
    agent = BenshiMasterAgent(
        distribution_baseline_path=_DISTRIBUTION_BASELINE_PATH,
    )
    output = agent.analyze(materials, agent.prepare(materials))

    distribution_summary = output.compact_payload["pack_summary"][
        "distribution_baseline_summary"
    ]
    assert distribution_summary is not None
    assert distribution_summary["dataset_id"] == "shi_group_751365230"
    assert distribution_summary["dominant_components"]
    assert distribution_summary["relay_shape"] == "forward_heavy"


def test_benshi_master_agent_reply_probe_placeholder_is_explicit() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_reply_probe_placeholder",
    )
    agent = BenshiMasterAgent()
    output = agent.analyze(materials, agent.prepare(materials))

    reply_probe_layer = output.compact_payload["reply_probe_layer"]
    assert "enabled" in reply_probe_layer
    assert "status" in reply_probe_layer
    assert "candidate_followups" in reply_probe_layer
    assert isinstance(reply_probe_layer["candidate_followups"], list)
    assert reply_probe_layer["status"] in {
        "disabled",
        "not_requested",
        "placeholder",
        "ready",
    }


def test_benshi_master_agent_voice_profile_is_exposed_even_before_live_llm() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_voice_profile",
    )
    agent = BenshiMasterAgent()
    output = agent.analyze(materials, agent.prepare(materials))

    register_layer = output.compact_payload["register_layer"]
    assert register_layer["voice_profile"] == "cn_high_context_benshi_commentator_v1"
    assert "rendered_commentary" in register_layer
    assert isinstance(register_layer["rendered_commentary"], str)


def test_benshi_prompt_payload_compacts_selected_messages_for_budget() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import build_benshi_master_prompt_payload

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_prompt_payload_budget",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)
    payload = build_benshi_master_prompt_payload(
        pack,
        max_selected_messages=8,
        max_forward_summaries=4,
        max_recurrence_summaries=4,
        max_missing_media_gaps=4,
    )

    selected_messages = payload["selected_messages"]
    assert len(selected_messages) <= 8
    assert selected_messages == sorted(
        selected_messages,
        key=lambda item: (item["timestamp_iso"], item["message_uid"]),
    )
    assert all("source_message_ids" not in item for item in selected_messages)
    assert all("source_thread_ids" not in item for item in selected_messages)


def test_benshi_reply_probe_prompt_version_enables_probe() -> None:
    from qq_data_analysis.benshi_prompting import resolve_benshi_prompt_scaffold

    scaffold = resolve_benshi_prompt_scaffold("benshi_master_v1_reply_probe")

    assert scaffold is not None
    assert scaffold.reply_probe_enabled is True


def test_benshi_prompt_payload_exposes_image_caption_samples() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import build_benshi_master_prompt_payload
    from qq_data_analysis.models import (
        BenshiForwardDegradedAssetHint,
        BenshiImageClusterSummary,
        BenshiReactionAggregateSummary,
        BenshiReactionPatternSummary,
        ImageCaptionSample,
    )

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_prompt_payload_captions",
    )
    pack = BenshiAnalysisPackBuilder().build(materials).model_copy(
        update={
            "image_cluster_summaries": [
                BenshiImageClusterSummary(
                    cluster_id="img_cluster_01",
                    cluster_kind="context_bundle_recurrent",
                    member_count=4,
                    reference_count=8,
                    distinct_message_count=2,
                    representative_message_uid="m_1",
                    representative_timestamp_iso="2026-03-18T00:00:00+08:00",
                    representative_file_name="sample.png",
                    representative_context_excerpt="四张图的图串上下文",
                    file_name_examples=["sample.png", "sample_2.png"],
                    notes=["同一图串重复出现两次。"],
                    evidence_message_uids=["m_1", "m_2"],
                )
            ],
            "image_caption_samples": [
                ImageCaptionSample(
                    cluster_id="img_cluster_01",
                    cluster_kind="context_bundle_recurrent",
                    message_uid="m_1",
                    timestamp_iso="2026-03-18T00:00:00+08:00",
                    sender_id="user_x",
                    sender_name="tester",
                    file_name="sample.png",
                    resolved_path="assets/images/sample.png",
                    context_excerpt="上下文",
                    caption="一张聊天截图，上方有几行文字。",
                    model_name="gpt-5.4",
                )
            ],
            "reaction_summary": BenshiReactionAggregateSummary(
                reaction_message_count=3,
                reactor_count=1,
                reply_participation_count=1,
                dominant_modes=["ridicule", "echo"],
                notes=["群友主要用短反应接球。"],
            ),
            "reaction_patterns": [
                BenshiReactionPatternSummary(
                    pattern_label="ridicule",
                    score=2.0,
                    message_count=2,
                    reactor_count=1,
                    representative_message_uids=["m_3"],
                    representative_excerpts=["这批一看就是库存回放。"],
                    notes=["短吐槽为主。"],
                )
            ],
            "forward_degraded_asset_hints": [
                BenshiForwardDegradedAssetHint(
                    hint_id="fwdhint_01",
                    asset_type="video",
                    file_name="demo.mp4",
                    occurrence_count=2,
                    outer_message_count=1,
                    representative_context_excerpt="deep forward 里提到一个视频壳子",
                    preview_examples=["[video:demo.mp4]"],
                )
            ],
        }
    )
    payload = build_benshi_master_prompt_payload(pack, max_selected_messages=4)

    assert payload["image_cluster_summaries"]
    assert payload["image_cluster_summaries"][0]["cluster_id"] == "img_cluster_01"
    assert payload["image_caption_samples"]
    assert payload["image_caption_samples"][0]["cluster_id"] == "img_cluster_01"
    assert payload["image_caption_samples"][0]["file_name"] == "sample.png"
    assert payload["reaction_summary"]["reaction_message_count"] == 3
    assert payload["reaction_patterns"][0]["pattern_label"] == "ridicule"
    assert payload["forward_degraded_asset_hints"][0]["file_name"] == "demo.mp4"


def test_benshi_prompt_payload_exposes_component_and_description_inputs() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import build_benshi_master_prompt_payload

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_prompt_payload_components",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)
    payload = build_benshi_master_prompt_payload(pack, max_selected_messages=6)

    assert payload["shi_component_summaries"]
    assert payload["shi_component_summaries"][0]["component_label"]
    assert payload["shi_description_profile"] is not None
    assert payload["shi_description_profile"]["base_definition"]
    assert payload["reaction_summary"] is not None
    assert "pattern_counts" in payload["reaction_summary"]
    assert isinstance(payload["reaction_patterns"], list)
    assert payload["ontology_pack"] is not None
    assert payload["ontology_pack"]["origin_definition"]
    assert payload["ontology_pack"]["taxonomy"]
    assert payload["ontology_pack"]["popular_forms"]


def test_benshi_prompt_payload_uses_compact_distribution_baseline_context() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import build_benshi_master_prompt_payload

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_prompt_distribution_context",
    )
    pack = BenshiAnalysisPackBuilder(
        distribution_baseline_path=_DISTRIBUTION_BASELINE_PATH,
    ).build(materials)
    payload = build_benshi_master_prompt_payload(pack, max_selected_messages=6)

    context = payload["distribution_baseline_context"]
    assert context is not None
    assert context["dataset_id"] == "shi_group_751365230"
    assert context["canonical_sample_overview"]["canonical_messages"] == 49
    assert context["current_window_distribution"]["dominant_components"]
    assert context["current_window_distribution"]["transport_pattern"]["relay_shape"] == "forward_heavy"
    assert "shi_type_candidates" not in context["current_window_distribution"]


def test_forward_expansion_extracts_deep_forward_video_and_file_tokens() -> None:
    from qq_data_analysis.preprocessors.forward_expansion import _build_forward_expansion

    message = SimpleNamespace(
        message_id="msg_forward_01",
        message_seq="seq_forward_01",
        message_uid="m_forward_01",
        timestamp_iso="2026-03-06T01:05:30+08:00",
        sender_id="user_forward",
        sender_name="forward_dumper",
        content="[forward message] 甲: [video:lost_clip.mp4]",
        text_content="甲: [video:lost_clip.mp4]",
        lineage=None,
    )
    segment = SimpleNamespace(
        type="forward",
        summary="forward_bundle",
        extra={
            "preview_lines": [
                "甲: [video:lost_clip.mp4]",
                "乙: [uploaded_file_name:lost_bundle.zip]",
            ],
            "detailed_text": "甲: [video:lost_clip.mp4]\n乙: [uploaded_file_name:lost_bundle.zip]",
            "children": [],
            "segment_id": "seg_forward_01",
        },
        segment_id="seg_forward_01",
    )

    result = _build_forward_expansion(message=message, segment=segment)

    assert result is not None
    refs = result.details["inner_asset_refs"]
    assert any(
        item["asset_type"] == "video"
        and item["file_name"] == "lost_clip.mp4"
        and item["forward_degraded"] is True
        for item in refs
    )
    assert any(
        item["asset_type"] == "file"
        and item["file_name"] == "lost_bundle.zip"
        and item["forward_degraded"] is True
        for item in refs
    )


def test_benshi_pack_and_prompt_include_forward_degraded_gaps() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import (
        build_benshi_master_prompt_payload,
        build_expired_inference_summary,
    )

    materials = _build_forward_degraded_materials()
    pack = BenshiAnalysisPackBuilder().build(materials)
    payload = build_benshi_master_prompt_payload(pack, max_selected_messages=4)
    live_summary = build_expired_inference_summary(materials)

    assert any(item.file_name == "lost_clip.mp4" for item in pack.forward_degraded_asset_hints)
    assert any(item.file_name == "lost_bundle.zip" for item in pack.forward_degraded_asset_hints)
    assert any(
        item.file_name == "lost_clip.mp4" and item.status == "forward_degraded_asset"
        for item in pack.missing_media_gaps
    )
    assert pack.expired_inference_summary.asset_type_counts.get("video") == 1
    assert payload["missing_media_gaps"][0]["forward_degraded"] is True
    assert payload["expired_inference_summary"]["top_items"][0]["file_name"] == "lost_clip.mp4"
    assert payload["expired_inference_summary"]["top_items"][0]["forward_degraded"] is True
    assert live_summary["top_records"][0]["file_name"] == "lost_clip.mp4"
    assert live_summary["top_records"][0]["forward_degraded"] is True


def test_benshi_master_agent_surfaces_forward_degraded_expired_inference() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_forward_degraded_materials()
    agent = BenshiMasterAgent()
    output = agent.analyze(materials, agent.prepare(materials))

    assert "DeepForward 退化媒体" in output.human_report
    assert "lost_clip.mp4" in output.human_report
    top_item = output.compact_payload["expired_inference_summary"]["top_items"][0]
    assert top_item["file_name"] == "lost_clip.mp4"
    assert top_item["forward_degraded"] is True


def test_benshi_live_smoke_pack_serialization_includes_missing_and_overlay_context() -> None:
    from qq_data_analysis.models import (
        BenshiMissingMediaGap,
        BenshiPreprocessOverlayItem,
        BenshiPreprocessOverlaySummary,
    )
    from scripts.run_benshi_live_llm_smoke import _serialize_pack_context
    from types import SimpleNamespace

    class _Dumpable:
        def __init__(self, payload):
            self._payload = payload

        def model_dump(self, mode="json"):
            assert mode == "json"
            return self._payload

    first_message = SimpleNamespace(
        message_uid="m_1",
        timestamp_iso="2026-03-19T00:00:01+08:00",
        missing_media_count=2,
        preprocess_labels=["expired_asset_inference", "missing_media_context"],
        decision_summary="失活视频仍需更多上下文。",
        processed_text="只能保守描述视频标题和周边文本。",
    )
    pack = SimpleNamespace(
        selected_messages=[first_message],
        reaction_summary=_Dumpable(
            {
                "reaction_message_count": 3,
                "reactor_count": 2,
                "dominant_modes": ["复读/回声", "围观/惊诧"],
            }
        ),
        reaction_patterns=[
            _Dumpable(
                {
                    "pattern_id": "repeat_echo",
                    "pattern_label": "复读/回声",
                    "scope": "top_level",
                    "message_count": 2,
                    "reactor_count": 2,
                }
            )
        ],
        missing_media_gaps=[
            BenshiMissingMediaGap(
                gap_id="gap_01",
                message_uid=first_message.message_uid,
                timestamp_iso=first_message.timestamp_iso,
                sender_id="user_x",
                sender_name="tester",
                asset_id="asset_video_01",
                asset_type="video",
                file_name="missing_video.mp4",
                status="missing_after_napcat",
                resolver="napcat_context_only",
                context_excerpt="视频标题只能看到壳子。",
                reason="token expired",
            )
        ],
        preprocess_overlay_summary=BenshiPreprocessOverlaySummary(
            view_id="shi_focus_test",
            delivery_profile="raw_plus_processed",
            top_labels={"expired_asset_inference": 1, "missing_media_context": 1},
            representative_items=[
                BenshiPreprocessOverlayItem(
                    message_uid=first_message.message_uid,
                    delivery_profile="raw_plus_processed",
                    processed_text="仅能保守描述视频标题与周边文本。",
                    decision_summary="失活视频需要更多上下文。",
                    labels=["expired_asset_inference", "missing_media_context"],
                    source_message_ids=["m_1"],
                )
            ],
            notes=["overlay 已附着到 1 条消息。"],
        ),
        asset_summary=_Dumpable({"asset_type_missing_counts": {"video": 1}}),
    )

    context = _serialize_pack_context(pack)

    assert context["reaction_summary"]["reaction_message_count"] == 3
    assert context["reaction_patterns"][0]["pattern_label"] == "复读/回声"
    assert context["missing_media_gaps"][0]["asset_type"] == "video"
    assert context["missing_media_gaps"][0]["reason"] == "token expired"
    assert context["preprocess_overlay_summary"]["top_labels"] == {
        "expired_asset_inference": 1,
        "missing_media_context": 1,
    }
    assert context["selected_message_overview"][0]["missing_media_count"] == 2
    assert context["selected_message_overview"][0]["decision_summary"] == "失活视频仍需更多上下文。"


def test_benshi_prompt_payload_keeps_ontology_when_example_bank_context_is_injected() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import build_benshi_master_prompt_payload
    from qq_data_analysis.benshi_seed_artifacts import (
        build_example_bank_prompt_context,
        load_distribution_baseline_prompt_context,
    )

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_prompt_payload_reference_context",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)
    example_bank_context = build_example_bank_prompt_context(
        Path("dev/testdata/local/shi_group_751365230/benshi_example_bank_manifest.json"),
        include_groups=[
            "good_judgment_examples",
            "good_description_examples",
        ],
        max_examples_per_group=1,
        max_negative_templates=1,
    )
    distribution_context = load_distribution_baseline_prompt_context(
        Path("dev/testdata/local/shi_group_751365230/benshi_distribution_baseline.json")
    )

    payload = build_benshi_master_prompt_payload(
        pack,
        max_selected_messages=6,
        example_bank_context=example_bank_context,
        distribution_baseline_context=distribution_context,
    )

    assert payload["ontology_pack"] is not None
    assert payload["ontology_pack"]["origin_definition"]
    assert payload["example_bank_context"] is not None
    assert payload["example_bank_context"]["selected_counts"]["good_judgment_examples"] == 1
    assert payload["example_bank_context"]["selected_counts"]["good_description_examples"] == 1
    assert "good_reply_probe_examples" not in payload["example_bank_context"]["selected_counts"]
    assert payload["distribution_baseline_context"] is not None


def test_benshi_description_layer_keeps_unknowns_when_media_is_missing() -> None:
    from qq_data_analysis.benshi_agent import BenshiMasterAgent

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_description_unknowns",
    )
    agent = BenshiMasterAgent()
    output = agent.analyze(materials, agent.prepare(materials))

    description_layer = output.compact_payload["shi_description_layer"]
    unknowns = description_layer["unknown_boundaries"]
    assert isinstance(unknowns, list)
    assert unknowns
    assert any("未知" in item or "缺失" in item or "保守" in item for item in unknowns)


def test_benshi_ontology_pack_distinguishes_origin_and_popular_forms() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_ontology_pack",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)

    ontology = pack.ontology_pack
    assert ontology is not None
    taxonomy_labels = {item.label for item in ontology.taxonomy}
    popular_labels = {item.label for item in ontology.popular_forms}

    assert {"原生史", "工业史", "典中典史", "外源史", "二手史", "二阶史"} <= taxonomy_labels
    assert {"外源截图史", "套娃 forward 史", "图串返场史", "拼盘混装史"} <= popular_labels
    assert any("popular" in (item.relation_to_origin or "") for item in ontology.popular_forms)


def test_benshi_prompt_payload_roundtrips_reference_contexts() -> None:
    from qq_data_analysis.benshi_pack import BenshiAnalysisPackBuilder
    from qq_data_analysis.benshi_prompting import build_benshi_master_prompt_payload

    materials = _build_materials(
        fixture_path=_FIXTURE_PATH,
        target_id=_TARGET_ID,
        tmp_name="test_benshi_prompt_payload_reference_contexts",
    )
    pack = BenshiAnalysisPackBuilder().build(materials)
    payload = build_benshi_master_prompt_payload(
        pack,
        max_selected_messages=4,
        example_bank_context={
            "artifact": "benshi_example_bank_prompt_context",
            "dataset_id": "shi_group_751365230",
            "selected_counts": {"good_judgment_examples": 1, "negative_templates": 2},
            "example_groups": [
                {
                    "group_name": "good_judgment_examples",
                    "examples": [
                        {
                            "example_id": "benshi_example_0001",
                            "expected_direction": "先按结构判断，不要空喊抽象。",
                        }
                    ],
                }
            ],
        },
        distribution_baseline_context={
            "artifact": "benshi_distribution_prompt_context",
            "dataset_id": "shi_group_751365230",
            "current_window_distribution": {
                "dominant_components": ["外源史", "二手史", "单人主导倾倒"],
            },
            "delivery_structure_distribution": {
                "delivery_mode_counts": {"forward_bundle": 40},
            },
        },
    )

    assert payload["example_bank_context"] is not None
    assert payload["example_bank_context"]["artifact"] == "benshi_example_bank_prompt_context"
    assert payload["example_bank_context"]["selected_counts"]["good_judgment_examples"] == 1
    assert payload["example_bank_context"]["example_groups"][0]["examples"][0]["example_id"] == "benshi_example_0001"
    assert payload["distribution_baseline_context"] is not None
    assert payload["distribution_baseline_context"]["artifact"] == "benshi_distribution_prompt_context"
    assert payload["distribution_baseline_context"]["current_window_distribution"]["dominant_components"][0] == "外源史"
