from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkAxis:
    reasoning_effort: str
    temperature: float | None
    timeout_s: int
    max_output_tokens: int


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    task_type: str
    description: str
    success_criteria: list[str]


def _build_matrix(profile: str) -> list[BenchmarkAxis]:
    if profile == "recommended":
        efforts = ("medium", "high", "xhigh")
        temperatures: tuple[float | None, ...] = (0.0, 0.2)
        timeouts = (120, 240)
        max_output_tokens = (800, 1600)
    else:
        efforts = ("low", "medium", "high", "xhigh")
        temperatures = (0.0, 0.2, 0.4)
        timeouts = (60, 120, 240)
        max_output_tokens = (800, 1600)

    matrix: list[BenchmarkAxis] = []
    for effort in efforts:
        for temperature in temperatures:
            for timeout_s in timeouts:
                for token_cap in max_output_tokens:
                    matrix.append(
                        BenchmarkAxis(
                            reasoning_effort=effort,
                            temperature=temperature,
                            timeout_s=timeout_s,
                            max_output_tokens=token_cap,
                        )
                    )
    return matrix


def _build_tasks() -> list[BenchmarkTask]:
    return [
        BenchmarkTask(
            task_id="text_analysis_smoke",
            task_type="text_analysis",
            description="高层文本分析 smoke，验证模型能稳定输出结构化摘要和不确定性说明。",
            success_criteria=[
                "返回非空结果",
                "能提取主要话题",
                "能指出证据和不确定性",
            ],
        ),
        BenchmarkTask(
            task_id="text_structured_json_smoke",
            task_type="structured_text",
            description="结构化 JSON 输出 smoke，验证 relay 路线对 JSON 指令是否稳定。",
            success_criteria=[
                "返回合法 JSON 对象",
                "字段齐全",
                "无明显 schema 漂移",
            ],
        ),
        BenchmarkTask(
            task_id="text_long_context_window",
            task_type="long_context",
            description="长上下文窗口文本分析，验证较高 reasoning effort 是否明显提升稳定性。",
            success_criteria=[
                "可在预算内完成",
                "报告不明显坍缩",
                "能区分直接证据与推断",
            ],
        ),
        BenchmarkTask(
            task_id="image_caption_smoke",
            task_type="multimodal_image",
            description="单图 caption smoke，用于验证 GPT-5.4 relay 的多模态 image 输入能力。",
            success_criteria=[
                "请求成功",
                "返回图像描述",
                "usage 与落盘工件完整",
            ],
        ),
    ]


def _result_schema() -> dict[str, Any]:
    return {
        "run_id": "string",
        "profile": "recommended|expanded",
        "provider": "openai_compatible",
        "task_id": "string",
        "reasoning_effort": "low|medium|high|xhigh",
        "temperature": "number|null",
        "timeout_s": "int",
        "max_output_tokens": "int",
        "status": "planned|success|error|timeout",
        "elapsed_s": "float|null",
        "usage": {
            "prompt_tokens": "int",
            "completion_tokens": "int",
            "total_tokens": "int",
            "reasoning_tokens": "int",
            "cached_tokens": "int",
        },
        "artifact_paths": ["string"],
        "notes": ["string"],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_readme(path: Path, *, profile: str, repetitions: int, matrix_size: int) -> None:
    lines = [
        "# OpenAI-Compatible LLM Benchmark Bundle",
        "",
        f"- profile: `{profile}`",
        f"- repetitions: `{repetitions}`",
        f"- matrix_size: `{matrix_size}`",
        "",
        "## Suggested order",
        "",
        "1. Fill `state/config/llm.local.json` with your GPT-5.4 relay credentials.",
        "2. Run the recommended matrix first.",
        "3. Inspect `benchmark_matrix.json` and trim tasks if the provider is slow or expensive.",
        "4. Persist each execution result into `results/*.json` using the schema in `benchmark_result_schema.json`.",
        "",
        "## Recommended first pass",
        "",
        "- reasoning_effort: `medium`, `high`, `xhigh`",
        "- temperature: `0.0`, `0.2`",
        "- timeout_s: `120`, `240`",
        "- max_output_tokens: `800`, `1600`",
        "- repetitions: `2`",
        "",
        "## Goal",
        "",
        "Find a stable, reasonably priced operating range rather than chasing a globally optimal setting.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an OpenAI-compatible GPT-5.4 benchmark plan bundle."
    )
    parser.add_argument(
        "--profile",
        choices=["recommended", "expanded"],
        default="recommended",
        help="Parameter sweep size. 'recommended' is the smaller first-pass matrix.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=2,
        help="Suggested repetition count to include in the manifest.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("state/llm_benchmarks"),
        help="Bundle output root.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional fixed run id. Defaults to a timestamped benchmark id.",
    )
    args = parser.parse_args()

    run_id = args.run_id or f"smoke_bench_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    run_dir = args.out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    matrix = [asdict(item) for item in _build_matrix(args.profile)]
    tasks = [asdict(item) for item in _build_tasks()]
    manifest = {
        "run_id": run_id,
        "profile": args.profile,
        "provider": "openai_compatible",
        "created_at": datetime.now().astimezone().isoformat(),
        "repetitions": args.repetitions,
        "matrix_size": len(matrix),
        "task_count": len(tasks),
        "notes": [
            "This bundle is plan-first; it does not execute remote calls yet.",
            "Use it to freeze the benchmark matrix and result schema before live GPT-5.4 relay tests.",
        ],
    }

    _write_json(run_dir / "benchmark_manifest.json", manifest)
    _write_json(run_dir / "benchmark_matrix.json", {"tasks": tasks, "matrix": matrix})
    _write_json(run_dir / "benchmark_result_schema.json", _result_schema())
    _write_readme(
        run_dir / "README.md",
        profile=args.profile,
        repetitions=args.repetitions,
        matrix_size=len(matrix),
    )

    print(f"Generated benchmark bundle: {run_dir}")


if __name__ == "__main__":
    main()
