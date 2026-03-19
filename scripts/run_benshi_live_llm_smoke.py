from __future__ import annotations

import argparse
from collections import defaultdict
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from qq_data_analysis import AnalysisJobConfig, AnalysisService, AnalysisTarget
from qq_data_analysis.benshi_llm_agent import BenshiMasterLlmAgent
from qq_data_analysis.benshi_seed_artifacts import write_seed_artifacts
from qq_data_analysis.llm_agent import OpenAICompatibleAnalysisClient
from qq_data_analysis.llm_window import load_text_analysis_client
from qq_data_analysis.models import BenshiImageClusterSummary, ImageCaptionSample
from qq_data_analysis.service import load_analysis_input
from qq_data_process.utils import preview_text, stable_digest
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


def _stream(kind: str, chunk: str) -> None:
    if not chunk:
        return
    prefix = "[reasoning]" if kind == "reasoning" else "[content]"
    print(f"{prefix}{chunk}", end="", flush=True)


def _stream_caption(index: int, total: int, kind: str, chunk: str) -> None:
    if not chunk:
        return
    lane = "reasoning" if kind == "reasoning" else "content"
    print(f"[caption {index}/{total} {lane}]{chunk}", end="", flush=True)


def _stage(message: str) -> None:
    print(f"[stage] {message}", flush=True)


def _stage_done(message: str) -> None:
    print(f"[stage_done] {message}", flush=True)


def _resolve_reference_artifacts(
    *,
    dataset_dir: Path | None,
    example_bank_manifest: Path | None,
    distribution_baseline: Path | None,
) -> dict[str, Any]:
    resolved_dataset_dir = dataset_dir.expanduser().resolve() if dataset_dir else None
    resolved_manifest = (
        example_bank_manifest.expanduser().resolve()
        if example_bank_manifest is not None
        else None
    )
    resolved_baseline = (
        distribution_baseline.expanduser().resolve()
        if distribution_baseline is not None
        else None
    )
    notes: list[str] = []

    if resolved_dataset_dir is not None:
        if resolved_manifest is None:
            resolved_manifest = resolved_dataset_dir / "benshi_example_bank_manifest.json"
        if resolved_baseline is None:
            resolved_baseline = resolved_dataset_dir / "benshi_distribution_baseline.json"
        if not resolved_manifest.exists() or not resolved_baseline.exists():
            _stage("seed artifacts missing, rebuilding from dataset dir")
            write_seed_artifacts(resolved_dataset_dir)
            _stage_done("seed artifacts rebuilt")
            notes.append("seed_artifacts_rebuilt")

    if resolved_manifest is not None and not resolved_manifest.exists():
        notes.append("example_bank_manifest_missing")
        resolved_manifest = None
    if resolved_baseline is not None and not resolved_baseline.exists():
        notes.append("distribution_baseline_missing")
        resolved_baseline = None

    return {
        "dataset_dir": str(resolved_dataset_dir) if resolved_dataset_dir else None,
        "example_bank_manifest_path": (
            str(resolved_manifest) if resolved_manifest is not None else None
        ),
        "distribution_baseline_path": (
            str(resolved_baseline) if resolved_baseline is not None else None
        ),
        "notes": notes,
    }


