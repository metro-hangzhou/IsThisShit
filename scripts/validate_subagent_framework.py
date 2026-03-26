from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

TRACKS = (
    "downloader_decision_surface",
    "provider_history_surface",
    "filesystem_materialization_surface",
    "speech_output_surface",
    "forward_recursive_surface",
    "coverage_reachability_surface",
    "napcat_truth_map_surface",
)

REQUIRED_OUTPUT_HEADINGS = (
    "# Dimensions",
    "# Reachability Rules",
    "# Already Modeled",
    "# Missing / Partial",
    "# Recommended Simulator Families",
    "# Concrete File Refs",
)

REQUIRED_NOTES_KEYS = {
    "track",
    "status",
    "missing_truth_source",
    "next_action",
}

REVIEWER_REQUIRED_KEYS = {
    "round",
    "status",
    "blockers",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _check_track(track: str, errors: list[str]) -> None:
    agent_path = ROOT / "dev" / "agents" / "subagents" / f"AGENTs.{track}.md"
    todo_path = ROOT / "dev" / "todos" / "subagents" / f"TODOs.{track}.md"
    state_dir = ROOT / "state" / "subagent_runs" / track
    input_path = state_dir / "input.md"
    output_path = state_dir / "output.md"
    notes_path = state_dir / "notes.json"

    for path in (agent_path, todo_path, input_path, output_path, notes_path):
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if output_path.exists():
        text = _read_text(output_path)
        for heading in REQUIRED_OUTPUT_HEADINGS:
            if heading not in text:
                errors.append(f"{output_path} missing heading: {heading}")

    if notes_path.exists():
        raw = _load_json(notes_path)
        if not isinstance(raw, dict):
            errors.append(f"{notes_path} is not a JSON object")
        else:
            missing = REQUIRED_NOTES_KEYS.difference(raw.keys())
            if missing:
                errors.append(f"{notes_path} missing keys: {sorted(missing)}")


def _check_reviewer(errors: list[str]) -> None:
    reviewer_agent = ROOT / "dev" / "agents" / "subagents" / "AGENTs.first-principles-reviewer.md"
    reviewer_todo = ROOT / "dev" / "todos" / "subagents" / "TODOs.first-principles-reviewer.md"
    round_dir = ROOT / "state" / "reviewer_runs" / "round_001"
    review_input = round_dir / "review_input.md"
    review_questions = round_dir / "review_questions.md"
    review_blockers = round_dir / "review_blockers.json"
    review_resolution = round_dir / "review_resolution.md"

    for path in (
        reviewer_agent,
        reviewer_todo,
        review_input,
        review_questions,
        review_blockers,
        review_resolution,
    ):
        if not path.exists():
            errors.append(f"missing required reviewer file: {path}")

    if review_blockers.exists():
        raw = _load_json(review_blockers)
        if not isinstance(raw, dict):
            errors.append(f"{review_blockers} is not a JSON object")
        else:
            missing = REVIEWER_REQUIRED_KEYS.difference(raw.keys())
            if missing:
                errors.append(f"{review_blockers} missing keys: {sorted(missing)}")
            blockers = raw.get("blockers")
            if not isinstance(blockers, list):
                errors.append(f"{review_blockers} field 'blockers' must be a list")


def main() -> int:
    errors: list[str] = []
    for track in TRACKS:
        _check_track(track, errors)
    _check_reviewer(errors)

    if errors:
        print("SUBAGENT_FRAMEWORK_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("SUBAGENT_FRAMEWORK_VALID")
    print(f"tracks={len(TRACKS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
