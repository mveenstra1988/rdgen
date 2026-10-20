"""Agent-modi zoals Cursor/Claude Code: agent | plan | ask."""

from __future__ import annotations

from typing import Any

MODES = ("agent", "plan", "ask")

# Tools die schrijven / uitvoeren — geblokkeerd in ask (en plan)
WRITE_TOOLS = frozenset(
    {
        "write_workspace_file",
        "search_replace",
        "run_in_workspace",
        "git_commit",
        "shell_allowlist",
        "open_app",
        "vit_app_open",
        "vit_app_handoff",
        "mcp_call_tool",
        "generate_image",
        "nano_banana",
    }
)

PLAN_SYSTEM = (
    "AGENT MODE = PLAN (zoals Cursor /plan en Claude Code /plan).\n"
    "- Ontwerp eerst: aanpak, bestanden, risico's, volgorde.\n"
    "- Stel max 3 verhelderende vragen als iets kritiek onduidelijk is.\n"
    "- Geen code wijzigen, geen commits, geen shell-mutaties.\n"
    "- Eindig met een genummerd uitvoeringsplan dat in Agent-modus gevolgd kan worden.\n"
    "- Markeer aannames expliciet."
)

ASK_SYSTEM = (
    "AGENT MODE = ASK (zoals Cursor Ask / Claude Code explore).\n"
    "- Alleen uitleggen, zoeken, lezen. Geen edits, geen commits, geen destructieve tools.\n"
    "- Gebruik read/list/search tools; antwoord met citaties (pad + korte snippet).\n"
    "- Als de user wil dat je wél wijzigt: zeg dat ze naar Agent-modus moeten."
)


def normalize_mode(raw: str | None) -> str:
    m = (raw or "agent").strip().lower()
    if m in {"plan", "planning", "/plan"}:
        return "plan"
    if m in {"ask", "explore", "readonly", "/ask"}:
        return "ask"
    return "agent"


def mode_system_prompt(mode: str) -> str | None:
    m = normalize_mode(mode)
    if m == "plan":
        return PLAN_SYSTEM
    if m == "ask":
        return ASK_SYSTEM
    return None


def filter_tools_for_mode(tools: list[dict[str, Any]] | None, mode: str) -> list[dict[str, Any]] | None:
    if not tools:
        return tools
    m = normalize_mode(mode)
    if m == "plan":
        # plan: geen tools (of alleen read) — strikt geen writes
        return [
            t
            for t in tools
            if (t.get("function") or {}).get("name")
            in {
                "codebase_search",
                "list_workspace",
                "read_workspace_file",
                "read_document",
                "memory_search",
                "vit_apps_list",
                "mcp_list_servers",
                "mcp_list_tools",
            }
        ]
    if m == "ask":
        return [
            t
            for t in tools
            if (t.get("function") or {}).get("name") not in WRITE_TOOLS
        ]
    return tools


def parse_leading_slash(text: str) -> tuple[str | None, str]:
    """Parse leading /plan|/ask|/agent from user message. Returns (mode, remainder)."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return None, text
    first, _, rest = t.partition(" ")
    cmd = first.lower()
    if cmd in {"/plan", "/ask", "/agent"}:
        return cmd[1:], rest.lstrip() if rest else ""
    return None, text
