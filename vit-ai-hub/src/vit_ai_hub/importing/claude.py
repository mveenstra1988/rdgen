from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


def _message_text(msg: dict[str, Any]) -> str:
    if msg.get("text"):
        return str(msg["text"])
    parts = []
    for block in msg.get("content") or []:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "text":
            parts.append(str(block.get("text") or ""))
        elif t == "thinking":
            parts.append(str(block.get("thinking") or ""))
        elif t == "tool_use":
            parts.append(f"[tool_use {block.get('name')}] {json.dumps(block.get('input') or {}, ensure_ascii=False)[:400]}")
        elif t == "tool_result":
            parts.append(f"[tool_result {block.get('name')}]")
    return "\n".join(p for p in parts if p)


def parse_conversations(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out = []
    for conv in data:
        if not isinstance(conv, dict):
            continue
        messages = []
        for msg in conv.get("chat_messages") or []:
            if not isinstance(msg, dict):
                continue
            sender = msg.get("sender") or "human"
            role = "user" if sender in {"human", "user"} else "assistant"
            text = _message_text(msg)
            if text.strip():
                messages.append({"role": role, "content": text})
        out.append(
            {
                "native_id": conv.get("uuid") or conv.get("id") or "",
                "title": conv.get("name") or conv.get("summary") or "Claude chat",
                "created_at": conv.get("created_at"),
                "updated_at": conv.get("updated_at"),
                "messages": messages,
                "meta": {"summary": conv.get("summary")},
            }
        )
    return out


def parse_memories(data: Any) -> list[dict[str, Any]]:
    items = data if isinstance(data, list) else (data.get("memories") if isinstance(data, dict) else None)
    if not isinstance(items, list):
        # sometimes dict of memories
        if isinstance(data, dict):
            items = []
            for k, v in data.items():
                if k in {"memories"}:
                    continue
                if isinstance(v, str):
                    items.append({"key": k, "content": v})
                elif isinstance(v, dict):
                    items.append(
                        {
                            "key": v.get("key") or k,
                            "content": v.get("content") or v.get("text") or json.dumps(v, ensure_ascii=False),
                            "native_id": v.get("uuid") or v.get("id") or k,
                        }
                    )
        else:
            return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            if isinstance(item, str):
                out.append({"content": item, "key": "memory"})
            continue
        content = item.get("content") or item.get("text") or item.get("memory") or ""
        if isinstance(content, (list, dict)):
            content = json.dumps(content, ensure_ascii=False)
        out.append(
            {
                "native_id": item.get("uuid") or item.get("id") or "",
                "key": item.get("key") or item.get("name") or "claude-memory",
                "content": str(content),
            }
        )
    return out


def parse_projects(data: Any) -> list[dict[str, Any]]:
    items = data if isinstance(data, list) else (data.get("projects") if isinstance(data, dict) else [])
    if not isinstance(items, list):
        return []
    out = []
    for p in items:
        if not isinstance(p, dict):
            continue
        docs = []
        for d in p.get("docs") or p.get("documents") or p.get("project_knowledge") or []:
            if isinstance(d, dict):
                docs.append(
                    {
                        "name": d.get("filename") or d.get("name") or "doc",
                        "content": d.get("content") or d.get("text") or "",
                    }
                )
            elif isinstance(d, str):
                docs.append({"name": "doc", "content": d})
        out.append(
            {
                "native_id": p.get("uuid") or p.get("id") or "",
                "name": p.get("name") or "Claude project",
                "instructions": p.get("prompt_template")
                or p.get("custom_instructions")
                or p.get("instructions")
                or "",
                "documents": docs,
            }
        )
    return out


def import_from_path(path: Path) -> dict[str, Any]:
    path = Path(path)
    conversations: list[dict[str, Any]] = []
    memories: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []

    def handle_json(name: str, raw: bytes) -> None:
        nonlocal conversations, memories, projects
        data = json.loads(raw.decode("utf-8", errors="replace"))
        base = Path(name).name.lower()
        if base == "conversations.json":
            conversations.extend(parse_conversations(data))
        elif base == "memories.json":
            memories.extend(parse_memories(data))
        elif base == "projects.json":
            projects.extend(parse_projects(data))

    if path.suffix.lower() == ".json":
        handle_json(path.name, path.read_bytes())
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                base = Path(name).name.lower()
                if base in {"conversations.json", "memories.json", "projects.json"}:
                    handle_json(name, zf.read(name))
    else:
        raise ValueError(f"Onbekend Claude-bestand: {path}")

    from vit_ai_hub.importing.store import log_import, save_conversations, save_memories, save_projects

    summary = {
        "source": "claude",
        "file": str(path),
        "conversations": save_conversations(conversations, source="claude"),
        "memories": save_memories(memories, source="claude"),
        "projects": save_projects(projects, source="claude"),
    }
    # project docs → memory snippets
    extra_mem = []
    for p in projects:
        if p.get("instructions"):
            extra_mem.append(
                {
                    "native_id": f"proj-instr-{p.get('native_id')}",
                    "key": f"claude-project:{p.get('name')}",
                    "content": str(p.get("instructions"))[:4000],
                }
            )
        for d in p.get("documents") or []:
            if d.get("content"):
                extra_mem.append(
                    {
                        "native_id": f"proj-doc-{p.get('native_id')}-{d.get('name')}",
                        "key": f"claude-doc:{p.get('name')}:{d.get('name')}",
                        "content": str(d.get("content"))[:4000],
                    }
                )
    if extra_mem:
        summary["project_memories"] = save_memories(extra_mem, source="claude")
    log_import(summary)
    return summary
