#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.config/vit/geheimen"
if [[ ! -f "$HOME/.config/vit/geheimen/ai-gateway.env" ]]; then
  cp "$ROOT/.env.example" "$HOME/.config/vit/geheimen/ai-gateway.env"
  echo "Secrets template gezet: ~/.config/vit/geheimen/ai-gateway.env"
  echo "Vul OPENROUTER_API_KEY / bridge keys in, en optioneel VIT_GATEWAY_TOKEN."
fi
chmod +x "$ROOT/scripts/start.sh"
"$ROOT/scripts/start.sh"