from __future__ import annotations

import argparse
import json
from pathlib import Path

from qq_data_process import RagService
from qq_data_process.rag_models import RetrievalConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run hybrid retrieval over a preprocessed QQ chat state."
    )
    parser.add_argument("query_text", help="Natural-language retrieval query")
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        required=True,
        help="Path to the preprocessing SQLite database",
    )
    parser.add_argument(
        "--qdrant-path",
        type=Path,
        required=True,
        help="Path to the local Qdrant store",
    )
    parser.add_argument("--run-id", default=None, help="Optional import run scope")
    parser.add_argument("--chat-id-raw", default=None)
    parser.add_argument("--chat-alias-id", default=None)
    parser.add_argument("--start-timestamp-ms", type=int, default=None)
    parser.add_argument("--end-timestamp-ms", type=int, default=None)
    parser.add_argument("--keyword-top-k", type=int, default=8)
    parser.add_argument("--vector-top-k", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--projection-mode", choices=["alias", "raw"], default="alias")
    parser.add_argument(
        "--danger-allow-raw-identity-output",
        action="store_true",
        help="Required when projection-mode=raw",
    )
    parser.add_argument("--context-window-before", type=int, default=2)
    parser.add_argument("--context-window-after", type=int, default=2)
    parser.add_argument("--max-context-blocks", type=int, default=6)
    parser.add_argument("--max-messages-per-block", type=int, default=24)
    parser.add_argument(
        "--no-chunk-context",
        action="store_true",
        help="Disable chunk-based context expansion and use message windows only",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="After retrieval, call DeepSeek for a grounded answer",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = RetrievalConfig(
        query_text=args.query_text,
        run_id=args.run_id,
        chat_id_raw=args.chat_id_raw,
        chat_alias_id=args.chat_alias_id,
        start_timestamp_ms=args.start_timestamp_ms,
        end_timestamp_ms=args.end_timestamp_ms,
        keyword_top_k=args.keyword_top_k,
        vector_top_k=args.vector_top_k,
        top_k=args.top_k,
        projection_mode=args.projection_mode,
        prefer_chunk_context=not args.no_chunk_context,
        context_window_before=args.context_window_before,
        context_window_after=args.context_window_after,
        max_context_blocks=args.max_context_blocks,
        max_messages_per_block=args.max_messages_per_block,
        danger_allow_raw_identity_output=args.danger_allow_raw_identity_output,
    )

    service = RagService.from_state(
        sqlite_path=args.sqlite_path,
        qdrant_path=args.qdrant_path,
        run_id=args.run_id,
    )
    try:
        if args.generate:
            answer = service.answer(config=config)
            print(json.dumps(answer.model_dump(mode="json"), ensure_ascii=False, indent=2))
        else:
            retrieval = service.retrieve(config)
            print(
                json.dumps(
                    retrieval.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
