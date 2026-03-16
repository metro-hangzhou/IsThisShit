from __future__ import annotations

import argparse
import importlib.metadata as importlib_metadata
import site
import shutil
import sys
from datetime import datetime
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

RUNTIME_ROOT_DISTS = [
    "httpx",
    "orjson",
    "pillow",
    "prompt-toolkit",
    "pydantic",
    "pypinyin",
    "qrcode",
    "rich",
    "typer",
    "websockets",
]


def _ignore_copy(path: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        lowered = name.lower()
        if lowered in {"__pycache__", ".pytest_cache", ".mypy_cache"}:
            ignored.add(name)
            continue
        if lowered.endswith(".pyc") or lowered.endswith(".pyo"):
            ignored.add(name)
            continue
    return ignored


def _copy_entry(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore_copy)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _site_packages_root() -> Path:
    for candidate in site.getsitepackages():
        path = Path(candidate)
        if path.name == "site-packages" and path.exists():
            return path
    raise RuntimeError("Could not locate site-packages root for share bundle build.")


def _iter_runtime_distribution_names() -> list[str]:
    resolved: dict[str, str] = {}
    pending = list(RUNTIME_ROOT_DISTS)

    while pending:
        requested = pending.pop()
        requested_key = canonicalize_name(requested)
        if requested_key in resolved:
            continue

        dist = importlib_metadata.distribution(requested)
        resolved[requested_key] = dist.metadata["Name"]

        for requirement_text in dist.requires or []:
            requirement = Requirement(requirement_text)
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            pending.append(requirement.name)

    return sorted(resolved.values(), key=str.lower)


def _copy_runtime_site_packages(bundle_dir: Path) -> None:
    site_root = _site_packages_root()
    target_root = bundle_dir / ".venv" / "Lib" / "site-packages"
    target_root.mkdir(parents=True, exist_ok=True)

    copied: set[Path] = set()
    for dist_name in _iter_runtime_distribution_names():
        dist = importlib_metadata.distribution(dist_name)
        for file in dist.files or []:
            src = Path(dist.locate_file(file))
            if not src.exists() or src.is_dir():
                continue
            try:
                relative = src.relative_to(site_root)
            except ValueError:
                continue
            if relative in copied:
                continue
            _copy_entry(src, target_root / relative)
            copied.add(relative)


def _copy_python_runtime(bundle_dir: Path) -> None:
    runtime_root = Path(sys.base_prefix)
    runtime_dst = bundle_dir / "python_runtime"
    if not runtime_root.exists():
        return

    runtime_dst.mkdir(parents=True, exist_ok=True)

    include_files = [
        "python.exe",
        "pythonw.exe",
        "python3.dll",
        "python313.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "LICENSE.txt",
    ]
    include_dirs = [
        "DLLs",
        "Lib",
        "libs",
        "tcl",
    ]

    for name in include_files:
        src = runtime_root / name
        if src.exists():
            _copy_entry(src, runtime_dst / name)

    for name in include_dirs:
        src = runtime_root / name
        if src.exists():
            _copy_entry(src, runtime_dst / name)


def _rewrite_napcat_loaders(bundle_dir: Path) -> None:
    top_loader = bundle_dir / "loadNapCat.js"
    nested_loader = bundle_dir / "NapCat" / "napcat" / "loadNapCat.js"

    if top_loader.exists():
        top_loader.write_text(
            '(async () => { await import(new URL("./NapCat/napcat/napcat.mjs", import.meta.url)); })();\n',
            encoding="utf-8",
        )

    if nested_loader.exists():
        nested_loader.write_text(
            '(async () => { await import(new URL("./napcat.mjs", import.meta.url)); })();\n',
            encoding="utf-8",
        )


def _write_bundle_files(bundle_dir: Path) -> None:
    exports_dir = bundle_dir / "exports"
    state_dir = bundle_dir / "state"
    exports_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    (bundle_dir / "start_cli.bat").write_text(
        "@echo off\n"
        "setlocal EnableExtensions EnableDelayedExpansion\n"
        "cd /d \"%~dp0\"\n"
        "set \"_CLI_ARGS=%*\"\n"
        "set \"_WT_EXE=\"\n"
        "if /I \"%~1\"==\"--launched-in-modern-host\" goto strip_modern_host\n"
        "if exist \"%LOCALAPPDATA%\\Microsoft\\WindowsApps\\wt.exe\" (\n"
        "  set \"_WT_EXE=%LOCALAPPDATA%\\Microsoft\\WindowsApps\\wt.exe\"\n"
        ") else (\n"
        "  for /f \"delims=\" %%I in ('where wt 2^>nul') do (\n"
        "    if not defined _WT_EXE set \"_WT_EXE=%%~fI\"\n"
        "  )\n"
        ")\n"
        "if \"%~1\"==\"\" (\n"
        "  if not defined WT_SESSION (\n"
        "    if not defined TERM_PROGRAM (\n"
        "      if not defined ConEmuPID (\n"
        "        if /I not \"%CLI_AUTO_WT%\"==\"0\" (\n"
        "          if defined _WT_EXE (\n"
        "            start \"\" \"!_WT_EXE!\" -w 0 new-tab cmd.exe /k \"\\\"%~dp0start_cli_modern_host.bat\\\"\"\n"
        "            exit /b 0\n"
        "          )\n"
        "        )\n"
        "      )\n"
        "    )\n"
        "  )\n"
        ")\n"
        ":prepare_runtime\n"
        "set \"BUNDLE_ROOT=%cd%\"\n"
        "set \"SRC_PATH=%BUNDLE_ROOT%\\src\"\n"
        "set \"SITE_PACKAGES=%BUNDLE_ROOT%\\.venv\\Lib\\site-packages\"\n"
        "set \"PYTHONPATH=%SRC_PATH%;%SITE_PACKAGES%;%PYTHONPATH%\"\n"
        "set \"PATH=%BUNDLE_ROOT%\\.venv\\Scripts;%BUNDLE_ROOT%\\python_runtime;%BUNDLE_ROOT%\\python_runtime\\Scripts;%PATH%\"\n"
        "if exist \"%BUNDLE_ROOT%\\python_runtime\\python.exe\" (\n"
        "  set \"PYTHONHOME=%BUNDLE_ROOT%\\python_runtime\"\n"
        "  call :run \"%BUNDLE_ROOT%\\python_runtime\\python.exe\"\n"
        "  exit /b !errorlevel!\n"
        ")\n"
        "where py >nul 2>nul\n"
        "if !errorlevel!==0 (\n"
        "  call :run py -3.13\n"
        "  exit /b !errorlevel!\n"
        ")\n"
        "where python >nul 2>nul\n"
        "if !errorlevel!==0 (\n"
        "  call :run python\n"
        "  exit /b !errorlevel!\n"
        ")\n"
        "echo Failed to find a usable Python runtime.\n"
        "echo This bundle prefers the packaged python_runtime\\python.exe.\n"
        "echo If it is missing, install Python 3.13 x64 locally and rerun start_cli.bat.\n"
        "pause\n"
        "exit /b 1\n"
        "\n"
        ":strip_modern_host\n"
        "shift\n"
        "call set \"_CLI_ARGS=%%1 %%2 %%3 %%4 %%5 %%6 %%7 %%8 %%9\"\n"
        "goto prepare_runtime\n"
        "\n"
        ":run\n"
        "%* -c \"import typer,prompt_toolkit,httpx,orjson,pydantic,rich,qrcode,websockets\" >nul 2>nul\n"
        "if not !errorlevel!==0 (\n"
        "  echo Python runtime found but bundled dependencies are incomplete.\n"
        "  echo Expected site-packages under .venv\\Lib\\site-packages.\n"
        "  pause\n"
        "  exit /b 1\n"
        ")\n"
        "%* app.py %_CLI_ARGS%\n"
        "set \"_rc=!errorlevel!\"\n"
        "if \"!_rc!\"==\"0\" exit /b 0\n"
        "echo Runtime exited with code !_rc!.\n"
        "pause\n"
        "exit /b !_rc!\n",
        encoding="utf-8",
    )

    (bundle_dir / "start_cli_modern_host.bat").write_text(
        "@echo off\n"
        "setlocal EnableDelayedExpansion\n"
        "cd /d \"%~dp0\"\n"
        "set \"CLI_AUTO_WT=0\"\n"
        "call \"%~dp0start_cli.bat\" --launched-in-modern-host %*\n"
        "exit /b %errorlevel%\n",
        encoding="utf-8",
    )

    (bundle_dir / "start_cli_compat.bat").write_text(
        "@echo off\n"
        "setlocal EnableDelayedExpansion\n"
        "cd /d \"%~dp0\"\n"
        "set \"CLI_AUTO_WT=0\"\n"
        "set \"CLI_UI_MODE=compat\"\n"
        "call \"%~dp0start_cli.bat\" --launched-in-modern-host %*\n"
        "exit /b %errorlevel%\n",
        encoding="utf-8",
    )

    (bundle_dir / "README.md").write_text(
        "# QQ Extractor Share Bundle\n\n"
        "这份包只包含 QQ 提取侧，不包含后续分析/LLM 流程。\n\n"
        "## 启动\n\n"
        "直接双击：\n\n"
        "```text\n"
        "start_cli.bat\n"
        "```\n\n"
        "它会优先尝试在 Windows Terminal 中打开。\n\n"
        "如果你遇到终端错位、排版混乱或只是想稳定一点，直接双击：\n\n"
        "```text\n"
        "start_cli_compat.bat\n"
        "```\n\n"
        "它会强制兼容显示模式，并禁用自动跳转。\n\n"
        "## 基本流程\n\n"
        "1. `/login`\n"
        "2. `/groups` 或 `/friends`\n"
        "3. `/watch ...`\n"
        "4. `/export ...`\n\n"
        "## 典型命令\n\n"
        "```text\n"
        "/watch group 群名\n"
        "/watch friend 好友名\n"
        "/export group 群名 data_count=300\n"
        "/export_TextImage friend 好友名 @final_content-7d @final_content asJSONL\n"
        "```\n\n"
        "## 输出位置\n\n"
        "默认输出到 `exports/`：\n"
        "- `*.txt` / `*.jsonl`\n"
        "- `*.manifest.json`\n"
        "- `<stem>_assets/`\n\n"
        "## 排错\n\n"
        "如果出现闪退、导出中断、`/watch` 异常退出：\n"
        "- 先看 `state/logs/cli_latest.log`\n"
        "- 导出相关问题再一起看对应的 `*.manifest.json`\n\n"
        "如果终端看起来错位：\n"
        "- 先尝试 `start_cli_compat.bat`\n"
        "- 或运行 `app.py --ui compat`\n"
        "- 再把 `/terminal-doctor` 输出和截图一起反馈\n\n"
        "## 运行时说明\n\n"
        "- 优先使用包内 `python_runtime/` 作为便携 Python 运行时\n"
        "- `.venv/` 在分享包内只作为依赖载荷，不作为可移植解释器本体\n"
        "- 如果包内 runtime 不存在，才回退到本机 `Python 3.13 x64`\n"
        "- NapCat 会按相对路径自动发现\n",
        encoding="utf-8",
    )

    (exports_dir / "README.txt").write_text(
        "Exported JSONL/TXT files will be written here.\n",
        encoding="utf-8",
    )
    (state_dir / "README.txt").write_text(
        "Local runtime state files may be written here.\n",
        encoding="utf-8",
    )


def build_bundle(*, name_prefix: str) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_name = f"{name_prefix}_{stamp}"
    bundle_dir = DIST / bundle_name
    zip_path = DIST / f"{bundle_name}.zip"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    include_entries = [
        Path("app.py"),
        Path("loadNapCat.js"),
        Path("pyproject.toml"),
        Path("uv.lock"),
        Path("NapCat"),
        Path("src/qq_data_cli"),
        Path("src/qq_data_core"),
        Path("src/qq_data_integrations"),
    ]

    for relative in include_entries:
        src = ROOT / relative
        if not src.exists():
            continue
        _copy_entry(src, bundle_dir / relative)

    _copy_runtime_site_packages(bundle_dir)
    _copy_python_runtime(bundle_dir)
    _rewrite_napcat_loaders(bundle_dir)
    _write_bundle_files(bundle_dir)

    archive_base = DIST / bundle_name
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(archive_base), "zip", root_dir=DIST, base_dir=bundle_name)
    return bundle_dir, zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a shareable QQ extractor zip bundle.")
    parser.add_argument(
        "--name-prefix",
        default="qq_extractor_share_bundle",
        help="Bundle name prefix. Timestamp is appended automatically.",
    )
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    bundle_dir, zip_path = build_bundle(name_prefix=args.name_prefix)
    print(bundle_dir)
    print(zip_path)


if __name__ == "__main__":
    main()
