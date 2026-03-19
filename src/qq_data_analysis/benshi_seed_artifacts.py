from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .models import BenshiDistributionBaselineSummary


@dataclass(slots=True)
class SeedArtifactBundle:
    example_bank_manifest: dict[str, Any]
    example_bank_groups: dict[str, list[dict[str, Any]]]
    example_bank_review_text: str
    distribution_baseline: dict[str, Any]
    distribution_review_text: str


def _coerce_local_artifact_path(base_dir: Path, path_like: str | None, fallback_name: str) -> Path:
    candidate = Path(path_like or fallback_name)
    if candidate.is_absolute():
        return candidate
    local_candidate = base_dir / candidate.name
    if local_candidate.exists():
        return local_candidate
    return base_dir / fallback_name


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _clean_excerpt(text: str | None, *, limit: int = 220) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _canonical_excerpt_map(canonical_rows: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in canonical_rows:
        canonical_id = str(row.get("canonical_id") or "")
        if not canonical_id:
            continue
        mapping[canonical_id] = _clean_excerpt(
            row.get("text_content") or row.get("content"),
            limit=280,
        )
    return mapping


def _build_window_ref(summary: dict[str, Any]) -> dict[str, Any]:
    selection = summary.get("selection_strategy") or {}
    return {
        "dataset_id": f"shi_group_{summary.get('group_id')}",
        "group_id": str(summary.get("group_id") or ""),
        "group_name": summary.get("group_name"),
        "include_windows": list(selection.get("include_windows") or []),
    }


def _make_example(
    *,
    example_id: str,
    example_kind: str,
    source_file: str,
    source_anchor: str,
    window_ref: dict[str, Any],
    input_excerpt: str,
    expected_direction: str,
    good_output: str | list[str],
    bad_output: str | list[str],
    review_notes: list[str],
    tags: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "example_id": example_id,
        "example_kind": example_kind,
        "source_file": source_file,
        "source_anchor": source_anchor,
        "window_ref": window_ref,
        "input_excerpt": input_excerpt,
        "expected_direction": expected_direction,
        "good_output": good_output,
        "bad_output": bad_output,
        "review_notes": review_notes,
        "tags": tags,
    }
    if extra:
        payload.update(extra)
    return payload


def build_example_bank(dataset_dir: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], str]:
    summary = _read_json(dataset_dir / "summary.json")
    llm_output = _read_json(dataset_dir / "benshi_llm_reply_probe_clusters_medium_output.json")
    ontology_output = _read_json(dataset_dir / "benshi_ontology_smoke_output.json")
    canonical_rows = _iter_jsonl(dataset_dir / "canonical_messages.local_assets.jsonl")
    excerpts = _canonical_excerpt_map(canonical_rows)
    window_ref = _build_window_ref(summary)

    compact_payload = llm_output["compact_payload"]
    evidence = compact_payload["evidence_layer"]
    component_layer = compact_payload["shi_component_analysis_layer"]
    description_layer = compact_payload["shi_description_layer"]
    reply_probe_layer = compact_payload["reply_probe_layer"]
    ontology_summary = (
        ontology_output.get("compact_payload", {})
        .get("pack_summary", {})
        .get("ontology_summary", {})
    )

    good_judgment_examples = [
        _make_example(
            example_id="benshi_example_0001",
            example_kind="good_judgment",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_review.txt",
            source_anchor="3.2-3.4",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0001", ""),
            expected_direction="先根据 forward 密度、单人主导和重复返场判断这是一窗结构性搬运史，而不是随便喊抽象。",
            good_output=" / ".join(
                item["label"] for item in evidence.get("shi_type_candidates", [])[:4]
            ),
            bad_output="这窗好抽象好逆天，应该算史。",
            review_notes=[
                "这条例子强调证据先行，而不是空喊抽象。",
                "判断重点在外源/二手/单人倾倒/返场结构。",
            ],
            tags=["good_judgment", "外源史", "二手史", "单人主导倾倒"],
            extra={
                "judgment_focus": "shi_presence|shi_type|transport_pattern",
                "evidence_basis": [
                    "forward_density",
                    "nested_forward",
                    "single_sender_dumping",
                    "image_cluster_recurrence",
                ],
                "must_preserve_uncertainty": True,
            },
        ),
        _make_example(
            example_id="benshi_example_0002",
            example_kind="good_judgment",
            source_file="dev/testdata/local/shi_group_751365230/benshi_ontology_smoke_review.txt",
            source_anchor="2.1-2.5",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0020", ""),
            expected_direction="保持保守边界，明确按本地 ontology 判断，不把当前窗口直接吹成典中典。",
            good_output={
                "shi_presence": "弱到中等存在",
                "shi_type_candidates": [
                    "二手史",
                    "外源史",
                    "工业史",
                ],
                "ontology_origin_definition": ontology_summary.get("origin_definition"),
            },
            bad_output="既然大家都在转，那这窗肯定是典中典神史，群里所有人都爱吃这一路。",
            review_notes=[
                "这条例子适合校准‘不要嗨过头’。",
                "它把原义、类型学和当前窗口分开了。",
            ],
            tags=["good_judgment", "ontology", "保守判断"],
            extra={
                "judgment_focus": "shi_presence|ontology_alignment|quality_band",
                "evidence_basis": ["ontology_origin", "taxonomy", "quality_band"],
                "must_preserve_uncertainty": True,
            },
        ),
        _make_example(
            example_id="benshi_example_0003",
            example_kind="good_judgment",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_cluster_review.txt",
            source_anchor="3.1-3.6",
            window_ref=window_ref,
            input_excerpt="图像簇里至少有 2 组图串重复返场，还有多张单图重复引用。",
            expected_direction="把图像簇和返场结构当成史判断证据，而不是只看文本。",
            good_output="重复图串 + 单图复现 + 截图壳，共同证明这坨东西不是一次性抛图，而是库存返场式搬运。",
            bad_output="图片很多，所以应该主要是图片好看导致大家转。",
            review_notes=[
                "这条例子防止 agent 忽略多模态结构证据。",
                "重点是图串返场，不是审美好不好看。",
            ],
            tags=["good_judgment", "图像簇", "补档返场"],
            extra={
                "judgment_focus": "image_cluster_structure|packaging",
                "evidence_basis": ["context_bundle_recurrent", "visual_recurrence"],
                "must_preserve_uncertainty": True,
            },
        ),
    ]

    good_description_examples = [
        _make_example(
            example_id="benshi_example_0101",
            example_kind="good_description",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_output.json",
            source_anchor="shi_description_layer.one_line_definition",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0015", ""),
            expected_direction="一句话先抓来源和搬运结构，再补史味主轴。",
            good_output=description_layer.get("one_line_definition"),
            bad_output="这窗东西很逆天，很抽象，很有节目效果。",
            review_notes=[
                "对路描述不能只有情绪词。",
                "一句话要先点明外源/二手/单人倾倒/返场拼盘。",
            ],
            tags=["good_description", "one_line_definition"],
            extra={
                "description_focus": "one_line_definition",
                "good_axes": ["来源", "搬运结构", "内容混装"],
            },
        ),
        _make_example(
            example_id="benshi_example_0102",
            example_kind="good_description",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_output.json",
            source_anchor="shi_description_layer.how_to_describe_this_shi",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0029", ""),
            expected_direction="先写来源和结构，再写内容层，最后收 unknown boundary。",
            good_output=description_layer.get("how_to_describe_this_shi"),
            bad_output="这群人天天都在发低俗垃圾，没什么好说的。",
            review_notes=[
                "这是当前最适合 future prompt few-shot 的描述模板。",
                "它把‘怎么说’和‘不能怎么说’分开了。",
            ],
            tags=["good_description", "description_template"],
            extra={
                "description_focus": "how_to_describe",
                "good_axes": ["来源", "搬运结构", "内容层", "未知边界"],
            },
        ),
        _make_example(
            example_id="benshi_example_0103",
            example_kind="good_description",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_output.json",
            source_anchor="shi_description_layer.good_description_patterns",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0008", ""),
            expected_direction="把中转站、库存清仓、包浆、返场这些关键词贴在结构上用，而不是乱扔梗。",
            good_output=list(description_layer.get("good_description_patterns") or []),
            bad_output=list(description_layer.get("bad_description_patterns") or []),
            review_notes=[
                "这条例子直接区分对路写法和不对路写法。",
                "适合后续做 ExampleBank 的 few-shot 主素材。",
            ],
            tags=["good_description", "good_vs_bad_patterns"],
            extra={
                "description_focus": "pattern_pair",
                "good_axes": ["对路写法", "不对路写法"],
            },
        ),
    ]

    good_reply_probe_examples = [
        _make_example(
            example_id="benshi_example_0201",
            example_kind="good_reply_probe",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_output.json",
            source_anchor="reply_probe_layer.candidate_followups[0:3]",
            window_ref=window_ref,
            input_excerpt="窗口结构是单人主导倾倒 + 前后补档返场 + 套娃 forward。",
            expected_direction="接茬要贴结构，不要脱离窗口。",
            good_output=list(reply_probe_layer.get("candidate_followups") or [])[:3],
            bad_output=[
                "太抽象了哈哈哈",
                "逆天，笑死。",
                "这也太有节目效果了。",
            ],
            review_notes=[
                "对路接茬要能点中中转站、返场、套娃等结构。",
                "坏接茬的典型问题是任何窗口都能套用。",
            ],
            tags=["good_reply_probe", "接茬", "结构贴合"],
            extra={
                "reply_style": "cn_high_context_benshi_commentator_v1",
                "reply_targets": ["中转站", "补档返场", "套娃包浆"],
                "why_good": "句子短、贴结构、不脑补媒体内容。",
            },
        )
    ]

    negative_templates = [
        _make_example(
            example_id="benshi_example_0301",
            example_kind="negative_template",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_shi_review.txt",
            source_anchor="4.6",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0003", ""),
            expected_direction="不要只会喊抽象。",
            good_output="这窗更像单人主导的外源二手搬运拼盘，史味主要来自套娃 forward 和返场回放。",
            bad_output="这窗好抽象好逆天。",
            review_notes=[
                "空喊抽象不等于吃懂了史。",
            ],
            tags=["negative_template", "generic_abstract_label"],
            extra={
                "failure_mode": "generic_abstract_label",
                "why_bad": "没有结构证据，也没有指出史味来自哪里。",
                "preferred_fix": "补上来源、搬运结构、内容混装和 unknown boundary。",
            },
        ),
        _make_example(
            example_id="benshi_example_0302",
            example_kind="negative_template",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_shi_review.txt",
            source_anchor="4.6",
            window_ref=window_ref,
            input_excerpt=excerpts.get("shi_0018", ""),
            expected_direction="不要把边角成分硬吹成全窗主轴。",
            good_output="窗口里有低俗猎奇成分，但主轴仍是外源二手拼盘和单人返场式搬运。",
            bad_output="因为有低俗内容，所以整窗主要就是低俗猎奇史。",
            review_notes=[
                "这类误判会把拼盘结构压扁成单一标签。",
            ],
            tags=["negative_template", "single_axis_bias"],
            extra={
                "failure_mode": "single_axis_bias",
                "why_bad": "把边角刺激性原料误判成唯一主轴。",
                "preferred_fix": "先列主成分，再列次成分和边角成分。",
            },
        ),
        _make_example(
            example_id="benshi_example_0303",
            example_kind="negative_template",
            source_file="dev/testdata/local/shi_group_751365230/benshi_ontology_smoke_review.txt",
            source_anchor="6-8",
            window_ref=window_ref,
            input_excerpt="当前窗口没有视频本体，图片 caption 也只覆盖少量样本。",
            expected_direction="不要脑补媒体剧情。",
            good_output="这里最多只能说它有视频壳/截图壳和传播结构，不能写具体剧情。",
            bad_output="视频里演的就是某人怎么怎样，所以这窗一定是……",
            review_notes=[
                "这是后续最容易爆的越界点。",
            ],
            tags=["negative_template", "media_hallucination"],
            extra={
                "failure_mode": "media_hallucination",
                "why_bad": "把缺失媒体当成已知事实。",
                "preferred_fix": "明确 unknown boundary，只写能证实的结构。",
            },
        ),
        _make_example(
            example_id="benshi_example_0304",
            example_kind="negative_template",
            source_file="dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_output.json",
            source_anchor="reply_probe_layer",
            window_ref=window_ref,
            input_excerpt="当前窗口是单人 99/103 条的集中倾倒。",
            expected_direction="不要把当前窗口外推出整群长期偏好。",
            good_output="这一窗更像一人倒库存，不足以代表整群长期口味。",
            bad_output="说明这个群所有人都爱吃这种史。",
            review_notes=[
                "这类过推会让 agent 把窗口判断写成人群画像。",
            ],
            tags=["negative_template", "groupwide_overgeneralization"],
            extra={
                "failure_mode": "groupwide_overgeneralization",
                "why_bad": "单窗结构不能直接代表整群偏好。",
                "preferred_fix": "把结论限定在当前窗口范围内。",
            },
        ),
    ]

    groups = {
        "good_judgment_examples": good_judgment_examples,
        "good_description_examples": good_description_examples,
        "good_reply_probe_examples": good_reply_probe_examples,
        "negative_templates": negative_templates,
    }
    manifest = {
        "artifact": "benshi_example_bank_seed",
        "version": 1,
        "generated_at": datetime.now().isoformat(),
        "dataset_id": window_ref["dataset_id"],
        "group_id": window_ref["group_id"],
        "source_files": [
            "dev/testdata/local/shi_group_751365230/benshi_llm_reply_probe_clusters_medium_output.json",
            "dev/testdata/local/shi_group_751365230/benshi_ontology_smoke_output.json",
            "dev/testdata/local/shi_group_751365230/summary.json",
            "dev/testdata/local/shi_group_751365230/canonical_messages.local_assets.jsonl",
        ],
        "groups": {
            key: {
                "count": len(value),
                "path": f"dev/testdata/local/shi_group_751365230/{key}.jsonl",
            }
            for key, value in groups.items()
        },
    }
    review_lines = [
        "Benshi ExampleBank Seed 审阅稿",
        "",
        "1. Manifest",
        f"  1.1 DatasetId: {manifest['dataset_id']}",
        f"  1.2 GroupId: {manifest['group_id']}",
    ]
    for idx, (group_name, rows) in enumerate(groups.items(), start=1):
        review_lines.append(f"  1.{idx + 2} {group_name}: {len(rows)}")
    review_lines.extend(["", "2. Groups"])
    section_index = 0
    for group_name, rows in groups.items():
        section_index += 1
        review_lines.append(f"  {section_index}. {group_name}")
        for row_index, row in enumerate(rows, start=1):
            review_lines.append(f"    {row_index}. {row['example_id']}")
            review_lines.append(f"      - source: {row['source_file']}#{row['source_anchor']}")
            review_lines.append(f"      - expected: {row['expected_direction']}")
            review_lines.append(f"      - tags: {', '.join(row['tags'])}")
            review_lines.append(f"      - excerpt: {row['input_excerpt']}")
            review_lines.append(f"      - good: {row['good_output']}")
            review_lines.append(f"      - bad: {row['bad_output']}")
    return manifest, groups, "\n".join(review_lines) + "\n"


