"""SQLite geheugen — gedeeld over alle modellen, sessions en vensters."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

DB_PATH = ROOT / "data" / "vit_memory.db"
LEGACY_JSONL = ROOT / "data" / "memory.jsonl"

_PIN_HINT = re.compile(
    r"\b(onthoud|remember|voorkeur|altijd|nooit|mijn naam is|ik ben|ik wil dat|"
    r"from now on|noteer|belangrijk:|pin:)\b",
    re.I,
)


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def ensure_db() -> None:
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
              session_id TEXT PRIMARY KEY,
              title TEXT,
              messages_json TEXT NOT NULL,
              models_json TEXT,
              studio TEXT,
              updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY,
              content TEXT NOT NULL,
              kind TEXT DEFAULT 'fact',
              tags TEXT DEFAULT '',
              source_session TEXT,
              model TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
              content, tags, content='memories', content_rowid='rowid'
            );
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
              INSERT INTO memories_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
              INSERT INTO memories_fts(memories_fts, rowid, content, tags)
              VALUES('delete', old.rowid, old.content, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
              INSERT INTO memories_fts(memories_fts, rowid, content, tags)
              VALUES('delete', old.rowid, old.content, old.tags);
              INSERT INTO memories_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
            END;
            """
        )
    _migrate_legacy_jsonl()


def _migrate_legacy_jsonl() -> None:
    if not LEGACY_JSONL.is_file():
        return
    flag = DB_PATH.parent / ".memory_migrated"
    if flag.is_file():
        return
    ensure_done = False
    try:
        with _conn() as con:
            n = con.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
            if n > 0:
                ensure_done = True
            else:
                for line in LEGACY_JSONL.read_text(encoding="utf-8").splitlines():
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = str(row.get("value") or row.get("content") or "").strip()
                    if not content:
                        continue
                    key = str(row.get("key") or "legacy")
                    mid = f"legacy-{uuid.uuid4().hex[:12]}"
                    now = float(row.get("ts") or time.time())
                    con.execute(
                        "INSERT OR IGNORE INTO memories(id, content, kind, tags, source_session, model, created_at, updated_at)"
                        " VALUES (?, ?, 'fact', ?, NULL, NULL, ?, ?)",
                        (mid, content, key, now, now),
                    )
                ensure_done = True
        if ensure_done:
            flag.write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


def pin_memory(
    content: str,
    *,
    kind: str = "fact",
    tags: str = "",
    source_session: str | None = None,
    model: str | None = None,
    memory_id: str | None = None,
) -> dict[str, Any]:
    ensure_db()
    content = (content or "").strip()
    if not content:
        return {"ok": False, "error": "lege content"}
    if len(content) > 4000:
        content = content[:4000]
    mid = memory_id or f"mem-{uuid.uuid4().hex[:14]}"
    now = time.time()
    with _conn() as con:
        con.execute(
            "INSERT INTO memories(id, content, kind, tags, source_session, model, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET content=excluded.content, tags=excluded.tags,"
            " updated_at=excluded.updated_at, model=excluded.model",
            (mid, content, kind[:40], (tags or "")[:200], source_session, model, now, now),
        )
    return {"ok": True, "id": mid, "content": content}


