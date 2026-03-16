from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from qq_data_analysis import AnalysisJobConfig, AnalysisSubstrate, AnalysisTarget
from qq_data_analysis.llm_agent import (
    DeepSeekAnalysisClient,
    DeepSeekRuntimeConfig,
    LlmResponseBundle,
    LlmUsageSnapshot,
    OpenAICompatibleAnalysisClient,
)
from qq_data_analysis.llm_window import (
    WholeWindowLlmAnalyzer,
    load_text_analysis_client,
    load_saved_analysis_pack,
    save_llm_analysis_result,
)
from qq_data_analysis.models import ImageCaptionSample, LlmAnalysisJobConfig
from qq_data_process import (
    ChunkPolicySpec,
    DeterministicEmbeddingProvider,
    EmbeddingPolicy,
    PreprocessJobConfig,
    PreprocessService,
)


class _FakeTextClient:
    def __init__(self) -> None:
        self.config = DeepSeekRuntimeConfig(api_key="fake-key", model="deepseek-chat")

    def analyze_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> LlmResponseBundle:
        assert (
            "高层、抽象、开放式的长报告" in system_prompt
            or "Benshi 工作流" in system_prompt
        )
        assert "Analysis Pack" in user_prompt
        assert max_output_tokens == 900
        return LlmResponseBundle(
            parsed_payload={},
            raw_text="# 总体概览\n\n这是一段测试长报告。\n\n## 值得继续细化的方向\n\n- 图文互动\n- 套娃转发",
            reasoning_text="",
            finish_reason="stop",
            usage=LlmUsageSnapshot(
                prompt_tokens=777,
                completion_tokens=333,
                total_tokens=1110,
                reasoning_tokens=0,
                cached_tokens=0,
            ),
            raw_response={"provider": "fake"},
        )


def _new_tmp_path(prefix: str) -> Path:
    tmp_root = Path(".tmp")
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_root / f"{prefix}_{uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    return tmp_path


def _build_analysis_state(tmp_name: str) -> tuple[Path, Path]:
    tmp_path = _new_tmp_path(tmp_name)

    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=Path("tests/fixtures/analysis_seed.jsonl"),
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        chunk_policy_specs=[
            ChunkPolicySpec(
                name="hybrid",
                params={"gap_seconds": 900, "max_messages": 5, "overlap": 1},
            )
        ],
    )
    result = service.run(config)
    return result.sqlite_path, result.qdrant_location


def test_whole_window_llm_prepare_builds_pack() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_whole_window_llm_prepare")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            max_representative_messages=6, max_output_tokens=900
        ),
    )
    plan = analyzer.prepare(materials)

    assert plan.pack.pack_summary
    assert len(plan.pack.representative_messages) <= 6
    assert plan.pack.message_reference_pool
    assert "image_messages" in plan.pack.special_content_types
    assert plan.estimated_input_tokens > 0
    assert plan.pack.media_coverage is not None
    assert isinstance(plan.pack.media_coverage.total_image_references, int)
    assert isinstance(plan.pack.media_coverage.overall_media_missing_ratio, float)


def test_whole_window_llm_analyze_and_artifacts_roundtrip() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_whole_window_llm_artifacts")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            max_representative_messages=6, max_output_tokens=900
        ),
    )
    plan = analyzer.prepare(materials)
    result = analyzer.analyze(plan)
    out_dir = _new_tmp_path("test_whole_window_llm_artifacts_out")
    result = save_llm_analysis_result(
        result=result,
        plan=plan,
        out_dir=out_dir,
        prefix="window_test",
    )

    assert "测试长报告" in result.report_body
    assert result.usage.total_tokens == 1110
    assert result.artifacts is not None
    pack = load_saved_analysis_pack(Path(result.artifacts.analysis_pack_path))
    assert pack.pack_summary == result.pack.pack_summary
    assert pack.media_coverage is not None
    assert (
        pack.media_coverage.total_image_references
        == result.pack.media_coverage.total_image_references
    )
    assert (
        pack.media_coverage.overall_media_missing_ratio
        == result.pack.media_coverage.overall_media_missing_ratio
    )
    assert "has_image" in pack.media_coverage.media_availability_flags
    assert Path(result.artifacts.report_path).exists()
    assert Path(result.artifacts.llm_run_meta_path).exists()
    assert Path(result.artifacts.usage_path).exists()


