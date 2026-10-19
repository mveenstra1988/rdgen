"""First-run setup helpers: status + secrets schrijven (localhost only)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from vit_ai_hub import __version__
from vit_ai_hub.config import ROOT

SECRET_FILE = Path.home() / ".config/vit/geheimen/ai-gateway.env"
SETUP_MARKER = ROOT / "data" / ".setup-complete"

ALLOWED_KEYS = {
    "VIT_GATEWAY_TOKEN",
    "OPENROUTER_API_KEY",
    "XAI_API_KEY",
    "BRIDGE_API_KEY",
    "BRIDGE_BASE_URL",
    "OMNIROUTE_API_KEY",
    "OMNIROUTE_BASE_URL",
    "LMSTUDIO_BASE_URL",
    "OLLAMA_BASE_URL",
    "VIT_LOCAL_LIGHT_MODEL",
    "VIT_LOCAL_HEAVY_MODEL",
}


def setup_status() -> dict[str, Any]:
    secret_exists = SECRET_FILE.is_file()
    keys_present = []
    if secret_exists:
        for line in SECRET_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                if k.strip() in ALLOWED_KEYS and v.strip() and "change-me" not in v:
                    keys_present.append(k.strip())
    lmstudio = False
    ollama = False
    try:
        import httpx

        try:
            lmstudio = httpx.get("http://127.0.0.1:1234/v1/models", timeout=1.5).status_code < 500
        except Exception:
            lmstudio = False
        try:
            ollama = httpx.get("http://127.0.0.1:11434/api/tags", timeout=1.5).status_code < 500
        except Exception:
            ollama = False
    except Exception:
        pass

    return {
        "version": __version__,
        "setup_complete": SETUP_MARKER.is_file(),
        "secret_file": str(SECRET_FILE),
        "secret_exists": secret_exists,
        "keys_present": keys_present,
        "lmstudio_up": lmstudio,
        "ollama_up": ollama,
        "darwin": os.uname().sysname == "Darwin",
        "hub_root": str(ROOT),
    }


def save_secrets(values: dict[str, str]) -> dict[str, Any]:
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    comments: list[str] = []
    if SECRET_FILE.is_file():
        for line in SECRET_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#"):
                comments.append(line)
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    for k, v in values.items():
        key = k.strip()
        if key not in ALLOWED_KEYS:
            continue
        if v is None:
            continue
        val = str(v).strip()
        if val == "":
            continue
        # never allow newlines
        if re.search(r"[\r\n]", val):
            continue
        existing[key] = val

    lines = ["# VIT AI Hub secrets — gegenereerd/ bijgewerkt door setup wizard", ""]
    for k in sorted(existing):
        lines.append(f"{k}={existing[k]}")
    SECRET_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(SECRET_FILE, 0o600)
    return {"ok": True, "path": str(SECRET_FILE), "keys": sorted(existing)}


def mark_setup_complete() -> dict[str, Any]:
    SETUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
    SETUP_MARKER.write_text("ok\n", encoding="utf-8")
    return {"ok": True}


def open_accessibility_settings() -> dict[str, Any]:
    if os.uname().sysname != "Darwin":
        return {"ok": False, "error": "alleen macOS"}
    subprocess.run(
        ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
        check=False,
    )
    return {"ok": True}
