"""Pytest collection boundary for the parent QQ exporter repository.

ORCH/Agent and Review Editor code now live in submodules. The parent repository
should only collect exporter/runtime tests; submodule tests run inside their own
repositories to avoid half-new/half-old package imports.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path


collect_ignore_glob = [
    "apps/*",
    "dev/archive/*",
    "NapCat/*",
    "NapCatQQ/*",
    "python_runtime/*",
    "runtime_site_packages/*",
    "state/*",
    "subrepos/*",
    "tests/domains/*",
    "tests/test_analysis_*.py",
    "tests/test_benshi_*.py",
    "tests/test_chat_orchestrator_*.py",
    "tests/test_chunk_policies.py",
    "tests/test_corpus_batch_suite.py",
    "tests/test_diagnostics.py",
    "tests/test_embedding_*.py",
    "tests/test_final_report_view.py",
    "tests/test_full_chain_profile_warnings.py",
    "tests/test_judgment_policy.py",
    "tests/test_llm_*.py",
    "tests/test_llm_session_*.py",
    "tests/test_local_corpora*.py",
    "tests/test_local_corpus_*.py",
    "tests/test_local_testdata_corpora.py",
    "tests/test_orch_*.py",
    "tests/test_preprocess_*.py",
    "tests/test_program_workbench_contract.py",
    "tests/test_rag_retrieval.py",
    "tests/test_relation_graph_assets.py",
    "tests/test_review_*.py",
    "tests/test_run_chat_orchestrator_script.py",
    "tests/test_run_review_editor_server.py",
    "tests/test_runtime_control.py",
]


def pytest_ignore_collect(collection_path: Path, config: object) -> bool:
    """Apply the same split-boundary ignore list on Windows and POSIX paths."""

    root = Path(__file__).resolve().parent
    try:
        rel = collection_path.resolve().relative_to(root).as_posix()
    except ValueError:
        rel = collection_path.as_posix()
    return any(fnmatch(rel, pattern) for pattern in collect_ignore_glob)