def test_benshi_prompt_version_exposes_uncertainty_and_media_coverage() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_prompt_version")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            prompt_version="benshi_window_v1",
            max_representative_messages=6,
            max_output_tokens=900,
        ),
    )
    plan = analyzer.prepare(materials)

    assert plan.prompt_version == "benshi_window_v1"
    assert "Benshi 工作流" in plan.system_prompt
    assert "不要伪造 OCR" in plan.system_prompt
    assert "如果 InferredItems 为 0" in plan.system_prompt
    assert "话题跳跃、事件触发、用户动机归因到某张缺失图片" in plan.system_prompt
    assert "## Media Coverage" in plan.user_prompt
    assert "## Missing Media Text-Only Inference" in plan.user_prompt
    assert "OverallMissingRatio" in plan.user_prompt
    assert "不确定性" in plan.user_prompt
    assert "no approved context-only missing-media hypotheses" in plan.user_prompt
    assert (
        "do not attribute topic jumps, event triggers, or user intent"
        in plan.user_prompt
    )


def test_benshi_prompt_version_roundtrips_in_saved_artifacts() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_artifact_roundtrip")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            prompt_version="benshi_window_v1",
            max_representative_messages=6,
            max_output_tokens=900,
        ),
    )
    plan = analyzer.prepare(materials)
    result = analyzer.analyze(plan)
    out_dir = _new_tmp_path("test_benshi_artifact_roundtrip_out")
    result = save_llm_analysis_result(
        result=result,
        plan=plan,
        out_dir=out_dir,
        prefix="benshi_window_test",
    )

    meta_path = Path(result.artifacts.llm_run_meta_path)
    prompt_path = Path(result.artifacts.prompt_path)
    pack = load_saved_analysis_pack(Path(result.artifacts.analysis_pack_path))

    assert meta_path.exists()
    assert prompt_path.exists()
    assert '"prompt_version": "benshi_window_v1"' in meta_path.read_text(
        encoding="utf-8"
    )
    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "Benshi 工作流" in prompt_text
    assert "Media Coverage" in prompt_text
    assert pack.pack_summary == result.pack.pack_summary


def test_benshi_v2_prompt_exposes_soft_roles_and_dimensions() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_v2_prompt")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            prompt_version="benshi_window_v2",
            max_representative_messages=6,
            max_output_tokens=900,
        ),
    )
    plan = analyzer.prepare(materials)

    assert plan.prompt_version == "benshi_window_v2"
    assert "第二轮报告" in plan.system_prompt
    assert "Stable Dimension Block" in plan.system_prompt
    assert "Soft Participant Roles" in plan.system_prompt
    assert "## Stable Review Dimensions" in plan.user_prompt
    assert "interaction_density" in plan.user_prompt
    assert "content_provenance" in plan.user_prompt
    assert "## Allowed Soft Participant Roles" in plan.user_prompt
    assert "narrative_carrier" in plan.user_prompt
    assert "noise_broadcaster" in plan.user_prompt
    assert "若证据不足请写 `unclear`" in plan.user_prompt


