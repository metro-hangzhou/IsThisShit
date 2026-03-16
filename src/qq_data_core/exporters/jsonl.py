from __future__ import annotations

from pathlib import Path

import orjson

from ..models import NormalizedSnapshot


def write_jsonl(snapshot: NormalizedSnapshot, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        for message in snapshot.messages:
            handle.write(orjson.dumps(message.model_dump(exclude_none=True)))
            handle.write(b"\n")
    return output_path
