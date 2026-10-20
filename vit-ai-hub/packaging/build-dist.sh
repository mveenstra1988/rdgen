#!/usr/bin/env bash
# Bouwt zip + DMG: één .app die hub start/stopt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VIT_PKG_VERSION:-2.6.5}"
DIST="$ROOT/dist"
STAGE="$DIST/VIT-AI-Hub-${VERSION}"
APP_NAME="VIT AI Hub"

rm -rf "$STAGE"
mkdir -p "$STAGE/hub"

# Hub payload (zonder zware caches)
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude 'data/' \
    --exclude 'dist/' \
    --exclude 'packaging/dmgmod' \
    --exclude '.git' \
    "$ROOT/" "$STAGE/hub/"
else
  (
    cd "$ROOT"
    tar -cf - \
      --exclude='.venv' \
      --exclude='__pycache__' \
      --exclude='.pytest_cache' \
      --exclude='data' \
      --exclude='dist' \
      --exclude='packaging/dmgmod' \
      --exclude='.git' \
      . | tar -xf - -C "$STAGE/hub"
  )
fi

# .app bundle met hub erin
cp -R "$ROOT/packaging/mac/${APP_NAME}.app" "$STAGE/"
# bump version in plist copy
python3 - <<PY
from pathlib import Path
p = Path("$STAGE/${APP_NAME}.app/Contents/Info.plist")
t = p.read_text(encoding="utf-8")
import re
t = re.sub(r"(<key>CFBundleVersion</key>\s*<string>)[^<]+", r"\g<1>${VERSION}", t)
t = re.sub(r"(<key>CFBundleShortVersionString</key>\s*<string>)[^<]+", r"\g<1>${VERSION}", t)
p.write_text(t, encoding="utf-8")
PY
# brand icons into .app
mkdir -p "$STAGE/${APP_NAME}.app/Contents/Resources"
cp -f "$ROOT/packaging/mac/${APP_NAME}.app/Contents/Resources/AppIcon.png" \
  "$STAGE/${APP_NAME}.app/Contents/Resources/AppIcon.png" 2>/dev/null || \
  cp -f "$ROOT/web/static/icon-512.png" "$STAGE/${APP_NAME}.app/Contents/Resources/AppIcon.png"
cp -f "$ROOT/packaging/mac/${APP_NAME}.app/Contents/Resources/AppIcon.icns" \
  "$STAGE/${APP_NAME}.app/Contents/Resources/AppIcon.icns" 2>/dev/null || true

rm -rf "$STAGE/${APP_NAME}.app/hub"
cp -R "$STAGE/hub" "$STAGE/${APP_NAME}.app/hub"
chmod +x "$STAGE/${APP_NAME}.app/Contents/MacOS/vit-ai-hub"
chmod +x "$STAGE/hub/scripts/"*.sh "$STAGE/hub/START.command" "$STAGE/hub/packaging/"*.sh 2>/dev/null || true

cp "$STAGE/hub/START.command" "$STAGE/START.command"
chmod +x "$STAGE/START.command"

cat >"$STAGE/LEESMIJ.txt" <<EOF
VIT AI Hub ${VERSION}

1. Sleep «VIT AI Hub» naar Applications (aanbevolen)
2. Open de app — er verschijnt een eigen venster (splash → wizard)
3. Project staat daarna in: ~/AI-projecten/VIT-ai-hub

Gedrag:
- Eigen GUI-venster (Chrome app-modus), geen losse tab
- App sluiten (Cmd+Q) → hub stopt
- Eerste keer: even wachten op Python-omgeving

Als macOS blokkeert:
  xattr -dr com.apple.quarantine "/Applications/VIT AI Hub.app"
EOF
chmod +x "$ROOT/scripts/open-gui.sh" "$ROOT/scripts/app-session.sh" \
  "$ROOT/packaging/mac/VIT AI Hub.app/Contents/MacOS/vit-ai-hub" 2>/dev/null || true

# Zip
(
  cd "$DIST"
  rm -f "VIT-AI-Hub-${VERSION}-mac.zip"
  zip -r "VIT-AI-Hub-${VERSION}-mac.zip" "VIT-AI-Hub-${VERSION}" >/dev/null
)
echo "Zip: $DIST/VIT-AI-Hub-${VERSION}-mac.zip"

# DMG stage: alleen .app + Applications symlink + LEESMIJ
DMG_STAGE="$DIST/dmg-stage-${VERSION}"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
cp -R "$STAGE/${APP_NAME}.app" "$DMG_STAGE/"
cp "$STAGE/LEESMIJ.txt" "$DMG_STAGE/LEESMIJ.txt"
# Eén-klik schone install (verwijdert duplicaten)
cat >"$DMG_STAGE/Installeer (1x).command" <<'CMD'
#!/bin/bash
cd "$(dirname "$0")"
APP="$(pwd)/VIT AI Hub.app"
bash "$APP/hub/scripts/install-mac-clean.sh" "$APP"
CMD
chmod +x "$DMG_STAGE/Installeer (1x).command"
ln -s /Applications "$DMG_STAGE/Applications"

# Go DMG builder (werkt op Linux)
GO_MOD_DIR="$ROOT/packaging/dmgmod"
mkdir -p "$GO_MOD_DIR"
if [[ ! -f "$GO_MOD_DIR/go.mod" ]]; then
  (
    cd "$GO_MOD_DIR"
    go mod init vit.aihub.dmg
    go get github.com/jetbrains/go-dmg-writer@v0.0.0-20260914114223-48284c0071ae
  )
fi
cp "$ROOT/packaging/build-dmg.go" "$GO_MOD_DIR/main.go"
(
  cd "$GO_MOD_DIR"
  go mod tidy
  go run . "$DMG_STAGE" "$DIST/VIT-AI-Hub-${VERSION}-mac.dmg"
)

ls -lh "$DIST/VIT-AI-Hub-${VERSION}-mac.zip" "$DIST/VIT-AI-Hub-${VERSION}-mac.dmg"
echo "Klaar: zip + dmg ${VERSION}"