def build_distribution_baseline(dataset_dir: Path) -> tuple[dict[str, Any], str]:
    summary = _read_json(dataset_dir / "summary.json")
    seed_rows = _iter_jsonl(dataset_dir / "seed_labels.jsonl")
    canonical_rows = _iter_jsonl(dataset_dir / "canonical_messages.local_assets.jsonl")
    all_occurrence_rows = _iter_jsonl(dataset_dir / "all_occurrences.jsonl")
    llm_output = _read_json(dataset_dir / "benshi_llm_reply_probe_clusters_medium_output.json")

    delivery_mode_counts = Counter(str(row.get("delivery_mode") or "unknown") for row in seed_rows)
    modality_counter: Counter[str] = Counter()
    for row in seed_rows:
        for modality in row.get("modalities") or []:
            modality_counter[str(modality)] += 1

    repeated_dump_counts = Counter(int(row.get("repeated_dump_count") or 1) for row in seed_rows)
    occurrence_window_counts = Counter(str(row.get("window_id") or "unknown") for row in all_occurrence_rows)
    sender_counts = Counter(str(row.get("sender_name") or "(unknown)") for row in canonical_rows)

    compact_payload = llm_output["compact_payload"]
    evidence = compact_payload["evidence_layer"]
    component_layer = compact_payload["shi_component_analysis_layer"]
    image_clusters = compact_payload.get("image_cluster_summaries") or []
    image_captions = compact_payload.get("image_caption_samples") or []

    component_candidates = component_layer.get("component_candidates") or []
    component_family_scores: defaultdict[str, float] = defaultdict(float)
    for item in component_candidates:
        component_family_scores[str(item.get("family") or "unknown")] += float(item.get("score") or 0.0)

    transport_pattern = evidence.get("transport_pattern") or {}
    baseline = {
        "artifact": "benshi_distribution_baseline",
        "version": 1,
        "generated_at": datetime.now().isoformat(),
        "dataset_id": f"shi_group_{summary.get('group_id')}",
        "canonical_sample_overview": {
            "canonical_messages": summary["counts"]["canonical_messages"],
            "all_occurrences": summary["counts"]["all_occurrences"],
            "debug_examples": summary["counts"]["debug_examples"],
            "repeated_dump_windows": [item[0] for item in summary["selection_strategy"]["include_windows"]],
            "sender_distribution": dict(sender_counts),
        },
        "delivery_structure_distribution": {
            "delivery_mode_counts": dict(delivery_mode_counts),
            "modality_counts": dict(modality_counter),
            "repeated_dump_count_distribution": dict(repeated_dump_counts),
            "occurrence_window_counts": dict(occurrence_window_counts),
        },
        "asset_distribution": {
            "unique_assets": summary["asset_transfer"]["unique_assets"],
            "copied_assets": summary["asset_transfer"]["copied_assets"],
            "missing_assets": summary["asset_transfer"]["missing_assets"],
            "by_type": dict(summary["asset_transfer"]["by_type"]),
            "by_type_status": dict(summary["asset_transfer"]["by_type_status"]),
        },
        "current_window_distribution": {
            "shi_presence": evidence.get("shi_presence"),
            "shi_type_candidates": evidence.get("shi_type_candidates"),
            "component_candidates": component_candidates,
            "dominant_components": component_layer.get("dominant_components") or [],
            "component_family_score_totals": {
                key: round(value, 3) for key, value in sorted(component_family_scores.items())
            },
            "transport_pattern": transport_pattern,
        },
        "image_cluster_distribution": {
            "cluster_count": len(image_clusters),
            "caption_count": len(image_captions),
            "cluster_kind_counts": dict(
                Counter(str(item.get("cluster_kind") or "unknown") for item in image_clusters)
            ),
            "recurrent_cluster_count": sum(
                1
                for item in image_clusters
                if int(item.get("distinct_message_count") or 0) >= 2
            ),
        },
    }
    review_lines = [
        "Benshi Distribution Baseline 审阅稿",
        "",
        "1. 集中式样本概览",
        f"  1.1 CanonicalMessages: {baseline['canonical_sample_overview']['canonical_messages']}",
        f"  1.2 AllOccurrences: {baseline['canonical_sample_overview']['all_occurrences']}",
        f"  1.3 DebugExamples: {baseline['canonical_sample_overview']['debug_examples']}",
        "  1.4 RepeatedDumpWindows: "
        + " / ".join(baseline["canonical_sample_overview"]["repeated_dump_windows"]),
        "",
        "2. 投递结构分布",
        "  2.1 DeliveryModes:",
    ]
    for key, value in baseline["delivery_structure_distribution"]["delivery_mode_counts"].items():
        review_lines.append(f"    - {key}: {value}")
    review_lines.append("  2.2 Modalities:")
    for key, value in baseline["delivery_structure_distribution"]["modality_counts"].items():
        review_lines.append(f"    - {key}: {value}")
    review_lines.extend(
        [
            "",
            "3. 资产分布",
            f"  3.1 UniqueAssets: {baseline['asset_distribution']['unique_assets']}",
            f"  3.2 CopiedAssets: {baseline['asset_distribution']['copied_assets']}",
            f"  3.3 MissingAssets: {baseline['asset_distribution']['missing_assets']}",
            "  3.4 ByType:",
        ]
    )
    for key, value in baseline["asset_distribution"]["by_type"].items():
        review_lines.append(f"    - {key}: {value}")
    review_lines.extend(
        [
            "",
            "4. 当前窗口史成分分布",
            f"  4.1 ShiPresence: {baseline['current_window_distribution']['shi_presence']}",
            "  4.2 DominantComponents: "
            + " / ".join(baseline["current_window_distribution"]["dominant_components"]),
            "  4.3 ComponentFamilyScoreTotals:",
        ]
    )
    for key, value in baseline["current_window_distribution"]["component_family_score_totals"].items():
        review_lines.append(f"    - {key}: {value}")
    review_lines.append("  4.4 ShiTypeCandidates:")
    for item in baseline["current_window_distribution"]["shi_type_candidates"]:
        review_lines.append(
            f"    - {item.get('label')}: {item.get('confidence')} | {', '.join(item.get('reasons') or [])}"
        )
    review_lines.extend(
        [
            "",
            "5. 图像簇分布",
            f"  5.1 ClusterCount: {baseline['image_cluster_distribution']['cluster_count']}",
            f"  5.2 CaptionCount: {baseline['image_cluster_distribution']['caption_count']}",
            f"  5.3 RecurrentClusterCount: {baseline['image_cluster_distribution']['recurrent_cluster_count']}",
            "  5.4 ClusterKinds:",
        ]
    )
    for key, value in baseline["image_cluster_distribution"]["cluster_kind_counts"].items():
        review_lines.append(f"    - {key}: {value}")
    return baseline, "\n".join(review_lines) + "\n"


