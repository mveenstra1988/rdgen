#!/usr/bin/env bash
# Bouwt zip + DMG: één .app die hub start/stopt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VIT_PKG_VERSION:-2.5.0}"
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
/usr/bin/sed -i.bak "s#<string>1\\.[0-9]\\.[0-9]</string>#<string>${VERSION}</string>#g" \
  "$STAGE/${APP_NAME}.app/Contents/Info.plist" 2>/dev/null || \
  sed -i "s/<string>1\\.[0-9]\\.[0-9]<\\/string>/<string>${VERSION}<\\/string>/g" \
  "$STAGE/${APP_NAME}.app/Contents/Info.plist"
rm -f "$STAGE/${APP_NAME}.app/Contents/Info.plist.bak"
rm -rf "$STAGE/${APP_NAME}.app/hub"
cp -R "$STAGE/hub" "$STAGE/${APP_NAME}.app/hub"
chmod +x "$STAGE/${APP_NAME}.app/Contents/MacOS/vit-ai-hub"
chmod +x "$STAGE/hub/scripts/"*.sh "$STAGE/hub/START.command" "$STAGE/hub/packaging/"*.sh 2>/dev/null || true

cp "$STAGE/hub/START.command" "$STAGE/START.command"
chmod +x "$STAGE/START.command"

cat >"$STAGE/LEESMIJ.txt" <<EOF
VIT AI Hub ${VERSION}

Installatie (aanbevolen): open het .dmg en sleep «VIT AI Hub» naar Applications.
Of: dubbelklik «VIT AI Hub.app» uit deze map.

Gedrag:
- App openen → hub start automatisch + browser
- App sluiten (Cmd+Q / Dock Quit) → hub stopt
- Geen losse tools nodig

Eerste keer: eventueel
  xattr -dr com.apple.quarantine "VIT AI Hub.app"
EOF

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
