#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/mnt/d/Coding_Project/IsThisShit"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.5}"
CODEX_REASONING_EFFORT="${CODEX_REASONING_EFFORT:-xhigh}"

cd "$REPO_ROOT"
exec codex resume --last \
  -C "$REPO_ROOT" \
  -m "$CODEX_MODEL" \
  -c "model_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
  -c "plan_mode_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
  -a never \
  -s workspace-write \
  "$@"
