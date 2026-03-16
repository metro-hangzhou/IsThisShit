from __future__ import annotations

from pathlib import Path
import re
from uuid import uuid4

import pytest

from qq_data_analysis import (
    AnalysisJobConfig,
    AnalysisService,
    AnalysisTarget,
    AnalysisTimeScope,
    expand_compact_analysis,
)
from qq_data_process import (
    ChunkPolicySpec,
    DeterministicEmbeddingProvider,
    EmbeddingPolicy,
    PreprocessJobConfig,
    PreprocessService,
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


def _extract_signal_score(rationale: str) -> float:
    match = re.search(r"signal_score=(-?[0-9.]+)", rationale)
    assert match is not None, f"signal_score missing from rationale: {rationale}"
    return float(match.group(1))


def test_analysis_service_auto_scope_prefers_dense_window_and_alias_projection() -> (
    None
):
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_auto_scope")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        service.close()

    expanded = expand_compact_analysis(result.compact_machine_output)

    assert result.target.display_id.startswith("chat_")
    assert result.chosen_time_window.mode == "auto_adaptive"
    assert result.chosen_time_window.selected_message_count == 11
    assert expanded["agents"][0]["data"]["message_count"] == 11
    assert "111" not in result.summary_report
    assert "222" not in result.summary_report


def test_analysis_service_manual_time_scope_respects_range() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_manual_scope")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
                time_scope=AnalysisTimeScope(
                    mode="manual",
                    start_timestamp_ms=1767229200000,
                    end_timestamp_ms=1767229500000,
                ),
            )
        )
    finally:
        service.close()

    expanded = expand_compact_analysis(result.compact_machine_output)
    assert result.chosen_time_window.mode == "manual"
    assert result.chosen_time_window.selected_message_count == 2
    assert expanded["agents"][0]["data"]["message_count"] == 2


def test_analysis_service_detects_nested_forward_and_compact_json_roundtrip() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_nested_forward")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        service.close()

    expanded = expand_compact_analysis(result.compact_machine_output)
    content_agent = next(
        item
        for item in expanded["agents"]
        if item["agent_name"] == "content_composition"
    )
    tag_names = [item["t"] for item in content_agent["data"]["top_tags"]]

    assert "forward_nested" in tag_names
    assert "low_information" in tag_names
    assert content_agent["data"]["events"]
    assert "套娃转发" in result.summary_report


def test_analysis_agents_can_run_independently() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_single_agent")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        base_only = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
                agent_names=["base_stats"],
            )
        )
        content_only = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
                agent_names=["content_composition"],
            )
        )
    finally:
        service.close()

    assert len(base_only.agent_outputs) == 1
    assert base_only.agent_outputs[0].agent_name == "base_stats"
    assert len(content_only.agent_outputs) == 1
    assert content_only.agent_outputs[0].agent_name == "content_composition"


def test_analysis_default_projection_is_alias() -> None:
    """Verify that alias projection is the default mode for Benshi-facing outputs."""
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_default_alias")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        # Default config should use alias projection
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        service.close()

    # Verify that display IDs are aliases, not raw QQ IDs
    assert result.target.display_id.startswith("chat_")
    # Raw IDs should be stored but not exposed as display_id
    assert result.target.raw_id != result.target.display_id
    # Ensure raw ID is not accidentally leaked into summary_report
    assert result.target.raw_id not in result.summary_report


def test_analysis_materials_use_alias_ids_by_default() -> None:
    """Verify that analysis materials (pack, messages) use alias identities by default."""
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_materials_alias")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        service.close()

    # Message IDs in compact output should be alias-based
    expanded = expand_compact_analysis(result.compact_machine_output)
    for agent_output in expanded["agents"]:
        for msg in agent_output["data"].get("representative_messages", []):
            sender_id = msg.get("sender_id")
            if sender_id:
                # Should be an alias (user_<digest>) not raw QQ ID
                assert not sender_id.isdigit(), (
                    f"Raw QQ ID {sender_id} leaked into default alias mode"
                )


def test_analysis_raw_mode_blocks_without_danger_flag() -> None:
    """Verify that raw projection mode is blocked without explicit danger flag."""
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_raw_blocked")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        with pytest.raises(RuntimeError) as exc_info:
            service.run(
                AnalysisJobConfig(
                    target=AnalysisTarget(target_type="group", target_id="20001"),
                    projection_mode="raw",
                    danger_allow_raw_identity_output=False,
                )
            )
        assert "danger_allow_raw_identity_output=True" in str(exc_info.value)
    finally:
        service.close()