def test_benshi_v2_prompt_can_include_image_caption_evidence() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_v2_image_caption")
    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            prompt_version="benshi_window_v2",
            max_representative_messages=6,
            max_output_tokens=900,
        ),
    )
    plan = analyzer.prepare(materials)
    augmented_pack = plan.pack.model_copy(
        update={
            "image_caption_samples": [
                ImageCaptionSample(
                    message_uid=plan.pack.representative_messages[0].message_uid,
                    timestamp_iso=plan.pack.representative_messages[0].timestamp_iso,
                    sender_id=plan.pack.representative_messages[0].sender_id,
                    sender_name=plan.pack.representative_messages[0].sender_name,
                    file_name="sample.png",
                    resolved_path="C:/tmp/sample.png",
                    context_excerpt="测试上下文",
                    caption="这是一张带有界面和少量文字的截图。",
                    model_name="gpt-5.4",
                )
            ]
        }
    )
    augmented_plan = analyzer.build_plan_from_pack(augmented_pack)

    assert "## Image Caption Evidence" in augmented_plan.user_prompt
    assert "测试上下文" in augmented_plan.user_prompt
    assert "这是一张带有界面和少量文字的截图。" in augmented_plan.user_prompt


def test_load_text_analysis_client_supports_openai_compatible_provider() -> None:
    tmp_path = _new_tmp_path("test_openai_compatible_loader")
    config_path = tmp_path / "llm.local.json"
    config_path.write_text(
        """
{
  "provider": "openai_compatible",
  "openai_compatible": {
    "api_key": "fake-key",
    "base_url": "http://127.0.0.1:9999/v1",
    "model": "gpt-5.4",
    "proxy_url": null,
    "timeout_s": 30.0
  }
}
""".strip(),
        encoding="utf-8",
    )

    client = load_text_analysis_client(config_path)

    assert isinstance(client, OpenAICompatibleAnalysisClient)
    assert client.config.model == "gpt-5.4"


def test_load_text_analysis_client_respects_explicit_deepseek_provider() -> None:
    tmp_path = _new_tmp_path("test_deepseek_loader")
    config_path = tmp_path / "llm.local.json"
    config_path.write_text(
        """
{
  "provider": "deepseek",
  "deepseek": {
    "api_key": "fake-key",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "proxy_url": null,
    "timeout_s": 30.0
  },
  "openai_compatible": {
    "api_key": "fake-key-2",
    "base_url": "http://127.0.0.1:9999/v1",
    "model": "gpt-4o",
    "proxy_url": null,
    "timeout_s": 30.0
  }
}
""".strip(),
        encoding="utf-8",
    )

    client = load_text_analysis_client(config_path)

    assert isinstance(client, DeepSeekAnalysisClient)
    assert client.config.model == "deepseek-chat"


