#!/usr/bin/env bash
# Diagnose waarom de Mac-app niet start — plak output hier terug.
set -u
echo "=== VIT AI Hub doctor ==="
echo "date: $(date)"
echo "user: $(whoami)"
echo "python3: $(command -v python3 || echo MISSING)"
python3 --version 2>&1 || true
echo "apps:"
ls -la /Applications 2>/dev/null | grep -i 'VIT AI' || echo "(geen in /Applications)"
mdfind 'kMDItemFSName == "VIT AI Hub.app"c' 2>/dev/null | head -20 || true
echo "project:"
ls -la "$HOME/AI-projecten/VIT-ai-hub/scripts/app-session.sh" 2>&1 || echo "geen ~/AI-projecten/VIT-ai-hub"
echo "port 8787:"
lsof -nP -iTCP:8787 -sTCP:LISTEN 2>/dev/null || echo "(vrij)"
echo "--- log (laatste 40) ---"
tail -n 40 "$HOME/Library/Logs/VIT-AI-Hub/app-session.log" 2>&1 || echo "(geen log)"
echo "=== einde ==="
