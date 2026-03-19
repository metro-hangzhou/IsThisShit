from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import orjson


REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "dev" / "testdata" / "local" / "shi_group_751365230"
CANONICAL_PATH = DATASET_DIR / "canonical_messages.local_assets.jsonl"
SEED_LABELS_PATH = DATASET_DIR / "seed_labels.jsonl"
OUTPUT_PATH = DATASET_DIR / "label_review_template.jsonl"


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("rb") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            rows.append(orjson.loads(line))
    return rows


def _normalize_text(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def _preview_text(payload: dict[str, Any], *, limit: int = 220) -> str:
    text = _normalize_text(payload.get("text_content") or payload.get("content"))
    if not text:
        text = _normalize_text(payload.get("content"))
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _segment_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for segment in payload.get("segments") or []:
        segment_type = str(segment.get("type") or "unknown")
        counts[segment_type] += 1
    return dict(sorted(counts.items()))


def _asset_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()

    def walk_segments(segments: list[dict[str, Any]] | None) -> None:
        for segment in segments or []:
            segment_type = str(segment.get("type") or "")
            if segment_type in {"image", "video", "file", "emoji", "sticker", "speech"}:
                counts[segment_type] += 1
            extra = segment.get("extra") or {}
            for forward_message in extra.get("forward_messages") or []:
                walk_segments(forward_message.get("segments") or [])

    walk_segments(payload.get("segments") or [])
    return dict(sorted(counts.items()))


def _suggest_primary_mode(payload: dict[str, Any]) -> str:
    segments = payload.get("segments") or []
    top_types = {str(segment.get("type") or "") for segment in segments}
    if "forward" in top_types:
        return "forward_bundle"
    if "image" in top_types or "video" in top_types or "file" in top_types:
        return "standalone_asset"
    return "text_or_mixed"


def _load_seed_index() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("canonical_id")): row
        for row in _iter_jsonl(SEED_LABELS_PATH)
        if row.get("canonical_id")
    }


def build_template() -> int:
    canonical_rows = _iter_jsonl(CANONICAL_PATH)
    seed_index = _load_seed_index()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("wb") as handle:
        for row in canonical_rows:
            canonical_id = str(row.get("canonical_id") or "")
            seed = seed_index.get(canonical_id, {})
            payload = {
                "canonical_id": canonical_id,
                "source_message_id": row.get("message_id"),
                "source_timestamp_iso": row.get("timestamp_iso"),
                "sender_name": row.get("sender_name"),
                "delivery_mode": seed.get("delivery_mode") or _suggest_primary_mode(row),
                "repeated_dump_count": row.get("occurrence_count", 1),
                "segment_type_counts": _segment_counts(row),
                "asset_counts_recursive": _asset_counts(row),
                "preview_text": _preview_text(row),
                "sample_role": seed.get("sample_role", "shi_candidate"),
                "manual_label": seed.get("manual_label"),
                "manual_subtype": seed.get("manual_subtype"),
                "manual_content_bucket": None,
                "manual_intensity": None,
                "manual_notes": None,
                "evidence_flags": {
                    "has_forward": bool(seed.get("has_forward")),
                    "has_image": bool(seed.get("has_image")),
                    "has_video": bool(seed.get("has_video")),
                    "has_file": bool(seed.get("has_file")),
                    "has_text": bool(seed.get("has_text")),
                },
            }
            handle.write(orjson.dumps(payload, option=orjson.OPT_APPEND_NEWLINE))
    return len(canonical_rows)


if __name__ == "__main__":
    count = build_template()
    print(f"Wrote {count} review rows to {OUTPUT_PATH}")