def test_media_coverage_tracks_missing_ratios_without_fabricating_semantics() -> None:
    from qq_data_analysis.llm_window import WholeWindowPackBuilder
    from qq_data_analysis.models import (
        AnalysisMaterials,
        AnalysisMessageFeatures,
        AnalysisMessageRecord,
        AnalysisStatsSnapshot,
        ResolvedAnalysisTarget,
        ResolvedTimeWindow,
    )

    materials = AnalysisMaterials(
        run_id="test_run",
        target=ResolvedAnalysisTarget(
            target_type="group",
            raw_id="30001",
            alias_id="chat_a",
            display_id="chat_a",
            display_name="测试群",
            run_id="test_run",
        ),
        chosen_time_window=ResolvedTimeWindow(
            mode="auto_adaptive",
            start_timestamp_ms=1767229200000,
            end_timestamp_ms=1767319200000,
            start_timestamp_iso="2026-01-01T09:00:00+08:00",
            end_timestamp_iso="2026-01-02T10:00:00+08:00",
            rationale="auto",
            selected_message_count=3,
        ),
        messages=[
            AnalysisMessageRecord(
                message_uid="uid_1",
                run_id="test_run",
                chat_type="group",
                chat_id="30001",
                sender_id="user_a",
                timestamp_ms=1767229200000,
                timestamp_iso="2026-01-01T09:00:00+08:00",
                content="test text",
                text_content="test text",
                assets=[
                    {"type": "image", "file_name": "a.jpg", "materialized": True},
                    {"type": "image", "file_name": "b.jpg", "materialized": False},
                ],
                features=AnalysisMessageFeatures(image_count=2),
            ),
            AnalysisMessageRecord(
                message_uid="uid_2",
                run_id="test_run",
                chat_type="group",
                chat_id="30001",
                sender_id="user_b",
                timestamp_ms=1767229500000,
                timestamp_iso="2026-01-01T09:05:00+08:00",
                content="test file",
                text_content="test file",
                assets=[
                    {"type": "file", "file_name": "doc.pdf", "materialized": False},
                ],
                features=AnalysisMessageFeatures(file_count=1),
            ),
        ],
        stats=AnalysisStatsSnapshot(
            message_count=2,
            sender_count=2,
            asset_count=3,
            image_message_count=1,
            forward_message_count=0,
            reply_message_count=0,
            emoji_message_count=0,
            low_information_count=0,
            image_ratio=0.5,
            forward_ratio=0.0,
            reply_ratio=0.0,
            emoji_ratio=0.0,
            low_information_ratio=0.0,
        ),
    )

    builder = WholeWindowPackBuilder(
        LlmAnalysisJobConfig(max_representative_messages=10)
    )
    pack = builder.build(materials)

    assert pack.media_coverage.total_image_references == 2
    assert pack.media_coverage.total_file_references == 1
    assert pack.media_coverage.missing_image_count == 1
    assert pack.media_coverage.missing_file_count == 1
    assert pack.media_coverage.image_missing_ratio == 0.5
    assert pack.media_coverage.file_missing_ratio == 1.0
    assert pack.media_coverage.overall_media_missing_ratio > 0.6
    assert pack.media_coverage.media_availability_flags["has_missing_media"] is True
    assert any("missing ratio" in w.lower() for w in pack.warnings)


def test_media_inference_scaffold_separates_observed_missing_and_inferred() -> None:
    from qq_data_analysis.llm_window import WholeWindowPackBuilder
    from qq_data_analysis.models import (
        AnalysisMaterials,
        AnalysisMessageFeatures,
        AnalysisMessageRecord,
        AnalysisStatsSnapshot,
        ResolvedAnalysisTarget,
        ResolvedTimeWindow,
    )

    materials = AnalysisMaterials(
        run_id="test_media_scaffold",
        target=ResolvedAnalysisTarget(
            target_type="group",
            raw_id="30002",
            alias_id="chat_b",
            display_id="chat_b",
            display_name="测试群二",
            run_id="test_media_scaffold",
        ),
        chosen_time_window=ResolvedTimeWindow(
            mode="auto_adaptive",
            start_timestamp_ms=1767229200000,
            end_timestamp_ms=1767229800000,
            start_timestamp_iso="2026-01-01T09:00:00+08:00",
            end_timestamp_iso="2026-01-01T09:10:00+08:00",
            rationale="auto",
            selected_message_count=2,
        ),
        messages=[
            AnalysisMessageRecord(
                message_uid="uid_obs",
                run_id="test_media_scaffold",
                chat_type="group",
                chat_id="30002",
                sender_id="user_a",
                timestamp_ms=1767229200000,
                timestamp_iso="2026-01-01T09:00:00+08:00",
                content="这里有一张图",
                text_content="这里有一张图",
                assets=[
                    {"asset_type": "image", "file_name": "ok.jpg", "materialized": True}
                ],
                features=AnalysisMessageFeatures(image_count=1),
            ),
            AnalysisMessageRecord(
                message_uid="uid_missing",
                run_id="test_media_scaffold",
                chat_type="group",
                chat_id="30002",
                sender_id="user_b",
                timestamp_ms=1767229500000,
                timestamp_iso="2026-01-01T09:05:00+08:00",
                content="这张图没加载出来",
                text_content="这张图没加载出来",
                assets=[
                    {
                        "asset_type": "image",
                        "file_name": "miss.jpg",
                        "materialized": False,
                    }
                ],
                features=AnalysisMessageFeatures(image_count=1),
            ),
        ],
        stats=AnalysisStatsSnapshot(
            message_count=2,
            sender_count=2,
            asset_count=2,
            image_message_count=2,
            forward_message_count=0,
            reply_message_count=0,
            emoji_message_count=0,
            low_information_count=0,
            image_ratio=1.0,
            forward_ratio=0.0,
            reply_ratio=0.0,
            emoji_ratio=0.0,
            low_information_ratio=0.0,
        ),
    )

    pack = WholeWindowPackBuilder(LlmAnalysisJobConfig()).build(materials)

    assert len(pack.media_inference_scaffold.observed) == 1
    assert len(pack.media_inference_scaffold.missing) == 1
    assert pack.media_inference_scaffold.inferred == []
    assert len(pack.media_inference_scaffold.unknown) == 1
    assert pack.media_inference_scaffold.observed[0].state == "observed"
    assert pack.media_inference_scaffold.observed[0].confidence_label == "direct"
    assert pack.media_inference_scaffold.missing[0].state == "missing"
    assert pack.media_inference_scaffold.missing[0].confidence_label == "unknown"
    assert pack.media_inference_scaffold.unknown[0].state == "unknown"


