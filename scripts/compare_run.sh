#!/usr/bin/env bash
# Reproduce the M11 comparison (reports/comparison-uk.md): accuracy, determinism, latency, score.
#
# Needs:
#   GEMINI_API_KEY      a Google AI Studio key on a paid-tier project (the free tier allows only
#                       20 requests a day per model; the run makes about 9,500 Gemini calls)
#   OPENROUTER_API_KEY  for Jev (typesafe/jev-1.13), about $0.30 of credit
#   data/index          the UK index the battery seal pins (uv run python -m eval.seal verify ...)
# Optional:
#   LRR_WORKERS         calls at a time for accuracy and determinism (default 4; latency is 1)
#   LRR_CLIENT_REGION   where this client runs, recorded in the manifest
#   LRR_ROW_B=1         also time the router as a Modal service in the latency pass; then set
#                       MODAL_ROUTER_URL, MODAL_KEY and MODAL_SECRET (deploy/modal_router.py)
#
#   caffeinate -dims bash scripts/compare_run.sh results/raw/compare     # macOS: stay awake
#   uv run python -m bench.compare status --dir results/raw/compare --no-service
#
# Safe to stop at any time: every finished call is on disk, and rerunning the same command makes
# only the calls still missing, retrying any that failed. Expect about $38 of Gemini at
# Google's promotional list price ($76 regular) and several hours at 4 workers.
set -euo pipefail
dir="${1:?usage: compare_run.sh <results dir>}"
cd "$(dirname "$0")/.."
: "${GEMINI_API_KEY:?GEMINI_API_KEY is not set}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is not set}"
workers="${LRR_WORKERS:-4}"
service=(--no-service)
if [ "${LRR_ROW_B:-0}" = "1" ]; then
  service=()
fi

uv run python -m eval.seal verify seals/battery-2026-09-29-v2.json
uv run python -m bench.compare run --dir "$dir" --pass accuracy --workers "$workers" --confirmed
uv run python -m bench.compare run --dir "$dir" --pass determinism --workers "$workers" --confirmed
uv run python -m bench.compare run --dir "$dir" --pass latency "${service[@]}" --confirmed
uv run python -m bench.compare score --dir "$dir"
echo "COMPARISON FINISHED $(date -u +%FT%TZ)"