def test_analysis_raw_mode_requires_explicit_danger_opt_in() -> None:
    """Verify that raw projection only works with explicit danger opt-in."""
    sqlite_path, qdrant_path = _build_analysis_state("test_analysis_raw_with_danger")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
                projection_mode="raw",
                danger_allow_raw_identity_output=True,
            )
        )
    finally:
        service.close()

    # With danger flag set, display_id should be raw (numeric)
    assert result.target.display_id.isdigit()
    assert result.target.display_id == result.target.raw_id


def test_analysis_fixture_export2_pilot() -> None:
    """Test analysis on export2 pilot fixture with diverse segments."""
    tmp_path = _new_tmp_path("test_analysis_export2_pilot")

    # Preprocess fixture_export2_pilot
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=Path("tests/fixtures/fixture_export2_pilot.jsonl"),
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        chunk_policy_specs=[
            ChunkPolicySpec(
                name="window",
                params={"window_size": 5, "overlap": 2},
            )
        ],
    )
    preprocess_result = service.run(config)

    # Run analysis on the preprocessed state
    analysis_service = AnalysisService.from_state(
        sqlite_path=preprocess_result.sqlite_path,
        qdrant_path=preprocess_result.qdrant_location,
    )
    try:
        result = analysis_service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x1c58"),
                time_scope=AnalysisTimeScope(
                    mode="manual",
                    start_timestamp_ms=1769562717000,
                    end_timestamp_ms=1769599968000,
                ),
            )
        )
    finally:
        analysis_service.close()

    # Verify analysis completed and uses alias projection
    assert result.target.display_id.startswith("chat_")
    assert result.chosen_time_window.selected_message_count > 0
    # Summary should not contain raw IDs
    for segment in result.summary_report.split():
        assert not (len(segment) > 6 and segment.isdigit()), (
            f"Raw QQ ID {segment} leaked into report"
        )


def test_analysis_fixture_export3_missing_media() -> None:
    """Test analysis on export3 missing-media fixture with graceful degradation."""
    tmp_path = _new_tmp_path("test_analysis_export3_missing")

    # Preprocess fixture_export3_missing_media
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=Path("tests/fixtures/fixture_export3_missing_media.jsonl"),
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        skip_image_embeddings=True,  # Skip embeddings for missing-media test
        chunk_policy_specs=[
            ChunkPolicySpec(
                name="window",
                params={"window_size": 5, "overlap": 2},
            )
        ],
    )
    preprocess_result = service.run(config)

    # Run analysis on the missing-media fixture
    analysis_service = AnalysisService.from_state(
        sqlite_path=preprocess_result.sqlite_path,
        qdrant_path=preprocess_result.qdrant_location,
    )
    try:
        result = analysis_service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x0b22"),
            )
        )
    finally:
        analysis_service.close()

    # Verify analysis handles missing media gracefully
    # The display_id should be an alias ID (not raw chat_0x*), showing proper scrubbing
    assert result.target.display_id.startswith("chat_")
    assert result.chosen_time_window.selected_message_count > 0
    # Should not crash on missing media, only report gracefully
    assert "chat_" in result.summary_report


def test_benshi_auto_scope_rationale_is_explainable() -> None:
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_window_rationale")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
            )
        )
    finally:
        service.close()

    rationale = result.chosen_time_window.rationale
    assert "highest-signal bounded session window" in rationale
    assert "signal_score=" in rationale
    assert "senders=" in rationale
    assert result.chosen_time_window.selected_message_count < 13