def test_text_only_gap_inference_uses_manifest_missing_status_and_context() -> None:
    tmp_path = _new_tmp_path("test_text_gap_inference")
    source_path = tmp_path / "seed.jsonl"
    manifest_path = tmp_path / "seed.manifest.json"

    jsonl_lines = [
        {
            "chat_type": "group",
            "chat_id": "40001",
            "group_id": "40001",
            "chat_name": "缺图推断测试群",
            "sender_id": "111",
            "sender_name": "甲",
            "message_id": "1",
            "message_seq": "1001",
            "timestamp_ms": 1767229200000,
            "timestamp_iso": "2026-01-01T09:00:00+08:00",
            "content": "[image:ref.png] 这张截图就是典中典史",
            "text_content": "这张截图就是典中典史",
            "image_file_names": ["ref.png"],
            "uploaded_file_names": [],
            "emoji_tokens": [],
            "segments": [
                {
                    "type": "image",
                    "file_name": "ref.png",
                    "path": "C:\\QQ\\ref.png",
                    "md5": "img-ref",
                    "extra": {},
                },
                {"type": "text", "text": "这张截图就是典中典史", "extra": {}},
            ],
            "extra": {},
        },
        {
            "chat_type": "group",
            "chat_id": "40001",
            "group_id": "40001",
            "chat_name": "缺图推断测试群",
            "sender_id": "222",
            "sender_name": "乙",
            "message_id": "2",
            "message_seq": "1002",
            "timestamp_ms": 1767229260000,
            "timestamp_iso": "2026-01-01T09:01:00+08:00",
            "content": "这也太典了",
            "text_content": "这也太典了",
            "image_file_names": [],
            "uploaded_file_names": [],
            "emoji_tokens": [],
            "segments": [{"type": "text", "text": "这也太典了", "extra": {}}],
            "extra": {},
        },
        {
            "chat_type": "group",
            "chat_id": "40001",
            "group_id": "40001",
            "chat_name": "缺图推断测试群",
            "sender_id": "333",
            "sender_name": "丙",
            "message_id": "3",
            "message_seq": "1003",
            "timestamp_ms": 1767229320000,
            "timestamp_iso": "2026-01-01T09:02:00+08:00",
            "content": "[image:miss.png] 这张图又是外源史截图吧",
            "text_content": "这张图又是外源史截图吧",
            "image_file_names": ["miss.png"],
            "uploaded_file_names": [],
            "emoji_tokens": [],
            "segments": [
                {
                    "type": "image",
                    "file_name": "miss.png",
                    "path": "C:\\QQ\\miss.png",
                    "md5": "img-miss",
                    "extra": {},
                },
                {"type": "text", "text": "这张图又是外源史截图吧", "extra": {}},
            ],
            "extra": {},
        },
        {
            "chat_type": "group",
            "chat_id": "40001",
            "group_id": "40001",
            "chat_name": "缺图推断测试群",
            "sender_id": "222",
            "sender_name": "乙",
            "message_id": "4",
            "message_seq": "1004",
            "timestamp_ms": 1767229380000,
            "timestamp_iso": "2026-01-01T09:03:00+08:00",
            "content": "还是聊天记录那种二手转发",
            "text_content": "还是聊天记录那种二手转发",
            "image_file_names": [],
            "uploaded_file_names": [],
            "emoji_tokens": [],
            "segments": [
                {"type": "text", "text": "还是聊天记录那种二手转发", "extra": {}}
            ],
            "extra": {},
        },
    ]
    source_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in jsonl_lines) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "chat_type": "group",
                "chat_id": "40001",
                "chat_name": "缺图推断测试群",
                "exported_at": "2026-01-01T09:05:00+08:00",
                "record_count": 4,
                "asset_summary": {
                    "copied": 1,
                    "reused": 0,
                    "missing": 1,
                    "error": 0,
                    "total": 2,
                },
                "assets": [
                    {
                        "message_id": "1",
                        "message_seq": "1001",
                        "sender_id": "111",
                        "timestamp_iso": "2026-01-01T09:00:00+08:00",
                        "asset_type": "image",
                        "asset_role": None,
                        "file_name": "ref.png",
                        "source_path": "C:\\QQ\\ref.png",
                        "resolved_source_path": "C:\\QQ\\ref.png",
                        "exported_rel_path": "images/ref.png",
                        "status": "copied",
                        "resolver": "segment_path",
                        "note": None,
                        "extra": {},
                    },
                    {
                        "message_id": "3",
                        "message_seq": "1003",
                        "sender_id": "333",
                        "timestamp_iso": "2026-01-01T09:02:00+08:00",
                        "asset_type": "image",
                        "asset_role": None,
                        "file_name": "miss.png",
                        "source_path": "C:\\QQ\\miss.png",
                        "resolved_source_path": None,
                        "exported_rel_path": None,
                        "status": "missing",
                        "resolver": "unresolved",
                        "note": "source file not found",
                        "extra": {},
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=source_path,
        state_dir=tmp_path / "state",
        skip_vector_index=True,
    )
    result = service.run(config)
    substrate = AnalysisSubstrate(
        sqlite_path=result.sqlite_path,
        qdrant_path=result.qdrant_location,
    )
    try:
        materials = substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="40001"),
            )
        )
    finally:
        substrate.close()

    analyzer = WholeWindowLlmAnalyzer(
        client=_FakeTextClient(),
        config=LlmAnalysisJobConfig(
            prompt_version="benshi_window_v1",
            max_representative_messages=4,
            max_text_gap_hypotheses=4,
        ),
    )
    plan = analyzer.prepare(materials)
    inferred = plan.pack.media_inference_scaffold.inferred

    assert plan.pack.media_coverage.missing_image_count == 1
    assert len(inferred) == 1
    assert inferred[0].state == "inferred"
    assert inferred[0].confidence_label == "context_only"
    assert inferred[0].hypothesis_kind == "benshi_candidate"
    assert inferred[0].confidence_score >= 0.58
    assert "benshi_lexicon" in inferred[0].support_signals
    assert "screenshot_marker" in inferred[0].support_signals
    assert inferred[0].reference_message_uids
    assert "## Missing Media Text-Only Inference" in plan.user_prompt
    assert "kind=benshi_candidate" in plan.user_prompt


