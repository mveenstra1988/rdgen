from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from vit_ai_hub.config import ROOT, load_yaml_config
from vit_ai_hub.pii import get_pii_engine

MEMORY_PATH = Path(ROOT) / "data" / "memory.jsonl"
MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)


def tool_specs() -> list[dict[str, Any]]:
    cfg = load_yaml_config().get("tools", {})
    tools: list[dict[str, Any]] = []
    if cfg.get("web_search", True):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Zoek actuele informatie op het web (DuckDuckGo lite).",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        )
    if cfg.get("fetch_url", True):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "description": "Haal tekstinhoud van een publieke URL op.",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                },
            }
        )
    if cfg.get("memory", True):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "memory_write",
                    "description": (
                        "Sla een feit op in het gedeelde hub-geheugen (model-agnostisch; "
                        "blijft bij modelwissel). Geen secrets/klant-PII."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Korte tag/label"},
                            "value": {"type": "string", "description": "Te onthouden feit"},
                        },
                        "required": ["key", "value"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "memory_read",
                    "description": (
                        "Zoek in gedeeld hub-geheugen (alle modellen delen dit). "
                        "Optioneel filter op key/tag of vrije query."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "query": {"type": "string"},
                        },
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "knowledge_search",
                    "description": "Zoek in geïmporteerde ChatGPT/Claude/Cursor kennis en geheugen.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        )
    if cfg.get("files", True):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "list_workspace",
                    "description": "Lijst bestanden in een allowlisted projectmap (Projects/Developer/hub).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "workspace": {"type": "string", "description": "Absolute projectroot"},
                        },
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "read_workspace_file",
                    "description": "Lees een tekstbestand in een allowlisted workspace (hub of ~/Projects etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "workspace": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "write_workspace_file",
                    "description": "Schrijf/update een tekstbestand in de allowlisted workspace (geen .env/secrets). Prefer search_replace voor kleine edits.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "workspace": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "search_replace",
                    "description": "Cursor-achtige gerichte patch: vervang exacte old_str door new_str in een bestand.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "old_str": {"type": "string"},
                            "new_str": {"type": "string"},
                            "replace_all": {"type": "boolean"},
                            "workspace": {"type": "string"},
                        },
                        "required": ["path", "old_str", "new_str"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "codebase_search",
                    "description": "@codebase: zoek tekst/symbolen in de workspace (ripgrep).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "glob": {"type": "string", "description": "bijv. *.py"},
                            "workspace": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Veilige git add + commit in workspace (geen force/hard reset).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optioneel: alleen deze paden stagen",
                            },
                            "workspace": {"type": "string"},
                        },
                        "required": ["message"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "run_in_workspace",
                    "description": "Run allowlisted commando (pytest, npm, git status/diff/add/commit/push, rg, …). Geen force-git.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "workspace": {"type": "string"},
                            "timeout_sec": {"type": "integer"},
                        },
                        "required": ["command"],
                    },
                },
            }
        )
    if cfg.get("desktop", True):
        from vit_ai_hub.tools.desktop import desktop_tool_specs

        tools.extend(desktop_tool_specs())
    if cfg.get("mcp", True):
        from vit_ai_hub.tools.mcp_runtime import mcp_tool_specs

        tools.extend(mcp_tool_specs())
    if cfg.get("ops", True):
        from vit_ai_hub.tools.ops import ops_tool_specs

        tools.extend(ops_tool_specs())
    if cfg.get("media", True):
        from vit_ai_hub.tools.media import media_tool_specs

        tools.extend(media_tool_specs())
    return tools


