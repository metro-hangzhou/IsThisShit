from __future__ import annotations

import argparse
import importlib.util
import json
import os
import site
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

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
    if os.environ.get("QQ_LLM_SMOKE_REEXEC") == "1":
        return
    if not _missing_runtime_dependency():
        return
    if not REPO_VENV_PYTHON.exists():
        return
    current_python = Path(sys.executable).resolve()
    target_python = REPO_VENV_PYTHON.resolve()
    if current_python == target_python:
        return
    os.environ["QQ_LLM_SMOKE_REEXEC"] = "1"
    os.execv(str(target_python), [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]])


_maybe_reexec_into_repo_venv()


if (
    RUNTIME_SITE_PACKAGES.exists()
    and _bundled_runtime_complete()
    and _missing_runtime_dependency()
):
    site.addsitedir(str(RUNTIME_SITE_PACKAGES))

from qq_data_analysis import (  # noqa: E402
    MultimodalInputImage,
    MultimodalSmokePack,
    load_multimodal_client,
    load_multimodal_runtime_config,
    load_multimodal_smoke_pack,
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a careful multimodal analysis assistant. Describe only what is directly "
    "observable in the supplied images. Separate visual facts from inference."
)
DEFAULT_USER_PROMPT = (
    "Analyze the supplied images. Summarize the visible scene, extract legible text, "
    "note any meme/repost cues, and call out uncertainty explicitly."
)
SUPPORTED_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Manual provider-agnostic multimodal smoke harness. "
            "Use config + images, or provide a JSON smoke pack."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("state/config/llm.local.json"),
        help="Provider config JSON. Defaults to state/config/llm.local.json",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Provider adapter id, for example openai_compatible",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override, for example gpt-5.4",
    )
    parser.add_argument(
        "--pack-file",
        type=Path,
        help="Optional JSON smoke pack. CLI prompt/provider/model flags override pack values.",
    )
    parser.add_argument(
        "--image",
        action="append",
        type=Path,
        default=[],
        help="Image path. Repeat for multiple images.",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        help="Optional directory to scan recursively for images.",
    )
    parser.add_argument(
        "--system-prompt",
        default=None,
        help="Optional system prompt override.",
    )
    parser.add_argument(
        "--user-prompt",
        "--prompt",
        dest="user_prompt",
        default=None,
        help="Optional user prompt override.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=600,
        help="Max output tokens for the multimodal response.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("state/llm_multimodal_smoke"),
        help="Directory where run artifacts are written.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional explicit run id. Defaults to smoke_<timestamp>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config/image/pack resolution and write request artifacts without making a live provider call.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable live streaming output and wait for the final response only.",
    )
    return parser.parse_args()