def test_media_inference_scaffold_requires_no_vlm_runtime() -> None:
    from qq_data_analysis.llm_window import WholeWindowPackBuilder
    from qq_data_analysis.models import (
        AnalysisMaterials,
        AnalysisStatsSnapshot,
        ResolvedAnalysisTarget,
        ResolvedTimeWindow,
    )

    materials = AnalysisMaterials(
        run_id="test_no_vlm",
        target=ResolvedAnalysisTarget(
            target_type="group",
            raw_id="30003",
            alias_id="chat_c",
            display_id="chat_c",
            display_name="测试群三",
            run_id="test_no_vlm",
        ),
        chosen_time_window=ResolvedTimeWindow(
            mode="auto_adaptive",
            start_timestamp_ms=1767229200000,
            end_timestamp_ms=1767229200000,
            start_timestamp_iso="2026-01-01T09:00:00+08:00",
            end_timestamp_iso="2026-01-01T09:00:00+08:00",
            rationale="auto",
            selected_message_count=0,
        ),
        messages=[],
        stats=AnalysisStatsSnapshot(
            message_count=0,
            sender_count=0,
            asset_count=0,
            image_message_count=0,
            forward_message_count=0,
            reply_message_count=0,
            emoji_message_count=0,
            low_information_count=0,
            image_ratio=0.0,
            forward_ratio=0.0,
            reply_ratio=0.0,
            emoji_ratio=0.0,
            low_information_ratio=0.0,
        ),
    )

    pack = WholeWindowPackBuilder(LlmAnalysisJobConfig()).build(materials)

    assert pack.media_inference_scaffold.inferred == []
    assert pack.media_inference_scaffold.unknown == []
    assert pack.media_inference_scaffold.observed == []
    assert pack.media_inference_scaffold.missing == []


