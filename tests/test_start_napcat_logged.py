from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _fresh_test_dir(name: str) -> Path:
    path = Path(".tmp") / "tests" / "start_napcat_logged" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def test_start_napcat_logged_reads_local_quick_login_file() -> None:
    tmp_path = _fresh_test_dir("reads_local_quick_login_file")
    repo_root = Path(__file__).resolve().parents[1]
    script_src = repo_root / "start_napcat_logged.bat"
    script_dst = tmp_path / "start_napcat_logged.bat"
    script_dst.write_text(script_src.read_text(encoding="utf-8"), encoding="utf-8")

    local_quick_file = tmp_path / "state" / "config" / "napcat_quick_login_uin.txt"
    local_quick_file.parent.mkdir(parents=True, exist_ok=True)
    local_quick_file.write_text("3956020260\n", encoding="utf-8")

    probe_file = tmp_path / "launcher_probe.txt"
    fake_launcher = tmp_path / "fake_launcher.bat"
    fake_launcher.write_text(
        "\n".join(
            [
                "@echo off",
                f'echo launcher_args=%* > "{probe_file}"',
                f'echo launcher_env=%NAPCAT_QUICK_ACCOUNT% >> "{probe_file}"',
                "exit /b 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["NAPCAT_SKIP_ADMIN_CHECK"] = "1"
    env["NAPCAT_LAUNCHER_OVERRIDE"] = str(fake_launcher)

    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", str(script_dst)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    assert probe_file.exists()
    probe_text = probe_file.read_text(encoding="utf-8")
    assert "launcher_args=-q 3956020260" in probe_text
    assert "launcher_env=3956020260" in probe_text


def test_start_napcat_logged_admin_relaunch_uses_log_dir_wrapper_and_explicit_filepath() -> None:
    script_text = (Path(__file__).resolve().parents[1] / "start_napcat_logged.bat").read_text(
        encoding="utf-8"
    )

    assert "setlocal EnableExtensions EnableDelayedExpansion" in script_text
    assert 'set "NAPCAT_ELEVATED_WRAPPER=%NAPCAT_LOG_DIR%\\napcat_elevated_' in script_text
    assert "Start-Process -FilePath '!NAPCAT_ELEVATED_WRAPPER!' -Verb RunAs" in script_text
