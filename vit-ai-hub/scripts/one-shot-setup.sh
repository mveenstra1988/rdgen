#!/usr/bin/env bash
# Één keer draaien op de Mac: alles installeren, starten, browser openen.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HOST="${VIT_GATEWAY_HOST:-127.0.0.1}"
PORT="${VIT_GATEWAY_PORT:-8787}"
SECRET_DIR="$HOME/.config/vit/geheimen"
SECRET_FILE="$SECRET_DIR/ai-gateway.env"
LAUNCH_AGENT="$HOME/Library/LaunchAgents/nl.veenstra-it.aihub.plist"
LOG_DIR="$HOME/Library/Logs/VIT-AI-Hub"
DATA_MARKER="$ROOT/data/.setup-complete"

echo "==> VIT AI Hub one-shot setup"
echo "    root: $ROOT"

mkdir -p "$SECRET_DIR" "$LOG_DIR" "$ROOT/data" "$HOME/Library/LaunchAgents"

if [[ ! -f "$SECRET_FILE" ]]; then
  cp "$ROOT/.env.example" "$SECRET_FILE"
  # generate local token
  if command -v openssl >/dev/null 2>&1; then
    TOKEN="vit-$(openssl rand -hex 12)"
  else
    TOKEN="vit-$(date +%s)"
  fi
  if grep -q '^VIT_GATEWAY_TOKEN=' "$SECRET_FILE"; then
    sed -i.bak "s/^VIT_GATEWAY_TOKEN=.*/VIT_GATEWAY_TOKEN=${TOKEN}/" "$SECRET_FILE" && rm -f "$SECRET_FILE.bak"
  else
    echo "VIT_GATEWAY_TOKEN=${TOKEN}" >>"$SECRET_FILE"
  fi
  echo "    secrets: $SECRET_FILE (nieuwe token gezet)"
else
  echo "    secrets: bestaat al"
fi

chmod +x "$ROOT/scripts/"*.sh "$ROOT/scripts/"*.py 2>/dev/null || true

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "    python venv aanmaken…"
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip -q install --upgrade pip
pip -q install -r "$ROOT/requirements.txt"
echo "    dependencies OK"

# Standaard: géén KeepAlive LaunchAgent — de .app start/stopt de hub.
# Opt-in: VIT_INSTALL_LAUNCH_AGENT=1 voor login-autostart.
if [[ "${VIT_INSTALL_LAUNCH_AGENT:-0}" == "1" ]]; then
  cat >"$LAUNCH_AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>nl.veenstra-it.aihub</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${ROOT}/scripts/start.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>WorkingDirectory</key><string>${ROOT}</string>
  <key>StandardOutPath</key><string>${LOG_DIR}/stdout.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
PLIST
  if [[ "$(uname -s)" == "Darwin" ]]; then
    launchctl bootout "gui/$(id -u)/nl.veenstra-it.aihub" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENT" 2>/dev/null || launchctl load -w "$LAUNCH_AGENT" 2>/dev/null || true
    echo "    LaunchAgent geladen (opt-in login start)"
  fi
else
  if [[ "$(uname -s)" == "Darwin" ]]; then
    launchctl bootout "gui/$(id -u)/nl.veenstra-it.aihub" 2>/dev/null || true
  fi
  echo "    sessie-modus: .app start/stopt hub (geen login KeepAlive)"
fi

# Start nu op de voorgrond-detached als nog niet up
if ! curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  echo "    gateway starten…"
  nohup bash "$ROOT/scripts/start.sh" >"$LOG_DIR/oneshot.log" 2>&1 &
  for i in $(seq 1 40); do
    if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
fi

if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  echo "    gateway online → http://${HOST}:${PORT}"
  FIRST_RUN=0
  if [[ ! -f "$DATA_MARKER" ]]; then
    FIRST_RUN=1
    echo "    eerste install-auto (bridge + migratie + Cursor)…"
    curl -sf -X POST "http://${HOST}:${PORT}/api/setup/install-auto" \
      -H "Content-Type: application/json" \
      -d '{"open_a11y":false,"mark_complete":false}' >/dev/null 2>&1 || \
    curl -sf -X POST "http://${HOST}:${PORT}/api/setup/bootstrap" \
      -H "Content-Type: application/json" \
      -d '{"open_a11y":false}' >/dev/null 2>&1 || true
  else
    TOKEN="$(grep -E '^VIT_GATEWAY_TOKEN=' "$SECRET_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
    AUTH=()
    if [[ -n "${TOKEN}" && "${TOKEN}" != *"change-me"* ]]; then
      AUTH=(-H "Authorization: Bearer ${TOKEN}")
    fi
    curl -sf -X POST "http://${HOST}:${PORT}/api/sync/once" "${AUTH[@]}" >/dev/null 2>&1 || true
    curl -sf -X POST "http://${HOST}:${PORT}/api/sync/start?interval_sec=300" "${AUTH[@]}" >/dev/null 2>&1 || true
  fi
  date >"$DATA_MARKER"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ "$FIRST_RUN" == "1" ]]; then
      open "http://${HOST}:${PORT}/?wizard=1"
    else
      open "http://${HOST}:${PORT}/"
    fi
  fi
  echo "==> Klaar. Wizard/GUI opent in de browser."
else
  echo "==> Gateway startte niet. Logs: $LOG_DIR/oneshot.log" >&2
  exit 1
fi