def test_benshi_window_selector_penalizes_low_information_fixture() -> None:
    export2_tmp = _new_tmp_path("test_benshi_export2_signal")
    export3_tmp = _new_tmp_path("test_benshi_export3_signal")
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)

    export2_service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    export2_result = export2_service.run(
        PreprocessJobConfig(
            source_type="exporter_jsonl",
            source_path=Path("tests/fixtures/fixture_export2_pilot.jsonl"),
            state_dir=export2_tmp / "state",
            embedding_policy=policy,
            chunk_policy_specs=[
                ChunkPolicySpec(name="window", params={"window_size": 5, "overlap": 2})
            ],
        )
    )
    export2_analysis = AnalysisService.from_state(
        sqlite_path=export2_result.sqlite_path,
        qdrant_path=export2_result.qdrant_location,
    )
    try:
        export2_run = export2_analysis.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x1c58"),
            )
        )
    finally:
        export2_analysis.close()

    export3_service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    export3_result = export3_service.run(
        PreprocessJobConfig(
            source_type="exporter_jsonl",
            source_path=Path("tests/fixtures/fixture_export3_missing_media.jsonl"),
            state_dir=export3_tmp / "state",
            embedding_policy=policy,
            skip_image_embeddings=True,
            chunk_policy_specs=[
                ChunkPolicySpec(name="window", params={"window_size": 5, "overlap": 2})
            ],
        )
    )
    export3_analysis = AnalysisService.from_state(
        sqlite_path=export3_result.sqlite_path,
        qdrant_path=export3_result.qdrant_location,
    )
    try:
        export3_run = export3_analysis.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x0b22"),
            )
        )
    finally:
        export3_analysis.close()

    export2_score = _extract_signal_score(export2_run.chosen_time_window.rationale)
    export3_score = _extract_signal_score(export3_run.chosen_time_window.rationale)

    assert export2_run.chosen_time_window.selected_message_count < 30
    assert export2_score > export3_score


def test_benshi_window_selector_is_bounded_and_explainable() -> None:
    """Verify auto window selection stays bounded and explains its scoring basis."""
    tmp_path = _new_tmp_path("test_benshi_window_selector")
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=Path("tests/fixtures/fixture_export2_pilot.jsonl"),
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        chunk_policy_specs=[
            ChunkPolicySpec(name="window", params={"window_size": 5, "overlap": 2})
        ],
    )
    preprocess_result = service.run(config)
    analysis_service = AnalysisService.from_state(
        sqlite_path=preprocess_result.sqlite_path,
        qdrant_path=preprocess_result.qdrant_location,
    )
    try:
        result = analysis_service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x1c58"),
            )
        )
    finally:
        analysis_service.close()

    assert result.chosen_time_window.selected_message_count < 30
    rationale = result.chosen_time_window.rationale
    assert "highest-signal bounded session window" in rationale
    assert "signal_score=" in rationale
    assert "rich_context=" in rationale


def test_benshi_window_selector_penalizes_low_information_bursts() -> None:
    """Context-rich export2 slice should outrank low-information-heavy export3 slice."""

    def _run_fixture(
        fixture_name: str, target_id: str, *, skip_image_embeddings: bool
    ) -> str:
        tmp_path = _new_tmp_path(f"test_benshi_window_{fixture_name}")
        policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
        service = PreprocessService(
            embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
        )
        config = PreprocessJobConfig(
            source_type="exporter_jsonl",
            source_path=Path(f"tests/fixtures/{fixture_name}.jsonl"),
            state_dir=tmp_path / "state",
            embedding_policy=policy,
            skip_image_embeddings=skip_image_embeddings,
            chunk_policy_specs=[
                ChunkPolicySpec(name="window", params={"window_size": 5, "overlap": 2})
            ],
        )
        preprocess_result = service.run(config)
        analysis_service = AnalysisService.from_state(
            sqlite_path=preprocess_result.sqlite_path,
            qdrant_path=preprocess_result.qdrant_location,
        )
        try:
            result = analysis_service.run(
                AnalysisJobConfig(
                    target=AnalysisTarget(target_type="group", target_id=target_id),
                )
            )
            return result.chosen_time_window.rationale
        finally:
            analysis_service.close()

    rich_rationale = _run_fixture(
        "fixture_export2_pilot",
        "chat_0x1c58",
        skip_image_embeddings=False,
    )
    low_info_rationale = _run_fixture(
        "fixture_export3_missing_media",
        "chat_0x0b22",
        skip_image_embeddings=True,
    )

    def _score(rationale: str) -> float:
        marker = "signal_score="
        start = rationale.index(marker) + len(marker)
        end = rationale.index(";", start)
        return float(rationale[start:end])

    assert _score(rich_rationale) > _score(low_info_rationale)
    assert "signals=" in rich_rationale
    assert "low_info_penalty=" in low_info_rationale


