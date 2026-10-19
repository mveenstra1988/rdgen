"""Volledige migratie: settings, MCP, rules, prompts, skills, hooks, geheugen.

Neemt alles mee wat lokaal op schijf staat voor Claude / ChatGPT / Cursor.
Server-side-only data (Custom GPTs, claude.ai cloud projects) blijft via export.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

MIGRATE_ROOT = ROOT / "data" / "migrated"
PROFILE_PATH = MIGRATE_ROOT / "active_profile.json"


def _home() -> Path:
    return Path.home()


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _copy_tree(src: Path, dest: Path) -> dict[str, int]:
    copied = 0
    skipped = 0
    if not src.exists():
        return {"copied": 0, "skipped": 0}
    dest.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return {"copied": 1, "skipped": 0}
    for dirpath, dirnames, filenames in os.walk(src):
        # skip bulky caches
        dirnames[:] = [
            d
            for d in dirnames
            if d
            not in {
                "Cache",
                "CachedData",
                "GPUCache",
                "Code Cache",
                "node_modules",
                ".git",
                "logs",
                "blob_storage",
            }
        ]
        rel = Path(dirpath).relative_to(src)
        target_dir = dest / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            sp = Path(dirpath) / name
            tp = target_dir / name
            try:
                if sp.stat().st_size > 25_000_000:
                    skipped += 1
                    continue
                shutil.copy2(sp, tp)
                copied += 1
            except OSError:
                skipped += 1
    return {"copied": copied, "skipped": skipped}


def _collect_named(paths: list[Path], kind: str) -> list[dict[str, Any]]:
    out = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            for p in path.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in {".json", ".jsonc", ".md", ".mdc", ".txt", ".toml", ".yaml", ".yml"}:
                    continue
                if p.stat().st_size > 2_000_000:
                    continue
                out.append(
                    {
                        "kind": kind,
                        "path": str(p),
                        "name": p.name,
                        "text": _read_text(p),
                        "json": _read_json(p) if p.suffix in {".json", ".jsonc"} else None,
                    }
                )
        else:
            out.append(
                {
                    "kind": kind,
                    "path": str(path),
                    "name": path.name,
                    "text": _read_text(path),
                    "json": _read_json(path) if path.suffix in {".json", ".jsonc"} else None,
                }
            )
    return out


def _project_glob_files(pattern_names: tuple[str, ...], max_hits: int = 80) -> list[Path]:
    hits: list[Path] = []
    h = _home()
    for base_name in ("Developer", "Projects", "code", "werk", "VIT", "src"):
        base = h / base_name
        if not base.is_dir():
            continue
        try:
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if p.name in pattern_names or (
                    p.suffix == ".mdc" and ".cursor" in p.parts
                ):
                    hits.append(p)
                if len(hits) >= max_hits:
                    return hits
        except OSError:
            continue
    return hits


def cursor_sources() -> dict[str, list[Path]]:
    h = _home()
    return {
        "settings": [
            h / "Library/Application Support/Cursor/User/settings.json",
            h / "Library/Application Support/Cursor/User/keybindings.json",
            h / ".cursor" / "argv.json",
            h / ".cursor" / "ide_state.json",
        ],
        "mcp": [
            h / ".cursor" / "mcp.json",
            h / ".cursor" / "mcp",
            h / "Library/Application Support/Cursor/User/globalStorage",
            Path("/home/ubuntu/.cursor/projects/workspace/mcps"),
            *_project_glob_files(("mcp.json", ".mcp.json"), max_hits=40),
        ],
        "rules": [
            h / ".cursor" / "rules",
            h / ".cursorrules",
            h / ".cursor" / "rules.md",
            *_project_glob_files(("AGENTS.md", ".cursorrules", "CLAUDE.md"), max_hits=60),
        ],
        "skills": [
            h / ".cursor" / "skills-cursor",
            h / ".cursor" / "skills",
            Path("/home/ubuntu/.cursor/skills-cursor"),
            Path("/cursor/stores/user/skills"),
        ],
        "prompts": [
            h / ".cursor" / "prompts",
            h / "Library/Application Support/Cursor/User/snippets",
        ],
        "agents": [
            h / ".cursor" / "agents",
            h / "Agent Store",
            Path("/cursor/stores/user"),
        ],
        "hooks": [
            h / ".cursor" / "hooks",
            h / ".cursor" / "hooks.json",
        ],
    }


def claude_sources() -> dict[str, list[Path]]:
    h = _home()
    return {
        "settings": [
            h / ".claude" / "settings.json",
            h / ".claude" / "settings.local.json",
            h / ".claude.json",
            h / "Library/Application Support/Claude" / "config.json",
            h / "Library/Application Support/Claude" / "Preferences",
        ],
        "mcp": [
            h / ".claude" / "mcp.json",
            h / ".claude.json",
            h / "Library/Application Support/Claude" / "mcp.json",
        ],
        "skills": [
            h / ".claude" / "skills",
            h / ".claude" / "plugins",
            h / ".claude" / "commands",
        ],
        "rules": [
            h / ".claude" / "CLAUDE.md",
            h / "CLAUDE.md",
            h / ".claude" / "rules",
        ],
        "prompts": [
            h / ".claude" / "prompts",
            h / ".claude" / "system-prompts",
        ],
        "hooks": [
            h / ".claude" / "hooks",
            h / ".claude" / "agent-hooks",
        ],
        "memory": [
            h / ".claude" / "memory",
            h / ".claude" / "projects",
        ],
        "desktop": [
            h / "Library/Application Support/Claude",
            h / "Library/Application Support/Claude-3p",
        ],
    }


def chatgpt_sources() -> dict[str, list[Path]]:
    h = _home()
    return {
        "settings": [
            h / "Library/Application Support/com.openai.chat" / "settings.json",
            h / "Library/Preferences/com.openai.chat.plist",
            h / "Library/Application Support/com.openai.chat" / "config.json",
        ],
        "prompts": [
            h / "Library/Application Support/com.openai.chat" / "prompts",
            h / "Library/Application Support/com.openai.chat" / "customInstructions",
        ],
        "gpts": [
            h / "Library/Application Support/com.openai.chat" / "gpts",
            h / "Library/Application Support/com.openai.chat" / "customGpts",
        ],
        "memory": [
            h / "Library/Application Support/com.openai.chat" / "memory",
        ],
        "support": [
            h / "Library/Application Support/com.openai.chat",
        ],
        "cache": [
            h / "Library/Caches/com.openai.chat",
        ],
    }


def _merge_mcp(entries: list[dict[str, Any]]) -> dict[str, Any]:
    servers: dict[str, Any] = {}
    for e in entries:
        data = e.get("json")
        if not isinstance(data, dict):
            continue
        # Cursor / Claude shapes
        block = data.get("mcpServers") or data.get("servers") or data
        if isinstance(block, dict):
            for name, cfg in block.items():
                if isinstance(cfg, dict) and ("command" in cfg or "url" in cfg or "args" in cfg):
                    servers[str(name)] = cfg
    return {"mcpServers": servers}


def _save_profile(profile: dict[str, Any]) -> None:
    MIGRATE_ROOT.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_active_profile() -> dict[str, Any]:
    if not PROFILE_PATH.is_file():
        return {}
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def migrate_everything(*, promote_skills: bool = True) -> dict[str, Any]:
    """Eén call: alles kopiëren + indexeren + actief profiel voor runtime."""
    started = time.time()
    MIGRATE_ROOT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "cursor": {},
        "claude": {},
        "chatgpt": {},
        "mirrored": {},
        "errors": [],
    }

    # 1) Mirror raw trees (niets overslaan binnen size-limiet)
    mirrors = {
        "cursor_dot": (_home() / ".cursor", MIGRATE_ROOT / "mirror" / "cursor_dot"),
        "cursor_app_support": (
            _home() / "Library/Application Support/Cursor",
            MIGRATE_ROOT / "mirror" / "cursor_app_support",
        ),
        "claude_dot": (_home() / ".claude", MIGRATE_ROOT / "mirror" / "claude_dot"),
        "claude_desktop": (
            _home() / "Library/Application Support/Claude",
            MIGRATE_ROOT / "mirror" / "claude_desktop",
        ),
        "chatgpt_support": (
            _home() / "Library/Application Support/com.openai.chat",
            MIGRATE_ROOT / "mirror" / "chatgpt_support",
        ),
        "chatgpt_cache": (
            _home() / "Library/Caches/com.openai.chat",
            MIGRATE_ROOT / "mirror" / "chatgpt_cache",
        ),
        "agent_store": (Path("/cursor/stores/user"), MIGRATE_ROOT / "mirror" / "agent_store"),
        "skills_cursor_home": (
            _home() / ".cursor" / "skills-cursor",
            MIGRATE_ROOT / "mirror" / "skills_cursor",
        ),
    }
    for key, (src, dest) in mirrors.items():
        try:
            report["mirrored"][key] = {
                "src": str(src),
                "dest": str(dest),
                **_copy_tree(src, dest),
                "exists": src.exists(),
            }
        except Exception as exc:
            report["errors"].append({"mirror": key, "error": str(exc)})

    # 2) Structured harvest
    for label, sources_fn in (
        ("cursor", cursor_sources),
        ("claude", claude_sources),
        ("chatgpt", chatgpt_sources),
    ):
        bucket: dict[str, Any] = {}
        for kind, paths in sources_fn().items():
            bucket[kind] = _collect_named(paths, f"{label}:{kind}")
        report[label] = {k: len(v) for k, v in bucket.items()}
        report[f"{label}_items"] = bucket

    # 3) Existing importers (chats/memory/skills)
    try:
        from vit_ai_hub.importing.pipeline import import_all_one_click

        report["knowledge_import"] = import_all_one_click()
    except Exception as exc:
        report["errors"].append({"knowledge_import": str(exc)})

    try:
        from vit_ai_hub.importing.skills import harvest_skills

        report["skills"] = harvest_skills(promote_agents=promote_skills)
    except Exception as exc:
        report["errors"].append({"skills": str(exc)})

    # 4) Persist structured artifacts + memories
    from vit_ai_hub.importing.store import save_memories, save_settings_bundle

    all_items: list[dict[str, Any]] = []
    for key in ("cursor_items", "claude_items", "chatgpt_items"):
        for kind, items in (report.get(key) or {}).items():
            all_items.extend(items)

    mem_rows = []
    mcp_entries = []
    rules_text: list[str] = []
    prompts_text: list[str] = []
    settings_bundle: dict[str, Any] = {"files": []}

    for item in all_items:
        kind = item.get("kind") or ""
        settings_bundle["files"].append(
            {"kind": kind, "path": item.get("path"), "name": item.get("name")}
        )
        mem_rows.append(
            {
                "native_id": item.get("path"),
                "key": f"migrate:{kind}:{item.get('name')}",
                "content": (item.get("text") or json.dumps(item.get("json"), ensure_ascii=False) or "")[:12000],
                "meta": {"kind": kind, "path": item.get("path")},
            }
        )
        if ":mcp" in kind or kind.endswith("mcp"):
            mcp_entries.append(item)
        if ":rules" in kind or kind.endswith("rules"):
            if item.get("text"):
                rules_text.append(f"## {item.get('path')}\n{item['text']}")
        if ":prompts" in kind or "prompt" in kind or "customInstructions" in kind:
            if item.get("text"):
                prompts_text.append(f"## {item.get('path')}\n{item['text']}")

    report["settings_saved"] = save_settings_bundle(settings_bundle)
    report["memories_saved"] = save_memories(mem_rows, source="full_migrate")

    mcp_merged = _merge_mcp(mcp_entries)
    mcp_path = MIGRATE_ROOT / "mcp.json"
    mcp_path.write_text(json.dumps(mcp_merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rules_path = MIGRATE_ROOT / "rules_combined.md"
    rules_path.write_text("\n\n".join(rules_text)[:500_000], encoding="utf-8")
    prompts_path = MIGRATE_ROOT / "prompts_combined.md"
    prompts_path.write_text("\n\n".join(prompts_text)[:500_000], encoding="utf-8")

    profile = {
        "updated_at": time.time(),
        "mcp_path": str(mcp_path),
        "mcp_servers": list((mcp_merged.get("mcpServers") or {}).keys()),
        "rules_path": str(rules_path),
        "prompts_path": str(prompts_path),
        "mirror_root": str(MIGRATE_ROOT / "mirror"),
        "inject_rules": True,
        "inject_prompts": True,
        "self_improve": True,
        "sources": {
            "cursor": report.get("cursor"),
            "claude": report.get("claude"),
            "chatgpt": report.get("chatgpt"),
            "mirrored_files": sum(int(v.get("copied") or 0) for v in report.get("mirrored", {}).values()),
        },
    }
    _save_profile(profile)
    report["profile"] = profile
    report["ok"] = True
    report["elapsed_sec"] = round(time.time() - started, 2)
    report["honest_limits"] = [
        "ChatGPT conversations-v2/v3 *.data blijven encrypted → officiële export-zip nodig voor volledige history.",
        "Custom GPTs / Claude.ai cloud-only bots/projects: alleen wat lokaal of in export staat.",
        "MCP-servers worden overgenomen als config; binaries/auth moeten op de Mac nog geldig zijn.",
    ]
    return report


def runtime_system_addons() -> str:
    """Tekst die bij elke chat wordt geïnjecteerd: rules + prompts uit migratie."""
    profile = load_active_profile()
    if not profile:
        return ""
    parts = ["[VIT gemigreerde Claude/Cursor/ChatGPT regels & prompts — actief]"]
    if profile.get("inject_rules"):
        rp = Path(profile.get("rules_path") or "")
        if rp.is_file():
            parts.append(rp.read_text(encoding="utf-8", errors="replace")[:8000])
    if profile.get("inject_prompts"):
        pp = Path(profile.get("prompts_path") or "")
        if pp.is_file():
            parts.append(pp.read_text(encoding="utf-8", errors="replace")[:6000])
    mcp = profile.get("mcp_servers") or []
    if mcp:
        parts.append("MCP-servers in profiel: " + ", ".join(mcp))
    if profile.get("self_improve"):
        parts.append(
            "Self-improve: als de user vraagt de hub te verbeteren, pas bestanden onder de hub-root aan "
            "via workspace-tools (schrijven/testen) en leg kort uit wat je wijzigde."
        )
    text = "\n\n".join(parts).strip()
    return text[:16000] if text else ""