def test_manifest_media_coverage_overrides_asset_local_fallback() -> None:
    from qq_data_analysis.llm_window import WholeWindowPackBuilder
    from qq_data_analysis.models import (
        AnalysisMaterials,
        AnalysisMessageFeatures,
        AnalysisMessageRecord,
        AnalysisStatsSnapshot,
        MediaCoverageSummary,
        ResolvedAnalysisTarget,
        ResolvedTimeWindow,
    )

    materials = AnalysisMaterials(
        run_id="test_manifest_override",
        target=ResolvedAnalysisTarget(
            target_type="group",
            raw_id="30004",
            alias_id="chat_d",
            display_id="chat_d",
            display_name="测试群四",
            run_id="test_manifest_override",
        ),
        chosen_time_window=ResolvedTimeWindow(
            mode="auto_adaptive",
            start_timestamp_ms=1767229200000,
            end_timestamp_ms=1767229200000,
            start_timestamp_iso="2026-01-01T09:00:00+08:00",
            end_timestamp_iso="2026-01-01T09:00:00+08:00",
            rationale="auto",
            selected_message_count=1,
        ),
        messages=[
            AnalysisMessageRecord(
                message_uid="uid_local",
                run_id="test_manifest_override",
                chat_type="group",
                chat_id="30004",
                sender_id="user_a",
                timestamp_ms=1767229200000,
                timestamp_iso="2026-01-01T09:00:00+08:00",
                content="本地 asset 没缺失标记",
                text_content="本地 asset 没缺失标记",
                assets=[{"asset_type": "image", "file_name": "local.jpg"}],
                features=AnalysisMessageFeatures(image_count=1),
            )
        ],
        stats=AnalysisStatsSnapshot(
            message_count=1,
            sender_count=1,
            asset_count=1,
            image_message_count=1,
            forward_message_count=0,
            reply_message_count=0,
            emoji_message_count=0,
            low_information_count=0,
            image_ratio=1.0,
            forward_ratio=0.0,
            reply_ratio=0.0,
            emoji_ratio=0.0,
            low_information_ratio=0.0,
        ),
        manifest_media_coverage=MediaCoverageSummary(
            total_image_references=10,
            missing_image_count=4,
            image_missing_ratio=0.4,
            overall_media_missing_ratio=0.4,
            media_availability_flags={"has_image": True, "has_missing_media": True},
        ),
    )

    pack = WholeWindowPackBuilder(LlmAnalysisJobConfig()).build(materials)

    assert pack.media_coverage.total_image_references == 10
    assert pack.media_coverage.missing_image_count == 4
    assert pack.media_coverage.image_missing_ratio == 0.4
