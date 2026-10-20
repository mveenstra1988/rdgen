#!/usr/bin/env bash
# Herstel + start VIT AI Hub direct (geen stille curl|bash).
# Gebruik:
#   curl -L -o /tmp/vit-fix.sh https://raw.githubusercontent.com/mveenstra1988/rdgen/cursor/vit-ai-hub-a440/vit-ai-hub/scripts/mac-fix-start.sh
#   bash /tmp/vit-fix.sh
set -u
set -o pipefail

LOG_DIR="$HOME/Library/Logs/VIT-AI-Hub"
LOG="$LOG_DIR/mac-fix-start.log"
PROJ="$HOME/AI-projecten/VIT-ai-hub"
REPO_URL="${VIT_AI_HUB_REPO:-https://github.com/mveenstra1988/rdgen.git}"
BRANCH="${VIT_AI_HUB_BRANCH:-cursor/vit-ai-hub-a440}"
PORT="${VIT_GATEWAY_PORT:-8787}"
UI="http://127.0.0.1:${PORT}"

mkdir -p "$LOG_DIR" "$(dirname "$PROJ")"
exec > >(tee -a "$LOG") 2>&1

echo ""
echo "========================================"
echo " VIT AI Hub mac-fix-start"
echo " $(date)"
echo " log: $LOG"
echo "========================================"

step() { echo ""; echo ">> $*"; }

step "1. Python zoeken"
PYTHON_BIN=""
for c in \
  /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 \
  /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 \
  /opt/homebrew/bin/python3 /usr/local/bin/python3 \
  python3.12 python3.11 python3
do
  if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then
    if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,9) else 1)' 2>/dev/null; then
      PYTHON_BIN="$c"
      break
    fi
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "FOUT: geen python3 ≥3.9. Installeer met: brew install python@3.12"
  echo "Of: xcode-select --install"
  exit 1
fi
echo "Gebruik: $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))"

step "2. Oude processen/poort stoppen"
pkill -f 'vit_ai_hub.main' 2>/dev/null || true
pkill -f 'uvicorn vit_ai_hub' 2>/dev/null || true
pkill -f 'Contents/MacOS/vit-ai-hub' 2>/dev/null || true
sleep 0.4
if command -v lsof >/dev/null 2>&1; then
  for p in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
    echo "kill pid $p op poort $PORT"
    kill "$p" 2>/dev/null || true
  done
fi

step "3. Code ophalen naar $PROJ"
TMP="$(mktemp -d /tmp/vit-hub-XXXXXX)"
cleanup_tmp() { rm -rf "$TMP"; }
trap cleanup_tmp EXIT

if ! command -v git >/dev/null 2>&1; then
  echo "FOUT: git ontbreekt"
  exit 1
fi

echo "git clone --depth 1 -b $BRANCH …"
if ! git clone --depth 1 --filter=blob:none --sparse -b "$BRANCH" "$REPO_URL" "$TMP/repo"; then
  echo "Sparse clone faalde — normale clone…"
  rm -rf "$TMP/repo"
  git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$TMP/repo" || {
    echo "FOUT: git clone mislukt. Repo privé? Log in met: gh auth login"
    exit 1
  }
fi
(
  cd "$TMP/repo"
  git sparse-checkout set vit-ai-hub 2>/dev/null || true
)

if [[ ! -f "$TMP/repo/vit-ai-hub/src/vit_ai_hub/main.py" ]]; then
  echo "FOUT: vit-ai-hub niet in clone"
  ls -la "$TMP/repo" || true
  exit 1
fi

mkdir -p "$PROJ"
# bewaar data/venv niet — schone deps
rm -rf "$PROJ/.venv" "$PROJ/data/.deps-ok"
# sync code, hou data/ chats als die er zijn
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '.venv' --exclude 'data/' --exclude '__pycache__' \
    "$TMP/repo/vit-ai-hub/" "$PROJ/"
else
  (cd "$TMP/repo/vit-ai-hub" && tar cf - --exclude='.venv' --exclude='data' --exclude='__pycache__' .) \
    | (cd "$PROJ" && tar xf -)
fi
mkdir -p "$PROJ/data" "$PROJ/data/run"
echo "Versie: $(grep __version__ "$PROJ/src/vit_ai_hub/__init__.py" | head -1)"
grep -q eval_type_backport "$PROJ/requirements.txt" && echo "eval_type_backport: ja" || echo "eval_type_backport: NEE"

step "4. venv + packages"
cd "$PROJ"
"$PYTHON_BIN" -m venv .venv || { echo "FOUT: venv"; exit 1; }
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt || { echo "FOUT: pip install"; exit 1; }
python -c "import eval_type_backport, fastapi, uvicorn; print('imports OK')" || {
  echo "FOUT: python imports"
  exit 1
}

step "5. secrets"
SECRET="$HOME/.config/vit/geheimen/ai-gateway.env"
mkdir -p "$(dirname "$SECRET")"
if [[ ! -f "$SECRET" ]]; then
  cp "$PROJ/.env.example" "$SECRET"
  TOKEN="vit-$(openssl rand -hex 12 2>/dev/null || date +%s)"
  if grep -q '^VIT_GATEWAY_TOKEN=' "$SECRET"; then
    sed -i.bak "s/^VIT_GATEWAY_TOKEN=.*/VIT_GATEWAY_TOKEN=${TOKEN}/" "$SECRET" && rm -f "$SECRET.bak"
  else
    echo "VIT_GATEWAY_TOKEN=${TOKEN}" >>"$SECRET"
  fi
fi
chmod 600 "$SECRET" 2>/dev/null || true

step "6. Hub starten op :$PORT"
set -a
# shellcheck disable=SC1090
source "$SECRET"
set +a
export PYTHONPATH="$PROJ/src${PYTHONPATH:+:$PYTHONPATH}"
export VIT_GATEWAY_HOST=127.0.0.1
export VIT_GATEWAY_PORT="$PORT"

nohup python -m uvicorn vit_ai_hub.main:app --host 127.0.0.1 --port "$PORT" \
  >>"$LOG_DIR/app-session.log" 2>&1 &
HUB_PID=$!
echo "uvicorn pid=$HUB_PID"
echo "$HUB_PID" >"$PROJ/data/run/hub.pid"

OK=0
for i in $(seq 1 60); do
  if curl -sf "$UI/health" >/dev/null 2>&1; then
    OK=1
    break
  fi
  if ! kill -0 "$HUB_PID" 2>/dev/null; then
    echo "FOUT: uvicorn gestopt tijdens start"
    tail -n 40 "$LOG_DIR/app-session.log" || true
    exit 1
  fi
  sleep 0.5
done

if [[ "$OK" != "1" ]]; then
  echo "FOUT: geen health na 30s"
  tail -n 40 "$LOG_DIR/app-session.log" || true
  exit 1
fi

echo "HEALTH: $(curl -sf "$UI/health")"
step "7. GUI openen"
if [[ -d "/Applications/Google Chrome.app" ]]; then
  open -na "Google Chrome" --args --app="$UI/?wizard=1" --new-window
else
  open "$UI/?wizard=1"
fi

# Eén app in Applications (best effort, blokkeert niet)
if [[ -d "$PROJ/packaging/mac/VIT AI Hub.app" ]]; then
  step "8. Eén .app in /Applications"
  bash "$PROJ/scripts/install-mac-clean.sh" "$PROJ/packaging/mac/VIT AI Hub.app" || true
fi

echo ""
echo "KLAAR. Hub draait: $UI"
echo "Project: $PROJ"
echo "Log: $LOG"
echo "========================================"
