from __future__ import annotations

import argparse
import importlib.util
import json
import os
import site
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
RUNTIME_SITE_PACKAGES = REPO_ROOT / "runtime_site_packages"
REPO_VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _missing_runtime_dependency() -> bool:
    for module_name in ("pydantic", "httpx"):
        if importlib.util.find_spec(module_name) is None:
            return True
    return False


def _bundled_runtime_complete() -> bool:
    pydantic_init = RUNTIME_SITE_PACKAGES / "pydantic" / "__init__.py"
    pydantic_core_dir = RUNTIME_SITE_PACKAGES / "pydantic_core"
    return pydantic_init.exists() and any(pydantic_core_dir.glob("*.pyd"))


def _maybe_reexec_into_repo_venv() -> None:
    if os.environ.get("QQ_LIVE_BENCH_REEXEC") == "1":
        return
    if not _missing_runtime_dependency():
        return
    if not REPO_VENV_PYTHON.exists():
        return
    current_python = Path(sys.executable).resolve()
    target_python = REPO_VENV_PYTHON.resolve()
    if current_python == target_python:
        return
    os.environ["QQ_LIVE_BENCH_REEXEC"] = "1"
    os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])


_maybe_reexec_into_repo_venv()

if (
    RUNTIME_SITE_PACKAGES.exists()
    and _bundled_runtime_complete()
    and _missing_runtime_dependency()
):
    site.addsitedir(str(RUNTIME_SITE_PACKAGES))

from qq_data_analysis.llm_agent import (  # noqa: E402
    MultimodalInputImage,
    OpenAICompatibleAnalysisClient,
    OpenAICompatibleRuntimeConfig,
    load_openai_compatible_runtime_config,
)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded live benchmark against the configured OpenAI-compatible GPT-5.4 relay."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("state/config/llm.local.json"),
        help="Path to llm.local.json",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=Path("state/llm_test_image.png"),
        help="Image used for caption smoke.",
    )
    parser.add_argument(
        "--efforts",
        nargs="+",
        default=["low", "medium", "high", "xhigh"],
        help="Reasoning effort sweep.",
    )
    parser.add_argument(
        "--temperatures",
        nargs="+",
        type=float,
        default=[0.0, 0.2],
        help="Temperature sweep.",
    )
    parser.add_argument(
        "--mode",
        choices=["bounded", "full_text_only", "full_with_image"],
        default="bounded",
        help="bounded = text(all efforts*temps) + image(efforts,temp=0.0).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("state/llm_benchmarks"),
        help="Output root directory.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional explicit run id.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable live streaming token/chunk output during each benchmark case.",
    )
    return parser.parse_args()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _usage_payload(bundle: Any) -> dict[str, int]:
    usage = getattr(bundle, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cached_tokens": 0,
        }
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        "reasoning_tokens": int(getattr(usage, "reasoning_tokens", 0) or 0),
        "cached_tokens": int(getattr(usage, "cached_tokens", 0) or 0),
    }


class _StreamPrinter:
    def __init__(self, *, case_label: str) -> None:
        self.case_label = case_label
        self._last_kind: str | None = None

    def __call__(self, kind: str, chunk: str) -> None:
        text = str(chunk or "")
        if not text:
            return
        safe = text.replace("\r", "")
        if kind != self._last_kind:
            if self._last_kind is not None:
                sys.stdout.write("\n")
            sys.stdout.write(f"[stream {self.case_label} {kind}] ")
            self._last_kind = kind
        sys.stdout.write(safe)
        sys.stdout.flush()

    def finish(self) -> None:
        if self._last_kind is not None:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._last_kind = None


def _text_prompts() -> tuple[str, str]:
    system = (
        "You are a careful analysis assistant. "
        "Return strict JSON only. Distinguish direct evidence from inference."
    )
    user = (
        "分析下面这段群聊上下文，并输出 JSON 对象，字段必须包含："
        "summary, domain, likely_noise, repost_signal, uncertainty, evidence.\n"
        "上下文：\n"
        "Kurnal: 这批素材先转统计群\n"
        "Ami: 先别管调试日志，先看转发链\n"
        "QQ用户: [video:example_a.mp4]\n"
        "QQ用户: [video:example_b.mp4]\n"
        "Kurnal: 这条 forward 里视频可能过期了\n"
        "Ami: 先把开发排障噪音压缩掉，只保留搬运相关证据"
    )
    return system, user


def _image_prompt() -> str:
    return (
        "Describe the image conservatively. If the content is too small or unclear, say so. "
        "If there is visible text, quote it. If it looks like meme/repost material, say why."
    )


def _build_cases(args: argparse.Namespace) -> list[dict[str, Any]]:
    efforts = list(dict.fromkeys(str(item).strip() for item in args.efforts if str(item).strip()))
    temperatures = list(dict.fromkeys(float(item) for item in args.temperatures))
    cases: list[dict[str, Any]] = []
    for effort in efforts:
        for temp in temperatures:
            cases.append(
                {
                    "task_id": "text_structured_json",
                    "reasoning_effort": effort,
                    "temperature": temp,
                    "max_output_tokens": 500,
                }
            )
    if args.mode == "full_with_image":
        image_temps = temperatures
    elif args.mode == "bounded":
        image_temps = [0.0]
    else:
        image_temps = []
    for effort in efforts:
        for temp in image_temps:
            cases.append(
                {
                    "task_id": "image_caption",
                    "reasoning_effort": effort,
                    "temperature": temp,
                    "max_output_tokens": 300,
                }
            )
    return cases


