from __future__ import annotations

from pathlib import Path

from .models import ImportSource


def detect_source_type(source_path: Path) -> ImportSource:
    suffix = source_path.suffix.lower()
    if suffix == ".jsonl":
        return "exporter_jsonl"
    if suffix == ".json":
        return "qce_json"
    if suffix == ".txt":
        return "qq_txt"
    raise ValueError(f"Unsupported preprocessing source suffix: {source_path.suffix}")
