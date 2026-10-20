#!/usr/bin/env bash
# Één script: diagnose + herstel + start. Plak output als het nog faalt.
set -u
LOG="$HOME/Library/Logs/VIT-AI-Hub/app-session.log"
PROJ="$HOME/AI-projecten/VIT-ai-hub"
mkdir -p "$(dirname "$LOG")"

echo "=== VIT mac-fix-start ==="
echo "date: $(date)"
echo "python candidates:"
for c in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /usr/local/bin/python3.12 python3; do
  if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then
    echo "  $c -> $($c --version 2>&1)"
  fi
done

echo "stop oude processen…"
pkill -f 'vit_ai_hub.main' 2>/dev/null || true
pkill -f 'Contents/MacOS/vit-ai-hub' 2>/dev/null || true
sleep 0.5
if command -v lsof >/dev/null 2>&1; then
  for p in $(lsof -tiTCP:8787 -sTCP:LISTEN 2>/dev/null || true); do
    echo "  kill port 8787 pid $p"
    kill "$p" 2>/dev/null || true
  done
fi

echo "oude venv weg…"
rm -rf "/Applications/VIT AI Hub.app/hub/.venv" \
       "$PROJ/.venv" \
       "/Applications/VIT AI Hub.app/hub/data/.deps-ok" \
       "$PROJ/data/.deps-ok"

echo "code ophalen…"
if ! curl -fsSL "https://raw.githubusercontent.com/mveenstra1988/rdgen/cursor/vit-ai-hub-a440/vit-ai-hub/scripts/pull-to-ai-projecten.sh" | bash; then
  echo "PULL MISLUKT"
  exit 1
fi

echo "versie in project:"
grep __version__ "$PROJ/src/vit_ai_hub/__init__.py" || true
grep eval_type "$PROJ/requirements.txt" || echo "GEEN eval_type_backport in requirements!"

echo "schone app-install…"
bash "$PROJ/scripts/install-mac-clean.sh" "$PROJ/packaging/mac/VIT AI Hub.app" || {
  echo "install-mac-clean faalde — probeer handmatig openen"
}

sleep 2
echo "health:"
curl -sf http://127.0.0.1:8787/health && echo || echo "HEALTH FAIL"

echo "--- laatste log ---"
tail -n 50 "$LOG" 2>&1 || true
echo "=== einde ==="
