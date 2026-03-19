from __future__ import annotations

import json
from pathlib import Path
import shutil
from uuid import uuid4

from qq_data_analysis.benshi_seed_artifacts import (
    build_distribution_baseline_prompt_context_from_summary,
    build_example_bank_prompt_context,
    build_seed_artifacts,
    load_distribution_baseline_summary,
    load_distribution_baseline_prompt_context,
    write_seed_artifacts,
)


DATASET_DIR = Path("dev/testdata/local/shi_group_751365230")


def _new_workspace_tmp_dir(prefix: str) -> Path:
    tmp_root = Path(".tmp")
    tmp_root.mkdir(parents=True, exist_ok=True)
    path = tmp_root / f"{prefix}_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_build_seed_artifacts_emits_example_groups_and_distribution() -> None:
    bundle = build_seed_artifacts(DATASET_DIR)

    assert bundle.example_bank_manifest["artifact"] == "benshi_example_bank_seed"
    assert bundle.distribution_baseline["artifact"] == "benshi_distribution_baseline"
    assert bundle.example_bank_groups["good_judgment_examples"]
    assert bundle.example_bank_groups["good_description_examples"]
    assert bundle.example_bank_groups["negative_templates"]
    assert "Benshi ExampleBank Seed 审阅稿" in bundle.example_bank_review_text
    assert "Benshi Distribution Baseline 审阅稿" in bundle.distribution_review_text


def test_distribution_baseline_keeps_canonical_occurrence_and_cluster_layers() -> None:
    bundle = build_seed_artifacts(DATASET_DIR)
    baseline = bundle.distribution_baseline

    assert baseline["canonical_sample_overview"]["canonical_messages"] == 49
    assert baseline["canonical_sample_overview"]["all_occurrences"] == 147
    assert "delivery_structure_distribution" in baseline
    assert "current_window_distribution" in baseline
    assert "image_cluster_distribution" in baseline
    assert baseline["image_cluster_distribution"]["cluster_count"] >= 1


def test_prompt_context_loaders_compact_seed_artifacts() -> None:
    write_seed_artifacts(DATASET_DIR)

    example_context = build_example_bank_prompt_context(
        DATASET_DIR / "benshi_example_bank_manifest.json",
        max_examples_per_group=1,
        max_negative_templates=2,
    )
    distribution_context = load_distribution_baseline_prompt_context(
        DATASET_DIR / "benshi_distribution_baseline.json"
    )

    assert example_context["artifact"] == "benshi_example_bank_prompt_context"
    assert example_context["example_groups"]
    assert example_context["selected_counts"]["negative_templates"] == 2
    assert distribution_context["artifact"] == "benshi_distribution_prompt_context"
    assert distribution_context["current_window_distribution"]["dominant_components"]


def test_distribution_baseline_summary_loader_keeps_prompt_context_compact() -> None:
    summary = load_distribution_baseline_summary(
        DATASET_DIR / "benshi_distribution_baseline.json"
    )
    prompt_context = build_distribution_baseline_prompt_context_from_summary(summary)

    assert summary.dataset_id == "shi_group_751365230"
    assert summary.canonical_messages == 49
    assert summary.all_occurrences == 147
    assert summary.relay_shape == "forward_heavy"
    assert prompt_context["current_window_distribution"]["dominant_components"]
    assert "shi_type_candidates" not in prompt_context["current_window_distribution"]


def test_example_bank_prompt_context_is_relocatable_and_group_bounded() -> None:
    tmp_path = _new_workspace_tmp_dir("test_example_bank_prompt_context_relocated")
    artifact_names = [
        "benshi_example_bank_manifest.json",
        "good_judgment_examples.jsonl",
        "good_description_examples.jsonl",
        "good_reply_probe_examples.jsonl",
        "negative_templates.jsonl",
    ]
    for name in artifact_names:
        shutil.copyfile(DATASET_DIR / name, tmp_path / name)

    manifest_path = tmp_path / "benshi_example_bank_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_id"] = "shi_group_relocated_example_bank"
    manifest["groups"]["good_judgment_examples"]["path"] = (
        "some/other/place/good_judgment_examples.jsonl"
    )
    manifest["groups"]["good_description_examples"]["path"] = (
        "another/place/good_description_examples.jsonl"
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    context = build_example_bank_prompt_context(
        manifest_path,
        include_groups=[
            "good_judgment_examples",
            "good_description_examples",
        ],
        max_examples_per_group=2,
        max_examples_by_group={
            "good_judgment_examples": 2,
            "good_description_examples": 1,
        },
        max_negative_templates=1,
    )

    assert context["dataset_id"] == "shi_group_relocated_example_bank"
    assert context["selected_counts"]["good_judgment_examples"] == 2
    assert context["selected_counts"]["good_description_examples"] == 1
    assert "good_reply_probe_examples" not in context["selected_counts"]
    assert len(context["negative_templates"]) == 1
