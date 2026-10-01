#!/usr/bin/env bash
# The rest of the M11 comparison, on the author's Mac (roadmap M11, 1 Oct 2026):
#
#   1. accuracy     Gemini end to end (2,112) and Gemini on the choice questions (6,150)
#   2. determinism  Gemini end to end, 200 rows x 5
#   3. latency      300 rows, one call at a time, interleaved: Gemini, Jev, the router in
#                   process, and Gemini's and Jev's floor calls. The router on Modal is left
#                   out (--no-service); its Row B was measured on 30 Sept.
#   4. score        -> results/raw/compare/summary.json
#
# Jev's accuracy and determinism are already in results/raw/compare (from the VM) and are not
# run again. Gemini goes only through the proxy (bench/clients/gemini_proxy.py).
#
# Before running:  export LRR_GEMINI_PROXY_KEY=...   (OPENROUTER_API_KEY is in your zsh profile)
# Run:             caffeinate -dims bash scripts/compare_local.sh
# Progress:        uv run python -m bench.compare status --dir results/raw/compare --no-service
#
# Safe to stop at any time (Ctrl-C, closing the terminal, sleep, a crash): every finished call
# is already on disk. Run the same command again and it carries on with the calls still missing.
# A rerun also retries every call that failed (a quota cooldown, say); the new answer supersedes
# the failure in every count, and the failed attempt stays in the file as history.
# Workers: LRR_WORKERS (default 4) for accuracy and determinism; latency is one call at a time.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${LRR_GEMINI_PROXY_KEY:?export LRR_GEMINI_PROXY_KEY first}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is not set}"
default_region="the author's Mac, Pakistan"
export LRR_CLIENT_REGION="${LRR_CLIENT_REGION:-$default_region}"
dir=results/raw/compare
workers="${LRR_WORKERS:-4}"

uv run python -m bench.compare run --dir "$dir" --pass accuracy \
  --systems gemini_route gemini_choice --workers "$workers" --confirmed
uv run python -m bench.compare run --dir "$dir" --pass determinism \
  --systems gemini_route --workers "$workers" --confirmed
uv run python -m bench.compare run --dir "$dir" --pass latency --no-service --confirmed
uv run python -m bench.compare score --dir "$dir"
echo "COMPARISON FINISHED $(date -u +%FT%TZ)"