def _build_review_text(*, payload: dict, output_json_path: Path) -> str:
    compact = payload["compact_payload"]
    evidence = compact.get("evidence_layer", {}) or {}
    shi_component = compact.get("shi_component_analysis_layer", {}) or {}
    shi_description = compact.get("shi_description_layer", {}) or {}
    cultural = compact.get("cultural_interpretation_layer", {}) or {}
    register = compact.get("register_layer", {}) or {}
    reply = compact.get("reply_probe_layer", {}) or {}
    meta = compact.get("llm_meta", {}) or {}
    image_clusters = compact.get("image_cluster_summaries", []) or []
    image_captions = compact.get("image_caption_samples", []) or []
    prompt_refs = compact.get("prompt_reference_context", {}) or {}
    example_bank_context = prompt_refs.get("example_bank_context") or {}
    distribution_context = prompt_refs.get("distribution_baseline_context") or {}
    artifact_inputs = payload.get("artifact_inputs", {}) or {}

    lines = [
        "BenshiMasterAgent LLM Medium 审阅稿",
        "",
        "1. 运行信息",
        f"  1.1 Agent: {payload.get('agent_name')}@{payload.get('agent_version')}",
        f"  1.2 OutputJson: {output_json_path.as_posix()}",
        f"  1.3 Provider: {meta.get('provider')}",
        f"  1.4 Model: {meta.get('model')}",
        f"  1.5 PromptVersion: {meta.get('prompt_version')}",
        f"  1.6 FinishReason: {meta.get('finish_reason')}",
        "",
        "2. Token / 用量",
        f"  2.1 PromptTokens: {(meta.get('usage') or {}).get('prompt_tokens')}",
        f"  2.2 CompletionTokens: {(meta.get('usage') or {}).get('completion_tokens')}",
        f"  2.3 TotalTokens: {(meta.get('usage') or {}).get('total_tokens')}",
        f"  2.4 ReasoningTokens: {(meta.get('usage') or {}).get('reasoning_tokens')}",
        f"  2.5 CachedTokens: {(meta.get('usage') or {}).get('cached_tokens')}",
        "",
        "2.6 增强输入",
        f"  2.6.1 DatasetDir: {artifact_inputs.get('dataset_dir') or '<none>'}",
        f"  2.6.2 ExampleBankManifest: {artifact_inputs.get('example_bank_manifest_path') or '<none>'}",
        f"  2.6.3 DistributionBaseline: {artifact_inputs.get('distribution_baseline_path') or '<none>'}",
        f"  2.6.4 ExampleBankEnabled: {bool(example_bank_context)}",
        f"  2.6.5 DistributionBaselineEnabled: {bool(distribution_context)}",
        "  2.6.6 ExampleBankSelectedCounts: "
        + (
            ", ".join(
                f"{key}={value}"
                for key, value in sorted(
                    (example_bank_context.get("selected_counts") or {}).items()
                )
            )
            if example_bank_context
            else "<none>"
        ),
        "  2.6.7 DistributionDominantComponents: "
        + (
            " / ".join(
                (distribution_context.get("current_window_distribution") or {}).get(
                    "dominant_components"
                )
                or []
            )
            if distribution_context
            else "<none>"
        ),
        "",
        "2.7 图像证据",
        f"  2.7.1 ImageClusterCount: {len(image_clusters)}",
        f"  2.7.2 ImageCaptionCount: {len(image_captions)}",
        "",
        "3. 证据层",
        f"  3.1 ShiPresence: {(evidence.get('shi_presence') or {}).get('label')}",
        "  3.2 ShiTypeCandidates:",
    ]
    if artifact_inputs.get("notes"):
        lines.append("  2.6.8 ArtifactNotes:")
        for item in artifact_inputs.get("notes") or []:
            lines.append(f"    - {item}")
    if example_bank_context.get("example_groups"):
        lines.append("  2.6.9 ExampleBankExamples:")
        for group in example_bank_context.get("example_groups") or []:
            lines.append(f"    - {group.get('group_name')}")
            for item in group.get("examples") or []:
                lines.append(
                    f"      - {item.get('example_id')}: {item.get('expected_direction')}"
                )
    for idx, item in enumerate(evidence.get("shi_type_candidates", []), start=1):
        lines.append(f"    {idx}. {item.get('label')} ({item.get('confidence') or item.get('score')})")
        reasons = item.get("reasons") or [item.get("why")] if item.get("why") else []
        for reason in reasons or []:
            lines.append(f"      - {reason}")
    direct_observations = evidence.get("direct_observations") or []
    if direct_observations:
        lines.append("  3.3 DirectObservations:")
        for item in direct_observations:
            lines.append(f"    - {item}")
    context_inferences = evidence.get("context_inferences") or []
    if context_inferences:
        lines.append("  3.4 ContextInferences:")
        for item in context_inferences:
            if isinstance(item, dict):
                lines.append(
                    f"    - {item.get('claim')} [{item.get('confidence')}]"
                )
                basis = item.get("basis") or []
                for basis_item in basis:
                    lines.append(f"      - basis: {basis_item}")
            else:
                lines.append(f"    - {item}")
    unknowns = evidence.get("unknowns") or []
    if unknowns:
        lines.append("  3.5 Unknowns:")
        for item in unknowns:
            lines.append(f"    - {item}")
    if image_captions:
        lines.append("  3.6 ImageCaptionEvidence:")
        for index, item in enumerate(image_captions, start=1):
            label = item.get("cluster_id") or item.get("file_name") or item.get("message_uid")
            lines.append(f"    {index}. {label}")
            if item.get("cluster_kind"):
                lines.append(f"      - cluster_kind: {item.get('cluster_kind')}")
            lines.append(f"      - ctx: {item.get('context_excerpt') or '<none>'}")
            lines.append(f"      - caption: {item.get('caption')}")
    if image_clusters:
        lines.append("  3.7 ImageClusterSummaries:")
        for index, item in enumerate(image_clusters, start=1):
            lines.append(
                f"    {index}. {item.get('cluster_id')} / {item.get('cluster_kind')}"
            )
            lines.append(
                "      - "
                f"members={item.get('member_count')} "
                f"refs={item.get('reference_count')} "
                f"messages={item.get('distinct_message_count')}"
            )
            lines.append(
                f"      - representative={item.get('representative_file_name') or '<none>'}"
            )
            if item.get("representative_context_excerpt"):
                lines.append(
                    f"      - ctx: {item.get('representative_context_excerpt')}"
                )
            examples = item.get("file_name_examples") or []
            if examples:
                lines.append(f"      - examples: {', '.join(examples)}")
            for note in item.get("notes") or []:
                lines.append(f"      - note: {note}")
    transport = evidence.get("transport_pattern") or {}
    if transport:
        lines.extend(
            [
                "",
                "4. 搬运结构",
                f"  4.1 RelayShape: {transport.get('relay_shape')}",
            ]
        )
        for item in transport.get("recurrence_notes") or []:
            lines.append(f"    - {item}")
    if shi_component:
        lines.extend(["", "5. 史成分分析"])
        definition = shi_component.get("definition")
        if definition:
            lines.append(f"  5.1 Definition: {definition}")
        dominant = shi_component.get("dominant_components") or []
        if dominant:
            lines.append("  5.2 DominantComponents:")
            for item in dominant:
                lines.append(f"    - {item}")
        candidates = shi_component.get("component_candidates") or []
        if candidates:
            lines.append("  5.3 ComponentCandidates:")
            for index, item in enumerate(candidates, start=1):
                lines.append(
                    f"    {index}. {item.get('label')} / {item.get('family')} / {item.get('score')}"
                )
                for reason in item.get("reasons") or []:
                    lines.append(f"      - {reason}")
        rationale_items = shi_component.get("component_rationale") or []
        if rationale_items:
            lines.append("  5.4 ComponentRationale:")
            for item in rationale_items:
                lines.append(f"    - {item}")
    if shi_description:
        lines.extend(["", "6. 史描述层"])
        if shi_description.get("what_is_shi_definition"):
            lines.append(
                f"  6.1 WhatIsShiDefinition: {shi_description.get('what_is_shi_definition')}"
            )
        if shi_description.get("one_line_definition"):
            lines.append(
                f"  6.2 OneLineDefinition: {shi_description.get('one_line_definition')}"
            )
        tags = shi_description.get("descriptive_tags") or []
        if tags:
            lines.append(f"  6.3 DescriptiveTags: {', '.join(tags)}")
        if shi_description.get("how_to_describe_this_shi"):
            lines.append(
                f"  6.4 HowToDescribe: {shi_description.get('how_to_describe_this_shi')}"
            )
        breakdown = shi_description.get("component_breakdown") or []
        if breakdown:
            lines.append("  6.5 ComponentBreakdown:")
            for index, item in enumerate(breakdown, start=1):
                lines.append(
                    f"    {index}. {item.get('label')} / {item.get('family')} / {item.get('score')}"
                )
                if item.get("why"):
                    lines.append(f"      - {item.get('why')}")
        if shi_description.get("good_description_patterns"):
            lines.append("  6.6 GoodDescriptionPatterns:")
            for item in shi_description.get("good_description_patterns") or []:
                lines.append(f"    - {item}")
        if shi_description.get("bad_description_patterns"):
            lines.append("  6.7 BadDescriptionPatterns:")
            for item in shi_description.get("bad_description_patterns") or []:
                lines.append(f"    - {item}")
        if shi_description.get("unknown_boundaries"):
            lines.append("  6.8 UnknownBoundaries:")
            for item in shi_description.get("unknown_boundaries") or []:
                lines.append(f"    - {item}")
    lines.extend(["", "7. 文化解释"])
    section5_index = 1
    for key, title in (
        ("why_this_is_shi", "WhyThisIsShi"),
        ("absurdity_mechanism", "AbsurdityMechanism"),
        ("packaging_notes", "PackagingNotes"),
        ("resonance_notes", "ResonanceNotes"),
    ):
        values = cultural.get(key) or []
        if not values:
            continue
        lines.append(f"  7.{section5_index} {title}:")
        section5_index += 1
        for item in values:
            lines.append(f"    - {item}")
    if cultural.get("classicness_potential") is not None:
        lines.append(f"  7.{section5_index} ClassicnessPotential: {cultural.get('classicness_potential')}")
    lines.extend(
        [
            "",
            "8. 口吻层",
            f"  8.1 VoiceProfile: {register.get('voice_profile')}",
            "  8.2 RenderedCommentary:",
            f"    {register.get('rendered_commentary')}",
        ]
    )
    constraints = register.get("style_constraints_followed") or register.get("register_constraints") or []
    if constraints:
        lines.append("  8.3 Constraints:")
        for item in constraints:
            lines.append(f"    - {item}")
    lines.extend(
        [
            "",
            "9. 接茬探针",
            f"  9.1 Enabled: {reply.get('enabled')}",
            f"  9.2 FollowupConfidence: {reply.get('followup_confidence')}",
        ]
    )
    for item in reply.get("candidate_followups") or []:
        lines.append(f"    - {item}")
    for item in reply.get("followup_rationale") or []:
        lines.append(f"    - rationale: {item}")
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "10. Warnings"])
        for item in warnings:
            lines.append(f"  10.x {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-path", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--preprocess-view", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--config-path", default="state/config/llm.local.json")
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt-version", default="benshi_master_v1")
    parser.add_argument("--dataset-dir", default=None)
    parser.add_argument(
        "--example-bank-manifest-path",
        "--example-bank-manifest",
        dest="example_bank_manifest_path",
        default=None,
    )
    parser.add_argument(
        "--distribution-baseline-path",
        "--distribution-baseline",
        dest="distribution_baseline_path",
        default=None,
    )
    parser.add_argument("--max-output-tokens", type=int, default=2800)
    parser.add_argument("--max-selected-messages", type=int, default=32)
    parser.add_argument("--max-examples-per-group", type=int, default=1)
    parser.add_argument("--max-negative-templates", type=int, default=2)
    parser.add_argument("--include-image-clusters", action="store_true")
    parser.add_argument("--max-image-clusters", type=int, default=6)
    parser.add_argument("--include-image-captions", action="store_true")
    parser.add_argument("--max-caption-images", type=int, default=4)
    parser.add_argument("--caption-max-output-tokens", type=int, default=180)
    args = parser.parse_args()

    export_path = Path(args.export_path).expanduser()
    preprocess_view = Path(args.preprocess_view).expanduser()
    dataset_dir = Path(args.dataset_dir).expanduser() if args.dataset_dir else None
    example_bank_manifest = (
        Path(args.example_bank_manifest_path).expanduser()
        if args.example_bank_manifest_path
        else None
    )
    distribution_baseline = (
        Path(args.distribution_baseline_path).expanduser()
        if args.distribution_baseline_path
        else None
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_inputs = _resolve_reference_artifacts(
        dataset_dir=dataset_dir,
        example_bank_manifest=example_bank_manifest,
        distribution_baseline=distribution_baseline,
    )
    if artifact_inputs.get("example_bank_manifest_path"):
        example_bank_manifest = Path(artifact_inputs["example_bank_manifest_path"])
    else:
        example_bank_manifest = None
    if artifact_inputs.get("distribution_baseline_path"):
        distribution_baseline = Path(artifact_inputs["distribution_baseline_path"])
    else:
        distribution_baseline = None

    _stage("building analysis state")
    sqlite_path, qdrant_path = _build_analysis_state(
        export_path=export_path,
        tmp_name="benshi_live_llm_smoke",
    )
    _stage_done(f"analysis state ready sqlite={sqlite_path}")
    agent = BenshiMasterLlmAgent(
        config_path=Path(args.config_path),
        model=args.model,
        prompt_version=args.prompt_version,
        max_output_tokens=args.max_output_tokens,
        max_selected_messages=args.max_selected_messages,
        stream_callback=_stream,
        example_bank_manifest_path=example_bank_manifest,
        distribution_baseline_path=distribution_baseline,
        max_examples_per_group=args.max_examples_per_group,
        max_negative_templates=args.max_negative_templates,
    )
    service = AnalysisService.from_state(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        _stage("loading preprocess view")
        analysis_input = load_analysis_input(preprocess_view_path=preprocess_view)
        _stage_done("preprocess view loaded")
        config = AnalysisJobConfig(
            target=AnalysisTarget(target_type="group", target_id=args.target_id),
            agent_names=["benshi_master_llm"],
        )
        _stage("building analysis materials")
        materials = service.build_materials(config, analysis_input=analysis_input)
        _stage_done(
            f"materials ready messages={len(materials.messages)} window={materials.chosen_time_window.start_timestamp_iso}->{materials.chosen_time_window.end_timestamp_iso}"
        )
        _stage("preparing benshi pack")
        prepared = agent.prepare(materials)
        _stage_done("benshi pack prepared")
        if example_bank_manifest is not None:
            _stage_done(f"example bank ready {example_bank_manifest}")
        if distribution_baseline is not None:
            _stage_done(f"distribution baseline ready {distribution_baseline}")
        if args.include_image_clusters or args.include_image_captions:
            prepared = _augment_benshi_pack_with_image_captions(
                pack=prepared,
                sqlite_path=sqlite_path,
                materials=materials.messages,
                config_path=Path(args.config_path),
                model=args.model,
                include_clusters=args.include_image_clusters,
                max_clusters=args.max_image_clusters,
                max_images=args.max_caption_images,
                include_captions=args.include_image_captions,
                caption_max_output_tokens=args.caption_max_output_tokens,
            )
            _stage_done(
                f"image augmentation complete clusters={len(prepared.image_cluster_summaries)} captions={len(prepared.image_caption_samples)}"
            )
        _stage("running benshi llm analysis")
        output = agent.analyze(materials, prepared)
        _stage_done("benshi llm analysis completed")
    finally:
        service.close()
    print()

    payload = {
        "agent_name": output.agent_name,
        "agent_version": output.agent_version,
        "human_report": output.human_report,
        "compact_payload": output.compact_payload,
        "warnings": output.warnings,
        "artifact_inputs": artifact_inputs,
    }
    suffix_parts: list[str] = []
    if "reply_probe" in args.prompt_version:
        suffix_parts.append("reply_probe")
    if args.include_image_clusters:
        suffix_parts.append("clusters")
    if example_bank_manifest is not None:
        suffix_parts.append("examples")
    if distribution_baseline is not None:
        suffix_parts.append("dist")
    suffix_parts.append("medium")
    suffix = "_".join(suffix_parts)
    output_json_path = output_dir / f"benshi_llm_{suffix}_output.json"
    review_path = output_dir / f"benshi_llm_{suffix}_review.txt"
    raw_report_path = output_dir / f"benshi_llm_{suffix}_human_report.md"
    cluster_review_path = output_dir / f"benshi_llm_{suffix}_cluster_review.txt"
    shi_review_path = output_dir / f"benshi_llm_{suffix}_shi_review.txt"
    _dump_json(output_json_path, payload)
    raw_report_path.write_text(output.human_report, encoding="utf-8")
    review_path.write_text(
        _build_review_text(payload=payload, output_json_path=output_json_path),
        encoding="utf-8",
    )
    cluster_review_path.write_text(
        _build_cluster_review_text(payload=payload, output_json_path=output_json_path),
        encoding="utf-8",
    )
    shi_review_path.write_text(
        _build_shi_review_text(payload=payload, output_json_path=output_json_path),
        encoding="utf-8",
    )
    _stage_done("artifacts written")
    print(f"benshi_llm_output={output_json_path}")
    print(f"benshi_llm_review={review_path}")
    print(f"benshi_llm_human_report={raw_report_path}")
    print(f"benshi_llm_cluster_review={cluster_review_path}")
    print(f"benshi_llm_shi_review={shi_review_path}")
    return 0


def _augment_benshi_pack_with_image_captions(
    *,
    pack,
    sqlite_path: Path,
    materials: list,
    config_path: Path,
    model: str | None,
    include_clusters: bool,
    max_clusters: int,
    max_images: int,
    include_captions: bool,
    caption_max_output_tokens: int,
):
    source_path = _load_import_source_path(sqlite_path, pack.run_id)
    if source_path is None:
        print("[benshi_image_clusters] source export path not found; skipping", flush=True)
        return pack

    _stage("collecting image refs for clustering")
    image_refs = _collect_benshi_image_asset_refs(
        pack=pack,
        materials=materials,
        source_path=source_path,
    )
    if not image_refs:
        print("[benshi_image_clusters] no usable image files found; skipping", flush=True)
        return pack

    clusters = _build_benshi_image_clusters(
        image_refs,
        max_clusters=max_clusters,
    )
    _stage_done(f"image clusters built count={len(clusters)} refs={len(image_refs)}")
    updated_warnings = list(pack.warnings)
    if clusters:
        updated_warnings.append(
            f"Benshi image clustering summarized {len(clusters)} image clusters."
        )

    if not include_captions:
        return pack.model_copy(
            update={
                "image_cluster_summaries": [
                    cluster["summary"] for cluster in clusters
                ],
                "warnings": updated_warnings,
            }
        )

    client = load_text_analysis_client(
        config_path,
        model=model,
        prompt_family="benshi_master_v1",
    )
    if not isinstance(client, OpenAICompatibleAnalysisClient):
        print("[benshi_image_caption] provider is not openai_compatible; skipping", flush=True)
        return pack.model_copy(
            update={
                "image_cluster_summaries": [
                    cluster["summary"] for cluster in clusters
                ],
                "warnings": updated_warnings,
            }
        )

    caption_candidates = _select_cluster_caption_candidates(
        clusters=clusters,
        max_images=max_images,
    )
    caption_samples: list[ImageCaptionSample] = []
    for index, item in enumerate(caption_candidates, start=1):
        print(
            f"[benshi_image_caption] {index}/{len(caption_candidates)} file={item['file_name'] or item['resolved_path'].name}",
            flush=True,
        )
        bundle = client.caption_image(
            image_path=item["resolved_path"],
            prompt=(
                "你在做QQ群搬史分析图像辅助标注。请用中文保守描述这张图片，输出1-2句。"
                "先说它更像聊天记录截图、通知图、梗图、实物照片、界面截图还是别的；"
                "再说主要可见主体和少量可读字。看不清就直说，不要脑补。"
                f" 当前聊天上下文提示：{item['context_excerpt'] or '<none>'}"
            ),
            max_output_tokens=caption_max_output_tokens,
            stream_callback=lambda kind, chunk, _index=index, _total=len(caption_candidates): _stream_caption(_index, _total, kind, chunk),
        )
        print()
        print(
            f"[benshi_image_caption_done] {preview_text(bundle.raw_text.strip(), 120)}",
            flush=True,
        )
        caption_samples.append(
            ImageCaptionSample(
                cluster_id=item.get("cluster_id"),
                cluster_kind=item.get("cluster_kind"),
                message_uid=item["message_uid"],
                timestamp_iso=item["timestamp_iso"],
                sender_id=item["sender_id"],
                sender_name=item.get("sender_name"),
                file_name=item.get("file_name"),
                resolved_path=str(item["resolved_path"]),
                context_excerpt=item["context_excerpt"],
                caption=bundle.raw_text.strip(),
                model_name=getattr(client.config, "model", "unknown"),
            )
        )

    updated_warnings.append(
        f"Benshi image caption augmentation added {len(caption_samples)} direct multimodal captions."
    )
    return pack.model_copy(
        update={
            "image_cluster_summaries": [
                cluster["summary"] for cluster in clusters
            ],
            "image_caption_samples": caption_samples,
            "warnings": updated_warnings,
        }
    )


def _load_import_source_path(sqlite_path: Path, run_id: str) -> Path | None:
    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute(
            "SELECT source_path FROM import_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row[0]:
        return None
    return Path(row[0])


def _collect_benshi_image_asset_refs(
    *,
    pack,
    materials: list,
    source_path: Path,
) -> list[dict]:
    assets_root = source_path.parent / f"{source_path.stem}_assets"
    message_by_uid = {item.message_uid: item for item in materials}
    selected: list[dict] = []
    scored_messages = sorted(
        pack.selected_messages,
        key=lambda item: (
            -(20 if item.has_forward else 0)
            - min(int(item.forward_depth or 0), 3) * 5
            - min(int(item.asset_count or 0), 4) * 2
            - min(int(item.missing_media_count or 0), 2) * 3
            - len(item.message_tags or []),
            item.timestamp_iso,
            item.message_uid,
        ),
    )
    for pack_message in scored_messages:
        message = message_by_uid.get(pack_message.message_uid)
        if message is None:
            continue
        context_excerpt = preview_text(
            ((pack_message.processed_text or pack_message.content or "").replace("\n", " / ")),
            120,
        )
        for asset_index, asset in enumerate(message.assets):
            if asset.get("asset_type") != "image":
                continue
            resolved_path = _resolve_image_asset_path(asset, assets_root)
            if resolved_path is None:
                continue
            selected.append(
                {
                    "message_uid": message.message_uid,
                    "timestamp_iso": message.timestamp_iso,
                    "sender_id": message.sender_id,
                    "sender_name": message.sender_name,
                    "file_name": asset.get("file_name"),
                    "resolved_path": resolved_path,
                    "resolved_key": str(resolved_path).lower(),
                    "context_excerpt": context_excerpt,
                    "has_forward": message.features.has_forward,
                    "forward_depth": message.features.forward_depth,
                    "asset_index": asset_index,
                }
            )
    return selected


def _build_benshi_image_clusters(
    image_refs: list[dict],
    *,
    max_clusters: int,
) -> list[dict]:
    by_message: dict[str, list[dict]] = defaultdict(list)
    by_path: dict[str, list[dict]] = defaultdict(list)
    for ref in image_refs:
        by_message[str(ref["message_uid"])].append(ref)
        by_path[str(ref["resolved_key"])].append(ref)

    candidates: list[dict] = []

    bundle_groups: dict[tuple[str, ...], list[list[dict]]] = defaultdict(list)
    for refs in by_message.values():
        unique_by_path = {str(item["resolved_key"]): item for item in refs}
        if len(unique_by_path) < 2:
            continue
        bundle_signature = tuple(sorted(unique_by_path))
        bundle_groups[bundle_signature].append(sorted(refs, key=lambda item: item["asset_index"]))

    for signature, occurrences in bundle_groups.items():
        representative_refs = occurrences[0]
        representative = representative_refs[0]
        distinct_message_uids = {
            str(item["message_uid"])
            for refs in occurrences
            for item in refs
        }
        member_count = len(signature)
        reference_count = sum(len(refs) for refs in occurrences)
        cluster_kind = (
            "context_bundle_recurrent"
            if len(distinct_message_uids) >= 2
            else "context_bundle"
        )
        notes = [
            f"同一条消息里的图串，单次包含 {member_count} 张图。"
        ]
        if len(distinct_message_uids) >= 2:
            notes.append(
                f"同一图串在窗口里重复出现 {len(distinct_message_uids)} 次，带明显补档/返场气味。"
            )
        cluster_id = f"img_{stable_digest(cluster_kind, *signature, length=12)}"
        candidates.append(
            {
                "score": 300 + len(distinct_message_uids) * 30 + member_count * 10 + reference_count,
                "summary": BenshiImageClusterSummary(
                    cluster_id=cluster_id,
                    cluster_kind=cluster_kind,
                    member_count=member_count,
                    reference_count=reference_count,
                    distinct_message_count=len(distinct_message_uids),
                    representative_message_uid=representative["message_uid"],
                    representative_timestamp_iso=representative["timestamp_iso"],
                    representative_file_name=representative.get("file_name"),
                    representative_context_excerpt=representative["context_excerpt"],
                    file_name_examples=[
                        str(item.get("file_name") or item["resolved_path"].name)
                        for item in representative_refs[:4]
                    ],
                    notes=notes,
                    evidence_message_uids=sorted(distinct_message_uids)[:8],
                ),
                "representative_ref": representative,
                "covered_paths": set(signature),
            }
        )

    covered_paths = {
        path
        for item in candidates
        for path in item["covered_paths"]
    }
    for path_key, refs in by_path.items():
        distinct_message_uids = {
            str(item["message_uid"])
            for item in refs
        }
        if len(distinct_message_uids) < 2 or path_key in covered_paths:
            continue
        representative = sorted(
            refs,
            key=lambda item: (item["timestamp_iso"], item["message_uid"], item["asset_index"]),
        )[0]
        cluster_id = f"img_{stable_digest('visual_recurrence', path_key, length=12)}"
        candidates.append(
            {
                "score": 180 + len(distinct_message_uids) * 25 + len(refs) * 8,
                "summary": BenshiImageClusterSummary(
                    cluster_id=cluster_id,
                    cluster_kind="visual_recurrence",
                    member_count=1,
                    reference_count=len(refs),
                    distinct_message_count=len(distinct_message_uids),
                    representative_message_uid=representative["message_uid"],
                    representative_timestamp_iso=representative["timestamp_iso"],
                    representative_file_name=representative.get("file_name"),
                    representative_context_excerpt=representative["context_excerpt"],
                    file_name_examples=[str(representative.get("file_name") or representative["resolved_path"].name)],
                    notes=[
                        f"同一张图在窗口里重复被引用 {len(refs)} 次。",
                        f"覆盖 {len(distinct_message_uids)} 条消息。",
                    ],
                    evidence_message_uids=sorted(distinct_message_uids)[:8],
                ),
                "representative_ref": representative,
                "covered_paths": {path_key},
            }
        )

    selected_clusters = sorted(
        candidates,
        key=lambda item: (
            -item["score"],
            item["summary"].representative_timestamp_iso or "",
            item["summary"].cluster_id,
        ),
    )[:max_clusters]
    return selected_clusters


def _select_cluster_caption_candidates(
    *,
    clusters: list[dict],
    max_images: int,
) -> list[dict]:
    selected: list[dict] = []
    seen_paths: set[str] = set()
    for cluster in clusters:
        representative = cluster.get("representative_ref")
        if not representative:
            continue
        norm = str(representative["resolved_path"]).lower()
        if norm in seen_paths:
            continue
        seen_paths.add(norm)
        selected.append(
            {
                **representative,
                "cluster_id": cluster["summary"].cluster_id,
                "cluster_kind": cluster["summary"].cluster_kind,
            }
        )
        if len(selected) >= max_images:
            break
    return selected


def _resolve_image_asset_path(asset: dict, assets_root: Path) -> Path | None:
    exported_rel_path = asset.get("exported_rel_path")
    if exported_rel_path:
        candidate = assets_root / exported_rel_path
        if candidate.exists():
            return candidate
    path_value = asset.get("path")
    if path_value:
        candidate = Path(path_value)
        if candidate.exists():
            return candidate
    return None


def _build_cluster_review_text(*, payload: dict, output_json_path: Path) -> str:
    compact = payload.get("compact_payload", {}) or {}
    clusters = compact.get("image_cluster_summaries", []) or []
    captions = {
        item.get("cluster_id"): item
        for item in (compact.get("image_caption_samples", []) or [])
        if item.get("cluster_id")
    }
    lines = [
        "Benshi 图像簇审阅稿",
        "",
        f"1. OutputJson: {output_json_path.as_posix()}",
        f"2. DatasetDir: {(payload.get('artifact_inputs') or {}).get('dataset_dir') or '<none>'}",
        f"3. ClusterCount: {len(clusters)}",
        "",
        "4. Clusters",
    ]
    for index, item in enumerate(clusters, start=1):
        cluster_id = item.get("cluster_id") or f"cluster_{index:02d}"
        lines.append(f"  {index}. {cluster_id}")
        lines.append(f"    - kind: {item.get('cluster_kind')}")
        lines.append(
            "    - "
            f"members={item.get('member_count')} "
            f"refs={item.get('reference_count')} "
            f"messages={item.get('distinct_message_count')}"
        )
        lines.append(
            f"    - representative: {item.get('representative_file_name') or '<none>'}"
        )
        if item.get("representative_context_excerpt"):
            lines.append(
                f"    - ctx: {item.get('representative_context_excerpt')}"
            )
        examples = item.get("file_name_examples") or []
        if examples:
            lines.append(f"    - examples: {', '.join(examples)}")
        for note in item.get("notes") or []:
            lines.append(f"    - note: {note}")
        caption_item = captions.get(cluster_id)
        if caption_item:
            lines.append("    - caption:")
            lines.append(f"      {caption_item.get('caption')}")
    return "\n".join(lines) + "\n"


def _build_shi_review_text(*, payload: dict, output_json_path: Path) -> str:
    compact = payload.get("compact_payload", {}) or {}
    shi_component = compact.get("shi_component_analysis_layer", {}) or {}
    shi_description = compact.get("shi_description_layer", {}) or {}
    evidence = compact.get("evidence_layer", {}) or {}
    prompt_refs = compact.get("prompt_reference_context", {}) or {}
    example_bank_context = prompt_refs.get("example_bank_context") or {}
    distribution_context = prompt_refs.get("distribution_baseline_context") or {}
    artifact_inputs = payload.get("artifact_inputs", {}) or {}
    lines = [
        "Benshi 史成分专项审阅稿",
        "",
        f"1. OutputJson: {output_json_path.as_posix()}",
        "",
        "2. 增强输入",
    ]
    lines.append(f"  2.1 DatasetDir: {artifact_inputs.get('dataset_dir') or '<none>'}")
    lines.append(
        f"  2.2 ExampleBankManifest: {artifact_inputs.get('example_bank_manifest_path') or '<none>'}"
    )
    lines.append(
        f"  2.3 DistributionBaseline: {artifact_inputs.get('distribution_baseline_path') or '<none>'}"
    )
    if example_bank_context:
        lines.append("  2.4 ExampleBankSelectedCounts:")
        for key, value in sorted((example_bank_context.get("selected_counts") or {}).items()):
            lines.append(f"    - {key}: {value}")
    if distribution_context:
        lines.append(
            "  2.5 BaselineDominantComponents: "
            + (
                " / ".join(
                    (distribution_context.get("current_window_distribution") or {}).get(
                        "dominant_components"
                    )
                    or []
                )
                or "<none>"
            )
        )
    lines.extend(["", "3. 什么是史"])
    if shi_component.get("definition"):
        lines.append(f"  3.1 系统定义: {shi_component.get('definition')}")
    if shi_description.get("what_is_shi_definition"):
        lines.append(
            f"  3.2 描述层定义: {shi_description.get('what_is_shi_definition')}"
        )
    shi_presence = evidence.get("shi_presence") or {}
    if shi_presence:
        lines.append(
            f"  3.3 当前判断: {shi_presence.get('label')} / {shi_presence.get('confidence') or shi_presence.get('score')}"
        )
    lines.extend(["", "4. 史成分有哪些"])
    dominant = shi_component.get("dominant_components") or []
    if dominant:
        lines.append("  4.1 主成分:")
        for item in dominant:
            lines.append(f"    - {item}")
    component_candidates = shi_component.get("component_candidates") or []
    if component_candidates:
        lines.append("  4.2 成分候选明细:")
        for index, item in enumerate(component_candidates, start=1):
            lines.append(
                f"    {index}. {item.get('label')} / {item.get('family')} / {item.get('score')}"
            )
            for reason in item.get("reasons") or []:
                lines.append(f"      - {reason}")
    if shi_component.get("transport_components"):
        lines.append("  4.3 搬运结构成分:")
        for item in shi_component.get("transport_components") or []:
            lines.append(f"    - {item}")
    if shi_component.get("content_components"):
        lines.append("  4.4 内容/包装成分:")
        for item in shi_component.get("content_components") or []:
            lines.append(f"    - {item}")
    if shi_component.get("component_rationale"):
        lines.append("  4.5 成分解释:")
        for item in shi_component.get("component_rationale") or []:
            lines.append(f"    - {item}")
    lines.extend(["", "5. 应该怎么描述这些史"])
    if shi_description.get("one_line_definition"):
        lines.append(
            f"  5.1 一句话定义: {shi_description.get('one_line_definition')}"
        )
    if shi_description.get("descriptive_tags"):
        lines.append(
            "  5.2 描述标签: "
            + " / ".join(shi_description.get("descriptive_tags") or [])
        )
    if shi_description.get("how_to_describe_this_shi"):
        lines.append(
            f"  5.3 建议描述方式: {shi_description.get('how_to_describe_this_shi')}"
        )
    if shi_description.get("component_breakdown"):
        lines.append("  5.4 分项描述:")
        for index, item in enumerate(shi_description.get("component_breakdown") or [], start=1):
            lines.append(
                f"    {index}. {item.get('label')} / {item.get('family')}"
            )
            if item.get("why"):
                lines.append(f"      - {item.get('why')}")
    if shi_description.get("good_description_patterns"):
        lines.append("  5.5 对路写法:")
        for item in shi_description.get("good_description_patterns") or []:
            lines.append(f"    - {item}")
    if shi_description.get("bad_description_patterns"):
        lines.append("  5.6 不对路写法:")
        for item in shi_description.get("bad_description_patterns") or []:
            lines.append(f"    - {item}")
    if shi_description.get("unknown_boundaries"):
        lines.append("  5.7 未知边界:")
        for item in shi_description.get("unknown_boundaries") or []:
            lines.append(f"    - {item}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
