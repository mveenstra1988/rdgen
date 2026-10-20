#!/usr/bin/env bash
# Installeert + configureert Claude/ChatGPT bridge (CLIProxyAPI) voor VIT AI Hub.
# Liever: wizard → «Bridge klaarzetten» / «Log in bij Claude».
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY="${PYTHON:-python3}"
echo "==> VIT bridge bootstrap"
"$PY" - <<'PY'
from vit_ai_hub.bridge import bootstrap_bridge, bridge_status
import json
print(json.dumps(bootstrap_bridge(), indent=2, ensure_ascii=False))
print("---")
print(json.dumps(bridge_status(), indent=2, ensure_ascii=False))
PY
echo
echo "Daarna OAuth:"
echo "  $PY -c \"from vit_ai_hub.bridge import start_login; print(start_login('claude'))\""
echo "  $PY -c \"from vit_ai_hub.bridge import start_login; print(start_login('chatgpt'))\""