def search_memories(query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    ensure_db()
    q = (query or "").strip()
    limit = max(1, min(50, limit))
    with _conn() as con:
        if q:
            # FTS: quote tokens simply
            tokens = [t for t in re.split(r"\s+", q) if t]
            fts = " ".join(tokens[:12]) if tokens else q
            try:
                rows = con.execute(
                    "SELECT m.id, m.content, m.kind, m.tags, m.model, m.created_at "
                    "FROM memories_fts f JOIN memories m ON m.rowid = f.rowid "
                    "WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = con.execute(
                    "SELECT id, content, kind, tags, model, created_at FROM memories "
                    "WHERE content LIKE ? ORDER BY updated_at DESC LIMIT ?",
                    (f"%{q}%", limit),
                ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, content, kind, tags, model, created_at FROM memories "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def list_memories(*, limit: int = 40) -> list[dict[str, Any]]:
    return search_memories("", limit=limit)


def recall(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    return search_memories(query, limit=limit)


def context_block(query: str, *, limit: int = 8) -> str | None:
    """Tekstblok voor system prompt — model-agnostisch."""
    hits = recall(query, limit=limit)
    if not hits:
        # recent fallback
        hits = list_memories(limit=min(5, limit))
    if not hits:
        return None
    lines = ["# VIT gedeeld geheugen (geldt voor elk model)", "Deze feiten blijven bij modelwissel:"]
    for h in hits:
        lines.append(f"- {h['content']}")
    return "\n".join(lines)


def save_conversation(
    session_id: str,
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    studio: str | None = None,
    title: str | None = None,
    auto_pin: bool = True,
) -> dict[str, Any]:
    ensure_db()
    sid = (session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "geen session_id"}
    # Only user/assistant turns for storage
    slim = []
    for m in messages:
        role = m.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = m.get("content")
        if not isinstance(content, str):
            content = str(content)
        slim.append({"role": role, "content": content[:20000]})
    if not slim:
        return {"ok": False, "error": "geen berichten"}
    now = time.time()
    if not title:
        first_user = next((m["content"] for m in slim if m["role"] == "user"), "Chat")
        title = first_user.strip().split("\n")[0][:80] or "Chat"
    models: list[str] = []
    with _conn() as con:
        prev = con.execute(
            "SELECT models_json FROM conversations WHERE session_id=?", (sid,)
        ).fetchone()
        if prev and prev["models_json"]:
            try:
                models = json.loads(prev["models_json"]) or []
            except json.JSONDecodeError:
                models = []
        if model and model not in models:
            models.append(model)
        con.execute(
            "INSERT INTO conversations(session_id, title, messages_json, models_json, studio, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(session_id) DO UPDATE SET"
            " title=excluded.title, messages_json=excluded.messages_json,"
            " models_json=excluded.models_json, studio=excluded.studio, updated_at=excluded.updated_at",
            (sid, title, json.dumps(slim, ensure_ascii=False), json.dumps(models), studio, now),
        )
    pinned = 0
    if auto_pin:
        pinned = _auto_pin_from_messages(slim, session_id=sid, model=model)
    return {"ok": True, "session_id": sid, "messages": len(slim), "models": models, "auto_pinned": pinned}


def _auto_pin_from_messages(
    messages: list[dict[str, Any]], *, session_id: str, model: str | None
) -> int:
    """Pin user-uitspraken die expliciet geheugen vragen — geen PII-dump."""
    pinned = 0
    for m in messages[-6:]:
        if m.get("role") != "user":
            continue
        text = (m.get("content") or "").strip()
        if len(text) < 12 or len(text) > 500:
            continue
        if not _PIN_HINT.search(text):
            continue
        # skip if looks like secrets
        if re.search(r"(api[_-]?key|password|secret|token\s*=)", text, re.I):
            continue
        pin_memory(
            text,
            kind="preference",
            tags="auto",
            source_session=session_id,
            model=model,
        )
        pinned += 1
    return pinned


def get_conversation(session_id: str) -> dict[str, Any] | None:
    ensure_db()
    with _conn() as con:
        row = con.execute(
            "SELECT session_id, title, messages_json, models_json, studio, updated_at "
            "FROM conversations WHERE session_id=?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "session_id": row["session_id"],
        "title": row["title"],
        "messages": json.loads(row["messages_json"] or "[]"),
        "models": json.loads(row["models_json"] or "[]"),
        "studio": row["studio"],
        "updated_at": row["updated_at"],
    }


def stats() -> dict[str, Any]:
    ensure_db()
    with _conn() as con:
        mem = con.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
        conv = con.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"]
    return {"memories": mem, "conversations": conv, "db": str(DB_PATH)}
