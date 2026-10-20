"""Project memory: AGENTS.md / CLAUDE.md / .cursorrules — zoals Cursor & Claude Code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

CANDIDATES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".claude/CLAUDE.md",
    ".cursor/rules.md",
)


def load_project_instructions(workspace: str | None, *, max_chars: int = 12000) -> dict[str, Any]:
    if not workspace:
        return {"ok": False, "files": [], "text": ""}
    root = Path(workspace).expanduser()
    if not root.is_dir():
        return {"ok": False, "error": "workspace geen map", "files": [], "text": ""}
    chunks: list[str] = []
    files: list[str] = []
    budget = max_chars
    for rel in CANDIDATES:
        p = root / rel
        if not p.is_file():
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not raw.strip():
            continue
        take = raw[: min(len(raw), max(800, budget))]
        chunks.append(f"## {rel}\n{take}")
        files.append(str(p))
        budget -= len(take)
        if budget <= 0:
            break
    # Also first .cursor/rules/*.mdc (max 3)
    rules_dir = root / ".cursor" / "rules"
    if rules_dir.is_dir() and budget > 400:
        for p in sorted(rules_dir.glob("*.mdc"))[:3]:
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            chunks.append(f"## .cursor/rules/{p.name}\n{raw}")
            files.append(str(p))
            budget -= len(raw)
            if budget <= 0:
                break
    text = "\n\n".join(chunks)[:max_chars]
    return {
        "ok": bool(text),
        "files": files,
        "text": text,
        "hint": "Geladen zoals Cursor/Claude Code project memory.",
    }


def project_system_block(workspace: str | None) -> str | None:
    info = load_project_instructions(workspace)
    if not info.get("ok") or not info.get("text"):
        return None
    return (
        "Project-instructies (AGENTS.md / CLAUDE.md / rules) — volg strikt tenzij user anders vraagt:\n\n"
        + info["text"]
    )
