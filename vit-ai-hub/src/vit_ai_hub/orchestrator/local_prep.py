"""Lokale voorbereiding vóór cloud (Claude/GPT): minder tokens, snellere uitvoering.

Flow:
1) Lokaal: zoek repo/kennis/geheugen, knip tot een EXEC_BRIEF
2) Cloud: krijgt alleen die brief + taak → uitvoeren i.p.v. zelf alles opnieuw zoeken
"""

from __future__ import annotations

import re
from typing import Any

from vit_ai_hub.config import load_yaml_config

_PATHISH = re.compile(
    r"(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|swift|md|json|yml|yaml|toml|css|html|sh)\b"
)
_WORD = re.compile(r"[A-Za-zÀ-ÿ_][\w.-]{2,}")


def prep_enabled() -> bool:
    cfg = load_yaml_config().get("orchestrator") or {}
    return bool(cfg.get("local_prep", True))


def prep_max_chars() -> int:
    cfg = load_yaml_config().get("orchestrator") or {}
    return max(2000, min(24_000, int(cfg.get("local_prep_max_chars") or 10_000)))


def _keywords(task: str, *, limit: int = 8) -> list[str]:
    stop = {
        "de", "het", "een", "van", "en", "voor", "met", "naar", "dat", "die",
        "the", "and", "for", "with", "please", "maak", "schrijf", "bouw",
        "doe", "kan", "wil", "zijn", "dit", "die", "also", "then",
    }
    words = []
    for w in _WORD.findall(task or ""):
        low = w.lower()
        if low in stop or len(low) < 3:
            continue
        if low not in {x.lower() for x in words}:
            words.append(w)
        if len(words) >= limit:
            break
    return words


def _clip(text: str, n: int) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _gather_workspace(task: str, workspace: str | None) -> list[dict[str, Any]]:
    if not workspace and not task:
        return []
    hits: list[dict[str, Any]] = []
    try:
        from vit_ai_hub.workspace import codebase_search, read_workspace_file

        # Explicit paths in the prompt first
        for path in _PATHISH.findall(task or "")[:6]:
            got = read_workspace_file(path, workspace=workspace, max_chars=2500)
            if got.get("content"):
                hits.append(
                    {
                        "path": got.get("path") or path,
                        "snippet": _clip(got["content"], 2200),
                        "via": "path",
                    }
                )
        # Keyword search
        q = " ".join(_keywords(task, limit=5)) or (task or "")[:80]
        if q.strip():
            res = codebase_search(q, workspace=workspace, limit=12)
            for h in (res.get("hits") or [])[:8]:
                path = h.get("path")
                if not path:
                    continue
                if any(x.get("path") == path for x in hits):
                    continue
                got = read_workspace_file(path, workspace=workspace, max_chars=1800)
                if got.get("content"):
                    hits.append(
                        {
                            "path": got.get("path") or path,
                            "snippet": _clip(got["content"], 1600),
                            "via": "search",
                            "line": h.get("line"),
                        }
                    )
                if len(hits) >= 6:
                    break
    except Exception:
        return hits
    return hits[:6]


def _bullets_from_block(block: str | None, *, limit: int = 6) -> list[str]:
    if not block:
        return []
    lines = []
    for ln in block.splitlines():
        s = ln.strip().lstrip("-•*").strip()
        if not s or s.startswith("#"):
            continue
        lines.append(_clip(s, 220))
        if len(lines) >= limit:
            break
    return lines


def build_exec_brief(
    *,
    task: str,
    workspace: str | None = None,
    studio: str | None = None,
    knowledge: str | None = None,
    memory: str | None = None,
    recent_user_turns: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministische lokale prep — geen LLM nodig (snel + goedkoop)."""
    files = _gather_workspace(task, workspace)
    mem_bits = _bullets_from_block(memory, limit=5)
    know_bits = _bullets_from_block(knowledge, limit=5)
    prior = []
    for t in (recent_user_turns or [])[-3:]:
        prior.append(_clip(t, 280))

    parts = [
        "# EXEC_BRIEF (lokaal voorbereid — voer uit, zoek niet opnieuw tenzij hiaat)",
        f"## Taak\n{_clip(task, 1200)}",
    ]
    if studio:
        parts.append(f"## Studio\n{studio}")
    if workspace:
        parts.append(f"## Workspace\n{workspace}")
    if prior:
        parts.append("## Recente context\n" + "\n".join(f"- {p}" for p in prior))
    if mem_bits:
        parts.append("## Geheugen (kern)\n" + "\n".join(f"- {b}" for b in mem_bits))
    if know_bits:
        parts.append("## Kennis (kern)\n" + "\n".join(f"- {b}" for b in know_bits))
    if files:
        parts.append("## Relevante bestanden (snippets)")
        for f in files:
            parts.append(f"### {f['path']}\n```\n{f['snippet']}\n```")
    parts.append(
        "## Instructie aan uitvoerder\n"
        "- Gebruik bovenstaande snippets als waarheid; geen brede codebase-tour opnieuw.\n"
        "- Lever direct het eindresultaat (code/tekst). Tools alleen bij ontbrekende info.\n"
        "- Geen fluff; geen herhaling van de brief."
    )
    brief = "\n\n".join(parts)
    max_c = prep_max_chars()
    truncated = False
    if len(brief) > max_c:
        brief = brief[: max_c - 1] + "…"
        truncated = True

    # Rough token estimate (~4 chars/token)
    est_tokens = max(1, len(brief) // 4)
    raw_est = max(1, (len(task) + len(knowledge or "") + len(memory or "") + sum(len(f.get("snippet") or "") for f in files)) // 4)
    return {
        "ok": True,
        "brief": brief,
        "files": [{"path": f["path"], "via": f.get("via")} for f in files],
        "memory_bullets": len(mem_bits),
        "knowledge_bullets": len(know_bits),
        "chars": len(brief),
        "est_tokens": est_tokens,
        "est_tokens_without_prep": raw_est,
        "truncated": truncated,
        "system_note": (
            "Dit verzoek is lokaal voorbereid (EXEC_BRIEF). "
            "Voer de taak uit met die context. Geen herverkenning tenzij iets ontbreekt. "
            "Doel: sneller klaar met minder tokens, zelfde of betere kwaliteit."
        ),
    }


def should_local_prep(
    *,
    destination_local: bool,
    studio: str | None,
    task: str,
    skip: bool = False,
) -> bool:
    if skip or not prep_enabled():
        return False
    # Prep vooral nuttig vóór cloud; lokaal mag ook bij code/workspace
    if not destination_local:
        return len((task or "").strip()) >= 12
    st = (studio or "").lower()
    if st in {"software", "self", "apps", "webdesign", "ops"}:
        return len((task or "").strip()) >= 20
    return False
