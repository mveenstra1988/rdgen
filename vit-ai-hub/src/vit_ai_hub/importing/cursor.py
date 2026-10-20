from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator


def candidate_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".cursor",
        home / "Library/Application Support/Cursor",
        home / ".config/Cursor",
        home / ".config/cursor",
        Path("/cursor/stores/user"),
        home / ".cursor-stores/user",
        home / "Agent Store",
    ]
    # optional override
    extra = os.environ.get("VIT_CURSOR_IMPORT_PATHS", "")
    for part in extra.split(":"):
        if part.strip():
            roots.append(Path(part.strip()).expanduser())
    return [p for p in roots if p.exists()]


def _iter_files(root: Path) -> Iterator[Path]:
    patterns = ("*.jsonl", "*.json", "*.md", "*.txt")
    skip_parts = {".git", "node_modules", "Cache", "CachedData", "GPUCache", "Code Cache"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_parts and not d.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            if any(path.match(pat) for pat in ("*.jsonl", "*.md")):
                yield path
            elif name.endswith(".json") and any(
                k in name.lower() for k in ("chat", "composer", "transcript", "memory", "agent")
            ):
                yield path
            elif name in {"heet.md", "logboek.md"} or "/geheugen/" in str(path).replace("\\", "/"):
                yield path


def _parse_jsonl_chat(path: Path) -> list[dict[str, Any]]:
    messages = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and ("role" in row or "message" in row):
                if "role" in row:
                    messages.append(
                        {
                            "role": row.get("role") or "assistant",
                            "content": str(row.get("content") or row.get("text") or ""),
                        }
                    )
                elif isinstance(row.get("message"), dict):
                    m = row["message"]
                    messages.append(
                        {
                            "role": m.get("role") or "assistant",
                            "content": str(m.get("content") or m.get("text") or ""),
                        }
                    )
            elif isinstance(row, dict) and row.get("text"):
                messages.append({"role": "assistant", "content": str(row["text"])})
    if not messages:
        return []
    return [
        {
            "native_id": str(path),
            "title": path.stem,
            "messages": messages,
            "meta": {"path": str(path)},
        }
    ]


def _parse_markdown_memory(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return [
        {
            "native_id": str(path),
            "key": f"cursor:{path.name}",
            "content": text[:12000],
            "meta": {"path": str(path)},
        }
    ]


def import_local(roots: list[Path] | None = None, *, max_files: int = 4000) -> dict[str, Any]:
    roots = roots or candidate_roots()
    conversations: list[dict[str, Any]] = []
    memories: list[dict[str, Any]] = []
    scanned = 0
    for root in roots:
        for path in _iter_files(root):
            scanned += 1
            if scanned > max_files:
                break
            try:
                if path.suffix == ".jsonl":
                    conversations.extend(_parse_jsonl_chat(path))
                elif path.suffix == ".md" or "geheugen" in str(path):
                    memories.extend(_parse_markdown_memory(path))
                elif path.suffix == ".json":
                    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(data, list) and data and isinstance(data[0], dict) and "mapping" in data[0]:
                        from vit_ai_hub.importing.chatgpt import parse_conversations_payload

                        conversations.extend(parse_conversations_payload(data))
                    elif isinstance(data, dict) and "messages" in data:
                        msgs = []
                        for m in data.get("messages") or []:
                            if isinstance(m, dict):
                                msgs.append(
                                    {
                                        "role": m.get("role") or "user",
                                        "content": str(m.get("content") or ""),
                                    }
                                )
                        if msgs:
                            conversations.append(
                                {
                                    "native_id": str(path),
                                    "title": path.stem,
                                    "messages": msgs,
                                    "meta": {"path": str(path)},
                                }
                            )
                    else:
                        memories.append(
                            {
                                "native_id": str(path),
                                "key": f"cursor-json:{path.name}",
                                "content": json.dumps(data, ensure_ascii=False)[:8000],
                            }
                        )
            except Exception:
                continue
        if scanned > max_files:
            break

    from vit_ai_hub.importing.store import log_import, save_conversations, save_memories

    summary = {
        "source": "cursor",
        "roots": [str(r) for r in roots],
        "files_scanned": scanned,
        "conversations": save_conversations(conversations, source="cursor"),
        "memories": save_memories(memories, source="cursor"),
    }
    log_import(summary)
    return summary
