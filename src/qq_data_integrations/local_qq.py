from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import Callable


def discover_qq_media_roots() -> list[Path]:
    env_value = os.getenv("QQ_MEDIA_ROOTS")
    if env_value:
        roots = [Path(part).expanduser().resolve() for part in env_value.split(";") if part.strip()]
        return [root for root in roots if root.exists()]

    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    for drive in ["C", "D", "E", "F", "G"]:
        drive_root = Path(f"{drive}:/")
        add(drive_root / "QQ")
        add(drive_root / "Tencent Files")
        add(drive_root / "QQ Files")
        _add_nested_targets(drive_root, add)

    user_profile = os.getenv("USERPROFILE")
    local_app_data = os.getenv("LOCALAPPDATA")
    app_data = os.getenv("APPDATA")

    if user_profile:
        home = Path(user_profile)
        add(home / "Documents" / "Tencent Files")
        add(home / "Documents" / "QQ Files")
    if local_app_data:
        local = Path(local_app_data)
        add(local / "Tencent" / "QQ")
        add(local / "Tencent" / "QQNT")
    if app_data:
        roaming = Path(app_data)
        add(roaming / "Tencent" / "QQ")
        add(roaming / "Tencent" / "QQNT")

    return candidates


def _add_nested_targets(root: Path, add: Callable[[Path], None]) -> None:
    with suppress(OSError):
        for child in root.iterdir():
            if not child.is_dir():
                continue
            add(child / "QQ")
            add(child / "Tencent Files")
            add(child / "QQ Files")
