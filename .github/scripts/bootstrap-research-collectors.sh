#!/usr/bin/env bash
set -euo pipefail

echo "Bootstrapping hosted source collectors"

python -m pip install --upgrade pip
python -m pip install yt-dlp >/dev/null

if command -v npm >/dev/null 2>&1; then
  npm install -g @mcporter/cli >/dev/null 2>&1 || npm install -g mcporter >/dev/null 2>&1 || true
  npm install -g twitter-cli >/dev/null 2>&1 || true
fi

python -m pip install rdt-cli >/dev/null 2>&1 || python -m pip install rdt >/dev/null 2>&1 || true

if [[ -n "${RESEARCH_INSTALL_REDDIT_CMD:-}" ]]; then
  bash -lc "${RESEARCH_INSTALL_REDDIT_CMD}"
fi

if [[ -n "${RESEARCH_INSTALL_TWITTER_CMD:-}" ]]; then
  bash -lc "${RESEARCH_INSTALL_TWITTER_CMD}"
fi

echo "Collector availability:"
for command_name in mcporter rdt yt-dlp twitter; do
  if command -v "${command_name}" >/dev/null 2>&1; then
    echo "  - ${command_name}: available"
  else
    echo "  - ${command_name}: missing"
  fi
done
