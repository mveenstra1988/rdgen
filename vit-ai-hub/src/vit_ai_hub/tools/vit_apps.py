"""VIT-suite desktop-integratie: Mail, Kluis, Backup, Office, PDF, Remote Manager, …"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

# Canonical VIT desktop apps (aliases → open -a namen / path-globs)
VIT_SUITE: dict[str, dict[str, Any]] = {
    "mail": {
        "id": "mail",
        "name": "VIT Mail",
        "aliases": ["vit mail", "vitmail", "mail vit"],
        "app_names": ["VIT Mail", "VITMail", "vit-mail"],
        "paths": ["VIT Mail.app", "VITMail.app"],
        "url_schemes": ["mailto:"],
        "web": None,
        "role": "E-mail client (Tauri)",
        "actions": {
            "open": None,
            "compose": "mailto:{to}?subject={subject}&body={body}",
        },
    },
    "kluis": {
        "id": "kluis",
        "name": "VIT Kluis",
        "aliases": ["vit kluis", "kluis", "vault", "bitwarden", "vaultwarden", "wachtwoorden"],
        "app_names": ["VIT Kluis", "VITKluis", "VIT-Kluis"],
        "paths": ["VIT Kluis.app", "VITKluis.app"],
        "url_schemes": ["bitwarden://"],
        "web": "https://secure.vitwerkplek.nl",
        "role": "Password vault (Vaultwarden/Bitwarden-compatibel)",
        "actions": {
            "open": None,
            "web": "https://secure.vitwerkplek.nl",
        },
    },
    "backup": {
        "id": "backup",
        "name": "VIT Backup",
        "aliases": ["vit backup", "backup", "schijfkluis", "vit-schijfkluis"],
        "app_names": ["VIT Backup", "VIT-Backup", "VIT Schijfkluis", "VIT-Schijfkluis"],
        "paths": ["VIT Backup.app", "VIT-Schijfkluis.app", "VIT Schijfkluis.app"],
        "url_schemes": [],
        "web": None,
        "role": "Backup / schijfkluis client",
        "actions": {"open": None},
        "ops_tool": "vit_backup_status",
    },
    "office": {
        "id": "office",
        "name": "VIT Office",
        "aliases": ["vit office", "office", "vit-office", "documenten"],
        "app_names": ["VIT Office", "VITOffice", "vit-office"],
        "paths": ["VIT Office.app", "VITOffice.app"],
        "url_schemes": [],
        "web": None,
        "role": "Office / documenten",
        "actions": {"open": None},
    },
    "pdf": {
        "id": "pdf",
        "name": "VIT PDF",
        "aliases": ["vit pdf", "pdf", "vit-pdf"],
        "app_names": ["VIT PDF", "VITPDF", "vit-pdf"],
        "paths": ["VIT PDF.app", "VITPDF.app"],
        "url_schemes": [],
        "web": None,
        "role": "PDF lezen/bewerken",
        "actions": {"open": None, "open_file": "file"},
    },
    "remote": {
        "id": "remote",
        "name": "VIT Remote Manager",
        "aliases": [
            "vit remote",
            "remote manager",
            "remote",
            "vit-remote",
            "vit remote manager",
            "rdp",
            "remote desktop",
        ],
        "app_names": [
            "VIT Remote Manager",
            "VIT Remote",
            "VITRemoteManager",
            "Remote Manager",
        ],
        "paths": [
            "VIT Remote Manager.app",
            "VIT Remote.app",
            "VITRemoteManager.app",
        ],
        "url_schemes": [],
        "web": None,
        "role": "Remote desktop / beheer",
        "actions": {"open": None},
    },
    "menubalk": {
        "id": "menubalk",
        "name": "VIT Menubalk",
        "aliases": ["vit menubalk", "menubalk", "menubar"],
        "app_names": ["VIT Menubalk", "VITMenubalk"],
        "paths": ["VIT Menubalk.app"],
        "url_schemes": [],
        "web": None,
        "role": "Menubar / Dock helper",
        "actions": {"open": None},
    },
    "rekenbladen": {
        "id": "rekenbladen",
        "name": "VIT Rekenbladen",
        "aliases": ["vit rekenbladen", "rekenbladen", "spreadsheet", "sheets"],
        "app_names": ["VIT Rekenbladen", "VITRekenbladen"],
        "paths": ["VIT Rekenbladen.app"],
        "url_schemes": [],
        "web": None,
        "role": "Spreadsheets",
        "actions": {"open": None},
    },
    "aihub": {
        "id": "aihub",
        "name": "VIT AI Hub",
        "aliases": ["vit ai hub", "ai hub", "aihub"],
        "app_names": ["VIT AI Hub"],
        "paths": ["VIT AI Hub.app"],
        "url_schemes": [],
        "web": "http://127.0.0.1:8787",
        "role": "Deze hub",
        "actions": {"open": None, "web": "http://127.0.0.1:8787"},
    },
}


def _darwin() -> bool:
    return os.uname().sysname == "Darwin"


def _app_search_roots() -> list[Path]:
    home = Path.home()
    return [
        home / "Applications",
        Path("/Applications"),
        home / "Desktop",
        home / "Downloads",
    ]


def _find_installed(entry: dict[str, Any]) -> dict[str, Any]:
    found_paths: list[str] = []
    for base in _app_search_roots():
        if not base.is_dir():
            continue
        for pname in entry.get("paths") or []:
            cand = base / pname
            if cand.is_dir():
                found_paths.append(str(cand))
        # fuzzy: any VIT* matching name words
        name_token = (entry.get("name") or "").replace("VIT ", "").strip()
        if name_token:
            for p in base.glob("VIT*.app"):
                if name_token.lower() in p.name.lower() and str(p) not in found_paths:
                    found_paths.append(str(p))
    running = False
    if _darwin() and found_paths:
        r = subprocess.run(
            ["pgrep", "-if", entry.get("name") or "VIT"],
            capture_output=True,
            text=True,
        )
        running = r.returncode == 0 and bool((r.stdout or "").strip())
    return {
        "installed": bool(found_paths),
        "paths": found_paths[:5],
        "running": running,
    }


def resolve_vit_app(query: str) -> dict[str, Any] | None:
    q = (query or "").strip().lower()
    if not q:
        return None
    if q in VIT_SUITE:
        return VIT_SUITE[q]
    for entry in VIT_SUITE.values():
        if q == entry["id"] or q == entry["name"].lower():
            return entry
        for a in entry.get("aliases") or []:
            if q == a or q in a or a in q:
                return entry
    return None


def list_vit_apps() -> dict[str, Any]:
    items = []
    for entry in VIT_SUITE.values():
        st = _find_installed(entry)
        items.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "role": entry["role"],
                "aliases": entry.get("aliases") or [],
                "installed": st["installed"],
                "paths": st["paths"],
                "running": st["running"],
                "web": entry.get("web"),
                "ops_tool": entry.get("ops_tool"),
            }
        )
    installed_n = sum(1 for i in items if i["installed"])
    return {
        "ok": True,
        "suite": "VIT",
        "count": len(items),
        "installed": installed_n,
        "apps": items,
        "hint": (
            "Gebruik vit_app_open met id (mail/kluis/backup/office/pdf/remote). "
            "Kluis = Vaultwarden @ secure.vitwerkplek.nl (Bitwarden-compat)."
        ),
    }


def open_vit_app(
    app: str,
    *,
    action: str = "open",
    to: str = "",
    subject: str = "",
    body: str = "",
    path: str = "",
    prefer_web: bool = False,
) -> dict[str, Any]:
    entry = resolve_vit_app(app)
    if not entry:
        return {
            "ok": False,
            "error": f"Onbekende VIT-app: {app}",
            "known": list(VIT_SUITE.keys()),
        }
    act = (action or "open").strip().lower()
    if not _darwin() and act != "web":
        return {"ok": False, "error": "App openen alleen op macOS", "app": entry["name"]}

    # Web / vault
    if act == "web" or prefer_web:
        url = entry.get("web") or (entry.get("actions") or {}).get("web")
        if not url:
            return {"ok": False, "error": "Geen web-URL voor deze app", "app": entry["name"]}
        r = subprocess.run(["open", url], capture_output=True, text=True) if _darwin() else None
        return {
            "ok": True if not _darwin() else (r.returncode == 0 if r else False),
            "app": entry["name"],
            "mode": "web",
            "url": url,
        }

    # Compose via mailto (Mail)
    if act == "compose" and entry["id"] == "mail":
        from urllib.parse import quote

        mail_to = quote(to or "", safe="@+.-_")
        qs = []
        if subject:
            qs.append(f"subject={quote(subject)}")
        if body:
            qs.append(f"body={quote(body)}")
        url = f"mailto:{mail_to}"
        if qs:
            url += "?" + "&".join(qs)
        # Prefer VIT Mail app if installed
        st = _find_installed(entry)
        if st["installed"] and st["paths"]:
            r = subprocess.run(["open", "-a", entry["app_names"][0], url], capture_output=True, text=True)
            if r.returncode == 0:
                return {"ok": True, "app": entry["name"], "mode": "compose", "url": url}
        r = subprocess.run(["open", url], capture_output=True, text=True)
        return {"ok": r.returncode == 0, "app": entry["name"], "mode": "compose", "url": url}

    # Open file in PDF app
    if act in {"open_file", "file"} and path:
        p = Path(path).expanduser()
        if not p.is_file():
            return {"ok": False, "error": f"bestand niet gevonden: {path}"}
        st = _find_installed(entry)
        if st["paths"]:
            r = subprocess.run(["open", "-a", st["paths"][0], str(p)], capture_output=True, text=True)
            if r.returncode == 0:
                return {"ok": True, "app": entry["name"], "mode": "open_file", "path": str(p)}
        r = subprocess.run(["open", str(p)], capture_output=True, text=True)
        return {"ok": r.returncode == 0, "mode": "open_file_default", "path": str(p)}

    # Default: launch app
    for name in entry.get("app_names") or []:
        r = subprocess.run(["open", "-a", name], capture_output=True, text=True)
        if r.returncode == 0:
            return {"ok": True, "app": name, "mode": "app", "id": entry["id"]}
    st = _find_installed(entry)
    for p in st["paths"]:
        r = subprocess.run(["open", p], capture_output=True, text=True)
        if r.returncode == 0:
            return {"ok": True, "app": p, "mode": "path", "id": entry["id"]}

    # Fallback web for kluis
    if entry.get("web"):
        r = subprocess.run(["open", entry["web"]], capture_output=True, text=True)
        return {
            "ok": r.returncode == 0,
            "app": entry["name"],
            "mode": "web_fallback",
            "url": entry["web"],
            "hint": "Desktop-app niet gevonden; web geopend.",
        }
    return {
        "ok": False,
        "error": f"{entry['name']} niet geïnstalleerd",
        "id": entry["id"],
        "tried": entry.get("app_names"),
        "hint": "Installeer de .app in ~/Applications of /Applications",
    }


def vit_app_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "vit_apps_list",
                "description": (
                    "Lijst VIT-suite apps (Mail, Kluis/Bitwarden, Backup, Office, PDF, "
                    "Remote Manager, …) + of ze geïnstalleerd/draaien."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vit_app_open",
                "description": (
                    "Open een VIT-app. app= mail|kluis|backup|office|pdf|remote|menubalk. "
                    "action=open|compose|web|open_file. Kluis = wachtwoorden (Vaultwarden)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app": {"type": "string"},
                        "action": {"type": "string"},
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "path": {"type": "string"},
                        "prefer_web": {"type": "boolean"},
                    },
                    "required": ["app"],
                },
            },
        },
    ]


async def run_vit_app_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "vit_apps_list":
        return json.dumps(list_vit_apps(), ensure_ascii=False)
    if name == "vit_app_open":
        return json.dumps(
            open_vit_app(
                str(arguments.get("app") or ""),
                action=str(arguments.get("action") or "open"),
                to=str(arguments.get("to") or ""),
                subject=str(arguments.get("subject") or ""),
                body=str(arguments.get("body") or ""),
                path=str(arguments.get("path") or ""),
                prefer_web=bool(arguments.get("prefer_web")),
            ),
            ensure_ascii=False,
        )
    return json.dumps({"error": f"onbekende vit app tool {name}"})
