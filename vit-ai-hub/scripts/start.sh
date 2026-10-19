#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip -q install -r requirements.txt

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Laad secrets als aanwezig
if [[ -f "$HOME/.config/vit/geheimen/ai-gateway.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$HOME/.config/vit/geheimen/ai-gateway.env"
  set +a
elif [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

HOST="${VIT_GATEWAY_HOST:-127.0.0.1}"
PORT="${VIT_GATEWAY_PORT:-8787}"

echo "VIT AI Hub → http://${HOST}:${PORT}"
exec python -m uvicorn vit_ai_hub.main:app --host "$HOST" --port "$PORT"