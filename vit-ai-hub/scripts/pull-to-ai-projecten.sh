#!/usr/bin/env bash
# Zet VIT AI Hub op je Mac in ~/AI-projecten/VIT-ai-hub
# Gebruik (één regel in Terminal):
#   curl -fsSL https://raw.githubusercontent.com/mveenstra1988/rdgen/cursor/vit-ai-hub-a440/vit-ai-hub/scripts/pull-to-ai-projecten.sh | bash
set -euo pipefail

DEST="${VIT_AI_HUB_DIR:-$HOME/AI-projecten/VIT-ai-hub}"
BRANCH="${VIT_AI_HUB_BRANCH:-cursor/vit-ai-hub-a440}"
REPO="${VIT_AI_HUB_REPO:-https://github.com/mveenstra1988/rdgen.git}"
TMP="$(mktemp -d /tmp/vit-ai-hub-pull.XXXXXX)"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "==> VIT AI Hub → $DEST"
echo "    branch: $BRANCH"

mkdir -p "$(dirname "$DEST")"

# Sparse clone: alleen vit-ai-hub/
git clone --depth 1 --filter=blob:none --sparse -b "$BRANCH" "$REPO" "$TMP/repo"
(
  cd "$TMP/repo"
  git sparse-checkout set vit-ai-hub
)

sync_tree() {
  local src="$1" dst="$2"
  mkdir -p "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.venv' --exclude 'data/' --exclude '__pycache__' \
      "$src/" "$dst/"
  else
    (cd "$src" && tar cf - --exclude='.venv' --exclude='data' --exclude='__pycache__' .) \
      | (cd "$dst" && tar xf -)
  fi
  mkdir -p "$dst/data"
}

if [[ -e "$DEST" && ! -d "$DEST" ]]; then
  echo "    fout: $DEST is geen map" >&2
  exit 1
fi
if [[ -d "$DEST" ]]; then
  echo "    bijwerken $DEST …"
else
  echo "    nieuw $DEST …"
fi
sync_tree "$TMP/repo/vit-ai-hub" "$DEST"

# Klein git-remote behouden voor updates (optioneel)
if [[ ! -d "$DEST/.git" ]]; then
  (
    cd "$DEST"
    git init -q
    git remote add origin "$REPO" 2>/dev/null || true
    git checkout -b "$BRANCH" 2>/dev/null || true
  ) || true
fi

DMG="$(ls -1 "$DEST"/dist/VIT-AI-Hub-*-mac.dmg 2>/dev/null | sort -V | tail -1 || true)"
echo "    klaar: $DEST"
if [[ -n "${DMG}" ]]; then
  echo "    DMG:  $DMG"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "$(dirname "$DMG")"
    echo "    Finder geopend op dist/ — dubbelklik de .dmg om te installeren."
  fi
else
  echo "    (nog geen .dmg in dist/ — bouw met: bash packaging/build-dist.sh)"
fi

echo ""
echo "Volgende:"
echo "  open $DEST"
echo "  open \"\${DMG:-$DEST/dist}\""