async def run_tool(name: str, arguments: dict[str, Any]) -> str:
    pii = get_pii_engine()
    if name == "web_search":
        query = str(arguments.get("query", "")).strip()
        scanned = pii.process(query, destination_local=False)
        if scanned.blocked or scanned.has_pii:
            return json.dumps(
                {"error": "Zoekopdracht bevat mogelijke klant-PII en is geblokkeerd."},
                ensure_ascii=False,
            )
        return await _duckduckgo(query)
    if name == "fetch_url":
        url = str(arguments.get("url", "")).strip()
        host = urlparse(url).hostname or ""
        if host in {"127.0.0.1", "localhost"} or host.endswith(".local"):
            return json.dumps({"error": "Lokale URLs zijn niet toegestaan via fetch_url."})
        return await _fetch_url(url)
    if name == "memory_write":
        key = str(arguments.get("key", "")).strip()
        value = str(arguments.get("value", "")).strip()
        scanned = pii.process(f"{key} {value}", destination_local=False)
        if scanned.has_pii:
            return json.dumps({"error": "Memory weigert PII/secrets."}, ensure_ascii=False)
        from vit_ai_hub.memory import pin_memory

        result = pin_memory(value, kind="fact", tags=key or "note")
        # legacy jsonl append for backwards compat
        try:
            with MEMORY_PATH.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {"ts": time.time(), "key": key, "value": value, "id": result.get("id")},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass
        return json.dumps({**result, "key": key, "shared": True}, ensure_ascii=False)
    if name == "memory_read":
        key = str(arguments.get("key") or "").strip()
        query = str(arguments.get("query") or key or "").strip()
        from vit_ai_hub.memory import search_memories
        from vit_ai_hub.importing.store import stats as kstats

        items = search_memories(query, limit=40)
        if key and not query:
            items = [i for i in items if key in (i.get("tags") or "")]
        return json.dumps(
            {
                "items": [
                    {
                        "id": i.get("id"),
                        "key": i.get("tags") or "",
                        "value": i.get("content"),
                        "kind": i.get("kind"),
                        "model": i.get("model"),
                    }
                    for i in items
                ],
                "shared": True,
                "imported_knowledge": kstats(),
            },
            ensure_ascii=False,
        )
    if name == "knowledge_search":
        from vit_ai_hub.importing.store import search_knowledge

        query = str(arguments.get("query", "")).strip()
        return json.dumps({"hits": search_knowledge(query, limit=20)}, ensure_ascii=False)
    if name == "list_workspace":
        from vit_ai_hub.workspace import list_workspace_dir

        return json.dumps(
            list_workspace_dir(
                str(arguments.get("path") or "."),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
            ),
            ensure_ascii=False,
        )
    if name == "read_workspace_file":
        from vit_ai_hub.workspace import read_workspace_file

        return json.dumps(
            read_workspace_file(
                str(arguments.get("path", "")).strip(),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
            ),
            ensure_ascii=False,
        )
    if name == "write_workspace_file":
        from vit_ai_hub.workspace import write_workspace_file

        content = str(arguments.get("content", ""))
        return json.dumps(
            write_workspace_file(
                str(arguments.get("path", "")).strip(),
                content,
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
            ),
            ensure_ascii=False,
        )
    if name == "search_replace":
        from vit_ai_hub.workspace import search_replace

        return json.dumps(
            search_replace(
                str(arguments.get("path", "")).strip(),
                str(arguments.get("old_str", "")),
                str(arguments.get("new_str", "")),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                replace_all=bool(arguments.get("replace_all")),
            ),
            ensure_ascii=False,
        )
    if name == "codebase_search":
        from vit_ai_hub.workspace import codebase_search

        return json.dumps(
            codebase_search(
                str(arguments.get("query", "")).strip(),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                glob=(str(arguments["glob"]) if arguments.get("glob") else None),
                limit=int(arguments.get("limit") or 40),
            ),
            ensure_ascii=False,
        )
    if name == "git_commit":
        from vit_ai_hub.workspace import git_commit

        paths = arguments.get("paths")
        path_list = [str(p) for p in paths] if isinstance(paths, list) else None
        return json.dumps(
            git_commit(
                str(arguments.get("message", "")).strip(),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                paths=path_list,
            ),
            ensure_ascii=False,
        )
    if name == "run_in_workspace":
        from vit_ai_hub.workspace import run_in_workspace

        return json.dumps(
            run_in_workspace(
                str(arguments.get("command", "")),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                timeout_sec=int(arguments.get("timeout_sec") or 60),
            ),
            ensure_ascii=False,
        )
    desktop_names = {
        "open_app",
        "open_url",
        "chrome_open_url",
        "chrome_list_tabs",
        "mail_compose",
        "vit_mail_open",
        "spotlight_search",
        "list_running_apps",
        "run_shell_safe",
        "open_penpot",
        "open_figcraft",
        "vit_apps_list",
        "vit_app_open",
    }
    if name in desktop_names:
        from vit_ai_hub.tools.desktop import run_desktop_tool

        return await run_desktop_tool(name, arguments)
    if name in {"mcp_list_servers", "mcp_list_tools", "mcp_call_tool"}:
        from vit_ai_hub.tools.mcp_runtime import run_mcp_tool

        return await run_mcp_tool(name, arguments)
    from vit_ai_hub.tools.ops import OPS_TOOL_NAMES, run_ops_tool

    if name in OPS_TOOL_NAMES:
        return await run_ops_tool(name, arguments)
    from vit_ai_hub.tools.media import MEDIA_TOOL_NAMES, run_media_tool

    if name in MEDIA_TOOL_NAMES:
        return await run_media_tool(name, arguments)
    return json.dumps({"error": f"Onbekende tool: {name}"})


