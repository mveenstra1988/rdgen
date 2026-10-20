"""Slash-commands zoals Claude Code / Cursor / Codex (okt 2026 subset in de hub)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

# Local commands (geen LLM nodig) + LLM-routed modes
CATALOG: list[dict[str, str]] = [
    {"cmd": "/plan", "blurb": "Plan-modus — eerst aanpak, geen edits", "kind": "mode"},
    {"cmd": "/ask", "blurb": "Ask-modus — alleen lezen/uitleggen", "kind": "mode"},
    {"cmd": "/agent", "blurb": "Agent-modus — edits + tools", "kind": "mode"},
    {"cmd": "/debug", "blurb": "Debug-modus — runtime-bewijs eerst", "kind": "mode"},
    {"cmd": "/clear", "blurb": "Nieuwe chat (context leeg)", "kind": "local"},
    {"cmd": "/compact", "blurb": "Vat chat samen → kortere context", "kind": "llm"},
    {"cmd": "/diff", "blurb": "Toon git diff in workspace", "kind": "local"},
    {"cmd": "/review", "blurb": "Code-review op huidige diff", "kind": "llm"},
    {"cmd": "/init", "blurb": "Schrijf AGENTS.md in project", "kind": "local"},
    {"cmd": "/memory", "blurb": "Toon recent geheugen", "kind": "local"},
    {"cmd": "/mcp", "blurb": "Lijst MCP-servers", "kind": "local"},
    {"cmd": "/skills", "blurb": "Lijst skills", "kind": "local"},
    {"cmd": "/doctor", "blurb": "Setup-checkup (bridge, keys, lokaal)", "kind": "local"},
    {"cmd": "/usage", "blurb": "Route/usage telemetrie", "kind": "local"},
    {"cmd": "/model", "blurb": "Huidige model-hint", "kind": "local"},
    {"cmd": "/checkpoint", "blurb": "Maak checkpoint (git + chat-tag)", "kind": "local"},
    {"cmd": "/rewind", "blurb": "Terug naar laatste checkpoint", "kind": "local"},
    {"cmd": "/help", "blurb": "Alle slash-commands", "kind": "local"},
]


def list_commands() -> dict[str, Any]:
    return {"ok": True, "commands": CATALOG, "hint": "Typ / in de composer voor autocomplete."}


def parse_slash(text: str) -> tuple[str | None, str]:
    t = (text or "").strip()
    if not t.startswith("/"):
        return None, text
    first, _, rest = t.partition(" ")
    return first.lower(), rest.lstrip()


def _git(workspace: str | None, *args: str) -> dict[str, Any]:
    if not workspace:
        return {"ok": False, "error": "geen workspace/projectmap gezet"}
    root = Path(workspace).expanduser()
    if not (root / ".git").exists() and not any((root / p).exists() for p in (".git",)):
        # allow nested: run from root anyway
        pass
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": r.returncode == 0,
        "stdout": (r.stdout or "")[:12000],
        "stderr": (r.stderr or "")[:2000],
        "code": r.returncode,
    }


def run_local(cmd: str, *, args: str = "", workspace: str | None = None) -> dict[str, Any]:
    """Voer lokale slash uit → {ok, message, action?}."""
    c = (cmd or "").lower().strip()
    if not c.startswith("/"):
        c = "/" + c

    if c in {"/help", "/commands"}:
        lines = [f"{x['cmd']} — {x['blurb']}" for x in CATALOG]
        return {"ok": True, "message": "Slash-commands:\n" + "\n".join(lines)}

    if c == "/clear":
        return {"ok": True, "action": "clear_chat", "message": "Nieuwe chat — context geleegd."}

    if c == "/diff":
        out = _git(workspace, "diff", "--stat", "HEAD")
        if not out.get("ok") and out.get("code") != 0:
            # unstaged
            out = _git(workspace, "diff", "--stat")
        body = out.get("stdout") or out.get("stderr") or "(geen diff)"
        detail = _git(workspace, "diff", "HEAD")
        full = (detail.get("stdout") or "")[:8000]
        return {
            "ok": True,
            "message": f"## Git diff\n```\n{body}\n```\n\n```diff\n{full}\n```",
        }

    if c == "/init":
        if not workspace:
            return {"ok": False, "message": "Zet eerst een Projectmap (workspace)."}
        root = Path(workspace).expanduser()
        path = root / "AGENTS.md"
        if path.is_file() and "force" not in args:
            return {"ok": True, "message": f"AGENTS.md bestaat al: {path}\n(gebruik `/init force` om te overschrijven)"}
        content = (
            "# AGENTS.md\n\n"
            "Projectregels voor VIT AI Hub / Cursor / Claude Code / Codex.\n\n"
            "## Stack\n- (vul in)\n\n"
            "## Commands\n- Test: \n- Build: \n\n"
            "## Regels\n- Kleine, reviewbare diffs\n- Geen secrets committen\n"
            "- Volg bestaande stijl\n"
        )
        try:
            root.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "message": f"Geschreven: {path}"}

    if c == "/memory":
        stats: dict[str, Any] = {}
        try:
            from vit_ai_hub.memory import memory_stats

            stats = memory_stats()
        except Exception:
            stats = {}
        lines = [f"Stats: {json.dumps(stats, ensure_ascii=False)}"]
        try:
            from vit_ai_hub.memory.store import list_recent

            for m in list_recent(limit=8):
                lines.append(f"- {m.get('key') or m.get('id')}: {str(m.get('content') or '')[:120]}")
        except Exception:
            lines.append("(recente items via memory_search in chat)")
        return {"ok": True, "message": "## Geheugen\n" + "\n".join(lines)}

    if c == "/mcp":
        from vit_ai_hub.extensions import list_mcp_managed

        data = list_mcp_managed()
        servers = data.get("active", {}).get("servers") or []
        if not servers:
            servers = [{"name": n} for n in (data.get("hub_servers") or {})]
        lines = [f"• {s.get('name')} {s.get('command') or ''}" for s in servers] or ["(geen MCP — Uitbreidingen → MCP)"]
        return {"ok": True, "message": "## MCP\n" + "\n".join(lines)}

    if c == "/skills":
        from vit_ai_hub.extensions import list_hub_skills

        data = list_hub_skills()
        rows = data.get("catalog") or []
        lines = [f"• {r.get('name')}: {str(r.get('description') or '')[:80]}" for r in rows[:40]] or [
            "(geen skills — Uitbreidingen → Skills)"
        ]
        return {"ok": True, "message": "## Skills\n" + "\n".join(lines)}

    if c == "/doctor":
        from vit_ai_hub.setup_api import probe_providers
        from vit_ai_hub.bridge import bridge_status

        p = probe_providers()
        b = bridge_status()
        lines = [
            f"Hub v{p.get('version')}",
            ("✓" if p.get("lmstudio_up") else "○") + " LM Studio",
            ("✓" if p.get("gemini_key") else "○") + " Gemini key",
            ("✓" if p.get("openrouter_key") else "○") + " OpenRouter",
            ("✓" if b.get("installed") else "○") + " Bridge geïnstalleerd",
            ("✓" if b.get("running") else "○") + " Bridge draait",
            ("✓" if b.get("claude_logged_in") else "○") + " Claude OAuth",
            ("✓" if b.get("chatgpt_logged_in") else "○") + " ChatGPT OAuth",
            ("✓" if p.get("bridge_key") else "○") + " Bridge key",
            f"VIT-apps: {p.get('vit_apps_installed')}/{p.get('vit_apps_count')}",
            "",
            "Fix: /?wizard=1 · of ⚙ Uitbreidingen / Bridge klaarzetten",
        ]
        return {"ok": True, "message": "## Doctor\n" + "\n".join(lines)}

    if c == "/usage":
        from vit_ai_hub.config import ROOT

        log = ROOT / "data" / "orchestrator.jsonl"
        n = 0
        models: dict[str, int] = {}
        if log.is_file():
            with log.open(encoding="utf-8") as fh:
                for line in fh:
                    n += 1
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    m = str(row.get("model") or row.get("chosen") or "?")
                    models[m] = models.get(m, 0) + 1
        top = sorted(models.items(), key=lambda x: -x[1])[:12]
        lines = [f"Events: {n}"] + [f"• {m}: {c}" for m, c in top] or ["(nog geen telemetrie)"]
        return {"ok": True, "message": "## Usage\n" + "\n".join(lines)}

    if c == "/model":
        return {
            "ok": True,
            "message": (
                "Kies model in de picker: **vit/auto** (slim) of **vit/max** (critic).\n"
                "Lokaal: LM Studio MLX · bridge: Claude/ChatGPT na wizard-login."
            ),
        }

    if c == "/checkpoint":
        from vit_ai_hub.checkpoints import create_checkpoint

        return create_checkpoint(workspace=workspace, note=args or "manual")

    if c == "/rewind":
        from vit_ai_hub.checkpoints import rewind_checkpoint

        return rewind_checkpoint(workspace=workspace, name=args or "")

    return {
        "ok": False,
        "message": f"Onbekend of LLM-commando: {c}. Gebruik /help. Modes: /plan /ask /agent /debug.",
        "passthrough": c in {"/plan", "/ask", "/agent", "/debug", "/compact", "/review"},
    }


def llm_prompt_for(cmd: str, args: str, *, workspace: str | None = None) -> str | None:
    """Extra user-prompt tekst voor LLM-routed slash."""
    c = cmd.lower()
    if c == "/compact":
        return (
            "Vat deze conversatie samen in ≤12 bullets: doelen, beslissingen, open punten, "
            "bestanden. Daarna werken we verder met alleen deze samenvatting als context."
            + (f"\n\nExtra: {args}" if args else "")
        )
    if c == "/review":
        diff = _git(workspace, "diff", "HEAD")
        body = diff.get("stdout") or "(geen git diff — review de laatste wijzigingen uit context)"
        return (
            "Je bent code-reviewer (Claude Code /review / Cursor Bugbot-stijl).\n"
            "Beoordeel op: bugs, security, performance, missing tests.\n"
            "Output: (1) Kritiek (2) Verbeteringen (3) Nitpicks. Geen loze lof.\n\n"
            f"```diff\n{body[:10000]}\n```\n"
            + (f"\nFocus: {args}" if args else "")
        )
    return None
