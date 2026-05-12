#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/mnt/d/Coding_Project/IsThisShit"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.5}"
CODEX_REASONING_EFFORT="${CODEX_REASONING_EFFORT:-xhigh}"

cd "$REPO_ROOT"

# Use this launcher for Windows interop / desktop localhost debugging:
# - calling cmd.exe, powershell.exe, or .venv/Scripts/python.exe from WSL
# - talking to the Tauri review-editor API on 127.0.0.1:43127
#
# Default keeps approval prompts but avoids the workspace-write bwrap sandbox.
# If WSL interop still fails, run:
#   CODEX_INTEROP_BYPASS=1 ./start_codex_wsl_interop.sh
if [[ "${CODEX_INTEROP_BYPASS:-0}" == "1" ]]; then
  exec codex resume --last \
    -C "$REPO_ROOT" \
    -m "$CODEX_MODEL" \
    -c "model_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
    -c "plan_mode_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
    --dangerously-bypass-approvals-and-sandbox \
    "$@"
fi

exec codex resume --last \
  -C "$REPO_ROOT" \
  -m "$CODEX_MODEL" \
  -c "model_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
  -c "plan_mode_reasoning_effort=\"$CODEX_REASONING_EFFORT\"" \
  -a on-request \
  -s danger-full-access \
  "$@"
