#!/usr/bin/env bash
# The full M11 comparison on the VM, unattended: accuracy, determinism, latency, then the score.
#
#     tmux new -s compare 'bash scripts/compare_run.sh results/raw/compare 2>&1 | tee -a compare.log'
#
# Every pass resumes where it stopped, so rerunning this after any interruption only makes the
# calls still missing. It assumes the cost estimate is confirmed (the M11 halt point).
set -euo pipefail
dir="${1:?usage: compare_run.sh <results dir>}"
# Keys come from the environment (start this from an interactive shell, e.g. inside tmux, so
# ~/.bashrc has set them), or from ~/.lrr-keys if that file exists.
if [ -f "$HOME/.lrr-keys" ]; then
  # shellcheck disable=SC1091
  source "$HOME/.lrr-keys"
fi
: "${GEMINI_API_KEY:?GEMINI_API_KEY is not set}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is not set}"
export PATH="$HOME/.local/bin:$PATH"
for stage in accuracy determinism latency; do
  uv run python -m bench.compare run --dir "$dir" --pass "$stage" --confirmed
done
uv run python -m bench.compare score --dir "$dir"
