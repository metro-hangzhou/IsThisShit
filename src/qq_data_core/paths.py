from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import EXPORT_TIMEZONE


def build_default_output_path(
    output_dir: Path,
    *,
    chat_type: str,
    chat_id: str,
    fmt: str,
) -> Path:
    timestamp = datetime.now(EXPORT_TIMEZONE).strftime("%Y%m%d_%H%M%S")
    prefix = "group" if chat_type == "group" else "friend"
    return output_dir / f"{prefix}_{chat_id}_{timestamp}.{fmt}"
