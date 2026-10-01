#!/usr/bin/env bash
# Prepare an Ubuntu VM for the M11 comparison (roadmap M11; the Azure client, 1 Oct 2026).
#
# Copy lrr.bundle (git bundle of main) and lrr-data.tgz (data/index) to the VM's home
# directory first, then run this there: bash setup.sh
# The API keys are not handled here: they go in ~/.lrr-keys (mode 600), written from the Mac.
set -euo pipefail
cd "$HOME"
# A 2 GB swap file as a backstop, so a memory peak slows the run instead of stopping it.
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap -q /swapfile
  sudo swapon /swapfile
fi
sudo apt-get update -qq
sudo apt-get install -y -qq git tmux
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
git config --global core.autocrlf false
if [ -d legal-rag-router ]; then
  git -C legal-rag-router pull -q ../lrr.bundle main
else
  git clone -q lrr.bundle legal-rag-router
fi
cd legal-rag-router
tar -xzf ../lrr-data.tgz
uv sync --locked
# The same batteries, index bytes, aliases and thresholds as the sealed run:
uv run python -m eval.seal verify seals/battery-2026-09-29-v2.json
git log --oneline -1