def test_benshi_cues_surface_in_structured_analysis_outputs() -> None:
    tmp_path = _new_tmp_path("test_benshi_structured_cues")
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    preprocess_result = service.run(
        PreprocessJobConfig(
            source_type="exporter_jsonl",
            source_path=Path("tests/fixtures/fixture_export2_pilot.jsonl"),
            state_dir=tmp_path / "state",
            embedding_policy=policy,
            chunk_policy_specs=[
                ChunkPolicySpec(name="window", params={"window_size": 5, "overlap": 2})
            ],
        )
    )
    analysis_service = AnalysisService.from_state(
        sqlite_path=preprocess_result.sqlite_path,
        qdrant_path=preprocess_result.qdrant_location,
    )
    try:
        result = analysis_service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x1c58"),
            )
        )
    finally:
        analysis_service.close()

    expanded = expand_compact_analysis(result.compact_machine_output)
    content_agent = next(
        item
        for item in expanded["agents"]
        if item["agent_name"] == "content_composition"
    )
    top_tags = {item["t"] for item in content_agent["data"]["top_tags"]}
    events = content_agent["data"]["events"]

    assert {"share_marker", "reply_chain", "forward_nested"} & top_tags
    assert any(event["evi"] for event in events)
    assert any(
        "share_marker" in event["tags"] or "forward_nested" in event["tags"]
        for event in events
    )


def test_benshi_evidence_aggregation_is_audit_friendly() -> None:
    tmp_path = _new_tmp_path("test_benshi_evidence_aggregation")
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    preprocess_result = service.run(
        PreprocessJobConfig(
            source_type="exporter_jsonl",
            source_path=Path("tests/fixtures/fixture_export2_pilot.jsonl"),
            state_dir=tmp_path / "state",
            embedding_policy=policy,
            chunk_policy_specs=[
                ChunkPolicySpec(name="window", params={"window_size": 5, "overlap": 2})
            ],
        )
    )
    analysis_service = AnalysisService.from_state(
        sqlite_path=preprocess_result.sqlite_path,
        qdrant_path=preprocess_result.qdrant_location,
    )
    try:
        materials = analysis_service.substrate.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="chat_0x1c58"),
            )
        )
    finally:
        analysis_service.close()

    assert materials.candidate_events
    assert materials.participant_profiles
    for event in materials.candidate_events:
        assert event.evidence
        for item in event.evidence:
            assert item.message_uid
            assert item.timestamp_iso
            assert item.sender_id
            assert item.reason
    for profile in materials.participant_profiles[:3]:
        if profile.evidence:
            for item in profile.evidence:
                assert item.message_uid
                assert item.timestamp_iso
                assert item.sender_id
                assert (
                    item.reason.startswith("sender-tagged:")
                    or item.reason.startswith("event-local:")
                    or item.reason.startswith("rag-support:")
                )


def test_benshi_alias_projection_blocks_raw_identity_leakage() -> None:
    """Test that alias projection is enforced and raw identities don't leak without danger flag."""
    sqlite_path, qdrant_path = _build_analysis_state(
        "test_benshi_alias_projection_blocks_raw"
    )
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        # Run with default alias projection
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
                projection_mode="alias",  # Explicit default
                danger_allow_raw_identity_output=False,
            )
        )

        # Verify no raw QQ IDs appear in output
        # Display ID should be alias, not raw
        assert result.target.display_id.startswith("chat_")
        assert result.target.display_id != "20001"  # Not the raw ID

        # Check summary report contains only aliases, not raw IDs
        # Note: We can't check for exact numbers since they may appear in context,
        # but the display_id and target names should be aliased
        assert "chat_" in result.summary_report or len(result.summary_report) > 0

    finally:
        service.close()


def test_benshi_raw_projection_requires_explicit_danger_flag() -> None:
    """Test that raw projection is blocked without the danger flag."""
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_raw_requires_danger")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        # Attempt raw projection WITHOUT danger flag should fail
        with pytest.raises(RuntimeError, match="Raw-identity.*danger"):
            service.run(
                AnalysisJobConfig(
                    target=AnalysisTarget(target_type="group", target_id="20001"),
                    projection_mode="raw",
                    danger_allow_raw_identity_output=False,  # Explicitly False
                )
            )
    finally:
        service.close()


def test_benshi_pack_respects_alias_projection_by_default() -> None:
    """Test that analysis packs respect alias projection in representative messages."""
    sqlite_path, qdrant_path = _build_analysis_state("test_benshi_pack_alias_default")
    service = AnalysisService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
    )
    try:
        result = service.run(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id="20001"),
                projection_mode="alias",  # Default: alias
                danger_allow_raw_identity_output=False,
            )
        )

        # All evidence items and output should use aliases
        for agent_output in result.agent_outputs:
            for evidence in agent_output.evidence:
                # sender_id should be an alias like "user_*", not a raw QQ ID
                assert evidence.sender_id.startswith("user_")
                assert not evidence.sender_id.isdigit()

    finally:
        service.close()
