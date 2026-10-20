"""First-run setup helpers: status + secrets schrijven (localhost only)."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any

from vit_ai_hub import __version__
from vit_ai_hub.config import ROOT

SECRET_FILE = Path.home() / ".config/vit/geheimen/ai-gateway.env"
SETUP_MARKER = ROOT / "data" / ".setup-complete"

DEFAULT_LIGHT_MODEL = "qwen3.6-35b-a3b"
DEFAULT_BANANA_MODEL = "gemini-2.0-flash-preview-image-generation"
HUB_BASE = "http://127.0.0.1:8787/v1"

ALLOWED_KEYS = {
    "VIT_GATEWAY_TOKEN",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "VIT_NANO_BANANA_MODEL",
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
    "gemini_keys": {
        "url": "https://aistudio.google.com/apikey",
        "label": "Gemini / Nano Banana API key",
    },
    "gemini": {
        "url": "https://aistudio.google.com/apikey",
        "label": "Gemini inloggen + API key",
    },
    "google_ai_studio": {
        "url": "https://aistudio.google.com/",
        "label": "Google AI Studio (inloggen)",
    },
    "deepseek_keys": {
        "url": "https://platform.deepseek.com/api_keys",
        "label": "DeepSeek API keys",
    },
    "xai_keys": {
        "url": "https://console.x.ai/",
        "label": "xAI / Grok console",
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
    "claude_code": {
        "url": "https://code.claude.com/docs/en/overview",
        "label": "Claude Code docs / login",
    },
    "codex": {
        "url": "https://chatgpt.com/codex",
        "label": "ChatGPT Codex",
    },
    "codex_cli": {
        "url": "https://github.com/openai/codex",
        "label": "Codex CLI",
    },
    "vit_kluis": {"app": "VIT Kluis", "label": "VIT Kluis", "url": "https://secure.vitwerkplek.nl"},
    "vit_mail": {"app": "VIT Mail", "label": "VIT Mail"},
    "vit_backup": {"app": "VIT Backup", "label": "VIT Backup"},
    "vit_office": {"app": "VIT Office", "label": "VIT Office"},
    "vit_pdf": {"app": "VIT PDF", "label": "VIT PDF"},
    "vit_remote": {"app": "VIT Remote Manager", "label": "VIT Remote Manager"},
    "kluis_web": {
        "url": "https://secure.vitwerkplek.nl",
        "label": "VIT Kluis web (Bitwarden/Vaultwarden)",
    },
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

    ops_env = Path.home() / ".config/vit/geheimen/ops.env"
    ops_configured: dict[str, bool] = {}
    try:
        from vit_ai_hub.ops.client import configured_services, ensure_ops_env_template

        ensure_ops_env_template()
        ops_configured = configured_services()
    except Exception:
        ops_configured = {}

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
        "ops_env": str(ops_env),
        "ops_env_exists": ops_env.is_file(),
        "ops_configured": ops_configured,
        "ops_ready": any(ops_configured.values()) if ops_configured else False,
    }
    if include_token:
        tok = secrets.get("VIT_GATEWAY_TOKEN", "")
        if tok and "change-me" not in tok:
            out["gateway_token"] = tok
    return out


def ensure_gateway_token() -> dict[str, Any]:
    """Maak VIT_GATEWAY_TOKEN aan als die ontbreekt."""
    existing = _read_secret_map().get("VIT_GATEWAY_TOKEN", "").strip()
    if existing and "change-me" not in existing:
        return {"ok": True, "created": False, "token": existing}
    token = "vit-" + secrets.token_hex(16)
    save_secrets({"VIT_GATEWAY_TOKEN": token})
    return {"ok": True, "created": True, "token": token}


def ensure_default_models() -> dict[str, Any]:
    """Zet verstandige defaults voor lokaal + Nano Banana als nog leeg."""
    cur = _read_secret_map()
    patch: dict[str, str] = {}
    if not (cur.get("VIT_LOCAL_LIGHT_MODEL") or "").strip():
        patch["VIT_LOCAL_LIGHT_MODEL"] = DEFAULT_LIGHT_MODEL
    if not (cur.get("VIT_NANO_BANANA_MODEL") or "").strip():
        patch["VIT_NANO_BANANA_MODEL"] = DEFAULT_BANANA_MODEL
    if patch:
        save_secrets(patch)
    return {"ok": True, "applied": patch, "current": {**{k: cur.get(k, "") for k in ("VIT_LOCAL_LIGHT_MODEL", "VIT_NANO_BANANA_MODEL")}, **patch}}


def export_continue_config(*, token: str | None = None) -> dict[str, Any]:
    """Schrijf Continue.dev config → hub (Cursor-exit / OpenAI-compat)."""
    tok = (token or "").strip()
    if not tok:
        tok = _read_secret_map().get("VIT_GATEWAY_TOKEN", "").strip() or "vit-local"
    dest = Path.home() / ".continue" / "config.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    cfg = {
        "models": [
            {
                "title": "VIT AI Hub (auto)",
                "provider": "openai",
                "model": "vit/auto",
                "apiBase": HUB_BASE,
                "apiKey": tok,
            },
            {
                "title": "VIT local light",
                "provider": "openai",
                "model": "vit/local-light",
                "apiBase": HUB_BASE,
                "apiKey": tok,
            },
        ],
        "tabAutocompleteModel": {
            "title": "VIT autocomplete",
            "provider": "openai",
            "model": "vit/local-light",
            "apiBase": HUB_BASE,
            "apiKey": tok,
        },
        "allowAnonymousTelemetry": False,
    }
    dest.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(dest)}


def wire_cursor_settings(*, token: str | None = None) -> dict[str, Any]:
    """Best-effort: Cursor User settings + hub-hint bestand."""
    tok = (token or "").strip() or _read_secret_map().get("VIT_GATEWAY_TOKEN", "").strip() or "vit-local"
    written: list[str] = []
    errors: list[str] = []

    hint_dir = Path.home() / ".config" / "vit"
    hint_dir.mkdir(parents=True, exist_ok=True)
    hint = {
        "openai_compatible_base_url": HUB_BASE,
        "api_key": tok,
        "models": ["vit/auto", "vit/max", "vit/local-light"],
        "cursor": {
            "settings": "Cursor → Settings → Models → OpenAI API Key + Override OpenAI Base URL",
            "base_url": HUB_BASE,
            "api_key": tok,
        },
    }
    hint_path = hint_dir / "cursor-hub.json"
    hint_path.write_text(json.dumps(hint, indent=2) + "\n", encoding="utf-8")
    written.append(str(hint_path))

    # Merge into Cursor settings.json when present (macOS + linux paths)
    candidates = [
        Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "settings.json",
        Path.home() / ".config" / "Cursor" / "User" / "settings.json",
    ]
    patch = {
        "cursor.openai.baseUrl": HUB_BASE,
        "cursor.general.disableHttp2": True,
    }
    for settings_path in candidates:
        try:
            if not settings_path.parent.is_dir():
                continue
            data: dict[str, Any] = {}
            if settings_path.is_file():
                raw = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
                if isinstance(raw, dict):
                    data = raw
            data.update(patch)
            # Don't overwrite an existing custom OpenAI key blindly if set to something else
            if not data.get("cursor.openai.apiKey"):
                data["cursor.openai.apiKey"] = tok
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            written.append(str(settings_path))
            break
        except Exception as exc:
            errors.append(f"{settings_path}: {exc}")

    return {"ok": True, "written": written, "errors": errors, "base_url": HUB_BASE}


def bootstrap_all(*, open_a11y: bool = False, mark_complete: bool = True) -> dict[str, Any]:
    """Één call: VOLLEDIGE migratie + sync (+ optioneel setup-complete)."""
    from vit_ai_hub.importing.full_migrate import migrate_everything
    from vit_ai_hub.importing.sync import start_sync, sync_once

    migration = migrate_everything(promote_skills=True)
    knowledge = (migration.get("knowledge_import") or {}).get("knowledge") or {}
    sync_result = sync_once(include_ax=False)
    sync_ctl = start_sync(interval_sec=300, include_ax=False)
    if open_a11y:
        open_accessibility_settings()
    done = mark_setup_complete() if mark_complete else {"ok": False, "skipped": True}
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


def install_auto(
    *,
    secrets: dict[str, str] | None = None,
    open_a11y: bool = False,
    mark_complete: bool = False,
) -> dict[str, Any]:
    """Volledige auto-install: token, defaults, bridge, migrate, Cursor-wire.

    Gebruiker hoeft alleen in te loggen (Claude / ChatGPT / Cursor / Gemini).
    """
    steps: dict[str, Any] = {}
    if secrets:
        steps["secrets"] = save_secrets(secrets)
    steps["gateway_token"] = ensure_gateway_token()
    steps["defaults"] = ensure_default_models()
    token = steps["gateway_token"].get("token") or ""

    try:
        from vit_ai_hub.bridge import bootstrap_bridge

        steps["bridge"] = bootstrap_bridge()
    except Exception as exc:
        steps["bridge"] = {"ok": False, "error": str(exc)}

    try:
        steps["migrate"] = bootstrap_all(open_a11y=open_a11y, mark_complete=False)
    except Exception as exc:
        steps["migrate"] = {"ok": False, "error": str(exc)}

    try:
        steps["continue"] = export_continue_config(token=token)
    except Exception as exc:
        steps["continue"] = {"ok": False, "error": str(exc)}

    try:
        steps["cursor"] = wire_cursor_settings(token=token)
    except Exception as exc:
        steps["cursor"] = {"ok": False, "error": str(exc)}

    try:
        from vit_ai_hub.ops.client import ensure_ops_env_template

        ensure_ops_env_template()
        steps["ops_template"] = {"ok": True}
    except Exception as exc:
        steps["ops_template"] = {"ok": False, "error": str(exc)}

    if mark_complete:
        steps["setup"] = mark_setup_complete()

    probe: dict[str, Any] = {}
    try:
        probe = probe_providers()
    except Exception:
        probe = {}

    ok = bool(
        steps.get("gateway_token", {}).get("ok")
        and (steps.get("migrate", {}).get("ok") or steps.get("bridge", {}).get("ok"))
    )
    return {
        "ok": ok,
        "steps": steps,
        "probe": {
            "bridge_up": probe.get("bridge_up"),
            "claude_logged_in": probe.get("claude_logged_in"),
            "chatgpt_logged_in": probe.get("chatgpt_logged_in"),
            "gemini_key": probe.get("gemini_key"),
            "bridge_key": probe.get("bridge_key"),
            "lmstudio_up": probe.get("lmstudio_up"),
        },
        "gateway_token": token if token else None,
        "cursor_base_url": HUB_BASE,
        "user_actions_left": [
            "Log in bij Claude (wizard-knop)",
            "Log in bij ChatGPT (wizard-knop)",
            "Open Cursor — hub-URL/token staan klaar",
            "Log in bij Gemini / plak API key (beelden)",
        ],
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
    # Prefer desktop app when both app+url (e.g. Kluis); fall back to web
    if info.get("app"):
        r = subprocess.run(["open", "-a", info["app"]], capture_output=True, text=True)
        if r.returncode == 0:
            return {
                "ok": True,
                "app": info["app"],
                "label": info.get("label"),
            }
        if info.get("url"):
            subprocess.run(["open", info["url"]], check=False)
            return {
                "ok": True,
                "opened": info["url"],
                "label": info.get("label"),
                "hint": f"{info['app']} niet gevonden; web geopend",
            }
        return {
            "ok": False,
            "app": info["app"],
            "label": info.get("label"),
            "error": (r.stderr or "").strip() or "app niet gevonden",
        }
    if info.get("url"):
        subprocess.run(["open", info["url"]], check=False)
        return {"ok": True, "opened": info["url"], "label": info.get("label")}
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
    vit_suite: dict[str, Any] = {}
    try:
        from vit_ai_hub.tools.vit_apps import list_vit_apps

        vit_suite = list_vit_apps()
    except Exception:
        vit_suite = {}

    gemini = bool(secrets.get("GEMINI_API_KEY") or secrets.get("GOOGLE_API_KEY"))
    bridge_detail: dict[str, Any] = {}
    try:
        from vit_ai_hub.bridge import bridge_status

        bridge_detail = bridge_status()
        bridge_up = bridge_up or bool(bridge_detail.get("running"))
    except Exception:
        bridge_detail = {}
    return {
        **status,
        "bridge_up": bridge_up,
        "omniroute_up": omni_up,
        "openrouter_key": bool(secrets.get("OPENROUTER_API_KEY")),
        "deepseek_key": bool(secrets.get("DEEPSEEK_API_KEY")),
        "xai_key": bool(secrets.get("XAI_API_KEY")),
        "gemini_key": gemini,
        "bridge_key": bool(secrets.get("BRIDGE_API_KEY") or bridge_detail.get("api_key_configured")),
        "bridge": bridge_detail,
        "claude_logged_in": bool(bridge_detail.get("claude_logged_in")),
        "chatgpt_logged_in": bool(bridge_detail.get("chatgpt_logged_in")),
        "cursor_base_url": "http://127.0.0.1:8787/v1",
        "vit_apps_installed": vit_suite.get("installed", 0),
        "vit_apps_count": vit_suite.get("count", 0),
        "vit_apps": [
            {"id": a["id"], "name": a["name"], "installed": a["installed"], "web": a.get("web")}
            for a in (vit_suite.get("apps") or [])
            if a["id"] in {"mail", "kluis", "backup", "office", "pdf", "remote"}
        ],
    }
