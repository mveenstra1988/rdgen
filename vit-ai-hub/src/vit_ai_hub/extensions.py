"""Eenvoudig skills, MCP-servers en extra apps toevoegen via GUI/API."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

HUB_MCP = ROOT / "data" / "mcp.json"
HUB_SKILLS_DIR = ROOT / "data" / "skills"
CUSTOM_APPS = ROOT / "data" / "custom_apps.json"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip()).strip("-").lower()
    return s or f"item-{int(time.time())}"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# —— Skills ——


def add_skill(
    *,
    name: str,
    description: str = "",
    content: str = "",
    promote_agent: bool = True,
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "naam verplicht"}
    body = (content or "").strip()
    if not body:
        return {"ok": False, "error": "content (SKILL.md body) verplicht"}
    desc = (description or "").strip() or name
    slug = _slug(name)
    skill_dir = HUB_SKILLS_DIR / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    # YAML frontmatter + body
    md = f"---\nname: {name}\ndescription: {desc}\n---\n\n{body}\n"
    path = skill_dir / "SKILL.md"
    path.write_text(md, encoding="utf-8")

    from vit_ai_hub.importing.store import save_skills

    written = save_skills(
        [
            {
                "source": "hub-gui",
                "name": name,
                "description": desc,
                "content": body,
                "path": str(path),
                "kind": "skill",
                "native_id": str(path),
            }
        ]
    )
    agents: dict[str, Any] | None = None
    if promote_agent:
        try:
            from vit_ai_hub.agents.store import get_agent, save_agent

            agent_id = f"agent-skill-{slug}"[:60]
            if get_agent(agent_id):
                agents = {"written": 0, "skipped": 1, "id": agent_id}
            else:
                save_agent(
                    {
                        "id": agent_id,
                        "name": name[:80],
                        "role": "Skill (hub)",
                        "color": "#5a8f12",
                        "model": "vit/auto",
                        "studio": "chat",
                        "system": (
                            f"Je volgt deze skill strikt.\n{desc}\n\n{body[:6000]}"
                        ),
                        "tools": True,
                        "preset": False,
                    }
                )
                agents = {"written": 1, "skipped": 0, "id": agent_id}
        except Exception as exc:
            agents = {"error": str(exc)}
    return {
        "ok": True,
        "name": name,
        "slug": slug,
        "path": str(path),
        "store": written,
        "agents": agents,
    }


def list_hub_skills() -> dict[str, Any]:
    from vit_ai_hub.importing.store import list_skills, stats

    on_disk = []
    if HUB_SKILLS_DIR.is_dir():
        for p in sorted(HUB_SKILLS_DIR.glob("*/SKILL.md")):
            on_disk.append({"name": p.parent.name, "path": str(p)})
    return {
        "ok": True,
        "skills_dir": str(HUB_SKILLS_DIR),
        "on_disk": on_disk,
        "catalog": list_skills(limit=100),
        "knowledge": stats(),
    }


# —— MCP ——


def _load_hub_mcp() -> dict[str, Any]:
    data = _read_json(HUB_MCP, {})
    servers = data.get("mcpServers") or data.get("servers") or {}
    if not isinstance(servers, dict):
        servers = {}
    return {"mcpServers": servers}


def add_mcp_server(
    *,
    name: str,
    command: str = "",
    args: list[str] | str | None = None,
    url: str = "",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    name = _slug(name)
    if not name:
        return {"ok": False, "error": "naam verplicht"}
    cmd = (command or "").strip()
    u = (url or "").strip()
    if not cmd and not u:
        return {"ok": False, "error": "command of url verplicht"}
    if isinstance(args, str):
        arg_list = [a for a in args.split() if a]
    else:
        arg_list = [str(a) for a in (args or [])]

    cfg = _load_hub_mcp()
    entry: dict[str, Any] = {}
    if cmd:
        entry["command"] = cmd
        if arg_list:
            entry["args"] = arg_list
    if u:
        entry["url"] = u
    if env:
        entry["env"] = {str(k): str(v) for k, v in env.items() if k}

    cfg["mcpServers"][name] = entry
    _write_json(HUB_MCP, cfg)
    return {"ok": True, "name": name, "path": str(HUB_MCP), "server": entry, "count": len(cfg["mcpServers"])}


def remove_mcp_server(name: str) -> dict[str, Any]:
    key = _slug(name)
    cfg = _load_hub_mcp()
    if key not in cfg["mcpServers"]:
        # try exact
        if name not in cfg["mcpServers"]:
            return {"ok": False, "error": f"onbekend: {name}"}
        key = name
    del cfg["mcpServers"][key]
    _write_json(HUB_MCP, cfg)
    return {"ok": True, "removed": key, "count": len(cfg["mcpServers"])}


def list_mcp_managed() -> dict[str, Any]:
    from vit_ai_hub.tools.mcp_runtime import list_servers

    hub = _load_hub_mcp()
    live = list_servers()
    return {
        "ok": True,
        "hub_path": str(HUB_MCP),
        "hub_servers": hub["mcpServers"],
        "active": live,
    }


# —— Custom desktop apps ——


def list_custom_apps() -> dict[str, Any]:
    apps = _read_json(CUSTOM_APPS, {"apps": []})
    if isinstance(apps, list):
        apps = {"apps": apps}
    return {"ok": True, "path": str(CUSTOM_APPS), "apps": apps.get("apps") or []}


def add_custom_app(
    *,
    name: str,
    app_name: str = "",
    aliases: list[str] | str | None = None,
    web: str = "",
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "naam verplicht"}
    launch = (app_name or name).strip()
    if isinstance(aliases, str):
        alias_list = [a.strip() for a in aliases.split(",") if a.strip()]
    else:
        alias_list = [str(a).strip() for a in (aliases or []) if str(a).strip()]
    aid = _slug(name)
    data = list_custom_apps()
    items = [a for a in data["apps"] if a.get("id") != aid]
    entry = {
        "id": aid,
        "name": name,
        "app_names": [launch],
        "aliases": alias_list,
        "web": (web or "").strip() or None,
        "role": "Custom app",
        "added_at": time.time(),
    }
    items.append(entry)
    _write_json(CUSTOM_APPS, {"apps": items})
    return {"ok": True, "app": entry, "count": len(items)}


def remove_custom_app(app_id: str) -> dict[str, Any]:
    aid = _slug(app_id)
    data = list_custom_apps()
    before = len(data["apps"])
    items = [a for a in data["apps"] if a.get("id") != aid and a.get("id") != app_id]
    _write_json(CUSTOM_APPS, {"apps": items})
    return {"ok": True, "removed": aid, "count": len(items), "changed": before != len(items)}


def extensions_overview() -> dict[str, Any]:
    skills = list_hub_skills()
    mcp = list_mcp_managed()
    apps = list_custom_apps()
    return {
        "ok": True,
        "skills": {"count": len(skills.get("catalog") or []), "on_disk": len(skills.get("on_disk") or [])},
        "mcp": {"count": len((mcp.get("hub_servers") or {})), "active_path": (mcp.get("active") or {}).get("path")},
        "custom_apps": {"count": len(apps.get("apps") or [])},
    }
