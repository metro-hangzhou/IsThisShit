from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from qq_data_analysis import AnalysisJobConfig, AnalysisService, AnalysisTarget
from qq_data_analysis.benshi_agent import BenshiMasterAgent
from qq_data_analysis.service import load_analysis_input
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


def _build_analysis_state(*, export_path: Path, tmp_name: str) -> tuple[Path, Path]:
    tmp_path = _new_tmp_path(tmp_name)
    policy = EmbeddingPolicy(provider_name="deterministic", vector_size_hint=8)
    service = PreprocessService(
        embedding_provider=DeterministicEmbeddingProvider(vector_size=8)
    )
    config = PreprocessJobConfig(
        source_type="exporter_jsonl",
        source_path=export_path,
        state_dir=tmp_path / "state",
        embedding_policy=policy,
        skip_image_embeddings=True,
        chunk_policy_specs=[
            ChunkPolicySpec(
                name="window",
                params={"window_size": 5, "overlap": 2},
            )
        ],
    )
    result = service.run(config)
    return result.sqlite_path, result.qdrant_location


def _dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_review_text(*, result_payload: dict, output_json_path: Path) -> str:
    evidence = result_payload["compact_payload"]["evidence_layer"]
    cultural = result_payload["compact_payload"]["cultural_interpretation_layer"]
    register = result_payload["compact_payload"]["register_layer"]
    reply_probe = result_payload["compact_payload"]["reply_probe_layer"]
    pack_summary = result_payload["compact_payload"]["pack_summary"]
    ontology_summary = pack_summary.get("ontology_summary") or {}
    distribution_summary = pack_summary.get("distribution_baseline_summary") or {}

    direct_obs = evidence.get("direct_observations", [])
    context_inferences = evidence.get("context_inferences", [])
    roles = evidence.get("participant_roles", [])
    why_items = cultural.get("why_this_is_shi", [])
    resonance_items = cultural.get("resonance_notes", [])
    gap_summary = evidence.get("missing_media_gaps", {})

    lines = [
        "BenshiMasterAgent 本地审阅稿",
        "",
        "1. 运行信息",
        f"  1.1 Agent: {result_payload['agent_name']}@{result_payload['agent_version']}",
        f"  1.2 OutputJson: {output_json_path.as_posix()}",
        f"  1.3 TargetId: {pack_summary.get('target_id')}",
        f"  1.4 TargetName: {pack_summary.get('target_name') or '(none)'}",
        f"  1.5 Window: {pack_summary.get('start_iso')} -> {pack_summary.get('end_iso')}",
        f"  1.6 MessageCount: {pack_summary.get('message_count')}",
        f"  1.7 SenderCount: {pack_summary.get('sender_count')}",
        f"  1.8 DeliveryProfile: {pack_summary.get('delivery_profile')}",
        f"  1.9 AnnotationCount: {pack_summary.get('annotation_count')}",
        "",
        "2. 核心判断",
        f"  2.1 ShiPresence: {evidence.get('shi_presence', {}).get('label')} (score={evidence.get('shi_presence', {}).get('score')})",
        "  2.2 ShiTypeCandidates:",
    ]
    for idx, item in enumerate(evidence.get("shi_type_candidates", []), start=1):
        lines.append(
            f"    {idx}. {item.get('label')} (score={item.get('score')})"
        )
        lines.append(f"      - why: {item.get('why')}")
    lines.extend(
        [
            f"  2.3 QualityBand: {evidence.get('shi_quality_band', {}).get('label')}",
            f"  2.4 Confidence: {evidence.get('confidence')}",
        ]
    )
    if ontology_summary:
        lines.extend(
            [
                "  2.5 OntologyParticipation:",
                f"    - 原义: {ontology_summary.get('origin_definition')}",
            ]
        )
        taxonomy_labels = ontology_summary.get("taxonomy_labels") or []
        if taxonomy_labels:
            lines.append(f"    - 类型学: {' / '.join(taxonomy_labels)}")
        popular_form_labels = ontology_summary.get("popular_form_labels") or []
        if popular_form_labels:
            lines.append(f"    - popular 形态: {' / '.join(popular_form_labels)}")
        source_documents = ontology_summary.get("source_documents") or []
        if source_documents:
            lines.append(f"    - 来源文档: {' / '.join(source_documents)}")
    if distribution_summary:
        lines.extend(
            [
                "  2.6 DistributionBaseline:",
                f"    - dataset: {distribution_summary.get('dataset_id')}",
                "    - "
                f"canonical={distribution_summary.get('canonical_messages')} "
                f"occurrences={distribution_summary.get('all_occurrences')}",
            ]
        )
        dominant_components = distribution_summary.get("dominant_components") or []
        if dominant_components:
            lines.append(f"    - 主成分背景: {' / '.join(dominant_components)}")
        if distribution_summary.get("relay_shape"):
            lines.append(
                f"    - relay_shape: {distribution_summary.get('relay_shape')}"
            )
    lines.extend(["", "3. 直接观察"])
    for idx, item in enumerate(direct_obs, start=1):
        lines.append(f"  3.{idx} {item}")
    lines.extend(["", "4. 语境推断"])
    for idx, item in enumerate(context_inferences, start=1):
        lines.append(f"  4.{idx} {item}")
    lines.extend(["", "5. 参与者角色"])
    for idx, item in enumerate(roles, start=1):
        lines.append(
            f"  5.{idx} {item.get('sender_id')} / {item.get('sender_name') or '(none)'} / {item.get('message_count')} 条"
        )
        role_names = item.get("candidate_roles") or []
        if role_names:
            lines.append(f"    - roles: {', '.join(role_names)}")
        notes = item.get("notes") or []
        for note in notes:
            lines.append(f"    - note: {note}")
    lines.extend(
        [
            "",
            "6. 缺失媒体",
            f"  6.1 MissingTotal: {gap_summary.get('missing_total', 0)}",
        ]
    )
    missing_by_type = gap_summary.get("missing_by_type") or {}
    if missing_by_type:
        lines.append("  6.2 MissingByType:")
        for key, value in missing_by_type.items():
            lines.append(f"    - {key}: {value}")
    top_missing_files = gap_summary.get("top_missing_files") or []
    if top_missing_files:
        lines.append("  6.3 TopMissingFiles:")
        for file_name in top_missing_files:
            lines.append(f"    - {file_name}")
    lines.extend(["", "7. 为什么它是史"])
    for idx, item in enumerate(why_items, start=1):
        lines.append(f"  7.{idx} {item}")
    lines.extend(
        [
            "",
            "8. 文化解释",
            f"  8.1 AbsurdityMechanism: {cultural.get('absurdity_mechanism')}",
            f"  8.2 ContextCollapse: {cultural.get('context_collapse_mechanism')}",
            f"  8.3 QualityAssessment: {cultural.get('quality_assessment')}",
            f"  8.4 ClassicnessPotential: {cultural.get('classicness_potential')}",
        ]
    )
    if resonance_items:
        lines.append("  8.5 ResonanceNotes:")
        for item in resonance_items:
            lines.append(f"    - {item}")
    lines.extend(
        [
            "",
            "9. 口吻层",
            f"  9.1 VoiceProfile: {register.get('voice_profile')}",
            "  9.2 RenderedCommentary:",
            f"    {register.get('rendered_commentary')}",
        ]
    )
    constraints = register.get("register_constraints") or []
    if constraints:
        lines.append("  9.3 Constraints:")
        for item in constraints:
            lines.append(f"    - {item}")
    lines.extend(
        [
            "",
            "10. 接茬探针",
            f"  10.1 Enabled: {reply_probe.get('enabled')}",
            f"  10.2 Status: {reply_probe.get('status')}",
            f"  10.3 Note: {reply_probe.get('note')}",
        ]
    )
    followups = reply_probe.get("candidate_followups") or []
    if followups:
        lines.append("  10.4 CandidateFollowups:")
        for item in followups:
            lines.append(f"    - {item}")
    rationale = reply_probe.get("followup_rationale") or []
    if rationale:
        lines.append("  10.5 FollowupRationale:")
        for item in rationale:
            lines.append(f"    - {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-path", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--preprocess-view", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--distribution-baseline-path",
        "--distribution-baseline",
        dest="distribution_baseline_path",
        default=None,
    )
    args = parser.parse_args()

    export_path = Path(args.export_path).expanduser()
    preprocess_view = Path(args.preprocess_view).expanduser()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    distribution_baseline_path = (
        Path(args.distribution_baseline_path).expanduser()
        if args.distribution_baseline_path
        else None
    )

    sqlite_path, qdrant_path = _build_analysis_state(
        export_path=export_path,
        tmp_name="benshi_local_smoke",
    )
    service = AnalysisService.from_state(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        analysis_input = load_analysis_input(preprocess_view_path=preprocess_view)
        materials = service.build_materials(
            AnalysisJobConfig(
                target=AnalysisTarget(target_type="group", target_id=args.target_id),
            ),
            analysis_input=analysis_input,
        )
        agent = BenshiMasterAgent(
            distribution_baseline_path=distribution_baseline_path,
        )
        prepared = agent.prepare(materials)
        output = agent.analyze(materials, prepared)
    finally:
        service.close()
    payload = {
        "agent_name": output.agent_name,
        "agent_version": output.agent_version,
        "human_report": output.human_report,
        "compact_payload": output.compact_payload,
        "warnings": output.warnings,
    }
    output_json_path = output_dir / "benshi_agent_output.json"
    review_path = output_dir / "benshi_agent_review.txt"
    _dump_json(output_json_path, payload)
    review_path.write_text(
        _build_review_text(result_payload=payload, output_json_path=output_json_path),
        encoding="utf-8",
    )
    print(f"benshi_output={output_json_path}")
    print(f"benshi_review={review_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
