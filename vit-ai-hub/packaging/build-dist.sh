#!/usr/bin/env bash
# Bouwt een zip die je op de Mac uitpakt en start (START.command of .app).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VIT_PKG_VERSION:-0.6.0}"
DIST="$ROOT/dist"
STAGE="$DIST/VIT-AI-Hub-${VERSION}"

rm -rf "$STAGE"
mkdir -p "$STAGE"

mkdir -p "$STAGE/hub"
# portable copy without rsync
tar -C "$ROOT" \
  --exclude='.venv' \
  --exclude='data' \
  --exclude='dist' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.git' \
  -cf - . | tar -C "$STAGE/hub" -xf -

mkdir -p "$STAGE"
cp -R "$ROOT/packaging/mac/VIT AI Hub.app" "$STAGE/"
# nest hub inside app for double-click launch
rm -rf "$STAGE/VIT AI Hub.app/hub"
cp -R "$STAGE/hub" "$STAGE/VIT AI Hub.app/hub"
chmod +x "$STAGE/VIT AI Hub.app/Contents/MacOS/vit-ai-hub"
chmod +x "$STAGE/hub/scripts/"*.sh "$STAGE/hub/START.command" "$STAGE/hub/packaging/"*.sh 2>/dev/null || true
chmod +x "$STAGE/hub/packaging/pkg-scripts/postinstall"

# Convenience: START at top level
cp "$STAGE/hub/START.command" "$STAGE/START.command"
chmod +x "$STAGE/START.command"

cat >"$STAGE/LEESMIJ.txt" <<EOF
VIT AI Hub ${VERSION}
====================

Morgen / op je Mac:

Optie A (snelst):
  1. Dubbelklik "VIT AI Hub.app"
  2. Volg de wizard in de browser

Optie B:
  1. Dubbelklik START.command
  2. Volg de wizard

Optie C (echte .pkg):
  Op de Mac: open Terminal in deze map/hub en run:
    bash packaging/build-mac-pkg.sh
  Installeer daarna dist/VIT_AI_Hub-${VERSION}.pkg

Daarna: http://127.0.0.1:8787
Cursor base URL: http://127.0.0.1:8787/v1
Secrets: ~/.config/vit/geheimen/ai-gateway.env
EOF

(
  cd "$DIST"
  rm -f "VIT-AI-Hub-${VERSION}-mac.zip"
  zip -r "VIT-AI-Hub-${VERSION}-mac.zip" "VIT-AI-Hub-${VERSION}" >/dev/null
)

echo "Klaar: $DIST/VIT-AI-Hub-${VERSION}-mac.zip"
ls -lh "$DIST/VIT-AI-Hub-${VERSION}-mac.zip"
