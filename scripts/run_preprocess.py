from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from qq_data_process import (
    ChunkPolicySpec,
    EmbeddingPolicy,
    PreprocessJobConfig,
    PreprocessService,
    detect_source_type,
)
from qq_data_process.runtime_control import (
    apply_cpu_thread_limit,
    apply_process_priority,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preprocessing pipeline on an exported QQ chat file. "
            "This is the pack-based entry path used before bounded analysis and "
            "Benshi plan-only/report workflows."
        )
    )
    parser.add_argument(
        "source_path", type=Path, help="Path to JSONL / JSON / TXT source"
    )
    parser.add_argument(
        "--source-type",
        choices=["exporter_jsonl", "qce_json", "qq_txt"],
        default=None,
        help="Override auto-detected source type",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("state/preprocess/manual_runs"),
        help="Directory for SQLite/Qdrant output",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="Optional explicit SQLite output path",
    )
    parser.add_argument(
        "--qdrant-path",
        type=Path,
        default=None,
        help="Optional explicit Qdrant output path; put this on SSD if available",
    )
    parser.add_argument(
        "--policy",
        choices=["none", "window", "timegap", "hybrid"],
        default="window",
        help="Chunk policy to apply",
    )
    parser.add_argument("--window-size", type=int, default=256)
    parser.add_argument("--overlap", type=int, default=32)
    parser.add_argument("--gap-seconds", type=int, default=600)
    parser.add_argument("--max-messages", type=int, default=256)
    parser.add_argument(
        "--embedding-provider",
        choices=["qwen3_vl", "openrouter", "jina_v4", "deterministic"],
        default="qwen3_vl",
        help="Embedding backend for text/image indexing",
    )
    parser.add_argument(
        "--embedding-model",
        default="Qwen/Qwen3-VL-Embedding-2B",
        help="Embedding model name when the backend uses a HuggingFace model",
    )
    parser.add_argument(
        "--embedding-device",
        default=None,
        help="Optional device override such as cpu or cuda",
    )
    parser.add_argument(
        "--embedding-cache-dir",
        type=Path,
        default=None,
        help="Optional local cache directory for model weights",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=None,
        help="Optional embedding batch size override",
    )
    parser.add_argument(
        "--embedding-dtype",
        choices=["auto", "float16", "float32", "bfloat16"],
        default=None,
        help="Optional torch dtype override for HuggingFace embedding models",
    )
    parser.add_argument(
        "--embedding-min-cuda-vram-gb",
        type=float,
        default=None,
        help="Auto mode will fall back to CPU when the detected CUDA VRAM is below this threshold",
    )
    parser.add_argument(
        "--embedding-quantization",
        choices=["auto", "none", "int8"],
        default=None,
        help="Optional quantization mode override for small-VRAM CUDA runs",
    )
    parser.add_argument(
        "--skip-image-embeddings",
        action="store_true",
        help="Skip image vectorization and keep only image references",
    )
    parser.add_argument(
        "--skip-vector-index",
        action="store_true",
        help="Skip all vector indexing and build only the SQLite/FTS analysis base",
    )
    parser.add_argument(
        "--skip-keyword-index",
        action="store_true",
        help="Skip building the SQLite FTS keyword index for faster import when whole-window analysis is enough",
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
        default=2,
        help="Sleep this many milliseconds every few hot-loop iterations to keep the desktop responsive",
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
        help="Lower the process priority so the system stays responsive during long preprocess runs",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_type = args.source_type or detect_source_type(args.source_path)
    params = {
        "window_size": args.window_size,
        "overlap": args.overlap,
        "gap_seconds": args.gap_seconds,
        "max_messages": args.max_messages,
    }

    specs = []
    if args.policy != "none":
        specs.append(ChunkPolicySpec(name=args.policy, params=params))

    embedding_kwargs = {
        "provider_name": args.embedding_provider,
        "model_name": args.embedding_model,
    }
    if args.embedding_device is not None:
        embedding_kwargs["device"] = args.embedding_device
    if args.embedding_cache_dir is not None:
        embedding_kwargs["cache_dir"] = args.embedding_cache_dir
    if args.embedding_batch_size is not None:
        embedding_kwargs["batch_size"] = args.embedding_batch_size
    elif args.embedding_provider == "openrouter":
        embedding_kwargs["batch_size"] = 2048
    elif args.embedding_provider == "qwen3_vl":
        embedding_kwargs["batch_size"] = 64
    if args.embedding_dtype is not None:
        embedding_kwargs["torch_dtype"] = args.embedding_dtype
    if args.embedding_min_cuda_vram_gb is not None:
        embedding_kwargs["min_cuda_vram_gb"] = args.embedding_min_cuda_vram_gb
    if args.embedding_quantization is not None:
        embedding_kwargs["quantization"] = args.embedding_quantization

    config = PreprocessJobConfig(
        source_type=source_type,
        source_path=args.source_path,
        state_dir=args.state_dir,
        sqlite_path=args.sqlite_path,
        qdrant_path=args.qdrant_path,
        chunk_policy_specs=specs,
        embedding_policy=EmbeddingPolicy(**embedding_kwargs),
        skip_vector_index=args.skip_vector_index,
        skip_keyword_index=args.skip_keyword_index,
        skip_image_embeddings=args.skip_image_embeddings,
    )
    cpu_policy = apply_cpu_thread_limit(
        max_threads=args.cpu_limit_threads,
        reserve_cores=args.cpu_reserve_cores,
        yield_ms=args.cpu_yield_ms,
        yield_every=args.cpu_yield_every,
    )
    priority_applied = apply_process_priority(args.process_priority)
    service = PreprocessService()
    started = datetime.now()
    config.state_dir.mkdir(parents=True, exist_ok=True)
    progress_log = config.state_dir / "preprocess.progress.jsonl"
    progress_status = config.state_dir / "preprocess.status.json"
    latest_progress: dict[str, object] = {
        "phase": "boot",
        "current": 0,
        "total": 0,
        "elapsed_s": 0.0,
        "message": "Starting preprocess",
    }
    progress_lock = threading.Lock()
    stop_event = threading.Event()

    def _print_progress(event: dict[str, object]) -> None:
        phase = str(event.get("phase", "unknown"))
        current = int(event.get("current", 0) or 0)
        total = int(event.get("total", 0) or 0)
        message = str(event.get("message", ""))
        elapsed = max(0.001, (datetime.now() - started).total_seconds())
        pct = None
        rate = None
        eta_seconds = None
        if total > 0:
            pct = current / total * 100.0
            rate = current / elapsed
            if current > 0 and current < total and rate > 0:
                eta_seconds = (total - current) / rate
        payload = {
            "ts": datetime.now().isoformat(),
            "phase": phase,
            "current": current,
            "total": total,
            "elapsed_s": round(elapsed, 3),
            "message": message,
        }
        if pct is not None:
            payload["percent"] = round(pct, 2)
        if rate is not None:
            payload["rate_per_s"] = round(rate, 3)
        if eta_seconds is not None:
            payload["eta_s"] = round(eta_seconds, 3)
        with progress_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        progress_status.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        with progress_lock:
            latest_progress.clear()
            latest_progress.update(payload)
        if total > 0:
            eta_text = "?"
            if eta_seconds is not None:
                eta_text = f"{eta_seconds:.1f}s"
            print(
                f"[{phase}] {current}/{total} ({pct:.1f}%) rate={rate:.1f}/s eta={eta_text} | {message}",
                flush=True,
            )
            return
        print(f"[{phase}] {message}", flush=True)

    def _heartbeat() -> None:
        last_fingerprint: tuple[object, ...] | None = None
        while not stop_event.wait(5.0):
            with progress_lock:
                snapshot = dict(latest_progress)
            fingerprint = (
                snapshot.get("phase"),
                snapshot.get("current"),
                snapshot.get("total"),
                snapshot.get("message"),
            )
            if fingerprint != last_fingerprint:
                last_fingerprint = fingerprint
                continue
            phase = str(snapshot.get("phase", "unknown"))
            current = int(snapshot.get("current", 0) or 0)
            total = int(snapshot.get("total", 0) or 0)
            elapsed = max(0.001, (datetime.now() - started).total_seconds())
            message = str(snapshot.get("message", ""))
            pct = snapshot.get("percent")
            rate = snapshot.get("rate_per_s")
            eta_s = snapshot.get("eta_s")
            if total > 0:
                pct_text = f"{float(pct):.1f}%" if pct is not None else "?"
                rate_text = f"{float(rate):.1f}/s" if rate is not None else "?"
                eta_text = f"{float(eta_s):.1f}s" if eta_s is not None else "?"
                print(
                    f"[heartbeat:{phase}] {current}/{total} ({pct_text}) elapsed={elapsed:.1f}s rate={rate_text} eta={eta_text} | {message}",
                    flush=True,
                )
            else:
                print(
                    f"[heartbeat:{phase}] elapsed={elapsed:.1f}s | {message}",
                    flush=True,
                )

    heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat_thread.start()

    if cpu_policy["applied"]:
        print(
            "[cpu_limit] policy={policy} cpu_count={cpu_count} thread_limit={thread_limit} "
            "torch_applied={torch_applied} yield_ms={yield_ms} yield_every={yield_every}".format(
                **cpu_policy
            ),
            flush=True,
        )
    print(
        f"[process_priority] mode={args.process_priority} applied={priority_applied}",
        flush=True,
    )

    try:
        result = service.run(config, progress_callback=_print_progress)
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=1.0)
    print(f"run_id={result.run_id}")
    print(f"source_type={result.source_type}")
    print(f"fidelity={result.fidelity}")
    print(f"sqlite_path={result.sqlite_path}")
    print(f"qdrant_location={result.qdrant_location}")
    print(f"message_count={result.message_count}")
    print(f"asset_count={result.asset_count}")
    print(f"chunk_set_count={result.chunk_set_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
