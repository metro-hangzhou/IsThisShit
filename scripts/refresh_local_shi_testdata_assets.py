from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


DATASET_DIR = Path(r"dev/testdata/local/shi_group_751365230")
CANONICAL_PATH = DATASET_DIR / "canonical_messages.jsonl"
LOCAL_CANONICAL_PATH = DATASET_DIR / "canonical_messages.local_assets.jsonl"
ASSET_INVENTORY_PATH = DATASET_DIR / "asset_inventory.jsonl"
SUMMARY_PATH = DATASET_DIR / "summary.json"
LOCAL_ASSET_ROOT = DATASET_DIR / "assets"


def _load_summary() -> dict[str, Any]:
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def _source_asset_root(summary: dict[str, Any]) -> Path:
    source_export = Path(str(summary["source_export"]))
    return source_export.with_name(f"{source_export.stem}_assets")


def _iter_segments(message: dict[str, Any], *, path: str = "root") -> list[tuple[dict[str, Any], str]]:
    items: list[tuple[dict[str, Any], str]] = []
    for index, segment in enumerate(message.get("segments") or []):
        if not isinstance(segment, dict):
            continue
        seg_path = f"{path}.segments[{index}]"
        items.append((segment, seg_path))
        if str(segment.get("type") or "").strip() == "forward":
            extra = segment.get("extra") or {}
            for child_index, child in enumerate(extra.get("forward_messages") or []):
                if not isinstance(child, dict):
                    continue
                items.extend(
                    _iter_segments(
                        child,
                        path=f"{seg_path}.forward_messages[{child_index}]",
                    )
                )
    return items


def _asset_file_name(segment: dict[str, Any]) -> str | None:
    file_name = str(segment.get("file_name") or "").strip()
    if file_name:
        return file_name
    extra = segment.get("extra") or {}
    for key in ("file_name", "path", "url"):
        value = str(extra.get(key) or "").strip()
        if not value:
            continue
        return Path(value).name
    return None


def _normalize_stem(name: str) -> str:
    stem = Path(name).stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and len(parts[1]) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in parts[1]):
        return parts[0].lower()
    return stem.lower()


def _source_index(source_asset_root: Path) -> dict[str, list[Path]]:
    by_stem: dict[str, list[Path]] = {}
    for file in source_asset_root.rglob("*"):
        if not file.is_file():
            continue
        stem = _normalize_stem(file.name)
        by_stem.setdefault(stem, []).append(file)
    for files in by_stem.values():
        files.sort(key=lambda p: (len(p.name), p.name.lower()))
    return by_stem


def _pick_source_match(file_name: str, candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    target = file_name.lower()
    target_ext = Path(file_name).suffix.lower()
    target_stem = Path(file_name).stem.lower()
    exact = [path for path in candidates if path.name.lower() == target]
    if exact:
        return exact[0]
    same_stem_same_ext = [
        path
        for path in candidates
        if _normalize_stem(path.name) == target_stem and path.suffix.lower() == target_ext
    ]
    if same_stem_same_ext:
        return sorted(same_stem_same_ext, key=lambda p: (len(p.name), p.name.lower()))[0]
    return candidates[0]


def _copy_asset(source_path: Path, *, source_asset_root: Path) -> str:
    rel = source_path.relative_to(source_asset_root)
    target = LOCAL_ASSET_ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source_path, target)
    return Path("assets") / rel.as_posix()


def _asset_type(segment: dict[str, Any]) -> str:
    seg_type = str(segment.get("type") or "").strip()
    if seg_type == "sticker":
        return "sticker"
    if seg_type == "emoji":
        return "emoji"
    if seg_type == "image":
        return "image"
    if seg_type == "video":
        return "video"
    if seg_type == "file":
        return "file"
    if seg_type == "speech":
        return "speech"
    return seg_type or "unknown"


def _source_locator(segment: dict[str, Any]) -> str | None:
    extra = segment.get("extra") or {}
    for key in ("path", "url", "file"):
        value = str(extra.get(key) or "").strip()
        if value:
            return value
    path = str(segment.get("path") or "").strip()
    return path or None