async def _duckduckgo(query: str) -> str:
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    results = {
        "heading": data.get("Heading"),
        "abstract": data.get("AbstractText"),
        "abstract_url": data.get("AbstractURL"),
        "related": [
            {"text": t.get("Text"), "url": t.get("FirstURL")}
            for t in (data.get("RelatedTopics") or [])
            if isinstance(t, dict) and t.get("Text")
        ][:8],
    }
    return json.dumps(results, ensure_ascii=False)


async def _fetch_url(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "VIT-AI-Hub/0.1"})
            text = resp.text
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    # crude tag strip
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return json.dumps({"url": url, "status": resp.status_code, "text": text[:20000]}, ensure_ascii=False)


def capabilities_manifest() -> dict[str, Any]:
    from vit_ai_hub.tools.media import media_capabilities

    return {
        "chat": True,
        "media": media_capabilities(),
        "streaming": True,
        "model_picker": True,
        "providers": [
            "lmstudio",
            "ollama",
            "claude_chatgpt_bridge",
            "cursor",
            "openrouter",
            "deepseek",
            "omniroute",
            "grok",
        ],
        "tools": [t["function"]["name"] for t in tool_specs()],
        "privacy_filter": True,
        "desktop": True,
        "import": [
            "chatgpt_export",
            "claude_export",
            "cursor_local",
            "one_click_all",
            "chatgpt_live_ax",
            "claude_live_ax",
            "live_sync",
        ],
        "studios": [
            "chat",
            "software",
            "webdesign",
            "apps",
            "design",
            "marketing",
            "socials",
            "seo",
            "visual",
            "self",
            "ops",
        ],
        "agent_teams": True,
        "full_migrate": True,
        "self_improve": True,
        "mcp_runtime": True,
        "ops": True,
        "ops_services": [
            "proxmox",
            "nextcloud",
            "gromox",
            "mailcow",
            "servicehub",
            "unifi",
            "automation_hub",
            "vit_backup",
        ],
        "growth": True,
        "growth_studios": ["marketing", "socials", "seo", "visual"],
        "growth_teams": [
            "team-marketing",
            "team-socials",
            "team-seo",
            "team-growth",
            "team-visual",
            "team-site",
        ],
        "visual_canva_alt": True,
        "figma_alt": "FigCraft (ArtCraft) + Penpot + design-in-code",
        "canva_alt": "studio Visual + visual_render/generate_image (HTML/SVG)",
        "nano_banana": "tool nano_banana / generate_image provider=banana (GEMINI_API_KEY)",
        "media_tools": [
            "visual_render",
            "generate_image",
            "nano_banana",
            "describe_image",
            "read_document",
            "speak_text",
        ],
        "app_lifecycle": "open .app starts hub; quit stops hub (session mode)",
        "pwa": True,
        "multi_window": True,
        "lan_iphone": "Instellingen → iPhone/PWA → LAN-modus + QR",
        "orchestrator": True,
        "account_pools": True,
        "account_pool_names": ["bridge", "cursor", "openrouter", "deepseek", "grok", "omniroute"],
        "vit_auto": (
            "intent → strong/weak + tradeoff + fallback cascade + critic + auto multi-agent "
            "+ growth router (marketing/socials/seo) + multi-abo pool failover"
        ),
        "cursor_exit": "VS Code + Continue → http://127.0.0.1:8787/v1 (scripts/export-continue-config.sh)",
        "parity_notes": [
            "vit/auto: intent, lokale modellen, per-rol model + auto-teams + growth/site/visual router.",
            "Canva-alt: studio Visual + HTML/SVG templates (geen Canva-abo).",
            "Figma-alt: Penpot + design-in-code (webdesign) + visual templates.",
            "Site pipeline: team-site = marketing → SEO → design → frontend → copy.",
            "Eén Mac-app (.dmg/.app): open start hub, sluiten stopt hub.",
            "Desktop: Chrome, Mail, VIT-suite (Mail/Kluis/Backup/Office/PDF/Remote), Penpot, FigCraft.",
            "Ops: Proxmox/Nextcloud/Mailcow/UniFi/Backup via ops.env (VPN, read-first).",
            "VIT Kluis = Vaultwarden/Bitwarden @ secure.vitwerkplek.nl (vit_app_open kluis).",
        ],
    }