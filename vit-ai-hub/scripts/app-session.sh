#!/usr/bin/env bash
# App-sessie: start hub (+ optioneel sync) bij openen; stop alles bij afsluiten.
# Gebruikt door VIT AI Hub.app — geen losse tools nodig.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HOST="${VIT_GATEWAY_HOST:-127.0.0.1}"
PORT="${VIT_GATEWAY_PORT:-8787}"
SECRET_DIR="$HOME/.config/vit/geheimen"
SECRET_FILE="$SECRET_DIR/ai-gateway.env"
LOG_DIR="$HOME/Library/Logs/VIT-AI-Hub"
PID_DIR="$ROOT/data/run"
HUB_PID_FILE="$PID_DIR/hub.pid"
SESSION_PID_FILE="$PID_DIR/session.pid"
DATA_MARKER="$ROOT/data/.setup-complete"

mkdir -p "$SECRET_DIR" "$LOG_DIR" "$PID_DIR" "$ROOT/data"
echo $$ >"$SESSION_PID_FILE"

STARTED_BY_US=0
cleanup() {
  echo "==> VIT AI Hub afsluiten…"
  if [[ "$STARTED_BY_US" == "1" ]] && [[ -f "$HUB_PID_FILE" ]]; then
    HUB_PID="$(cat "$HUB_PID_FILE" 2>/dev/null || true)"
    if [[ -n "${HUB_PID}" ]] && kill -0 "$HUB_PID" 2>/dev/null; then
      kill "$HUB_PID" 2>/dev/null || true
      for _ in 1 2 3 4 5 6 7 8; do
        kill -0 "$HUB_PID" 2>/dev/null || break
        sleep 0.25
      done
      kill -9 "$HUB_PID" 2>/dev/null || true
    fi
    # Alleen poort legen als wij startten
    if command -v lsof >/dev/null 2>&1; then
      for p in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
        kill "$p" 2>/dev/null || true
      done
    fi
  fi
  rm -f "$HUB_PID_FILE" "$SESSION_PID_FILE"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    launchctl bootout "gui/$(id -u)/nl.veenstra-it.aihub" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Secrets
if [[ ! -f "$SECRET_FILE" ]]; then
  cp "$ROOT/.env.example" "$SECRET_FILE"
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
fi

chmod +x "$ROOT/scripts/"*.sh 2>/dev/null || true

# venv
if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip -q install --upgrade pip
pip -q install -r "$ROOT/requirements.txt"

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
set -a
# shellcheck disable=SC1090
source "$SECRET_FILE"
set +a

ALREADY_UP=0
if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  ALREADY_UP=1
else
  STARTED_BY_US=1
  nohup bash "$ROOT/scripts/start.sh" >"$LOG_DIR/app-session.log" 2>&1 &
  echo $! >"$HUB_PID_FILE"
  for _ in $(seq 1 60); do
    if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
fi

if ! curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  osascript -e 'display dialog "VIT AI Hub startte niet.\nZie ~/Library/Logs/VIT-AI-Hub/app-session.log" buttons {"OK"} default button 1' 2>/dev/null || true
  exit 1
fi

FIRST=0
if [[ ! -f "$DATA_MARKER" ]]; then
  FIRST=1
  curl -sf -X POST "http://${HOST}:${PORT}/api/setup/bootstrap" \
    -H "Content-Type: application/json" \
    -d '{"open_a11y":false}' >/dev/null 2>&1 || true
fi
date >"$DATA_MARKER"

if [[ "$(uname -s)" == "Darwin" ]]; then
  osascript -e 'display notification "Hub draait — sluit de app om te stoppen" with title "VIT AI Hub"' 2>/dev/null || true
  if [[ "$FIRST" == "1" ]]; then
    open "http://${HOST}:${PORT}/?wizard=1"
  else
    open "http://${HOST}:${PORT}/"
  fi
fi

# Blijf leven tot de .app wordt afgesloten (Dock Quit / Cmd+Q)
# Heartbeat: als poort wegvalt en wij hem startten, exit
while true; do
  sleep 2
  if [[ "$ALREADY_UP" == "0" ]]; then
    if [[ -f "$HUB_PID_FILE" ]]; then
      HUB_PID="$(cat "$HUB_PID_FILE" 2>/dev/null || true)"
      if [[ -n "${HUB_PID}" ]] && ! kill -0 "$HUB_PID" 2>/dev/null; then
        break
      fi
    fi
  fi
  # macOS: als parent (.app) dood is, stop — launchd/open houdt ons soms los
  if [[ "$(uname -s)" == "Darwin" ]] && [[ -n "${PPID:-}" ]]; then
    if ! kill -0 "$PPID" 2>/dev/null; then
      break
    fi
  fi
done
