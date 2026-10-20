#!/usr/bin/env bash
# Schrijf Continue.dev config → VIT AI Hub (pad om Cursor op te zeggen).
set -euo pipefail
HOST="${VIT_GATEWAY_HOST:-127.0.0.1}"
PORT="${VIT_GATEWAY_PORT:-8787}"
curl -sf -X POST "http://${HOST}:${PORT}/api/workspace/export-continue" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
echo
echo "Installeer daarna: VS Code/Zed + Continue-extensie → model VIT AI Hub (auto)."
