from __future__ import annotations

import argparse
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from qq_data_analysis import AnalysisJobConfig, AnalysisTarget, AnalysisTimeScope
from qq_data_analysis.llm_agent import OpenAICompatibleAnalysisClient
from qq_data_process.runtime_control import (
    apply_cpu_thread_limit,
    apply_process_priority,
)
from qq_data_process.utils import preview_text
from qq_data_analysis.llm_window import (
    WholeWindowLlmAnalyzer,
    WindowReportPlan,
    load_saved_analysis_pack,
    load_text_analysis_client,
    save_llm_analysis_result,
)
from qq_data_analysis.models import (
    AnalysisPack,
    ImageCaptionSample,
    LlmAnalysisJobConfig,
)
from qq_data_analysis.substrate import AnalysisSubstrate


def _parse_timestamp(value: str) -> int:
    for fmt in ("%Y-%m-%d_%H-%M-%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(value, fmt).astimezone().timestamp() * 1000)
        except ValueError:
            continue
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run first-phase whole-window LLM analysis. "
            "This builds or reuses a bounded analysis pack, then emits a long report "
            "plus machine-readable artifacts. Use --plan-only for pack-based previews "
            "such as the Benshi workflow without making a live provider call."
        )
    )
    parser.add_argument("target_type", nargs="?", choices=["group", "friend"])
    parser.add_argument("target_id", nargs="?")
    parser.add_argument("--pack-file", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path("state/preprocess"))
    parser.add_argument("--sqlite-path", type=Path)
    parser.add_argument("--qdrant-path", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--auto-window-hours", type=int, default=24)
    parser.add_argument("--projection-mode", choices=["alias", "raw"], default="alias")
    parser.add_argument("--danger-allow-raw-identity-output", action="store_true")
    parser.add_argument(
        "--llm-config",
        type=Path,
        default=Path("state/config/llm.local.json"),
    )
    parser.add_argument("--model")
    parser.add_argument(
        "--prompt-version",
        default="window_report_v1",
        help="Prompt profile to use, for example window_report_v1 or benshi_window_v1",
    )
    parser.add_argument("--max-candidate-events", type=int, default=5)
    parser.add_argument("--max-people", type=int, default=5)
    parser.add_argument("--max-representative-messages", type=int, default=40)
    parser.add_argument("--max-reference-messages", type=int, default=64)
    parser.add_argument("--include-retrieval-snippets", action="store_true")
    parser.add_argument("--max-retrieval-snippets", type=int, default=4)
    parser.add_argument(
        "--disable-text-gap-inference",
        action="store_true",
        help="Disable text-only missing-image inference in the analysis pack",
    )
    parser.add_argument(
        "--text-gap-context-radius",
        type=int,
        default=2,
        help="How many messages before/after a missing image to use for text-only inference",
    )
    parser.add_argument(
        "--max-text-gap-hypotheses",
        type=int,
        default=12,
        help="Maximum number of text-only missing-image hypotheses to include in the pack",
    )
    parser.add_argument("--max-input-tokens", type=int, default=16000)
    parser.add_argument("--max-output-tokens", type=int, default=2200)
    parser.add_argument(
        "--include-image-captions",
        action="store_true",
        help="Caption a small set of available images with the active OpenAI-compatible model and include them in the prompt",
    )
    parser.add_argument(
        "--max-caption-images",
        type=int,
        default=6,
        help="Maximum number of image captions to include when --include-image-captions is enabled",
    )
    parser.add_argument(
        "--caption-max-output-tokens",
        type=int,
        default=180,
        help="Maximum output tokens per image caption request",
    )
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument(
        "--save-plan",
        action="store_true",
        help="When used with --plan-only, save the pack, prompt, and plan metadata for manual review",
    )
    parser.add_argument(
        "--cpu-limit-threads",
        type=int,
        default=None,
        help="Cap CPU-heavy runtime libraries to this many threads so the system keeps headroom",
    )
    parser.add_argument(
        "--cpu-reserve-cores",
        type=int,
        default=None,
        help="Leave this many CPU cores free instead of using all logical cores",
    )
    parser.add_argument(
        "--cpu-yield-ms",
        type=int,
        default=0,
        help="Optional cooperative yield sleep for long local analysis loops",
    )
    parser.add_argument(
        "--cpu-yield-every",
        type=int,
        default=256,
        help="How many hot-loop iterations to process before a cooperative yield sleep",
    )
    parser.add_argument(
        "--process-priority",
        choices=["normal", "below_normal", "idle"],
        default="below_normal",
        help="Lower the process priority so the system stays responsive during long runs",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("state/analysis_runs"))
    args = parser.parse_args()

    llm_config = LlmAnalysisJobConfig(
        prompt_version=args.prompt_version,
        max_candidate_events=args.max_candidate_events,
        max_people=args.max_people,
        max_representative_messages=args.max_representative_messages,
        max_reference_messages=args.max_reference_messages,
        include_retrieval_snippets=args.include_retrieval_snippets,
        max_retrieval_snippets=args.max_retrieval_snippets,
        enable_text_gap_inference=not args.disable_text_gap_inference,
        text_gap_context_radius=args.text_gap_context_radius,
        max_text_gap_hypotheses=args.max_text_gap_hypotheses,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
    )
    cpu_policy = apply_cpu_thread_limit(
        max_threads=args.cpu_limit_threads,
        reserve_cores=args.cpu_reserve_cores,
        yield_ms=args.cpu_yield_ms,
        yield_every=args.cpu_yield_every,
    )
    priority_applied = apply_process_priority(args.process_priority)
    if cpu_policy["applied"]:
        print(
            "[cpu_limit] policy={policy} cpu_count={cpu_count} thread_limit={thread_limit} "
            "torch_applied={torch_applied} yield_ms={yield_ms} yield_every={yield_every}".format(
                **cpu_policy
            )
        )
    print(f"[process_priority] mode={args.process_priority} applied={priority_applied}")

    if args.pack_file is None and (args.target_type is None or args.target_id is None):
        raise SystemExit("Provide target_type + target_id, or use --pack-file.")

    if args.pack_file is not None:
        pack = load_saved_analysis_pack(args.pack_file)
        plan = _plan_from_saved_pack(pack, llm_config)
        if args.plan_only:
            _print_plan(plan)
            if args.save_plan:
                _save_plan_artifacts(
                    plan=plan,
                    out_dir=args.out_dir,
                    prefix=_result_prefix(
                        pack.target.target_type, pack.target.display_id
                    ),
                )
            return
        if args.include_image_captions:
            raise SystemExit(
                "Image caption augmentation currently requires build-from-state mode, not --pack-file."
            )
        client = load_text_analysis_client(args.llm_config, model=args.model)
        analyzer = WholeWindowLlmAnalyzer(client=client, config=llm_config)
        result = _run_analysis_with_console_stream(analyzer, plan)
        prefix = _result_prefix(pack.target.target_type, pack.target.display_id)
        result = save_llm_analysis_result(
            result=result,
            plan=plan,
            out_dir=args.out_dir,
            prefix=prefix,
        )
        _print_result(result)
        return

    sqlite_path = args.sqlite_path or args.state_dir / "db" / "analysis.db"
    qdrant_path = args.qdrant_path or args.state_dir / "qdrant"
    if args.start or args.end:
        if not args.start or not args.end:
            raise SystemExit("Manual analysis requires both --start and --end.")
        time_scope = AnalysisTimeScope(
            mode="manual",
            start_timestamp_ms=_parse_timestamp(args.start),
            end_timestamp_ms=_parse_timestamp(args.end),
        )
    else:
        time_scope = AnalysisTimeScope(
            mode="auto_adaptive",
            auto_window_ms=args.auto_window_hours * 60 * 60 * 1000,
        )

    config = AnalysisJobConfig(
        target=AnalysisTarget(
            target_type=args.target_type,
            target_id=args.target_id,
            run_id=args.run_id,
        ),
        time_scope=time_scope,
        projection_mode=args.projection_mode,
        danger_allow_raw_identity_output=args.danger_allow_raw_identity_output,
    )

    substrate = AnalysisSubstrate(sqlite_path=sqlite_path, qdrant_path=qdrant_path)
    try:
        materials = substrate.build_materials(config)
        client = (
            load_text_analysis_client(args.llm_config, model=args.model)
            if not args.plan_only
            else _PlanOnlyTextClient()
        )
        analyzer = WholeWindowLlmAnalyzer(
            client=client,
            config=llm_config,
        )
        plan = analyzer.prepare(materials)
        if args.include_image_captions:
            if args.plan_only:
                raise SystemExit(
                    "Image caption augmentation requires a live provider call; do not combine it with --plan-only."
                )
            plan = _augment_plan_with_image_captions(
                analyzer=analyzer,
                plan=plan,
                materials=materials.messages,
                sqlite_path=sqlite_path,
                client=client,
                max_images=args.max_caption_images,
                caption_max_output_tokens=args.caption_max_output_tokens,
            )
        _print_plan(plan)
        if args.plan_only:
            if args.save_plan:
                _save_plan_artifacts(
                    plan=plan,
                    out_dir=args.out_dir,
                    prefix=_result_prefix(
                        materials.target.target_type, materials.target.display_id
                    ),
                )
            return
        result = _run_analysis_with_console_stream(analyzer, plan)
        prefix = _result_prefix(
            materials.target.target_type, materials.target.display_id
        )
        result = save_llm_analysis_result(
            result=result,
            plan=plan,
            out_dir=args.out_dir,
            prefix=prefix,
        )
        _print_result(result)
    finally:
        substrate.close()


def _plan_from_saved_pack(
    pack: AnalysisPack, config: LlmAnalysisJobConfig
) -> WindowReportPlan:
    analyzer = WholeWindowLlmAnalyzer(client=_PlanOnlyTextClient(), config=config)
    return analyzer.build_plan_from_pack(pack)


def _augment_plan_with_image_captions(
    *,
    analyzer: WholeWindowLlmAnalyzer,
    plan: WindowReportPlan,
    materials: list,
    sqlite_path: Path,
    client,
    max_images: int,
    caption_max_output_tokens: int,
) -> WindowReportPlan:
    if not isinstance(client, OpenAICompatibleAnalysisClient):
        raise SystemExit(
            "Image caption augmentation currently requires the OpenAI-compatible provider."
        )

    source_path = _load_import_source_path(sqlite_path, plan.pack.run_id)
    if source_path is None:
        print("[image_caption] source export path not found; skipping image captions")
        return plan

    caption_candidates = _select_image_caption_candidates(
        plan=plan,
        materials=materials,
        source_path=source_path,
        max_images=max_images,
    )
    if not caption_candidates:
        print("[image_caption] no usable image files found; skipping image captions")
        return plan

    caption_samples: list[ImageCaptionSample] = []
    for index, item in enumerate(caption_candidates, start=1):
        print(
            f"[image_caption] {index}/{len(caption_candidates)} file={item['file_name'] or item['resolved_path'].name}",
            flush=True,
        )
        bundle = client.caption_image(
            image_path=item["resolved_path"],
            prompt=(
                "你在做QQ群聊天图像辅助分析。请用中文保守描述这张图片，输出1-2句。"
                "优先说明图片类型（截图/聊天记录/梗图/实物/界面/文档/照片/其他），"
                "再说明主要可见主体；若有明显可读文字，提取少量关键词；看不清就直说，不要脑补。"
                f" 聊天上下文提示：{item['context_excerpt'] or '<none>'}"
            ),
            max_output_tokens=caption_max_output_tokens,
        )
        print(
            f"[image_caption_done] {preview_text(bundle.raw_text.strip(), 120)}",
            flush=True,
        )
        caption_samples.append(
            ImageCaptionSample(
                message_uid=item["message_uid"],
                timestamp_iso=item["timestamp_iso"],
                sender_id=item["sender_id"],
                sender_name=item.get("sender_name"),
                file_name=item.get("file_name"),
                resolved_path=str(item["resolved_path"]),
                context_excerpt=item["context_excerpt"],
                caption=bundle.raw_text.strip(),
                model_name=getattr(client.config, "model", "unknown"),
            )
        )

    updated_pack = plan.pack.model_copy(
        update={"image_caption_samples": caption_samples}
    )
    updated_warnings = list(updated_pack.warnings)
    updated_warnings.append(
        f"Image caption augmentation added {len(caption_samples)} direct multimodal image captions."
    )
    updated_pack = updated_pack.model_copy(update={"warnings": updated_warnings})
    return analyzer.build_plan_from_pack(updated_pack)


def _load_import_source_path(sqlite_path: Path, run_id: str) -> Path | None:
    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute(
            "SELECT source_path FROM import_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row[0]:
        return None
    return Path(row[0])


def _select_image_caption_candidates(
    *,
    plan: WindowReportPlan,
    materials: list,
    source_path: Path,
    max_images: int,
) -> list[dict]:
    assets_root = source_path.parent / f"{source_path.stem}_assets"
    by_uid = {item.message_uid: item for item in materials}
    selected: list[dict] = []
    seen_paths: set[str] = set()
    message_uid_order = [item.message_uid for item in plan.pack.representative_messages]
    for evidence in plan.pack.message_reference_pool:
        if evidence.message_uid not in message_uid_order:
            message_uid_order.append(evidence.message_uid)

    for message_uid in message_uid_order:
        message = by_uid.get(message_uid)
        if message is None:
            continue
        context_excerpt = preview_text(
            ((message.text_content or message.content or "").replace("\n", " / ")),
            120,
        )
        for asset in message.assets:
            if asset.get("asset_type") != "image":
                continue
            resolved_path = _resolve_image_asset_path(asset, assets_root)
            if resolved_path is None:
                continue
            norm = str(resolved_path).lower()
            if norm in seen_paths:
                continue
            seen_paths.add(norm)
            selected.append(
                {
                    "message_uid": message.message_uid,
                    "timestamp_iso": message.timestamp_iso,
                    "sender_id": message.sender_id,
                    "sender_name": message.sender_name,
                    "file_name": asset.get("file_name"),
                    "resolved_path": resolved_path,
                    "context_excerpt": context_excerpt,
                }
            )
            if len(selected) >= max_images:
                return selected
    return selected


def _resolve_image_asset_path(asset: dict, assets_root: Path) -> Path | None:
    exported_rel_path = asset.get("exported_rel_path")
    if exported_rel_path:
        candidate = assets_root / exported_rel_path
        if candidate.exists():
            return candidate
    path_value = asset.get("path")
    if path_value:
        candidate = Path(path_value)
        if candidate.exists():
            return candidate
    return None


def _print_plan(plan: WindowReportPlan) -> None:
    print("## Whole-Window LLM Plan")
    print(
        "target={target} window={start} -> {end}".format(
            target=plan.pack.target.display_name or plan.pack.target.display_id,
            start=plan.pack.chosen_time_window.start_timestamp_iso,
            end=plan.pack.chosen_time_window.end_timestamp_iso,
        )
    )
    print(f"prompt_version={plan.prompt_version}")
    print("pack_mode=bounded_analysis_pack")
    print(f"representative_messages={len(plan.pack.representative_messages)}")
    print(f"reference_pool={len(plan.pack.message_reference_pool)}")
    print(
        f"text_gap_inferred={len(plan.pack.media_inference_scaffold.inferred)} "
        f"unknown={len(plan.pack.media_inference_scaffold.unknown)}"
    )
    print(f"image_captions={len(plan.pack.image_caption_samples)}")
    print(
        "token_budget estimated_input={inp} max_output={out}".format(
            inp=plan.estimated_input_tokens,
            out=plan.max_output_tokens,
        )
    )
    print(f"pack_summary={plan.pack.pack_summary}")


def _save_plan_artifacts(*, plan: WindowReportPlan, out_dir: Path, prefix: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    analysis_pack_path = out_dir / f"{prefix}.analysis_pack.json"
    llm_run_meta_path = out_dir / f"{prefix}.llm_run_meta.json"
    prompt_path = out_dir / f"{prefix}.prompt.txt"
    plan_path = out_dir / f"{prefix}.plan.txt"

    analysis_pack_path.write_text(
        json.dumps(plan.pack.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    llm_run_meta_path.write_text(
        json.dumps(
            {
                "prompt_version": plan.prompt_version,
                "provider_name": "plan_only",
                "model_name": "plan_only",
                "warnings": plan.pack.warnings,
                "estimated_input_tokens": plan.estimated_input_tokens,
                "max_output_tokens": plan.max_output_tokens,
                "target": plan.pack.target.model_dump(mode="json"),
                "chosen_time_window": plan.pack.chosen_time_window.model_dump(
                    mode="json"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    prompt_path.write_text(
        "\n\n--- USER PROMPT ---\n\n".join([plan.system_prompt, plan.user_prompt]),
        encoding="utf-8",
    )
    plan_path.write_text(
        "\n".join(
            [
                "## Whole-Window LLM Plan",
                "target={target} window={start} -> {end}".format(
                    target=plan.pack.target.display_name or plan.pack.target.display_id,
                    start=plan.pack.chosen_time_window.start_timestamp_iso,
                    end=plan.pack.chosen_time_window.end_timestamp_iso,
                ),
                f"prompt_version={plan.prompt_version}",
                "pack_mode=bounded_analysis_pack",
                f"representative_messages={len(plan.pack.representative_messages)}",
                f"reference_pool={len(plan.pack.message_reference_pool)}",
                f"text_gap_inferred={len(plan.pack.media_inference_scaffold.inferred)} unknown={len(plan.pack.media_inference_scaffold.unknown)}",
                f"image_captions={len(plan.pack.image_caption_samples)}",
                "token_budget estimated_input={inp} max_output={out}".format(
                    inp=plan.estimated_input_tokens,
                    out=plan.max_output_tokens,
                ),
                f"pack_summary={plan.pack.pack_summary}",
            ]
        ),
        encoding="utf-8",
    )
    print("## Plan Artifacts")
    print(f"analysis_pack={analysis_pack_path}")
    print(f"llm_run_meta={llm_run_meta_path}")
    print(f"prompt={prompt_path}")
    print(f"plan={plan_path}")


def _print_result(result) -> None:
    print("## LLM Report")
    print(result.report_body)
    print("## Usage")
    print(
        "prompt={p} completion={c} total={t} reasoning={r} cached={ca}".format(
            p=result.usage.prompt_tokens,
            c=result.usage.completion_tokens,
            t=result.usage.total_tokens,
            r=result.usage.reasoning_tokens,
            ca=result.usage.cached_tokens,
        )
    )
    if result.artifacts is not None:
        print("## Artifacts")
        print(f"analysis_pack={result.artifacts.analysis_pack_path}")
        print(f"llm_run_meta={result.artifacts.llm_run_meta_path}")
        print(f"report={result.artifacts.report_path}")
        print(f"usage={result.artifacts.usage_path}")
        print(f"prompt={result.artifacts.prompt_path}")


def _run_analysis_with_console_stream(
    analyzer: WholeWindowLlmAnalyzer,
    plan: WindowReportPlan,
):
    stop_event = threading.Event()
    stream_started = threading.Event()

    def _heartbeat() -> None:
        started = time.time()
        while not stop_event.wait(5.0):
            elapsed = time.time() - started
            if stream_started.is_set():
                print(f"\n[llm_stream_wait] elapsed={elapsed:.1f}s", flush=True)
            else:
                print(
                    f"[llm_wait] elapsed={elapsed:.1f}s waiting_for_first_chunk",
                    flush=True,
                )

    def _stream_callback(kind: str, chunk: str) -> None:
        if not chunk:
            return
        if not stream_started.is_set():
            stream_started.set()
            print("## LLM Stream", flush=True)
        if kind == "reasoning":
            print(chunk, end="", flush=True)
            return
        print(chunk, end="", flush=True)

    heartbeat = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat.start()
    try:
        result = analyzer.analyze(plan, stream_callback=_stream_callback)
    finally:
        stop_event.set()
        heartbeat.join(timeout=1.0)
    if stream_started.is_set():
        print("", flush=True)
    return result


def _result_prefix(target_type: str, target_id: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"llm_window_{target_type}_{target_id}_{stamp}"


class _PlanOnlyTextClient:
    config = type("Cfg", (), {"model": "plan-only"})()

    def analyze_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        stream_callback=None,
    ):
        raise RuntimeError("Plan-only mode should not execute the LLM client.")


if __name__ == "__main__":
    main()
