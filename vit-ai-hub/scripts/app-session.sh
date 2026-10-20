#!/usr/bin/env bash
# App-sessie: snelle start, GUI, duidelijke fouten, auto-herstart.
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
DEPS_MARKER="$ROOT/data/.deps-ok"
REQ_FILE="$ROOT/requirements.txt"
LOG_FILE="$LOG_DIR/app-session.log"

mkdir -p "$SECRET_DIR" "$LOG_DIR" "$PID_DIR" "$ROOT/data"
echo $$ >"$SESSION_PID_FILE"
: >>"$LOG_FILE"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

fail_dialog() {
  local msg="$1"
  local tail
  tail="$(tail -n 20 "$LOG_FILE" 2>/dev/null | sed 's/"/\\"/g' | tr '\n' '|' | sed 's/|/\\n/g')"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    osascript -e "display dialog \"${msg}\\n\\nLaatste log:\\n${tail}\" buttons {\"OK\"} default button 1 with title \"VIT AI Hub\"" 2>/dev/null || true
  fi
  log "FAIL: $msg"
  exit 1
}

STARTED_BY_US=0
cleanup() {
  log "afsluiten…"
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

# Beste Python kiezen (Homebrew 3.12/3.11 vóór Xcode 3.9)
pick_python() {
  local c
  for c in \
    /opt/homebrew/bin/python3.12 \
    /usr/local/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /usr/local/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /usr/local/bin/python3.10 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    python3.12 python3.11 python3.10 python3
  do
    if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then
      if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
        echo "$c"
        return 0
      fi
    fi
  done
  return 1
}
PYTHON_BIN="$(pick_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  fail_dialog "Geen Python ≥3.9 gevonden.\\nInstalleer: brew install python@3.12\\nof: xcode-select --install"
fi
PYVER="$("$PYTHON_BIN" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "0.0")"
log "python=$PYTHON_BIN ($PYVER) root=$ROOT"

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

req_hash() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$REQ_FILE" 2>/dev/null | awk '{print $1}'
  else
    cksum "$REQ_FILE" 2>/dev/null | awk '{print $1}'
  fi
}

ensure_deps() {
  local need=0 h
  h="$(req_hash)"
  # Oude venv op Python 3.9 zonder backport → opnieuw
  if [[ -d "$ROOT/.venv" ]]; then
    if ! "$ROOT/.venv/bin/python" -c "import eval_type_backport, fastapi, uvicorn" 2>/dev/null; then
      log "venv incompleet of oud — opnieuw aanmaken"
      rm -rf "$ROOT/.venv"
      rm -f "$DEPS_MARKER"
      need=1
    fi
  fi
  if [[ ! -d "$ROOT/.venv" ]]; then need=1
  elif [[ ! -f "$DEPS_MARKER" ]]; then need=1
  elif [[ "$(cat "$DEPS_MARKER" 2>/dev/null || true)" != "$h" ]]; then need=1
  fi
  if [[ "$need" != "1" ]]; then
    log "deps OK (cache)"
    return 0
  fi
  log "deps installeren met $PYTHON_BIN…"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    osascript -e 'display notification "Eenmalig: packages installeren…" with title "VIT AI Hub"' 2>/dev/null || true
  fi
  if [[ ! -d "$ROOT/.venv" ]]; then
    "$PYTHON_BIN" -m venv "$ROOT/.venv" >>"$LOG_FILE" 2>&1 || fail_dialog "venv aanmaken mislukt\\nProbeer: brew install python@3.12"
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  if ! pip -q install -r "$REQ_FILE" >>"$LOG_FILE" 2>&1; then
    fail_dialog "pip install mislukt. Zie log."
  fi
  if ! python -c "import eval_type_backport, fastapi, uvicorn" 2>/dev/null; then
    fail_dialog "Packages niet geladen (eval_type_backport/fastapi)."
  fi
  echo "$h" >"$DEPS_MARKER"
  log "deps klaar"
}

open_gui() {
  bash "$ROOT/scripts/open-gui.sh" "$1" 2>>"$LOG_FILE" || open "$1" 2>/dev/null || true
}

free_port() {
  if command -v lsof >/dev/null 2>&1; then
    for p in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
      log "poort $PORT bezet door pid $p — stoppen"
      kill "$p" 2>/dev/null || true
    done
    sleep 0.3
  fi
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

  if [[ ! -f "$ROOT/src/vit_ai_hub/main.py" ]]; then
    fail_dialog "Hub-bestanden incompleet in:\\n$ROOT\\nRun install-mac-clean of pull-script."
  fi

  free_port
  nohup python -m uvicorn vit_ai_hub.main:app --host "$BIND_HOST" --port "$PORT" \
    >>"$LOG_FILE" 2>&1 &
  echo $! >"$HUB_PID_FILE"
  STARTED_BY_US=1
  log "uvicorn pid=$(cat "$HUB_PID_FILE")"

  for _ in $(seq 1 80); do
    if curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
      log "health OK"
      return 0
    fi
    # vroeg crashen?
    if [[ -f "$HUB_PID_FILE" ]]; then
      HUB_PID="$(cat "$HUB_PID_FILE" 2>/dev/null || true)"
      if [[ -n "$HUB_PID" ]] && ! kill -0 "$HUB_PID" 2>/dev/null; then
        log "uvicorn gestopt tijdens start"
        return 1
      fi
    fi
    sleep 0.25
  done
  return 1
}

# Snelle path
if curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
  log "al online — GUI openen"
  if [[ -f "$SETUP_MARKER" ]]; then
    open_gui "http://${UI_HOST}:${PORT}/"
  else
    open_gui "http://${UI_HOST}:${PORT}/?wizard=1"
  fi
else
  ensure_deps
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  (
    for _ in $(seq 1 80); do
      if curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
        if [[ -f "$SETUP_MARKER" ]]; then
          open_gui "http://${UI_HOST}:${PORT}/static/splash.html?next=%2F"
        else
          open_gui "http://${UI_HOST}:${PORT}/static/splash.html?next=%2F%3Fwizard%3D1"
        fi
        exit 0
      fi
      sleep 0.25
    done
  ) &
  SPLASH_PID=$!
  if ! start_hub; then
    fail_dialog "VIT AI Hub startte niet.\\nLog: ~/Library/Logs/VIT-AI-Hub/app-session.log"
  fi
  if ! kill -0 "${SPLASH_PID:-0}" 2>/dev/null; then
    if [[ -f "$SETUP_MARKER" ]]; then
      open_gui "http://${UI_HOST}:${PORT}/"
    else
      open_gui "http://${UI_HOST}:${PORT}/?wizard=1"
    fi
  fi
fi

if [[ ! -f "$SETUP_MARKER" ]]; then
  (
    curl -sf -X POST "http://${UI_HOST}:${PORT}/api/setup/install-auto" \
      -H "Content-Type: application/json" \
      -d '{"open_a11y":false,"mark_complete":false}' >/dev/null 2>&1 || true
  ) &
fi

while true; do
  sleep 2
  if [[ "$(uname -s)" == "Darwin" ]] && [[ -n "${PPID:-}" ]]; then
    if ! kill -0 "$PPID" 2>/dev/null; then
      break
    fi
  fi
  if ! curl -sf "http://${UI_HOST}:${PORT}/health" >/dev/null 2>&1; then
    log "hub weg — herstarten"
    ensure_deps || true
    start_hub || true
  fi
done
