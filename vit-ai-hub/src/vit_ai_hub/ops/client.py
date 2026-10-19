"""Secrets + HTTP/SSH helpers voor VIT ops (Proxmox, Nextcloud, …)."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

OPS_ENV = Path.home() / ".config/vit/geheimen/ops.env"
OPS_ENV_EXAMPLE_KEYS = [
    "PVE_HOSTS",
    "PVE_TOKEN_ID",
    "PVE_TOKEN_SECRET",
    "PVE_VERIFY_SSL",
    "NEXTCLOUD_URL",
    "NEXTCLOUD_USER",
    "NEXTCLOUD_APP_PASSWORD",
    "GROMOX_SSH",
    "GROMOX_URL",
    "MAILCOW_URL",
    "MAILCOW_API_KEY",
    "SERVICEHUB_URL",
    "SERVICEHUB_TOKEN",
    "UNIFI_URL",
    "UNIFI_USER",
    "UNIFI_PASSWORD",
    "UNIFI_API_KEY",
    "AUTOMATION_HUB_SSH",
    "VIT_BACKUP_URL",
    "VIT_BACKUP_TOKEN",
    "SSH_IDENTITY_FILE",
]


def load_ops_env() -> dict[str, str]:
    out: dict[str, str] = {}
    # also allow process env
    for k in OPS_ENV_EXAMPLE_KEYS:
        if os.environ.get(k):
            out[k] = os.environ[k]
    if OPS_ENV.is_file():
        for line in OPS_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip("'").strip('"')
    return out


def redact(obj: Any) -> Any:
    """Strip secret-looking values from nested structures."""
    if isinstance(obj, dict):
        bad = ("password", "secret", "token", "authorization", "api_key", "apikey", "cookie")
        return {
            k: ("***" if any(b in k.lower() for b in bad) else redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 40 and any(x in obj.lower() for x in ("eyj", "sk-", "pve:")):
        return obj[:6] + "***"
    return obj


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    auth: tuple[str, str] | None = None,
    verify: bool = True,
    timeout: float = 20.0,
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout, verify=verify, follow_redirects=True) as client:
            resp = client.request(method, url, headers=headers or {}, json=json_body, auth=auth)
            ctype = resp.headers.get("content-type", "")
            data: Any
            if "json" in ctype:
                data = resp.json()
            else:
                data = {"text": resp.text[:8000]}
            return {
                "ok": resp.status_code < 400,
                "status": resp.status_code,
                "url": url,
                "data": redact(data),
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


def ssh_run(target: str, command: str, *, timeout: int = 30) -> dict[str, Any]:
    """Allowlisted SSH: alleen host uit ops.env targets, BatchMode."""
    env = load_ops_env()
    allowed = set()
    for key in ("GROMOX_SSH", "AUTOMATION_HUB_SSH"):
        if env.get(key):
            allowed.add(env[key].strip())
    # also allow host part
    allowed_hosts = set()
    for a in list(allowed):
        if "@" in a:
            allowed_hosts.add(a.split("@", 1)[1])
        else:
            allowed_hosts.add(a)
    host = target.split("@", 1)[-1]
    if target not in allowed and host not in allowed_hosts:
        return {"ok": False, "error": f"SSH target niet in allowlist: {target}"}
    # block dangerous shell chains
    if any(x in command for x in (";", "&&", "||", "`", "$(", "\n", "rm -rf", "mkfs", "dd ")):
        return {"ok": False, "error": "commando geweigerd (shell/destructief)"}
    identity = env.get("SSH_IDENTITY_FILE") or ""
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=8",
    ]
    if identity and Path(identity).expanduser().is_file():
        cmd.extend(["-i", str(Path(identity).expanduser())])
    cmd.extend([target, command])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ssh timeout", "target": target}
    except FileNotFoundError:
        return {"ok": False, "error": "ssh niet geïnstalleerd"}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "target": target,
        "stdout": (proc.stdout or "")[-12000:],
        "stderr": (proc.stderr or "")[-4000:],
    }


def configured_services() -> dict[str, bool]:
    e = load_ops_env()
    return {
        "proxmox": bool(e.get("PVE_HOSTS") and e.get("PVE_TOKEN_ID") and e.get("PVE_TOKEN_SECRET")),
        "nextcloud": bool(e.get("NEXTCLOUD_URL") and e.get("NEXTCLOUD_USER") and e.get("NEXTCLOUD_APP_PASSWORD")),
        "gromox": bool(e.get("GROMOX_SSH") or e.get("GROMOX_URL")),
        "mailcow": bool(e.get("MAILCOW_URL") and e.get("MAILCOW_API_KEY")),
        "servicehub": bool(e.get("SERVICEHUB_URL")),
        "unifi": bool(e.get("UNIFI_URL") and (e.get("UNIFI_API_KEY") or e.get("UNIFI_USER"))),
        "automation_hub": bool(e.get("AUTOMATION_HUB_SSH")),
        "vit_backup": bool(e.get("VIT_BACKUP_URL")),
    }


def ensure_ops_env_template() -> dict[str, Any]:
    OPS_ENV.parent.mkdir(parents=True, exist_ok=True)
    if OPS_ENV.is_file():
        return {"ok": True, "path": str(OPS_ENV), "created": False}
    template = """# VIT AI Hub — ops secrets (chmod 600). Nooit committen.
# Alleen localhost-hub leest dit.

# Proxmox cluster (comma-separated)
PVE_HOSTS=https://10.20.1.123:8006,https://10.20.1.20:8006
PVE_TOKEN_ID=vit@pve!hub
PVE_TOKEN_SECRET=
PVE_VERIFY_SSL=false

# Nextcloud
NEXTCLOUD_URL=https://cloud.example.nl
NEXTCLOUD_USER=
NEXTCLOUD_APP_PASSWORD=

# Gromox (SSH jump of HTTP health)
GROMOX_SSH=
GROMOX_URL=

# Mailcow
MAILCOW_URL=https://eas.vitwerkplek.nl
MAILCOW_API_KEY=

# ServiceHub
SERVICEHUB_URL=
SERVICEHUB_TOKEN=

# UniFi OS Server
UNIFI_URL=https://10.20.1.40:11443
UNIFI_USER=
UNIFI_PASSWORD=
UNIFI_API_KEY=

# automation-hub
AUTOMATION_HUB_SSH=

# VIT Backup API (optioneel)
VIT_BACKUP_URL=
VIT_BACKUP_TOKEN=

# Optionele SSH key
SSH_IDENTITY_FILE=
"""
    OPS_ENV.write_text(template, encoding="utf-8")
    os.chmod(OPS_ENV, 0o600)
    return {"ok": True, "path": str(OPS_ENV), "created": True}