def build_seed_artifacts(dataset_dir: Path) -> SeedArtifactBundle:
    manifest, groups, example_bank_review_text = build_example_bank(dataset_dir)
    distribution_baseline, distribution_review_text = build_distribution_baseline(dataset_dir)
    return SeedArtifactBundle(
        example_bank_manifest=manifest,
        example_bank_groups=groups,
        example_bank_review_text=example_bank_review_text,
        distribution_baseline=distribution_baseline,
        distribution_review_text=distribution_review_text,
    )


def load_example_bank_bundle(
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest = _read_json(manifest_path)
    base_dir = manifest_path.parent
    groups: dict[str, list[dict[str, Any]]] = {}
    for group_name, meta in (manifest.get("groups") or {}).items():
        group_path = _coerce_local_artifact_path(
            base_dir,
            str((meta or {}).get("path") or ""),
            f"{group_name}.jsonl",
        )
        groups[group_name] = _iter_jsonl(group_path)
    return manifest, groups


def _prompt_safe_text(value: Any, *, limit: int = 180) -> Any:
    if isinstance(value, str):
        return _clean_excerpt(value, limit=limit)
    if isinstance(value, list):
        return [_prompt_safe_text(item, limit=limit) for item in value[:4]]
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key in list(value.keys())[:8]:
            compact[str(key)] = _prompt_safe_text(value[key], limit=limit)
        return compact
    return value


def _distribution_baseline_to_summary(
    baseline: dict[str, Any],
    *,
    baseline_path: Path | None = None,
) -> BenshiDistributionBaselineSummary:
    overview = baseline.get("canonical_sample_overview") or {}
    delivery = baseline.get("delivery_structure_distribution") or {}
    current = baseline.get("current_window_distribution") or {}
    transport = current.get("transport_pattern") or {}
    image_clusters = baseline.get("image_cluster_distribution") or {}

    dominant_components = [
        str(item).strip()
        for item in list(current.get("dominant_components") or [])[:8]
        if str(item).strip()
    ]
    component_family_score_totals: dict[str, float] = {}
    for key, value in dict(current.get("component_family_score_totals") or {}).items():
        try:
            component_family_score_totals[str(key)] = round(float(value or 0.0), 3)
        except (TypeError, ValueError):
            component_family_score_totals[str(key)] = 0.0

    notes = [
        "distribution baseline 只作为集中式样本背景先验，不能覆盖当前窗口的直接证据。",
    ]
    if dominant_components:
        notes.append("主成分背景=" + " / ".join(dominant_components[:4]))
    relay_shape = str(transport.get("relay_shape") or "").strip() or None
    if relay_shape:
        notes.append(f"relay_shape={relay_shape}")

    return BenshiDistributionBaselineSummary(
        dataset_id=str(baseline.get("dataset_id") or "").strip() or None,
        artifact=str(baseline.get("artifact") or "").strip() or None,
        baseline_path=str(baseline_path) if baseline_path is not None else None,
        canonical_messages=int(overview.get("canonical_messages") or 0),
        all_occurrences=int(overview.get("all_occurrences") or 0),
        repeated_dump_windows=[
            str(item).strip()
            for item in list(overview.get("repeated_dump_windows") or [])[:8]
            if str(item).strip()
        ],
        dominant_components=dominant_components,
        component_family_score_totals=component_family_score_totals,
        delivery_mode_counts={
            str(key): int(value or 0)
            for key, value in dict(delivery.get("delivery_mode_counts") or {}).items()
        },
        modality_counts={
            str(key): int(value or 0)
            for key, value in dict(delivery.get("modality_counts") or {}).items()
        },
        relay_shape=relay_shape,
        recurrence_notes=[
            str(item).strip()
            for item in list(transport.get("recurrence_notes") or [])[:8]
            if str(item).strip()
        ],
        cluster_count=int(image_clusters.get("cluster_count") or 0),
        caption_count=int(image_clusters.get("caption_count") or 0),
        recurrent_cluster_count=int(image_clusters.get("recurrent_cluster_count") or 0),
        cluster_kind_counts={
            str(key): int(value or 0)
            for key, value in dict(image_clusters.get("cluster_kind_counts") or {}).items()
        },
        notes=notes,
    )


def load_distribution_baseline_summary(
    path: Path | str,
) -> BenshiDistributionBaselineSummary:
    baseline_path = Path(path)
    baseline = _read_json(baseline_path)
    return _distribution_baseline_to_summary(
        baseline,
        baseline_path=baseline_path,
    )


def build_distribution_baseline_prompt_context_from_summary(
    summary: BenshiDistributionBaselineSummary,
) -> dict[str, Any]:
    return {
        "artifact": "benshi_distribution_prompt_context",
        "dataset_id": summary.dataset_id,
        "canonical_sample_overview": {
            "canonical_messages": summary.canonical_messages,
            "all_occurrences": summary.all_occurrences,
            "repeated_dump_windows": list(summary.repeated_dump_windows),
        },
        "delivery_structure_distribution": {
            "delivery_mode_counts": dict(summary.delivery_mode_counts),
            "modality_counts": dict(summary.modality_counts),
        },
        "current_window_distribution": {
            "dominant_components": list(summary.dominant_components),
            "component_family_score_totals": dict(summary.component_family_score_totals),
            "transport_pattern": {
                "relay_shape": summary.relay_shape,
                "recurrence_notes": list(summary.recurrence_notes),
            },
        },
        "image_cluster_distribution": {
            "cluster_count": summary.cluster_count,
            "caption_count": summary.caption_count,
            "recurrent_cluster_count": summary.recurrent_cluster_count,
            "cluster_kind_counts": dict(summary.cluster_kind_counts),
        },
    }


def build_example_bank_prompt_context(
    manifest_path: Path,
    *,
    max_examples_per_group: int = 1,
    max_negative_templates: int = 2,
    include_groups: list[str] | None = None,
    max_examples_by_group: dict[str, int] | None = None,
) -> dict[str, Any]:
    manifest, groups = load_example_bank_bundle(manifest_path)
    ordered_groups = include_groups or [
        "good_judgment_examples",
        "good_description_examples",
        "good_reply_probe_examples",
    ]
    selected_groups: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}
    for group_name in ordered_groups:
        group_limit = max_examples_per_group
        if max_examples_by_group is not None:
            group_limit = max_examples_by_group.get(group_name, group_limit)
        rows = list(groups.get(group_name) or [])[:group_limit]
        if not rows:
            continue
        selected_counts[group_name] = len(rows)
        selected_groups.append(
            {
                "group_name": group_name,
                "examples": [
                    {
                        "example_id": row.get("example_id"),
                        "expected_direction": _prompt_safe_text(
                            row.get("expected_direction"),
                            limit=180,
                        ),
                        "input_excerpt": _prompt_safe_text(
                            row.get("input_excerpt"),
                            limit=220,
                        ),
                        "good_output": _prompt_safe_text(
                            row.get("good_output"),
                            limit=180,
                        ),
                        "tags": list(row.get("tags") or [])[:6],
                    }
                    for row in rows
                ],
            }
        )

    negative_rows = list(groups.get("negative_templates") or [])[:max_negative_templates]
    selected_counts["negative_templates"] = len(negative_rows)
    negative_templates = [
        {
            "example_id": row.get("example_id"),
            "failure_mode": row.get("failure_mode"),
            "expected_direction": _prompt_safe_text(
                row.get("expected_direction"),
                limit=160,
            ),
            "bad_output": _prompt_safe_text(row.get("bad_output"), limit=120),
            "preferred_fix": _prompt_safe_text(row.get("preferred_fix"), limit=160),
        }
        for row in negative_rows
    ]

    return {
        "artifact": "benshi_example_bank_prompt_context",
        "dataset_id": manifest.get("dataset_id"),
        "group_id": manifest.get("group_id"),
        "selected_counts": selected_counts,
        "example_groups": selected_groups,
        "negative_templates": negative_templates,
    }


def load_distribution_baseline_prompt_context(path: Path) -> dict[str, Any]:
    summary = load_distribution_baseline_summary(path)
    return build_distribution_baseline_prompt_context_from_summary(summary)


def write_seed_artifacts(dataset_dir: Path) -> SeedArtifactBundle:
    bundle = build_seed_artifacts(dataset_dir)
    _write_json(dataset_dir / "benshi_example_bank_manifest.json", bundle.example_bank_manifest)
    for group_name, rows in bundle.example_bank_groups.items():
        _write_jsonl(dataset_dir / f"{group_name}.jsonl", rows)
    (dataset_dir / "benshi_example_bank_review.txt").write_text(
        bundle.example_bank_review_text,
        encoding="utf-8",
    )
    _write_json(dataset_dir / "benshi_distribution_baseline.json", bundle.distribution_baseline)
    (dataset_dir / "benshi_distribution_review.txt").write_text(
        bundle.distribution_review_text,
        encoding="utf-8",
    )
    return bundle
