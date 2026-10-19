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
    "DEEPSEEK_API_KEY",
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

# Guided wizard: open these URLs/apps for login & keys
GUIDE_TARGETS: dict[str, dict[str, str]] = {
    "openrouter_keys": {
        "url": "https://openrouter.ai/keys",
        "label": "OpenRouter API keys",
    },
    "deepseek_keys": {
        "url": "https://platform.deepseek.com/api_keys",
        "label": "DeepSeek API keys",
    },
    "omniroute_docs": {
        "url": "https://github.com/router-for-me/OmniRoute",
        "label": "OmniRoute",
    },
    "bridge_docs": {
        "url": "https://github.com/router-for-me/CLIProxyAPI",
        "label": "Claude/ChatGPT abo-bridge (CLIProxyAPI)",
    },
    "lmstudio": {
        "app": "LM Studio",
        "label": "LM Studio",
    },
    "cursor_settings": {
        "app": "Cursor",
        "label": "Cursor",
    },
    "chatgpt": {"app": "ChatGPT", "label": "ChatGPT"},
    "claude": {"app": "Claude", "label": "Claude"},
}


def _read_secret_map() -> dict[str, str]:
    out: dict[str, str] = {}
    if not SECRET_FILE.is_file():
        return out
    for line in SECRET_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def setup_status(*, include_token: bool = False) -> dict[str, Any]:
    secret_exists = SECRET_FILE.is_file()
    secrets = _read_secret_map()
    keys_present = [
        k
        for k, v in secrets.items()
        if k in ALLOWED_KEYS and v and "change-me" not in v
    ]
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

    out: dict[str, Any] = {
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
    if include_token:
        tok = secrets.get("VIT_GATEWAY_TOKEN", "")
        if tok and "change-me" not in tok:
            out["gateway_token"] = tok
    return out


def bootstrap_all(*, open_a11y: bool = False) -> dict[str, Any]:
    """Één call: VOLLEDIGE migratie + sync + setup-complete."""
    from vit_ai_hub.importing.full_migrate import migrate_everything
    from vit_ai_hub.importing.sync import start_sync, sync_once

    migration = migrate_everything(promote_skills=True)
    knowledge = (migration.get("knowledge_import") or {}).get("knowledge") or {}
    sync_result = sync_once(include_ax=False)
    sync_ctl = start_sync(interval_sec=300, include_ax=False)
    if open_a11y:
        open_accessibility_settings()
    done = mark_setup_complete()
    return {
        "ok": True,
        "knowledge": knowledge,
        "import": migration.get("knowledge_import") or {},
        "migration": migration,
        "sync": sync_result,
        "sync_ctl": sync_ctl,
        "setup": done,
        "profile": migration.get("profile"),
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


def open_guide(target: str) -> dict[str, Any]:
    """Open login/key/docs voor de wizard (localhost guided setup)."""
    key = (target or "").strip().lower()
    info = GUIDE_TARGETS.get(key)
    if not info:
        return {"ok": False, "error": f"onbekend target: {target}", "known": sorted(GUIDE_TARGETS)}
    if os.uname().sysname != "Darwin":
        return {"ok": False, "error": "alleen macOS", "hint": info}
    if info.get("url"):
        subprocess.run(["open", info["url"]], check=False)
        return {"ok": True, "opened": info["url"], "label": info.get("label")}
    if info.get("app"):
        r = subprocess.run(["open", "-a", info["app"]], capture_output=True, text=True)
        return {
            "ok": r.returncode == 0,
            "app": info["app"],
            "label": info.get("label"),
            "error": (r.stderr or "").strip() or None,
        }
    return {"ok": False, "error": "geen actie"}


def probe_providers() -> dict[str, Any]:
    """Snelle status voor wizard-checklist."""
    status = setup_status(include_token=False)
    secrets = _read_secret_map()
    bridge_up = False
    omni_up = False
    try:
        import httpx

        try:
            bridge_up = httpx.get("http://127.0.0.1:8317/v1/models", timeout=1.2).status_code < 500
        except Exception:
            bridge_up = False
        try:
            omni_up = httpx.get("http://127.0.0.1:20128/v1/models", timeout=1.2).status_code < 500
        except Exception:
            omni_up = False
    except Exception:
        pass
    return {
        **status,
        "bridge_up": bridge_up,
        "omniroute_up": omni_up,
        "openrouter_key": bool(secrets.get("OPENROUTER_API_KEY")),
        "deepseek_key": bool(secrets.get("DEEPSEEK_API_KEY")),
        "xai_key": bool(secrets.get("XAI_API_KEY")),
        "bridge_key": bool(secrets.get("BRIDGE_API_KEY")),
        "cursor_base_url": "http://127.0.0.1:8787/v1",
    }
