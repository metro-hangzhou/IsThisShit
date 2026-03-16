from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from qq_data_process import RagService
from qq_data_process.rag_models import RetrievalConfig, RetrievalResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview current RAG retrieval quality in a human-readable format."
    )
    parser.add_argument("query_text", help="Natural-language query")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Preprocess state directory containing db/analysis.db and qdrant/",
    )
    parser.add_argument("--sqlite-path", type=Path, default=None)
    parser.add_argument("--qdrant-path", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--keyword-top-k", type=int, default=5)
    parser.add_argument("--vector-top-k", type=int, default=5)
    parser.add_argument(
        "--max-context-blocks",
        type=int,
        default=3,
        help="Maximum context blocks to render per mode",
    )
    parser.add_argument(
        "--no-compare",
        action="store_true",
        help="Show only the hybrid result instead of hybrid/keyword/vector comparison",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.state_dir is not None:
        return args.state_dir / "db" / "analysis.db", args.state_dir / "qdrant"
    if args.sqlite_path is None or args.qdrant_path is None:
        raise SystemExit("Provide either --state-dir or both --sqlite-path and --qdrant-path.")
    return args.sqlite_path, args.qdrant_path


def make_config(
    *,
    query_text: str,
    args: argparse.Namespace,
    keyword_top_k: int,
    vector_top_k: int,
) -> RetrievalConfig:
    return RetrievalConfig(
        query_text=query_text,
        run_id=args.run_id,
        top_k=args.top_k,
        keyword_top_k=keyword_top_k,
        vector_top_k=vector_top_k,
        max_context_blocks=args.max_context_blocks,
    )


def render_result(console: Console, *, title: str, result: RetrievalResult) -> None:
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
    table.add_column("Source", style="magenta", no_wrap=True)
    table.add_column("Score", justify="right", style="green", no_wrap=True)
    table.add_column("Time", style="blue", no_wrap=True)
    table.add_column("Sender", style="yellow", no_wrap=True)
    table.add_column("Content", style="white")

    for index, hit in enumerate(result.hits, start=1):
        table.add_row(
            str(index),
            "/".join(hit.match_sources),
            f"{hit.fused_score:.4f}",
            hit.timestamp_iso[11:19],
            hit.sender_name or hit.sender_id,
            hit.content,
        )
    console.print(table)

    if not result.context_blocks:
        console.print("[dim]No context blocks generated.[/dim]")
        return

    for index, block in enumerate(result.context_blocks, start=1):
        console.print(
            Panel(
                block.rendered_text,
                title=(
                    f"{title} Context {index} | {block.source_kind} | "
                    f"anchor={block.anchor_message_uid}"
                ),
                expand=False,
            )
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    sqlite_path, qdrant_path = resolve_paths(args)

    console = Console()
    console.print(
        Rule(
            title=(
                f"RAG Preview | query={args.query_text} | "
                f"sqlite={sqlite_path} | qdrant={qdrant_path}"
            )
        )
    )

    service = RagService.from_state(
        sqlite_path=sqlite_path,
        qdrant_path=qdrant_path,
        run_id=args.run_id,
    )
    try:
        modes = [
            ("Hybrid", args.keyword_top_k, args.vector_top_k),
        ]
        if not args.no_compare:
            modes.extend(
                [
                    ("Keyword Only", args.keyword_top_k, 0),
                    ("Vector Only", 0, args.vector_top_k),
                ]
            )

        for title, keyword_top_k, vector_top_k in modes:
            result = service.retrieve(
                make_config(
                    query_text=args.query_text,
                    args=args,
                    keyword_top_k=keyword_top_k,
                    vector_top_k=vector_top_k,
                )
            )
            render_result(console, title=title, result=result)
            console.print()
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
