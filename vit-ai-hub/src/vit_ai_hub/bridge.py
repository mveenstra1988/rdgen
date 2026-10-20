"""Claude/ChatGPT abo-bridge (CLIProxyAPI): install, config, OAuth-login, start.

Gebruiker logt alleen in via browser; hub genereert keys, config en account-pool.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any

BRIDGE_HOME = Path.home() / ".local" / "vit" / "bridge"
BRIDGE_BIN_NAME = "cli-proxy-api"
CONFIG_PATH = BRIDGE_HOME / "config.yaml"
AUTH_DIR = Path.home() / ".cli-proxy-api"
PID_FILE = BRIDGE_HOME / "bridge.pid"
LOG_FILE = BRIDGE_HOME / "bridge.log"
DEFAULT_PORT = 8317
DEFAULT_BASE = f"http://127.0.0.1:{DEFAULT_PORT}/v1"
RELEASE_API = "https://api.github.com/repos/router-for-me/CLIProxyAPI/releases/latest"


def _darwin() -> bool:
    return platform.system() == "Darwin"


def _arch_asset() -> str:
    mach = platform.machine().lower()
    if mach in {"arm64", "aarch64"}:
        return "darwin_aarch64"
    return "darwin_amd64"


def bridge_binary() -> Path | None:
    for cand in (
        BRIDGE_HOME / BRIDGE_BIN_NAME,
        BRIDGE_HOME / "CLIProxyAPI",
        Path("/usr/local/bin") / BRIDGE_BIN_NAME,
        Path.home() / "bin" / BRIDGE_BIN_NAME,
    ):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    which = shutil.which(BRIDGE_BIN_NAME) or shutil.which("CLIProxyAPI")
    return Path(which) if which else None


def _read_config_key() -> str | None:
    if not CONFIG_PATH.is_file():
        return None
    text = CONFIG_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and "api-keys" not in line.lower():
            # list item under api-keys
            val = line[2:].strip().strip("\"'")
            if val and not val.startswith("#"):
                return val
    # simpler parse
    in_keys = False
    for line in text.splitlines():
        if line.strip().startswith("api-keys:"):
            in_keys = True
            continue
        if in_keys:
            if line.strip().startswith("-"):
                return line.split("-", 1)[1].strip().strip("\"'")
            if line.strip() and not line.startswith(" "):
                break
    return None


def ensure_config(*, force_new_key: bool = False) -> dict[str, Any]:
    BRIDGE_HOME.mkdir(parents=True, exist_ok=True)
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    key = None if force_new_key else _read_config_key()
    if not key:
        key = "vit-" + secrets.token_hex(24)
    cfg = f"""# VIT AI Hub — gegenereerd, niet handmatig nodig
host: "127.0.0.1"
port: {DEFAULT_PORT}
auth-dir: "{AUTH_DIR}"
api-keys:
  - "{key}"
debug: false
request-retry: 3
routing:
  strategy: "round-robin"
