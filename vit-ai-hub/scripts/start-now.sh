#!/usr/bin/env bash
# Minimale start — download zip, venv, uvicorn. Altijd zichtbare output.
set -eu
PROJ="$HOME/AI-projecten/VIT-ai-hub"
BRANCH="cursor/vit-ai-hub-a440"
PORT=8787
LOG="$HOME/Library/Logs/VIT-AI-Hub"
mkdir -p "$LOG" "$HOME/AI-projecten"

echo "=== start-now $(date) ==="

pkill -f 'uvicorn vit_ai_hub' 2>/dev/null || true
pkill -f 'vit_ai_hub.main' 2>/dev/null || true
sleep 0.3

PY=""
for c in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then PY="$c"; break; fi
done
[[ -n "$PY" ]] || { echo "Geen python3. brew install python@3.12"; exit 1; }
echo "Python: $PY ($($PY --version))"

TMP=$(mktemp -d)
echo "Download bron…"
curl -L --progress-bar -o "$TMP/src.tgz" \
  "https://github.com/mveenstra1988/rdgen/archive/refs/heads/${BRANCH}.tar.gz"
tar -xzf "$TMP/src.tgz" -C "$TMP"
SRC=$(find "$TMP" -type d -name vit-ai-hub | head -1)
[[ -d "$SRC" ]] || { echo "vit-ai-hub niet in archive"; ls -R "$TMP" | head; exit 1; }

mkdir -p "$PROJ"
rm -rf "$PROJ/.venv"
rsync -a --delete --exclude data --exclude .venv "$SRC/" "$PROJ/" 2>/dev/null || \
  (cd "$SRC" && tar cf - --exclude=data --exclude=.venv .) | (cd "$PROJ" && tar xf -)
mkdir -p "$PROJ/data"

cd "$PROJ"
echo "Versie $(grep __version__ src/vit_ai_hub/__init__.py)"
$PY -m venv .venv
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt
python -c "import eval_type_backport,fastapi,uvicorn; print('imports OK')"

SECRET="$HOME/.config/vit/geheimen/ai-gateway.env"
mkdir -p "$(dirname "$SECRET")"
[[ -f "$SECRET" ]] || { cp .env.example "$SECRET"; echo "VIT_GATEWAY_TOKEN=vit-$(openssl rand -hex 8)" >> "$SECRET"; }

set -a; source "$SECRET"; set +a
export PYTHONPATH="$PROJ/src" VIT_GATEWAY_HOST=127.0.0.1 VIT_GATEWAY_PORT=$PORT
nohup python -m uvicorn vit_ai_hub.main:app --host 127.0.0.1 --port $PORT \
  >>"$LOG/app-session.log" 2>&1 &
echo "pid $!"

for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/health"; then
    echo ""
    echo "ONLINE"
    open -na "Google Chrome" --args --app="http://127.0.0.1:$PORT/?wizard=1" --new-window 2>/dev/null \
      || open "http://127.0.0.1:$PORT/?wizard=1"
    echo "KLAAR — sluit oude grijze vensters"
    exit 0
  fi
  sleep 0.5
done
echo "START MISLUKT — log:"
tail -n 30 "$LOG/app-session.log"
exit 1
