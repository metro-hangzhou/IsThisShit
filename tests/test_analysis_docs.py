from __future__ import annotations

from pathlib import Path


def test_analysis_docs_exist_and_are_routed_from_main_docs() -> None:
    major = Path("major_AGENTs.md")
    process = Path("process_AGENTs.md")
    rag = Path("TODOs.rag.md")
    todo = Path("TODOs.analysis-agents.md")

    assert major.exists()
    assert process.exists()
    assert rag.exists()
    assert todo.exists()

    major_text = major.read_text(encoding="utf-8")
    process_text = process.read_text(encoding="utf-8")
    rag_text = rag.read_text(encoding="utf-8")
    todo_text = todo.read_text(encoding="utf-8")

    assert "pluggable analysis agents" in major_text
    assert "analysis substrate" in process_text
    assert "internal evidence services for analysis agents" in rag_text
    assert "Analysis Agent TODOs" in todo_text


def test_qq_data_analysis_does_not_import_cli_ui_or_napcat_modules() -> None:
    analysis_root = Path("src/qq_data_analysis")
    for path in analysis_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "qq_data_cli" not in text
        assert "prompt_toolkit" not in text
        assert "napcat" not in text.lower()
