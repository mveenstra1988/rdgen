"""VIT-suite desktop-integratie: Mail, Kluis, Backup, Office, PDF, Remote Manager, …"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

# Canonical VIT desktop apps (aliases → open -a namen / path-globs)
VIT_SUITE: dict[str, dict[str, Any]] = {
    "mail": {
        "id": "mail",
        "name": "VIT Mail",
        "aliases": ["vit mail", "vitmail", "mail vit", "email"],
        "app_names": ["VIT Mail", "VITMail", "vit-mail"],
        "paths": ["VIT Mail.app", "VITMail.app"],
        "url_schemes": ["mailto:", "vitmail:"],
        "web": None,
        "role": "E-mail client (Tauri)",
        "extensions": [".eml", ".msg"],
        "actions": {
            "open": None,
            "compose": "mailto",
            "open_file": "file",
        },
    },
    "kluis": {
        "id": "kluis",
        "name": "VIT Kluis",
        "aliases": ["vit kluis", "kluis", "vault", "bitwarden", "vaultwarden", "wachtwoorden", "passwords"],
        "app_names": ["VIT Kluis", "VITKluis", "VIT-Kluis"],
        "paths": ["VIT Kluis.app", "VITKluis.app"],
        "url_schemes": ["bitwarden://"],
        "web": "https://secure.vitwerkplek.nl",
        "role": "Password vault (Vaultwarden/Bitwarden-compatibel)",
        "actions": {
            "open": None,
            "web": "https://secure.vitwerkplek.nl",
            "search": "bitwarden://password?search={q}",
            "unlock": None,
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
        "actions": {"open": None, "status": "ops"},
        "ops_tool": "vit_backup_status",
    },
    "office": {
        "id": "office",
        "name": "VIT Office",
        "aliases": ["vit office", "office", "vit-office", "documenten", "word", "docx"],
        "app_names": ["VIT Office", "VITOffice", "vit-office"],
        "paths": ["VIT Office.app", "VITOffice.app"],
        "url_schemes": [],
        "web": None,
        "role": "Office / documenten",
        "extensions": [".doc", ".docx", ".odt", ".rtf", ".txt", ".md"],
        "actions": {"open": None, "open_file": "file"},
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
        "extensions": [".pdf"],
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
        "url_schemes": ["rdp://", "vnc://"],
        "web": None,
        "role": "Remote desktop / beheer",
        "actions": {"open": None, "connect": "host"},
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
        "aliases": ["vit rekenbladen", "rekenbladen", "spreadsheet", "sheets", "xlsx", "csv"],
        "app_names": ["VIT Rekenbladen", "VITRekenbladen"],
        "paths": ["VIT Rekenbladen.app"],
        "url_schemes": [],
        "web": None,
        "role": "Spreadsheets",
        "extensions": [".xlsx", ".xls", ".ods", ".csv", ".tsv"],
        "actions": {"open": None, "open_file": "file"},
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

# extension → preferred suite id
_EXT_ROUTE: dict[str, str] = {}
for _eid, _e in VIT_SUITE.items():
    for _ext in _e.get("extensions") or []:
        _EXT_ROUTE[_ext.lower()] = _eid


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


def _custom_suite() -> dict[str, dict[str, Any]]:
    try:
        from vit_ai_hub.extensions import list_custom_apps

        out: dict[str, dict[str, Any]] = {}
        for a in list_custom_apps().get("apps") or []:
            aid = str(a.get("id") or "")
            if not aid:
                continue
            out[aid] = {
                "id": aid,
                "name": a.get("name") or aid,
                "aliases": a.get("aliases") or [],
                "app_names": a.get("app_names") or [a.get("name") or aid],
                "paths": [f"{n}.app" for n in (a.get("app_names") or [])],
                "url_schemes": [],
                "web": a.get("web"),
                "role": a.get("role") or "Custom app",
                "actions": {"open": None, **({"web": a["web"]} if a.get("web") else {})},
                "custom": True,
            }
        return out
    except Exception:
        return {}


def _all_suite() -> dict[str, dict[str, Any]]:
    merged = dict(VIT_SUITE)
    merged.update(_custom_suite())
    return merged


def resolve_vit_app(query: str) -> dict[str, Any] | None:
    q = (query or "").strip().lower()
    if not q:
        return None
    suite = _all_suite()
    if q in suite:
        return suite[q]
    for entry in suite.values():
        if q == entry["id"] or q == entry["name"].lower():
            return entry
        for a in entry.get("aliases") or []:
            if q == a or q in a or a in q:
                return entry
    return None


def list_vit_apps() -> dict[str, Any]:
    items = []
    for entry in _all_suite().values():
        st = _find_installed(entry)
        acts = list((entry.get("actions") or {}).keys())
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
                "actions": acts,
                "extensions": entry.get("extensions") or [],
                "custom": bool(entry.get("custom")),
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
            "vit_app_open (mail/kluis/backup/office/pdf/remote) · "
            "vit_app_handoff path=… (kiest Office/PDF/Mail/Rekenbladen) · "
            "Kluis = Vaultwarden @ secure.vitwerkplek.nl · "
            "Eigen apps via sidebar Uitbreidingen"
        ),
    }


def _open_url(url: str, *, app_name: str | None = None, app_path: str | None = None) -> subprocess.CompletedProcess[str]:
    if app_path:
        return subprocess.run(["open", "-a", app_path, url], capture_output=True, text=True)
    if app_name:
        return subprocess.run(["open", "-a", app_name, url], capture_output=True, text=True)
    return subprocess.run(["open", url], capture_output=True, text=True)


def _open_path_in_app(entry: dict[str, Any], path: Path) -> dict[str, Any]:
    st = _find_installed(entry)
    if st["paths"]:
        r = subprocess.run(["open", "-a", st["paths"][0], str(path)], capture_output=True, text=True)
        if r.returncode == 0:
            return {"ok": True, "app": entry["name"], "mode": "open_file", "path": str(path)}
    for name in entry.get("app_names") or []:
        r = subprocess.run(["open", "-a", name, str(path)], capture_output=True, text=True)
        if r.returncode == 0:
            return {"ok": True, "app": name, "mode": "open_file", "path": str(path)}
    r = subprocess.run(["open", str(path)], capture_output=True, text=True)
    return {
        "ok": r.returncode == 0,
        "mode": "open_file_default",
        "path": str(path),
        "hint": f"{entry['name']} niet gevonden; macOS default gebruikt",
    }


def open_vit_app(
    app: str,
    *,
    action: str = "open",
    to: str = "",
    subject: str = "",
    body: str = "",
    path: str = "",
    query: str = "",
    host: str = "",
    prefer_web: bool = False,
) -> dict[str, Any]:
    entry = resolve_vit_app(app)
    if not entry:
        return {
            "ok": False,
            "error": f"Onbekende VIT-app: {app}",
            "known": list(_all_suite().keys()),
        }
    act = (action or "open").strip().lower()
    if not _darwin() and act not in {"web", "status"}:
        return {"ok": False, "error": "App openen alleen op macOS", "app": entry["name"]}

    # Backup status via ops
    if act == "status" and entry.get("ops_tool"):
        try:
            from vit_ai_hub.ops.providers import run_ops_action

            return {"ok": True, "app": entry["name"], "mode": "status", "result": run_ops_action(entry["ops_tool"])}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "app": entry["name"]}

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

    # Kluis search via Bitwarden URL scheme
    if act == "search" and entry["id"] == "kluis":
        q = query or path or ""
        url = f"bitwarden://password?search={quote(q)}"
        st = _find_installed(entry)
        app_path = st["paths"][0] if st["paths"] else None
        r = _open_url(url, app_path=app_path, app_name=(entry["app_names"] or [None])[0])
        if r.returncode != 0 and entry.get("web"):
            web = entry["web"]
            if q:
                web = f"{web}/#/vault?search={quote(q)}"
            subprocess.run(["open", web], capture_output=True, text=True)
            return {"ok": True, "app": entry["name"], "mode": "web_search", "url": web, "query": q}
        return {"ok": r.returncode == 0, "app": entry["name"], "mode": "search", "url": url, "query": q}

    # Unlock = open app (user unlocks in UI)
    if act == "unlock" and entry["id"] == "kluis":
        out = open_vit_app("kluis", action="open")
        out["mode"] = "unlock"
        out["hint"] = "Kluis geopend — ontgrendel in de app of via Face ID / wachtwoord."
        return out

    # Compose via mailto (Mail)
    if act == "compose" and entry["id"] == "mail":
        mail_to = quote(to or "", safe="@+.-_")
        qs = []
        if subject:
            qs.append(f"subject={quote(subject)}")
        if body:
            qs.append(f"body={quote(body)}")
        url = f"mailto:{mail_to}"
        if qs:
            url += "?" + "&".join(qs)
        st = _find_installed(entry)
        if st["installed"] and st["paths"]:
            r = subprocess.run(["open", "-a", entry["app_names"][0], url], capture_output=True, text=True)
            if r.returncode == 0:
                return {"ok": True, "app": entry["name"], "mode": "compose", "url": url}
        r = subprocess.run(["open", url], capture_output=True, text=True)
        return {"ok": r.returncode == 0, "app": entry["name"], "mode": "compose", "url": url}

    # Remote connect hint
    if act == "connect" and entry["id"] == "remote":
        h = (host or path or query or "").strip()
        launched = open_vit_app("remote", action="open")
        if h:
            for scheme in ("rdp://", "vnc://"):
                url = f"{scheme}{h}"
                r = subprocess.run(["open", url], capture_output=True, text=True)
                if r.returncode == 0:
                    return {
                        "ok": True,
                        "app": entry["name"],
                        "mode": "connect",
                        "host": h,
                        "url": url,
                        "launched": launched.get("ok"),
                    }
            return {
                "ok": launched.get("ok", False),
                "app": entry["name"],
                "mode": "connect_manual",
                "host": h,
                "hint": "Remote Manager geopend — verbind handmatig naar de host.",
            }
        return {**launched, "mode": "connect", "hint": "Geef host= mee voor rdp:// of vnc://"}

    # Reveal in Finder
    if act == "reveal" and path:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": f"pad niet gevonden: {path}"}
        r = subprocess.run(["open", "-R", str(p)], capture_output=True, text=True)
        return {"ok": r.returncode == 0, "mode": "reveal", "path": str(p)}

    # Open file in app
    if act in {"open_file", "file"} and path:
        p = Path(path).expanduser()
        if not p.is_file():
            return {"ok": False, "error": f"bestand niet gevonden: {path}"}
        return _open_path_in_app(entry, p)

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


def handoff_file(path: str, *, prefer_app: str = "") -> dict[str, Any]:
    """Open een bestand in de juiste VIT-app (PDF/Office/Mail/Rekenbladen)."""
    p = Path(path).expanduser()
    if not p.is_file():
        return {"ok": False, "error": f"bestand niet gevonden: {path}"}
    if prefer_app:
        entry = resolve_vit_app(prefer_app)
        if entry:
            return _open_path_in_app(entry, p)
    ext = p.suffix.lower()
    target_id = _EXT_ROUTE.get(ext)
    if not target_id:
        # images → preview via open; unknown → Office fallback then default
        if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"}:
            r = subprocess.run(["open", str(p)], capture_output=True, text=True) if _darwin() else None
            return {
                "ok": True if not _darwin() else (r.returncode == 0 if r else False),
                "mode": "system_open",
                "path": str(p),
                "hint": "Geen VIT-beeldapp; systeemviewer.",
            }
        entry = _all_suite().get("office")
        if entry:
            out = _open_path_in_app(entry, p)
            out["routed"] = "office_fallback"
            return out
        return {"ok": False, "error": f"geen VIT-app voor extensie {ext or '(geen)'}"}
    entry = _all_suite()[target_id]
    out = _open_path_in_app(entry, p)
    out["routed"] = target_id
    return out


def vit_app_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "vit_apps_list",
                "description": (
                    "Lijst VIT-suite apps (Mail, Kluis/Bitwarden, Backup, Office, PDF, "
                    "Remote Manager, Rekenbladen, …) + geïnstalleerd/draaiend + acties."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vit_app_open",
                "description": (
                    "Open/bedien een VIT-app. app= mail|kluis|backup|office|pdf|remote|rekenbladen|menubalk. "
                    "action=open|compose|web|open_file|search|unlock|connect|status|reveal. "
                    "Kluis=wachtwoorden (Vaultwarden). Mail compose: to/subject/body. "
                    "Remote connect: host=. Backup status: action=status."
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
                        "query": {"type": "string"},
                        "host": {"type": "string"},
                        "prefer_web": {"type": "boolean"},
                    },
                    "required": ["app"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vit_app_handoff",
                "description": (
                    "Geef een bestand door aan de juiste VIT-app: .pdf→PDF, .docx→Office, "
                    ".xlsx/.csv→Rekenbladen, .eml→Mail. Optioneel prefer_app forceren."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Pad naar bestand"},
                        "prefer_app": {
                            "type": "string",
                            "description": "Optioneel: mail|office|pdf|rekenbladen|…",
                        },
                    },
                    "required": ["path"],
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
                query=str(arguments.get("query") or ""),
                host=str(arguments.get("host") or ""),
                prefer_web=bool(arguments.get("prefer_web")),
            ),
            ensure_ascii=False,
        )
    if name == "vit_app_handoff":
        return json.dumps(
            handoff_file(
                str(arguments.get("path") or ""),
                prefer_app=str(arguments.get("prefer_app") or ""),
            ),
            ensure_ascii=False,
        )
    return json.dumps({"error": f"onbekende vit app tool {name}"})
