#!/usr/bin/env bash
# Claude/ChatGPT abo-bridge helper (CLIProxyAPI-achtig) op :8317
set -euo pipefail
echo "==> VIT bridge helper"
echo "    Doel: lokale OAuth-bridge zodat Claude/ChatGPT-abo via de hub werkt."
echo
if command -v brew >/dev/null 2>&1; then
  echo "Optie: zoek een bridge zoals CLIProxyAPI / omniroute-bridge."
fi
echo "Documentatie openen…"
if [[ "$(uname -s)" == "Darwin" ]]; then
  open "https://github.com/router-for-me/CLIProxyAPI" || true
fi
SECRET="$HOME/.config/vit/geheimen/ai-gateway.env"
mkdir -p "$(dirname "$SECRET")"
if [[ -f "$SECRET" ]]; then
  if ! grep -q '^BRIDGE_BASE_URL=' "$SECRET"; then
    echo "BRIDGE_BASE_URL=http://127.0.0.1:8317/v1" >>"$SECRET"
  fi
  echo "    BRIDGE_BASE_URL gezet/gecontroleerd in $SECRET"
fi
echo "Na installatie van de bridge: log één keer in (Claude/ChatGPT OAuth),"
echo "start de hub opnieuw, kies Claude/GPT-modellen in de picker."
