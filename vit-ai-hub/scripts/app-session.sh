#!/usr/bin/env bash
# App-sessie: start hub bij openen; mooie GUI-venster; herstart hub als die crasht; stop bij Cmd+Q.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${VIT_LAN_ACCESS:-0}" == "1" ]] || [[ "${VIT_LAN_ACCESS:-}" == "true" ]]; then
  BIND_HOST="${VIT_GATEWAY_HOST:-0.0.0.0}"
else
  BIND_HOST="${VIT_GATEWAY_HOST:-127.0.0.1}"
fi
UI_HOST="127.0.0.1"
PORT="${VIT_GATEWAY_PORT:-8787}"
SECRET_DIR="$HOME/.config/vit/geheimen"
SECRET_FILE="$SECRET_DIR/ai-gateway.env"
LOG_DIR="$HOME/Library/Logs/VIT-AI-Hub"
PID_DIR="$ROOT/data/run"
HUB_PID_FILE="$PID_DIR/hub.pid"
SESSION_PID_FILE="$PID_DIR/session.pid"
SETUP_MARKER="$ROOT/data/.setup-complete"

mkdir -p "$SECRET_DIR" "$LOG_DIR" "$PID_DIR" "$ROOT/data"
echo $$ >"$SESSION_PID_FILE"

STARTED_BY_US=0
cleanup() {
  echo "==> VIT AI Hub afsluiten…"
  if [[ "$STARTED_BY_US" == "1" ]]; then
    if [[ -f "$HUB_PID_FILE" ]]; then
      HUB_PID="$(cat "$HUB_PID_FILE" 2>/dev/null || true)"
      if [[ -n "${HUB_PID}" ]] && kill -0 "$HUB_PID" 2>/dev/null; then
        kill "$HUB_PID" 2>/dev/null || true
        for _ in 1 2 3 4 5 6 7 8; do
          kill -0 "$HUB_PID" 2>/dev/null || break
          sleep 0.25
        done
        kill -9 "$HUB_PID" 2>/dev/null || true
      fi
    fi
    if command -v lsof >/dev/null 2>&1; then
      for p in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
        kill "$p" 2>/dev/null || true
      done
    fi
  fi
  rm -f "$HUB_PID_FILE" "$SESSION_PID_FILE"
}
trap cleanup EXIT INT TERM

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
chmod 600 "$SECRET_FILE" 2>/dev/null || true
chmod +x "$ROOT/scripts/"*.sh 2>/dev/null || true

open_splash_soon() {
  local next_q="%2F"
  if [[ ! -f "$SETUP_MARKER" ]]; then
    next_q="%2F%3Fwizard%3D1"
  fi
  (
    for _ in $(seq 1 120); do
      if curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
        bash "$ROOT/scripts/open-gui.sh" \
          "http://${UI_HOST}:${PORT}/static/splash.html?next=${next_q}"
        exit 0
      fi
      sleep 0.25
    done
  ) &
  SPLASH_PID=$!
}

start_hub() {
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
  export VIT_GATEWAY_HOST="$BIND_HOST"
  set -a
  # shellcheck disable=SC1090
  source "$SECRET_FILE"
  set +a
  export VIT_GATEWAY_HOST="$BIND_HOST"

  # Start uvicorn direct (betrouwbaarder PID dan geneste bash)
  nohup python -m uvicorn vit_ai_hub.main:app --host "$BIND_HOST" --port "$PORT" \
    >>"$LOG_DIR/app-session.log" 2>&1 &
  echo $! >"$HUB_PID_FILE"
  STARTED_BY_US=1

  for _ in $(seq 1 90); do
    if curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

# venv
if [[ ! -d "$ROOT/.venv" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    osascript -e 'display notification "Eerste keer: Python-omgeving wordt gezet…" with title "VIT AI Hub"' 2>/dev/null || true
  fi
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip -q install --upgrade pip
pip -q install -r "$ROOT/requirements.txt"

ALREADY_UP=0
if curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
  ALREADY_UP=1
else
  open_splash_soon
  if ! start_hub; then
    osascript -e 'display dialog "VIT AI Hub startte niet.\nZie ~/Library/Logs/VIT-AI-Hub/app-session.log" buttons {"OK"} default button 1' 2>/dev/null || true
    exit 1
  fi
fi

if [[ ! -f "$SETUP_MARKER" ]]; then
  curl -sf -X POST "http://${UI_HOST}:${PORT}/api/setup/install-auto" \
    -H "Content-Type: application/json" \
    -d '{"open_a11y":false,"mark_complete":false}' >/dev/null 2>&1 || true
  NEXT="http://${UI_HOST}:${PORT}/?wizard=1"
else
  NEXT="http://${UI_HOST}:${PORT}/"
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  osascript -e 'display notification "Hub draait — sluit de app (Cmd+Q) om te stoppen" with title "VIT AI Hub"' 2>/dev/null || true
  if [[ "$ALREADY_UP" == "1" ]] || ! kill -0 "${SPLASH_PID:-0}" 2>/dev/null; then
    bash "$ROOT/scripts/open-gui.sh" "$NEXT"
  fi
fi

# Blijf leven; herstart hub automatisch als die crasht (tot .app quit)
while true; do
  sleep 2
  if [[ "$(uname -s)" == "Darwin" ]] && [[ -n "${PPID:-}" ]]; then
    if ! kill -0 "$PPID" 2>/dev/null; then
      break
    fi
  fi
  if ! curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
    echo "==> hub weg — herstarten…" >>"$LOG_DIR/app-session.log"
    start_hub || true
  fi
done
