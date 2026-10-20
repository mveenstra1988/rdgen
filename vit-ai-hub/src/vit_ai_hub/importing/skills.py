"""Importeer Claude/Cursor skills, commands en bot-achtige instructies."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


def _home() -> Path:
    return Path.home()


def skill_candidate_roots() -> list[Path]:
    from vit_ai_hub.config import ROOT

    h = _home()
    roots = [
        ROOT / "data" / "skills",
        h / ".claude" / "skills",
        h / ".claude" / "commands",
        h / ".claude" / "plugins",
        h / ".config" / "claude" / "skills",
        h / ".cursor" / "skills-cursor",
        h / ".cursor" / "skills",
        h / ".agents" / "skills",
        Path("/home/ubuntu/.cursor/skills-cursor"),
        Path("/cursor/stores/user/skills"),
        h / "Library/Application Support/Claude" / "skills",
        h / "Library/Application Support/Cursor" / "User" / "globalStorage",
    ]
    # project-local .claude/skills under common work dirs
    for base_name in ("Developer", "Projects", "code", "werk", "VIT", "src"):
        base = h / base_name
        if base.is_dir():
            roots.append(base)
    return roots


def _parse_skill_md(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    text = text.strip()
    if not text:
        return None
    name = path.parent.name if path.name in {"SKILL.md", "skill.md"} else path.stem
    description = ""
    body = text
    named_from_fm = False
    m = _FRONTMATTER.match(text)
    if m:
        fm, body = m.group(1), m.group(2)
        for line in fm.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                k, v = k.strip().lower(), v.strip().strip("\"'")
                if k in {"name", "title"} and v:
                    name = v
                    named_from_fm = True
                elif k in {"description", "desc"}:
                    description = v
    # first heading as name fallback only if frontmatter had no name
    if not named_from_fm:
        for line in body.splitlines():
            if line.startswith("# "):
                name = line[2:].strip() or name
                break
    return {
        "native_id": str(path.resolve()),
        "name": name[:80],
        "description": description[:240],
        "content": body.strip()[:20000],
        "path": str(path),
        "kind": "skill",
    }


def _iter_skill_files(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        return found
    # shallow for huge trees like Projects
    max_depth = 4 if root.name in {"Developer", "Projects", "code", "werk", "VIT", "src"} else 8
    root_depth = len(root.parts)
    patterns = ("SKILL.md", "skill.md", "*.skill.md")
    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            depth = len(path.parts) - root_depth
            if depth > max_depth:
                continue
            name = path.name
            if name in {"SKILL.md", "skill.md"} or name.endswith(".skill.md"):
                found.append(path)
            elif path.suffix == ".md" and any(
                p in path.parts for p in ("skills", "skills-cursor", "commands", "plugins")
            ):
                # skip huge logs
                if name.lower() in {"logboek.md", "readme.md", "changelog.md"}:
                    continue
                found.append(path)
            if len(found) >= 400:
                break
    except OSError:
        pass
    return found


def discover_skills() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for root in skill_candidate_roots():
        for path in _iter_skill_files(root):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            parsed = _parse_skill_md(path)
            if not parsed:
                continue
            # source tag
            p = key.lower()
            if "/.claude/" in p or "claude" in p:
                parsed["source"] = "claude_skill"
            elif "cursor" in p or "skills-cursor" in p:
                parsed["source"] = "cursor_skill"
            else:
                parsed["source"] = "local_skill"
            out.append(parsed)
    return out


def harvest_skills(*, promote_agents: bool = True) -> dict[str, Any]:
    """Scan Mac voor skills → knowledge store (+ optioneel agent per skill)."""
    from vit_ai_hub.importing.store import save_memories, save_skills

    skills = discover_skills()
    memory_rows = []
    for s in skills:
        memory_rows.append(
            {
                "native_id": s["native_id"],
                "key": f"skill:{s['name']}",
                "content": f"# Skill: {s['name']}\n{s.get('description') or ''}\n\n{s['content']}",
                "meta": {"kind": "skill", "path": s.get("path"), "source": s.get("source")},
            }
        )
    skill_save = save_skills(skills)
    mem_save = save_memories(memory_rows, source="skills")

    promoted = {"written": 0, "skipped": 0}
    if promote_agents and skills:
        from vit_ai_hub.agents.store import save_agent, get_agent

        for s in skills:
            slug = re.sub(r"[^a-z0-9_-]+", "-", s["name"].lower()).strip("-")[:40] or "skill"
            agent_id = f"agent-skill-{slug}"
            if get_agent(agent_id):
                promoted["skipped"] += 1
                continue
            save_agent(
                {
                    "id": agent_id,
                    "name": s["name"][:80],
                    "role": "Skill (geïmporteerd)",
                    "color": "#ffb454",
                    "model": "vit/auto",
                    "studio": "software" if "code" in (s.get("content") or "").lower()[:200] else "chat",
                    "system": (
                        f"Je volgt deze geïmporteerde skill strikt.\n"
                        f"{s.get('description') or ''}\n\n{s['content'][:6000]}"
                    ),
                    "tools": True,
                    "preset": False,
                }
            )
            promoted["written"] += 1

    return {
        "source": "skills",
        "found": len(skills),
        "skills": skill_save,
        "memories": mem_save,
        "agents_promoted": promoted,
        "samples": [{"name": s["name"], "source": s.get("source"), "path": s.get("path")} for s in skills[:12]],
    }
