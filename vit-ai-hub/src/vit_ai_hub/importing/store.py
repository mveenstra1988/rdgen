from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Iterable

from vit_ai_hub.config import ROOT

DATA = ROOT / "data" / "knowledge"
CONVERSATIONS = DATA / "conversations.jsonl"
MEMORIES = DATA / "memories.jsonl"
PROJECTS = DATA / "projects.jsonl"
SKILLS = DATA / "skills.jsonl"
IMPORT_LOG = DATA / "imports.jsonl"


def _ensure() -> None:
    DATA.mkdir(parents=True, exist_ok=True)


def _hash_id(source: str, native_id: str) -> str:
    raw = f"{source}:{native_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def _append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    _ensure()
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _existing_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.is_file():
        return ids
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("id"):
                ids.add(row["id"])
    return ids


def save_conversations(items: list[dict[str, Any]], *, source: str) -> dict[str, int]:
    existing = _existing_ids(CONVERSATIONS)
    rows = []
    skipped = 0
    for item in items:
        native = str(item.get("native_id") or item.get("id") or "")
        cid = _hash_id(source, native or json.dumps(item.get("title"), ensure_ascii=False))
        if cid in existing:
            skipped += 1
            continue
        rows.append(
            {
                "id": cid,
                "source": source,
                "native_id": native,
                "title": item.get("title") or "Untitled",
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "messages": item.get("messages") or [],
                "meta": item.get("meta") or {},
                "imported_at": time.time(),
            }
        )
        existing.add(cid)
    written = _append_jsonl(CONVERSATIONS, rows)
    return {"written": written, "skipped": skipped}


def save_memories(items: list[dict[str, Any]], *, source: str) -> dict[str, int]:
    existing = _existing_ids(MEMORIES)
    rows = []
    skipped = 0
    for item in items:
        native = str(item.get("native_id") or item.get("key") or item.get("content") or "")[:200]
        mid = _hash_id(source, native)
        if mid in existing:
            skipped += 1
            continue
        rows.append(
            {
                "id": mid,
                "source": source,
                "key": item.get("key") or "",
                "content": item.get("content") or "",
                "meta": item.get("meta") or {},
                "imported_at": time.time(),
            }
        )
        existing.add(mid)
    return {"written": _append_jsonl(MEMORIES, rows), "skipped": skipped}


def save_projects(items: list[dict[str, Any]], *, source: str) -> dict[str, int]:
    existing = _existing_ids(PROJECTS)
    rows = []
    skipped = 0
    for item in items:
        native = str(item.get("native_id") or item.get("name") or "")
        pid = _hash_id(source, native)
        if pid in existing:
            skipped += 1
            continue
        rows.append(
            {
                "id": pid,
                "source": source,
                "name": item.get("name") or "project",
                "instructions": item.get("instructions") or "",
                "documents": item.get("documents") or [],
                "meta": item.get("meta") or {},
                "imported_at": time.time(),
            }
        )
        existing.add(pid)
    return {"written": _append_jsonl(PROJECTS, rows), "skipped": skipped}


def save_skills(items: list[dict[str, Any]]) -> dict[str, int]:
    existing = _existing_ids(SKILLS)
    rows = []
    skipped = 0
    for item in items:
        source = str(item.get("source") or "skill")
        native = str(item.get("native_id") or item.get("path") or item.get("name") or "")
        sid = _hash_id(source, native)
        if sid in existing:
            skipped += 1
            continue
        rows.append(
            {
                "id": sid,
                "source": source,
                "name": item.get("name") or "skill",
                "description": item.get("description") or "",
                "content": item.get("content") or "",
                "path": item.get("path") or "",
                "kind": item.get("kind") or "skill",
                "meta": item.get("meta") or {},
                "imported_at": time.time(),
            }
        )
        existing.add(sid)
    return {"written": _append_jsonl(SKILLS, rows), "skipped": skipped}


def list_skills(*, limit: int = 200) -> list[dict[str, Any]]:
    if not SKILLS.is_file():
        return []
    out: list[dict[str, Any]] = []
    with SKILLS.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "description": row.get("description"),
                    "source": row.get("source"),
                    "path": row.get("path"),
                    "content_preview": str(row.get("content") or "")[:280],
                }
            )
            if len(out) >= limit:
                break
    return out


def log_import(summary: dict[str, Any]) -> None:
    _append_jsonl(IMPORT_LOG, [{**summary, "ts": time.time()}])


def stats() -> dict[str, Any]:
    def count(path: Path) -> int:
        if not path.is_file():
            return 0
        with path.open(encoding="utf-8") as fh:
            return sum(1 for _ in fh if _.strip())

    return {
        "conversations": count(CONVERSATIONS),
        "memories": count(MEMORIES),
        "projects": count(PROJECTS),
        "skills": count(SKILLS),
        "imports": count(IMPORT_LOG),
        "paths": {
            "conversations": str(CONVERSATIONS),
            "memories": str(MEMORIES),
            "projects": str(PROJECTS),
            "skills": str(SKILLS),
        },
    }


def search_knowledge(query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    try:
        from vit_ai_hub.importing.index_fts import fts_search

        fts_hits = fts_search(q, limit=limit)
        if fts_hits:
            return fts_hits
    except Exception:
        pass

    q_lower = q.lower()
    hits: list[dict[str, Any]] = []

    def scan(path: Path, kind: str) -> None:
        if not path.is_file():
            return
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                blob = json.dumps(row, ensure_ascii=False).lower()
                if q_lower in blob:
                    snippet = ""
                    if kind == "conversation":
                        msgs = row.get("messages") or []
                        for m in msgs[-6:]:
                            snippet += f"{m.get('role')}: {str(m.get('content') or '')[:240]}\n"
                    elif kind == "memory":
                        snippet = str(row.get("content") or "")[:800]
                    elif kind == "skill":
                        snippet = str(row.get("description") or "") + "\n" + str(row.get("content") or "")[:700]
                    else:
                        snippet = str(row.get("instructions") or row.get("name") or "")[:800]
                    hits.append(
                        {
                            "kind": kind,
                            "source": row.get("source"),
                            "title": row.get("title") or row.get("name") or row.get("key") or row.get("id"),
                            "snippet": snippet[:1200],
                            "id": row.get("id"),
                        }
                    )
                    if len(hits) >= limit:
                        return

    scan(SKILLS, "skill")
    if len(hits) < limit:
        scan(MEMORIES, "memory")
    if len(hits) < limit:
        scan(PROJECTS, "project")
    if len(hits) < limit:
        scan(CONVERSATIONS, "conversation")
    return hits[:limit]


def knowledge_context_block(query: str, *, limit: int = 8) -> str:
    hits = search_knowledge(query, limit=limit)
    if not hits and MEMORIES.is_file():
        rows = []
        with MEMORIES.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        for row in rows[-limit:]:
            hits.append(
                {
                    "kind": "memory",
                    "source": row.get("source"),
                    "title": row.get("key") or row.get("id"),
                    "snippet": str(row.get("content") or "")[:800],
                }
            )
    if not hits:
        return ""
    parts = ["[VIT geïmporteerde kennis / geheugen]"]
    for h in hits:
        parts.append(f"- ({h.get('source')}/{h.get('kind')}) {h.get('title')}: {h.get('snippet')}")
    return "\n".join(parts)[:12000]
