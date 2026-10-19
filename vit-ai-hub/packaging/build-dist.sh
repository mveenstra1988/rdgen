#!/usr/bin/env bash
# Bouwt een zip die je op de Mac uitpakt en start (START.command of .app).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VIT_PKG_VERSION:-0.7.1}"
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

Op je Mac (één keer):

1. Unzip deze map ergens (bijv. ~/Applications)
2. Als macOS "onbekende ontwikkelaar" zegt:
     xattr -dr com.apple.quarantine "VIT AI Hub.app" hub
3. Dubbelklik "VIT AI Hub.app" (of START.command)
4. Klik in de wizard op "Alles nu regelen"
   (optioneel: keys invullen vóór die knop)

Dat zet venv, secrets, import, live sync en de GUI klaar.

Daarna:
  http://127.0.0.1:8787
  Cursor → OpenAI Base URL: http://127.0.0.1:8787/v1
  Secrets: ~/.config/vit/geheimen/ai-gateway.env

Echte .pkg (optioneel, op de Mac):
  bash hub/packaging/build-mac-pkg.sh
EOF

(
  cd "$DIST"
  rm -f "VIT-AI-Hub-${VERSION}-mac.zip"
  zip -r "VIT-AI-Hub-${VERSION}-mac.zip" "VIT-AI-Hub-${VERSION}" >/dev/null
)

echo "Klaar: $DIST/VIT-AI-Hub-${VERSION}-mac.zip"
ls -lh "$DIST/VIT-AI-Hub-${VERSION}-mac.zip"
