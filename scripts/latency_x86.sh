#!/usr/bin/env bash
# Routing latency on an x86-64 CPU (roadmap M10: the GTX 1650 rig; the GPU is not used).
#
# Before running, copy these from the Mac into the same paths in this checkout:
#   data/index/                     the full UK index (320 MB; the seal checks every byte)
#   results/raw/replays-100k.txt    the 100,000 replayed citations (6.8 MB)
# Then, from the repository root (Linux, WSL or Git Bash):
#   bash scripts/latency_x86.sh
# and bring back bench/results/latency-*-x86_64.json.
set -euo pipefail

machine="$(uv run python -c 'import platform; print(platform.machine().lower())')"
case "$machine" in
  x86_64 | amd64) ;;
  *) echo "This is $machine, not x86-64: run it on the rig." >&2; exit 1 ;;
esac

uv sync --locked
# The same batteries, index bytes, aliases and thresholds as the sealed Mac run:
uv run python -m eval.seal verify seals/battery-2026-09-29-v2.json
system="$(uv run python -c 'import platform; print(platform.system().lower())')"
uv run python -m bench.latency \
  --queries results/raw/replays-100k.txt --repeats 3 \
  --json "bench/results/latency-${system}-x86_64.json"
