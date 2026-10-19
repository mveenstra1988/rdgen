"""Lees wat er lokaal op de Mac staat (zelfde machine als ChatGPT/Claude/Cursor).

Feiten:
- Claude Code / Cowork: JSONL + markdown memory, wél leesbaar.
- Claude Desktop: vooral UI/auth lokaal; claude.ai-chats server-side.
- ChatGPT Mac-app: conversations-v2/v3/*.data is encrypted at rest.
  Wel probeerbaar: cache-fragmenten under Library/Caches.
- Officiële export blijft de volledige ChatGPT/claude.ai history; we starten
  die met één klik via open/osascript en importeren de zip automatisch.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def _home() -> Path:
    return Path.home()


def chatgpt_roots() -> list[Path]:
    h = _home()
    return [
        h / "Library/Application Support/com.openai.chat",
        h / "Library/Caches/com.openai.chat",
        h / "Library/Containers/com.openai.chat/Data/Library/Application Support/com.openai.chat",
    ]


def claude_roots() -> list[Path]:
    h = _home()
    return [
        h / "Library/Application Support/Claude",
        h / "Library/Application Support/Claude-3p",
        h / ".claude",
    ]


def detect_local_apps() -> dict[str, Any]:
    info: dict[str, Any] = {
        "chatgpt_app": False,
        "chatgpt_encrypted_conversations": 0,
        "chatgpt_cache_files": 0,
        "claude_desktop": False,
        "claude_code_home": False,
        "claude_code_transcripts": 0,
        "paths": {},
    }
    for root in chatgpt_roots():
        if not root.exists():
            continue
        if "Application Support" in str(root) and root.name == "com.openai.chat":
            info["chatgpt_app"] = True
            info["paths"]["chatgpt_support"] = str(root)
            count = 0
            for p in root.glob("conversations-*/**/*"):
                if p.is_file() and p.suffix in {".data", ""}:
                    count += 1
            for p in root.glob("conversations-*/*.data"):
                count += 1
            info["chatgpt_encrypted_conversations"] = max(
                info["chatgpt_encrypted_conversations"], count
            )
        if "Caches" in str(root):
            cache = root / "fsCachedData"
            if cache.is_dir():
                info["chatgpt_cache_files"] = sum(1 for _ in cache.iterdir() if _.is_file())
                info["paths"]["chatgpt_cache"] = str(cache)

    claude_app = _home() / "Library/Application Support/Claude"
    if claude_app.exists():
        info["claude_desktop"] = True
        info["paths"]["claude_desktop"] = str(claude_app)
    code = _home() / ".claude"
    if code.exists():
        info["claude_code_home"] = True
        info["paths"]["claude_code"] = str(code)
        info["claude_code_transcripts"] = sum(1 for _ in code.glob("projects/**/*.jsonl"))
    return info


def _parse_jsonl_messages(path: Path) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            # Claude Code style
            if row.get("type") in {"user", "assistant"} and isinstance(row.get("message"), dict):
                msg = row["message"]
                role = msg.get("role") or row.get("type")
                content = msg.get("content")
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(str(block.get("text") or ""))
                        elif isinstance(block, str):
                            texts.append(block)
                    content = "\n".join(t for t in texts if t)
                if content:
                    messages.append({"role": str(role), "content": str(content)})
            elif row.get("role") and (row.get("content") or row.get("text")):
                messages.append(
                    {
                        "role": str(row.get("role")),
                        "content": str(row.get("content") or row.get("text") or ""),
                    }
                )
    return messages


def harvest_claude_code() -> dict[str, Any]:
    from vit_ai_hub.importing.store import save_conversations, save_memories

    root = _home() / ".claude"
    conversations = []
    memories = []
    if not root.exists():
        return {"source": "claude_code", "conversations": {"written": 0, "skipped": 0}, "memories": {"written": 0, "skipped": 0}}

    for path in root.glob("projects/**/*.jsonl"):
        msgs = _parse_jsonl_messages(path)
        if msgs:
            conversations.append(
                {
                    "native_id": str(path),
                    "title": f"Claude Code · {path.parent.name}/{path.stem}",
                    "messages": msgs,
                    "meta": {"path": str(path)},
                }
            )
    for path in root.glob("**/*.md"):
        if path.name.lower() in {"claude.md", "memory.md"} or "memory" in path.parts:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                memories.append(
                    {
                        "native_id": str(path),
                        "key": f"claude-code:{path}",
                        "content": text[:12000],
                    }
                )
    return {
        "source": "claude_code",
        "conversations": save_conversations(conversations, source="claude_code"),
        "memories": save_memories(memories, source="claude_code"),
    }


def harvest_claude_desktop() -> dict[str, Any]:
    roots = [
        _home() / "Library/Application Support/Claude",
        _home() / "Library/Application Support/Claude-3p",
    ]
    conversations = []
    memories = []
    scanned = 0
    for root in roots:
        if not root.exists():
            continue
        # Cowork / local-agent sessions
        for path in root.glob("local-agent-mode-sessions/**/*.json"):
            scanned += 1
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(data, dict):
                title = data.get("title") or path.stem
                msgs = []
                for m in data.get("messages") or data.get("chat_messages") or []:
                    if isinstance(m, dict):
                        role = m.get("role") or ("user" if m.get("sender") == "human" else "assistant")
                        content = m.get("content") or m.get("text") or ""
                        if isinstance(content, list):
                            content = " ".join(
                                str(b.get("text") if isinstance(b, dict) else b) for b in content
                            )
                        if content:
                            msgs.append({"role": str(role), "content": str(content)})
                if msgs:
                    conversations.append(
                        {
                            "native_id": str(path),
                            "title": f"Claude Desktop · {title}",
                            "messages": msgs,
                            "meta": {"path": str(path)},
                        }
                    )
                # nested summary fields
                for key in ("summary", "instructions", "system"):
                    if data.get(key):
                        memories.append(
                            {
                                "native_id": f"{path}:{key}",
                                "key": f"claude-desktop:{title}:{key}",
                                "content": str(data.get(key))[:8000],
                            }
                        )
        for path in root.glob("local-agent-mode-sessions/**/memory/**/*.md"):
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                memories.append(
                    {
                        "native_id": str(path),
                        "key": f"claude-memory:{path.name}",
                        "content": text[:12000],
                    }
                )
        # also harvest nested .claude projects under local sessions
        for path in root.glob("local-agent-mode-sessions/**/.claude/projects/**/*.jsonl"):
            msgs = _parse_jsonl_messages(path)
            if msgs:
                conversations.append(
                    {
                        "native_id": str(path),
                        "title": f"Claude Cowork · {path.stem}",
                        "messages": msgs,
                        "meta": {"path": str(path)},
                    }
                )
    from vit_ai_hub.importing.store import save_conversations, save_memories

    return {
        "source": "claude_desktop",
        "files_scanned": scanned,
        "conversations": save_conversations(conversations, source="claude_desktop"),
        "memories": save_memories(memories, source="claude_desktop"),
    }


def harvest_chatgpt_cache() -> dict[str, Any]:
    """Best-effort: fsCachedData + eventuele plaintext leftovers (pre-encrypt)."""
    from vit_ai_hub.importing.store import save_conversations, save_memories

    conversations = []
    memories = []
    cache_dirs = [
        _home() / "Library/Caches/com.openai.chat/fsCachedData",
        _home() / "Library/Caches/com.openai.chat",
    ]
    support = _home() / "Library/Application Support/com.openai.chat"
    # old plaintext layout (pre mid-2024), if somehow still present
    if support.exists():
        for path in support.glob("conversations-*/*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(data, dict) and (data.get("mapping") or data.get("title")):
                from vit_ai_hub.importing.chatgpt import parse_conversations_payload

                conversations.extend(parse_conversations_payload([data]))

    for cache in cache_dirs:
        if not cache.exists():
            continue
        files = list(cache.iterdir()) if cache.is_dir() else []
        for path in files[:2000]:
            if not path.is_file():
                continue
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # keep text snippets that look like chat
                if '"role"' in raw or "assistant" in raw.lower():
                    memories.append(
                        {
                            "native_id": str(path),
                            "key": f"chatgpt-cache:{path.name}",
                            "content": raw[:8000],
                        }
                    )
                continue
            # common API envelope fragments
            if isinstance(data, dict):
                if data.get("mapping") or data.get("conversation_id"):
                    from vit_ai_hub.importing.chatgpt import parse_conversations_payload

                    conversations.extend(parse_conversations_payload([data]))
                elif "messages" in data and isinstance(data["messages"], list):
                    msgs = []
                    for m in data["messages"]:
                        if isinstance(m, dict) and (m.get("content") or m.get("text")):
                            msgs.append(
                                {
                                    "role": m.get("role") or "assistant",
                                    "content": str(m.get("content") or m.get("text")),
                                }
                            )
                    if msgs:
                        conversations.append(
                            {
                                "native_id": str(path),
                                "title": f"ChatGPT cache · {path.name[:12]}",
                                "messages": msgs,
                            }
                        )
                else:
                    blob = json.dumps(data, ensure_ascii=False)
                    if any(k in blob.lower() for k in ("assistant", "chatgpt", "message")):
                        memories.append(
                            {
                                "native_id": str(path),
                                "key": f"chatgpt-cache-json:{path.name}",
                                "content": blob[:8000],
                            }
                        )

    enc = 0
    if support.exists():
        enc = sum(1 for _ in support.glob("conversations-*/*.data"))
    return {
        "source": "chatgpt_local",
        "encrypted_conversation_files": enc,
        "note": (
            "ChatGPT Mac-app encrypteert conversations-v2/v3 at rest; "
            "volledige history via officiële export of cache-fragmenten hieronder."
            if enc
            else "Geen encrypted conversation store gevonden."
        ),
        "conversations": save_conversations(conversations, source="chatgpt_local"),
        "memories": save_memories(memories, source="chatgpt_local"),
    }


def request_official_exports() -> dict[str, Any]:
    """Open de juiste export/settings in de apps (macOS). User bevestigt 1x; wij watchen Downloads."""
    results = {"chatgpt": None, "claude": None, "commands": []}
    if os.uname().sysname != "Darwin":
        return {
            **results,
            "ok": False,
            "error": "Export-aanvraag via apps werkt alleen op macOS.",
        }

    # ChatGPT: activeer app + open data controls indien mogelijk
    chatgpt_script = """
    tell application "System Events"
      if exists (application process "ChatGPT") then
        tell application "ChatGPT" to activate
      end if
    end tell
    """
    claude_script = """
    tell application "System Events"
      if exists (application process "Claude") then
        tell application "Claude" to activate
      end if
    end tell
    """
    try:
        subprocess.run(["osascript", "-e", chatgpt_script], check=False, capture_output=True)
        # OpenAI help / in-app settings deep link fallbacks
        subprocess.run(
            ["open", "https://chatgpt.com/#settings/DataControls"],
            check=False,
            capture_output=True,
        )
        results["chatgpt"] = "opened"
        results["commands"].append("open ChatGPT + DataControls")
    except Exception as exc:
        results["chatgpt"] = str(exc)

    try:
        subprocess.run(["osascript", "-e", claude_script], check=False, capture_output=True)
        subprocess.run(
            ["open", "https://claude.ai/settings/privacy"],
            check=False,
            capture_output=True,
        )
        results["claude"] = "opened"
        results["commands"].append("open Claude + privacy settings")
    except Exception as exc:
        results["claude"] = str(exc)

    results["ok"] = True
    results["next"] = (
        "Klik Export in beide schermen. Zet de zips in Downloads; "
        "gebruik daarna 'Wacht op exports & importeer' of Importeer alles."
    )
    return results


def wait_and_import_exports(*, timeout_sec: int = 600, poll_sec: int = 5) -> dict[str, Any]:
    """Watch Downloads/Desktop for nieuwe ChatGPT/Claude zips en importeer ze."""
    from vit_ai_hub.importing.pipeline import find_export_zips, import_file

    started = time.time()
    seen = set()
    imported = []
    while time.time() - started < timeout_sec:
        found = find_export_zips()
        for src in ("chatgpt", "claude"):
            for path in found.get(src) or []:
                key = (src, str(path), path.stat().st_mtime)
                if key in seen:
                    continue
                # only import relatively new files (2h) during wait
                if time.time() - path.stat().st_mtime > 7200:
                    continue
                seen.add(key)
                try:
                    imported.append(import_file(path, source=src))
                except Exception as exc:
                    imported.append({"source": src, "file": str(path), "error": str(exc)})
        if any(i.get("source") == "chatgpt" for i in imported) and any(
            i.get("source") == "claude" for i in imported
        ):
            break
        time.sleep(poll_sec)
    return {
        "imported": imported,
        "elapsed_sec": round(time.time() - started, 1),
        "timed_out": time.time() - started >= timeout_sec and not imported,
    }


def harvest_all_local() -> dict[str, Any]:
    detection = detect_local_apps()
    out: dict[str, Any] = {
        "detection": detection,
        "claude_code": harvest_claude_code(),
        "claude_desktop": harvest_claude_desktop(),
        "chatgpt_local": harvest_chatgpt_cache(),
    }
    # Als ChatGPT op deze Mac staat: lees wat de app toont / keychain kan geven
    try:
        from vit_ai_hub.importing.chatgpt_live import harvest_chatgpt_readable

        out["chatgpt_readable"] = harvest_chatgpt_readable()
    except Exception as exc:
        out["chatgpt_readable"] = {"ok": False, "error": str(exc)}
    return out
