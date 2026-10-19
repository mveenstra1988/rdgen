from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


def _parts_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            out = []
            for p in parts:
                if isinstance(p, str):
                    out.append(p)
                elif isinstance(p, dict):
                    out.append(str(p.get("text") or p.get("content") or ""))
            return "\n".join(x for x in out if x)
        return str(content.get("text") or "")
    return str(content)


def _linearize_mapping(conv: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = conv.get("mapping") or {}
    current = conv.get("current_node")
    if not mapping:
        return []
    # walk parents from current_node
    chain_ids: list[str] = []
    node_id = current
    seen = set()
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        chain_ids.append(node_id)
        node_id = mapping[node_id].get("parent")
    chain_ids.reverse()
    messages = []
    for nid in chain_ids:
        node = mapping.get(nid) or {}
        msg = node.get("message") or {}
        if not msg:
            continue
        role = ((msg.get("author") or {}).get("role")) or "assistant"
        if role not in {"user", "assistant", "system", "tool"}:
            role = "assistant"
        text = _parts_to_text(msg.get("content"))
        if not text.strip():
            continue
        messages.append({"role": role, "content": text})
    return messages


def parse_conversations_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and "conversations" in data:
        data = data["conversations"]
    if not isinstance(data, list):
        return []
    out = []
    for conv in data:
        if not isinstance(conv, dict):
            continue
        messages = _linearize_mapping(conv)
        if not messages and isinstance(conv.get("messages"), list):
            for m in conv["messages"]:
                if not isinstance(m, dict):
                    continue
                messages.append(
                    {
                        "role": m.get("role") or "user",
                        "content": _parts_to_text(m.get("content") or m.get("text")),
                    }
                )
        out.append(
            {
                "native_id": conv.get("conversation_id") or conv.get("id") or "",
                "title": conv.get("title") or "ChatGPT chat",
                "created_at": conv.get("create_time"),
                "updated_at": conv.get("update_time"),
                "messages": messages,
                "meta": {"gizmo_id": conv.get("gizmo_id")},
            }
        )
    return out


def _load_json_bytes(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8", errors="replace"))


def import_from_path(path: Path) -> dict[str, Any]:
    path = Path(path)
    conversations: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        conversations.extend(parse_conversations_payload(_load_json_bytes(path.read_bytes())))
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            # nested zips
            for name in names:
                lower = name.lower()
                if lower.endswith(".zip") and ("conversation" in lower or "part-" in lower):
                    with zf.open(name) as nested_fh:
                        nested_bytes = nested_fh.read()
                    import io

                    with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested:
                        for n2 in nested.namelist():
                            if _is_conversations_file(n2):
                                conversations.extend(
                                    parse_conversations_payload(_load_json_bytes(nested.read(n2)))
                                )
                elif _is_conversations_file(name):
                    conversations.extend(parse_conversations_payload(_load_json_bytes(zf.read(name))))
    else:
        raise ValueError(f"Onbekend ChatGPT-bestand: {path}")

    from vit_ai_hub.importing.store import log_import, save_conversations

    stats = save_conversations(conversations, source="chatgpt")
    # distill short memory snippets from titles + last user lines
    memories = []
    for c in conversations[:500]:
        last_user = next((m["content"] for m in reversed(c["messages"]) if m["role"] == "user"), "")
        if last_user:
            memories.append(
                {
                    "native_id": c.get("native_id"),
                    "key": f"chatgpt:{c.get('title')}",
                    "content": f"ChatGPT '{c.get('title')}': {last_user[:500]}",
                }
            )
    from vit_ai_hub.importing.store import save_memories

    mem_stats = save_memories(memories, source="chatgpt")
    summary = {
        "source": "chatgpt",
        "file": str(path),
        "conversations": stats,
        "memories": mem_stats,
    }
    log_import(summary)
    return summary


def _is_conversations_file(name: str) -> bool:
    base = Path(name).name.lower()
    return base == "conversations.json" or (
        base.startswith("conversations-") and base.endswith(".json")
    )
