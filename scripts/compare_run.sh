#!/usr/bin/env bash
# The full M11 comparison on the VM, unattended: accuracy, determinism, latency, then the score.
#
#     tmux new -s compare 'bash scripts/compare_run.sh results/raw/compare 2>&1 | tee -a compare.log'
#
# Every pass resumes where it stopped, so rerunning this after any interruption only makes the
# calls still missing. It assumes the cost estimate is confirmed (the M11 halt point).
set -euo pipefail
dir="${1:?usage: compare_run.sh <results dir>}"
# shellcheck disable=SC1090
source "$HOME/.lrr-keys"
export PATH="$HOME/.local/bin:$PATH"
for stage in accuracy determinism latency; do
  uv run python -m bench.compare run --dir "$dir" --pass "$stage" --confirmed
done
uv run python -m bench.compare score --dir "$dir"