"""
    CONFIG_PATH.write_text(cfg, encoding="utf-8")
    return {"ok": True, "path": str(CONFIG_PATH), "api_key": key, "port": DEFAULT_PORT}


def wire_hub_secrets(api_key: str) -> dict[str, Any]:
    """Schrijf BRIDGE_* naar secrets + accounts pool."""
    from vit_ai_hub.setup_api import save_secrets
    from vit_ai_hub.pool.store import add_account

    saved = save_secrets(
        {
            "BRIDGE_BASE_URL": DEFAULT_BASE,
            "BRIDGE_API_KEY": api_key,
        }
    )
    acc = add_account(
        "bridge",
        {
            "id": "bridge-primary",
            "label": "Claude/ChatGPT bridge",
            "base_url": DEFAULT_BASE,
            "api_key": api_key,
            "tags": ["claude", "chatgpt", "codex"],
            "enabled": True,
        },
    )
    return {"secrets": saved, "account": acc}


def download_bridge() -> dict[str, Any]:
    """Download CLIProxyAPI darwin binary (alleen macOS)."""
    if not _darwin():
        return {
            "ok": False,
            "error": "Bridge-binary download alleen op macOS",
            "hint": "Op Linux CI: mock/skip. Op Mac: wizard installeert automatisch.",
        }
    BRIDGE_HOME.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(RELEASE_API, timeout=30) as resp:
            release = json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": f"releases ophalen mislukt: {exc}"}
    want = _arch_asset()
    asset = None
    for a in release.get("assets") or []:
        name = a.get("name") or ""
        if want in name and name.endswith(".tar.gz"):
            asset = a
            break
    if not asset:
        return {"ok": False, "error": f"geen asset voor {want}", "tag": release.get("tag_name")}
    url = asset["browser_download_url"]
    tgz = BRIDGE_HOME / asset["name"]
    try:
        urllib.request.urlretrieve(url, tgz)
    except Exception as exc:
        return {"ok": False, "error": f"download mislukt: {exc}"}
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            tf.extractall(BRIDGE_HOME)
    except Exception as exc:
        return {"ok": False, "error": f"uitpakken mislukt: {exc}"}
    # find binary
    found = None
    for p in BRIDGE_HOME.rglob("*"):
        if p.is_file() and p.name in {BRIDGE_BIN_NAME, "CLIProxyAPI", "cli-proxy-api"}:
            found = p
            break
    if not found:
        return {"ok": False, "error": "binary niet in archief"}
    dest = BRIDGE_HOME / BRIDGE_BIN_NAME
    if found.resolve() != dest.resolve():
        shutil.copy2(found, dest)
    dest.chmod(0o755)
    return {
        "ok": True,
        "path": str(dest),
        "version": release.get("tag_name"),
        "asset": asset["name"],
    }


def ensure_installed() -> dict[str, Any]:
    existing = bridge_binary()
    if existing:
        return {"ok": True, "path": str(existing), "installed": True, "downloaded": False}
    dl = download_bridge()
    if not dl.get("ok"):
        return dl
    return {**dl, "installed": True, "downloaded": True}


def is_running() -> bool:
    try:
        import httpx

        r = httpx.get(f"http://127.0.0.1:{DEFAULT_PORT}/v1/models", timeout=1.2)
        return r.status_code < 500
    except Exception:
        return False


def start_bridge() -> dict[str, Any]:
    if is_running():
        return {"ok": True, "already": True, "port": DEFAULT_PORT}
    bin_path = bridge_binary()
    if not bin_path:
        inst = ensure_installed()
        if not inst.get("ok"):
            return inst
        bin_path = bridge_binary()
    if not bin_path:
        return {"ok": False, "error": "bridge binary ontbreekt"}
    cfg = ensure_config()
    wire_hub_secrets(cfg["api_key"])
    BRIDGE_HOME.mkdir(parents=True, exist_ok=True)
    log_f = open(LOG_FILE, "a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [str(bin_path), "-config", str(CONFIG_PATH)],
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(BRIDGE_HOME),
            start_new_session=True,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    # wait briefly
    for _ in range(15):
        time.sleep(0.4)
        if is_running():
            return {
                "ok": True,
                "pid": proc.pid,
                "port": DEFAULT_PORT,
                "base_url": DEFAULT_BASE,
                "api_key_set": True,
            }
    return {
        "ok": True,
        "pid": proc.pid,
        "port": DEFAULT_PORT,
        "hint": "proces gestart; /v1/models nog niet bereikbaar — even wachten",
        "log": str(LOG_FILE),
    }


def stop_bridge() -> dict[str, Any]:
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 15)
            PID_FILE.unlink(missing_ok=True)
            return {"ok": True, "stopped": pid}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    # pkill fallback
    if _darwin():
        subprocess.run(["pkill", "-f", "cli-proxy-api"], check=False)
    return {"ok": True, "stopped": "pkill"}


def _auth_files() -> dict[str, list[str]]:
    claude: list[str] = []
    codex: list[str] = []
    if AUTH_DIR.is_dir():
        for p in AUTH_DIR.glob("*.json"):
            name = p.name.lower()
            if "claude" in name or "anthropic" in name:
                claude.append(str(p))
            elif "codex" in name or "openai" in name or "chatgpt" in name:
                codex.append(str(p))
    return {"claude": claude, "codex": codex}


def start_login(provider: str) -> dict[str, Any]:
    """Start OAuth login (opent browser op macOS). provider=claude|chatgpt|codex"""
    prov = (provider or "").strip().lower()
    if prov in {"chatgpt", "gpt", "openai"}:
        prov = "codex"
    if prov not in {"claude", "codex"}:
        return {"ok": False, "error": "provider=claude of chatgpt/codex"}
    if not _darwin():
        return {
            "ok": False,
            "error": "OAuth-login alleen op macOS",
            "hint": "Op je Mac: wizard knop Log in bij Claude / ChatGPT",
        }
    # ensure running config + binary
    ens = ensure_installed()
    if not ens.get("ok") and not bridge_binary():
        return ens
    cfg = ensure_config()
    wire_hub_secrets(cfg["api_key"])
    bin_path = bridge_binary()
    if not bin_path:
        return {"ok": False, "error": "bridge niet geïnstalleerd"}
    flag = "--claude-login" if prov == "claude" else "--codex-login"
    # CLIProxyAPI accepts -config with login flags
    cmd = [str(bin_path), "-config", str(CONFIG_PATH), flag]
    log_f = open(LOG_FILE, "a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(BRIDGE_HOME),
            start_new_session=True,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "provider": prov,
        "pid": proc.pid,
        "hint": (
            "Browser opent voor inloggen. Klaar? Klik «Status vernieuwen». "
            "Daarna start de hub de bridge automatisch."
        ),
        "log": str(LOG_FILE),
    }


def bootstrap_bridge() -> dict[str, Any]:
    """Één call: install + config + secrets + start (na OAuth of voor)."""
    steps: dict[str, Any] = {}
    steps["install"] = ensure_installed()
    cfg = ensure_config()
    steps["config"] = {"path": cfg["path"], "port": cfg["port"]}
    steps["wire"] = wire_hub_secrets(cfg["api_key"])
    steps["start"] = start_bridge()
    steps["status"] = bridge_status()
    steps["ok"] = bool(steps["status"].get("configured"))
    return steps


def bridge_status() -> dict[str, Any]:
    bin_path = bridge_binary()
    auth = _auth_files()
    key = _read_config_key()
    running = is_running()
    return {
        "ok": True,
        "darwin": _darwin(),
        "installed": bool(bin_path),
        "binary": str(bin_path) if bin_path else None,
        "config": str(CONFIG_PATH) if CONFIG_PATH.is_file() else None,
        "api_key_configured": bool(key),
        "base_url": DEFAULT_BASE,
        "port": DEFAULT_PORT,
        "running": running,
        "claude_logged_in": bool(auth["claude"]),
        "chatgpt_logged_in": bool(auth["codex"]),
        "auth_files": auth,
        "configured": bool(bin_path and key),
        "ready": bool(running and (auth["claude"] or auth["codex"])),
        "hint": (
            "Klaar voor gebruik."
            if running and (auth["claude"] or auth["codex"])
            else (
                "Log in bij Claude en/of ChatGPT via de wizard-knoppen."
                if not (auth["claude"] or auth["codex"])
                else "Bridge starten…"
            )
        ),
    }