def _run_case(
    *,
    base_config: OpenAICompatibleRuntimeConfig,
    image_path: Path,
    case: dict[str, Any],
    stream: bool,
    case_label: str,
) -> dict[str, Any]:
    config = base_config.model_copy(
        update={
            "reasoning_effort": case["reasoning_effort"],
            "temperature": case["temperature"],
        }
    )
    client = OpenAICompatibleAnalysisClient(config)
    started = time.perf_counter()
    printer = _StreamPrinter(case_label=case_label) if stream else None
    try:
        if case["task_id"] == "text_structured_json":
            system_prompt, user_prompt = _text_prompts()
            bundle = client.analyze_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_output_tokens=case["max_output_tokens"],
                stream_callback=printer,
            )
            parsed = _extract_json_object(bundle.raw_text)
            json_ok = isinstance(parsed, dict) and bool(parsed)
            status = "success" if json_ok else "weak_success"
            result = {
                "status": status,
                "finish_reason": bundle.finish_reason,
                "usage": _usage_payload(bundle),
                "raw_preview": bundle.raw_text[:800],
                "json_ok": json_ok,
                "json_keys": sorted(parsed.keys()) if json_ok else [],
                "elapsed_s": round(time.perf_counter() - started, 3),
            }
        else:
            bundle = client.analyze_multimodal(
                system_prompt="You are a careful multimodal analysis assistant.",
                user_prompt=_image_prompt(),
                images=[MultimodalInputImage(path=image_path)],
                max_output_tokens=case["max_output_tokens"],
                stream_callback=printer,
            )
            text_ok = bool((bundle.raw_text or "").strip())
            status = "success" if text_ok else "weak_success"
            result = {
                "status": status,
                "finish_reason": bundle.finish_reason,
                "usage": _usage_payload(bundle),
                "raw_preview": bundle.raw_text[:800],
                "json_ok": False,
                "json_keys": [],
                "elapsed_s": round(time.perf_counter() - started, 3),
            }
        return {**case, **result}
    except Exception as exc:
        result = {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "elapsed_s": round(time.perf_counter() - started, 3),
        }
        return {**case, **result}
    finally:
        if printer is not None:
            printer.finish()


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def _recommend(results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in results if row.get("status") in {"success", "weak_success"}]
    text_success = [
        row for row in successful
        if row.get("task_id") == "text_structured_json" and row.get("json_ok")
    ]
    image_success = [
        row for row in successful
        if row.get("task_id") == "image_caption" and row.get("raw_preview")
    ]
    recommendation: dict[str, Any] = {
        "text_recommended": None,
        "image_recommended": None,
        "notes": [],
    }
    if text_success:
        text_sorted = sorted(
            text_success,
            key=lambda row: (
                {"low": 0, "medium": 1, "high": 2, "xhigh": 3}.get(str(row.get("reasoning_effort")), 99),
                float(row.get("temperature") or 0.0),
                float(row.get("elapsed_s") or 9999.0),
            ),
        )
        recommendation["text_recommended"] = {
            "reasoning_effort": text_sorted[0]["reasoning_effort"],
            "temperature": text_sorted[0]["temperature"],
        }
    if image_success:
        image_sorted = sorted(
            image_success,
            key=lambda row: (
                {"low": 0, "medium": 1, "high": 2, "xhigh": 3}.get(str(row.get("reasoning_effort")), 99),
                float(row.get("temperature") or 0.0),
                float(row.get("elapsed_s") or 9999.0),
            ),
        )
        recommendation["image_recommended"] = {
            "reasoning_effort": image_sorted[0]["reasoning_effort"],
            "temperature": image_sorted[0]["temperature"],
        }
    if not text_success:
        recommendation["notes"].append("No text case returned valid structured JSON.")
    if any(row.get("task_id") == "image_caption" for row in results) and not image_success:
        recommendation["notes"].append("No image caption case returned non-empty text.")
    return recommendation


def main() -> int:
    args = _parse_args()
    run_id = args.run_id or f"live_openai_bench_{_timestamp()}"
    run_dir = args.out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_config = load_openai_compatible_runtime_config(args.config.expanduser().resolve())
    image_path = args.image.expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Benchmark image does not exist: {image_path}")

    cases = _build_cases(args)
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        case_label = f"{index:02d}/{len(cases)} {case['task_id']} {case['reasoning_effort']} t={case['temperature']}"
        print(f"[start] {case_label}", flush=True)
        row = _run_case(
            base_config=base_config,
            image_path=image_path,
            case=case,
            stream=not args.no_stream,
            case_label=case_label,
        )
        row["index"] = index
        results.append(row)
        _write_json(run_dir / f"{index:02d}_{case['task_id']}_{case['reasoning_effort']}_{str(case['temperature']).replace('.', '_')}.json", row)
        print(
            f"[{index:02d}/{len(cases)}] {case['task_id']} effort={case['reasoning_effort']} "
            f"temp={case['temperature']} -> {row['status']} elapsed={row.get('elapsed_s')}s"
        )

    summary = {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "config": {
            "base_url": base_config.base_url,
            "model": base_config.model,
            "timeout_s": base_config.timeout_s,
        },
        "case_count": len(cases),
        "results": results,
        "recommendation": _recommend(results),
    }
    _write_json(run_dir / "summary.json", summary)
    print(f"[done] wrote live benchmark summary to {run_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
