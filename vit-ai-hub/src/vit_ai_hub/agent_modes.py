"""Agent-modi zoals Cursor/Claude Code: agent | plan | ask | debug."""

from __future__ import annotations

from typing import Any

MODES = ("agent", "plan", "ask", "debug")

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
    "AGENT MODE = PLAN (Cursor /plan · Claude Code /plan).\n"
    "- Ontwerp eerst: aanpak, bestanden, risico's, volgorde.\n"
    "- Stel max 3 verhelderende vragen als iets kritiek onduidelijk is.\n"
    "- Geen code wijzigen, geen commits, geen shell-mutaties.\n"
    "- Eindig met een genummerd uitvoeringsplan voor Agent-modus.\n"
    "- Markeer aannames expliciet."
)

ASK_SYSTEM = (
    "AGENT MODE = ASK (Cursor Ask · Claude explore).\n"
    "- Alleen uitleggen, zoeken, lezen. Geen edits/commits.\n"
    "- Gebruik read/list/search; citeer pad + korte snippet.\n"
    "- Voor wijzigingen: verwijs naar Agent-modus."
)

DEBUG_SYSTEM = (
    "AGENT MODE = DEBUG (Cursor Debug).\n"
    "- Verzamel runtime-bewijs: logs, stacktraces, reproduceer-stappen, falende tests.\n"
    "- Hypothese → experiment (kleine patch of test) → bewijs → fix.\n"
    "- Geen grote refactors; minimale diff die het bewijs adresseert.\n"
    "- Eindig met: root cause · fix · hoe geverifieerd."
)


def normalize_mode(raw: str | None) -> str:
    m = (raw or "agent").strip().lower()
    if m in {"plan", "planning", "/plan"}:
        return "plan"
    if m in {"ask", "explore", "readonly", "/ask"}:
        return "ask"
    if m in {"debug", "dbg", "/debug"}:
        return "debug"
    return "agent"


def mode_system_prompt(mode: str) -> str | None:
    m = normalize_mode(mode)
    if m == "plan":
        return PLAN_SYSTEM
    if m == "ask":
        return ASK_SYSTEM
    if m == "debug":
        return DEBUG_SYSTEM
    return None


def filter_tools_for_mode(tools: list[dict[str, Any]] | None, mode: str) -> list[dict[str, Any]] | None:
    if not tools:
        return tools
    m = normalize_mode(mode)
    if m == "plan":
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
        return [t for t in tools if (t.get("function") or {}).get("name") not in WRITE_TOOLS]
    # debug + agent: full tools
    return tools


def parse_leading_slash(text: str) -> tuple[str | None, str]:
    """Parse leading mode slash. Returns (mode, remainder) or (None, text)."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return None, text
    first, _, rest = t.partition(" ")
    cmd = first.lower()
    if cmd in {"/plan", "/ask", "/agent", "/debug"}:
        return cmd[1:], rest.lstrip() if rest else ""
    return None, text
