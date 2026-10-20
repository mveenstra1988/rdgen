#!/usr/bin/env bash
# Één schone installatie: verwijdert alle dubbele VIT AI Hub.app, zet er één in /Applications.
set -euo pipefail

APP_NAME="VIT AI Hub.app"
DEST="/Applications/${APP_NAME}"
SRC="${1:-}"

die() { echo "fout: $*" >&2; exit 1; }

if [[ -z "$SRC" ]]; then
  HERE="$(cd "$(dirname "$0")/.." && pwd)"
  for cand in \
    "$HERE/packaging/mac/${APP_NAME}" \
    "/Volumes/VIT AI Hub/${APP_NAME}" \
    "$HOME/AI-projecten/VIT-ai-hub/packaging/mac/${APP_NAME}" \
    "$HOME/Downloads/${APP_NAME}" \
    "$DEST"
  do
    if [[ -d "$cand/Contents/MacOS" ]]; then
      SRC="$cand"
      break
    fi
  done
fi
[[ -n "$SRC" && -d "$SRC/Contents/MacOS" ]] || die "geen ${APP_NAME} gevonden — gebruik: $0 \"/pad/naar/VIT AI Hub.app\""

echo "==> Bron: $SRC"
echo "==> Doel: $DEST"

pkill -f 'vit_ai_hub.main' 2>/dev/null || true
pkill -f 'Contents/MacOS/vit-ai-hub' 2>/dev/null || true
sleep 0.4

REMOVED=0
sweep_dir() {
  local dir="$1" maxd="${2:-3}"
  [[ -d "$dir" ]] || return 0
  while IFS= read -r app; do
    [[ -z "$app" ]] && continue
    [[ "$app" == "$SRC" ]] && continue
    echo "    weg: $app"
    rm -rf "$app" || true
    REMOVED=$((REMOVED + 1))
  done < <(find "$dir" -maxdepth "$maxd" -name 'VIT AI Hub.app' -type d 2>/dev/null || true)
}

sweep_dir /Applications 2
sweep_dir "$HOME/Applications" 3
sweep_dir "$HOME/Desktop" 3
sweep_dir "$HOME/Downloads" 3
sweep_dir "$HOME/AI-projecten" 4

# Spotlight-treffers (extra)
if command -v mdfind >/dev/null 2>&1; then
  while IFS= read -r app; do
    [[ -z "$app" || ! -d "$app" ]] && continue
    [[ "$app" == "$SRC" ]] && continue
    [[ "$app" == "$DEST" ]] && continue
    echo "    weg: $app"
    rm -rf "$app" || true
    REMOVED=$((REMOVED + 1))
  done < <(mdfind 'kMDItemFSName == "VIT AI Hub.app"c' 2>/dev/null || true)
fi

TMP_COPY="$(mktemp -d)/${APP_NAME}"
# Kopieer bron eerst naar tmp als bron==DEST (anders wissen we onszelf)
if [[ "$SRC" == "$DEST" ]]; then
  cp -R "$SRC" "$TMP_COPY"
  SRC="$TMP_COPY"
fi

rm -rf "$DEST"
mkdir -p /Applications
cp -R "$SRC" "$DEST"
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
chmod +x "$DEST/Contents/MacOS/vit-ai-hub"

# Dock/Launchpad verversen
killall Dock 2>/dev/null || true

echo "==> Klaar: 1× $DEST (verwijderd: ${REMOVED})"
open "$DEST"
