#!/usr/bin/env bash
# Open VIT AI Hub in een app-achtig venster (geen losse browser-tab).
set -euo pipefail
URL="${1:-http://127.0.0.1:8787/}"

open_chrome_app() {
  local app="$1"
  if [[ -d "$app" ]]; then
    open -na "$app" --args --app="$URL" --new-window
    return 0
  fi
  return 1
}

if [[ "$(uname -s)" == "Darwin" ]]; then
  open_chrome_app "/Applications/Google Chrome.app" && exit 0
  open_chrome_app "$HOME/Applications/Google Chrome.app" && exit 0
  open_chrome_app "/Applications/Microsoft Edge.app" && exit 0
  open_chrome_app "/Applications/Brave Browser.app" && exit 0
  open_chrome_app "/Applications/Chromium.app" && exit 0
  # Safari heeft geen --app; wel een dedicated venster
  osascript <<OSA 2>/dev/null && exit 0
tell application "Safari"
  activate
  make new document with properties {URL:"$URL"}
end tell
OSA
fi

open "$URL" 2>/dev/null || true