def _ensure_clean_local_assets() -> None:
    if LOCAL_ASSET_ROOT.exists():
        shutil.rmtree(LOCAL_ASSET_ROOT)
    LOCAL_ASSET_ROOT.mkdir(parents=True, exist_ok=True)


def refresh() -> dict[str, Any]:
    summary = _load_summary()
    source_asset_root = _source_asset_root(summary)
    source_idx = _source_index(source_asset_root)
    _ensure_clean_local_assets()

    inventory_rows: list[dict[str, Any]] = []
    updated_messages: list[dict[str, Any]] = []
    local_copy_cache: dict[str, str] = {}
    asset_seq = 1
    copied = 0
    missing = 0
    type_counter: Counter[str] = Counter()
    type_status_counter: dict[str, Counter[str]] = {}

    with CANONICAL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            message = json.loads(line)
            canonical_id = str(message.get("canonical_id") or "")
            for segment, seg_path in _iter_segments(message):
                seg_type = _asset_type(segment)
                if seg_type not in {"image", "video", "file", "speech", "emoji", "sticker"}:
                    continue
                file_name = _asset_file_name(segment)
                if not file_name:
                    continue
                stem = _normalize_stem(file_name)
                source_match = _pick_source_match(file_name, source_idx.get(stem, []))
                extra = dict(segment.get("extra") or {})
                row: dict[str, Any] = {
                    "asset_id": f"asset_{asset_seq:04d}",
                    "type": seg_type,
                    "file_name": file_name,
                    "source_locator": _source_locator(segment),
                    "referenced_by": [
                        {
                            "canonical_id": canonical_id,
                            "message_id": str(message.get("message_id") or ""),
                            "location": seg_path,
                        }
                    ],
                }
                asset_seq += 1
                type_counter[seg_type] += 1
                if source_match is None:
                    row["status"] = "missing_in_source_export"
                    row["source_export_asset_rel_path"] = None
                    row["local_test_asset_rel_path"] = None
                    extra["test_asset_status"] = "missing_in_source_export"
                    extra["local_test_asset_rel_path"] = None
                    missing += 1
                    type_status_counter.setdefault(seg_type, Counter())["missing_in_source_export"] += 1
                else:
                    rel_source = source_match.relative_to(source_asset_root).as_posix()
                    cached = local_copy_cache.get(rel_source)
                    if cached is None:
                        cached_path = _copy_asset(source_match, source_asset_root=source_asset_root)
                        cached = cached_path.as_posix() if isinstance(cached_path, Path) else str(cached_path)
                        local_copy_cache[rel_source] = cached
                        copied += 1
                    row["status"] = "copied"
                    row["source_export_asset_rel_path"] = rel_source
                    row["local_test_asset_rel_path"] = cached
                    extra["test_asset_status"] = "copied"
                    extra["local_test_asset_rel_path"] = cached
                    extra["test_asset_matched_file_name"] = source_match.name
                    type_status_counter.setdefault(seg_type, Counter())["copied"] += 1
                segment["extra"] = extra
                inventory_rows.append(row)
            updated_messages.append(message)

    with ASSET_INVENTORY_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in inventory_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    with LOCAL_CANONICAL_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for message in updated_messages:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")

    summary["asset_transfer"] = {
        "unique_assets": len(inventory_rows),
        "copied_assets": copied,
        "missing_assets": missing,
        "by_type": dict(type_counter),
        "by_type_status": {key: dict(counter) for key, counter in sorted(type_status_counter.items())},
        "matching_policy": "stem_based_no_md5; tolerate extension changes and dedupe suffixes",
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "asset_records": len(inventory_rows),
        "copied": copied,
        "missing": missing,
        "asset_root": str(LOCAL_ASSET_ROOT.resolve()),
    }


if __name__ == "__main__":
    print(json.dumps(refresh(), ensure_ascii=False, indent=2))
