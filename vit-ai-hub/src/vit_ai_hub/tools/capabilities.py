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
                    "description": "Sla een lokaal geheugenfeit op (geen secrets/klant-PII).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
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
                    "description": "Lees lokale geheugenfeiten (optioneel filter op key).",
                    "parameters": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}},
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
                    "description": "Schrijf/update een tekstbestand in de allowlisted workspace (geen .env/secrets).",
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
                    "name": "run_in_workspace",
                    "description": "Run allowlisted commando in workspace (pytest, npm, git status/diff, …).",
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
        with MEMORY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "key": key, "value": value}, ensure_ascii=False) + "\n")
        return json.dumps({"ok": True, "key": key})
    if name == "memory_read":
        key = str(arguments.get("key") or "").strip()
        rows = []
        if MEMORY_PATH.is_file():
            for line in MEMORY_PATH.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if key and row.get("key") != key:
                    continue
                rows.append(row)
        from vit_ai_hub.importing.store import stats as kstats

        return json.dumps(
            {"items": rows[-50:], "imported_knowledge": kstats()},
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
    }
    if name in desktop_names:
        from vit_ai_hub.tools.desktop import run_desktop_tool

        return await run_desktop_tool(name, arguments)
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
    return {
        "chat": True,
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
        "studios": ["chat", "software", "webdesign", "apps", "design", "self"],
        "agent_teams": True,
        "full_migrate": True,
        "self_improve": True,
        "cursor_exit": "VS Code + Continue → http://127.0.0.1:8787/v1 (scripts/export-continue-config.sh)",
        "figma_alt": "Penpot (scripts/install-penpot-mac.sh) + design studio",
        "parity_notes": [
            "Visuele agent-teams (webdesign, apps) — zelf bouwen en runnen.",
            "Studio-modi: software/webdesign/apps/design vervangen dagelijks Claude/ChatGPT/Cursor-werk.",
            "Workspace read/write/run in allowlisted projectmappen.",
            "Cursor-exit: Continue/VS Code of Zed op dezelfde gateway.",
            "Figma-alt: Penpot lokaal of design-in-code (webdesign studio).",
            "Desktop: Chrome, Mail, VIT Mail, Penpot, Spotlight.",
        ],
    }