def _resolve_image_dir(image_dir: Path) -> list[Path]:
    resolved = image_dir.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Image directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Image directory is not a directory: {resolved}")
    images = [
        path
        for path in sorted(resolved.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]
    if not images:
        raise FileNotFoundError(
            f"No supported images were found under directory: {resolved}"
        )
    return images


def _normalize_image(path: Path, *, label: str | None = None) -> MultimodalInputImage:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Image does not exist: {resolved}")
    return MultimodalInputImage(path=resolved, label=label)


def _dedupe_images(images: Iterable[MultimodalInputImage]) -> list[MultimodalInputImage]:
    seen: set[tuple[str, str]] = set()
    deduped: list[MultimodalInputImage] = []
    for image in images:
        key = (str(image.path.expanduser().resolve()).lower(), image.label or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            image.model_copy(update={"path": image.path.expanduser().resolve()})
        )
    return deduped


def _resolve_pack(path: Path | None) -> MultimodalSmokePack | None:
    if path is None:
        return None
    return load_multimodal_smoke_pack(path.expanduser().resolve())


def _build_images(args: argparse.Namespace, pack: MultimodalSmokePack | None) -> list[MultimodalInputImage]:
    images: list[MultimodalInputImage] = []
    if pack is not None:
        images.extend(pack.images)
    for image_path in args.image:
        images.append(_normalize_image(image_path))
    if args.image_dir is not None:
        images.extend(_normalize_image(path) for path in _resolve_image_dir(args.image_dir))
    images = _dedupe_images(images)
    if not images:
        raise SystemExit("Provide at least one image via --image, --image-dir, or --pack-file.")
    return images


def _build_request_document(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
    images: list[MultimodalInputImage],
    config_path: Path,
    pack_file: Path | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "config_path": str(config_path),
        "pack_file": str(pack_file) if pack_file is not None else None,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "max_output_tokens": max_output_tokens,
        "images": [image.model_dump(mode="json") for image in images],
        "metadata": metadata,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class _StreamPrinter:
    def __init__(self) -> None:
        self._last_kind: str | None = None

    def __call__(self, kind: str, chunk: str) -> None:
        text = str(chunk or "")
        if not text:
            return
        safe = text.replace("\r", "")
        if kind != self._last_kind:
            if self._last_kind is not None:
                sys.stdout.write("\n")
            sys.stdout.write(f"[stream:{kind}] ")
            self._last_kind = kind
        sys.stdout.write(safe)
        sys.stdout.flush()

    def finish(self) -> None:
        if self._last_kind is not None:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._last_kind = None


def _main() -> int:
    args = _parse_args()
    pack = _resolve_pack(args.pack_file)

    provider = (
        args.provider
        or (pack.provider if pack is not None and pack.provider else None)
        or "openai_compatible"
    )
    model_override = args.model or (pack.model if pack is not None and pack.model else None)
    system_prompt = (
        args.system_prompt
        or (pack.system_prompt if pack is not None and pack.system_prompt else None)
        or DEFAULT_SYSTEM_PROMPT
    )
    user_prompt = (
        args.user_prompt
        or (pack.user_prompt if pack is not None and pack.user_prompt else None)
        or DEFAULT_USER_PROMPT
    )
    images = _build_images(args, pack)
    config_path = args.config.expanduser().resolve()

    runtime_config = load_multimodal_runtime_config(config_path, provider=provider)
    resolved_model = model_override or getattr(runtime_config, "model", "unknown")
    run_id = args.run_id or f"smoke_{_timestamp()}"
    run_dir = args.out_dir.expanduser().resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = dict(pack.metadata) if pack is not None else {}
    request_document = _build_request_document(
        provider=provider,
        model=resolved_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=args.max_output_tokens,
        images=images,
        config_path=config_path,
        pack_file=args.pack_file.expanduser().resolve() if args.pack_file else None,
        metadata=metadata,
    )
    _write_json(run_dir / "request.json", request_document)

    if args.dry_run:
        response_payload = {
            "status": "dry_run",
            "raw_text": "",
            "reasoning_text": "",
            "finish_reason": "dry_run",
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "cached_tokens": 0,
            },
            "raw_response": {},
        }
        summary = {
            "status": "dry_run",
            "provider": provider,
            "model": resolved_model,
            "image_count": len(images),
            "run_dir": str(run_dir),
        }
        _write_json(run_dir / "response.json", response_payload)
        (run_dir / "response.txt").write_text("", encoding="utf-8")
        _write_json(run_dir / "summary.json", summary)
        print(f"[dry-run] wrote request artifacts to {run_dir}")
        return 0

    client = load_multimodal_client(
        config_path,
        provider=provider,
        model=model_override,
    )
    stream_printer = None if args.no_stream else _StreamPrinter()
    if stream_printer is not None:
        print("[stream] live content/reasoning chunks will be printed below.")
    bundle = client.analyze_multimodal(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        images=images,
        max_output_tokens=args.max_output_tokens,
        stream_callback=stream_printer,
    )
    if stream_printer is not None:
        stream_printer.finish()

    response_payload = {
        "status": "ok",
        "raw_text": bundle.raw_text,
        "reasoning_text": bundle.reasoning_text,
        "finish_reason": bundle.finish_reason,
        "usage": {
            "prompt_tokens": bundle.usage.prompt_tokens,
            "completion_tokens": bundle.usage.completion_tokens,
            "total_tokens": bundle.usage.total_tokens,
            "reasoning_tokens": bundle.usage.reasoning_tokens,
            "cached_tokens": bundle.usage.cached_tokens,
        },
        "raw_response": bundle.raw_response,
    }
    summary = {
        "status": "ok",
        "provider": provider,
        "model": resolved_model,
        "config_path": str(config_path),
        "pack_file": str(args.pack_file.expanduser().resolve()) if args.pack_file else None,
        "image_count": len(images),
        "images": [str(image.path) for image in images],
        "finish_reason": bundle.finish_reason,
        "usage": response_payload["usage"],
        "run_dir": str(run_dir),
    }
    _write_json(run_dir / "response.json", response_payload)
    (run_dir / "response.txt").write_text(bundle.raw_text, encoding="utf-8")
    _write_json(run_dir / "summary.json", summary)
    print(f"[ok] wrote multimodal smoke artifacts to {run_dir}")
    print(f"[model] provider={provider} model={resolved_model}")
    print(f"[result] finish_reason={bundle.finish_reason} total_tokens={bundle.usage.total_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
