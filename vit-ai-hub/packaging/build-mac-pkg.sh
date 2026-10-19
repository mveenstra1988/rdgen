#!/usr/bin/env bash
# Draai dit OP DE MAC om een .pkg te maken.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
STAGE="$DIST/stage"
APP_NAME="VIT AI Hub"
PKG_ID="nl.veenstra-it.aihub"
VERSION="${VIT_PKG_VERSION:-1.5.0}"

rm -rf "$STAGE" "$DIST/${APP_NAME// /_}-${VERSION}.pkg"
mkdir -p "$STAGE/Applications/VIT-AI-Hub" "$DIST"

# App + hub payload
cp -R "$ROOT/packaging/mac/${APP_NAME}.app" "$STAGE/Applications/"
mkdir -p "$STAGE/Applications/VIT-AI-Hub/hub"
tar -C "$ROOT" \
  --exclude='.venv' --exclude='data' --exclude='dist' \
  --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.git' \
  -cf - . | tar -C "$STAGE/Applications/VIT-AI-Hub/hub" -xf -

# Place hub next to .app for the launcher candidates
mkdir -p "$STAGE/Applications/${APP_NAME}.app/Contents/Resources"
ln -sfn "/Applications/VIT-AI-Hub/hub" "$STAGE/Applications/${APP_NAME}.app/Contents/Resources/hub" || true
cp -R "$STAGE/Applications/VIT-AI-Hub/hub" "$STAGE/Applications/${APP_NAME}.app/hub"

chmod +x "$STAGE/Applications/${APP_NAME}.app/Contents/MacOS/vit-ai-hub"
find "$STAGE/Applications/VIT-AI-Hub/hub/scripts" -type f -name '*.sh' -exec chmod +x {} \;

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Niet op macOS: stage staat klaar in $STAGE"
  echo "Maak op de Mac: bash packaging/build-mac-pkg.sh"
  # zip fallback
  (cd "$STAGE/Applications" && zip -r "$DIST/VIT-AI-Hub-${VERSION}-mac.zip" "${APP_NAME}.app" "VIT-AI-Hub")
  echo "Zip: $DIST/VIT-AI-Hub-${VERSION}-mac.zip"
  exit 0
fi

pkgbuild \
  --root "$STAGE" \
  --identifier "$PKG_ID" \
  --version "$VERSION" \
  --install-location "/" \
  --scripts "$ROOT/packaging/pkg-scripts" \
  "$DIST/VIT_AI_Hub-${VERSION}.pkg"

echo "PKG: $DIST/VIT_AI_Hub-${VERSION}.pkg"
