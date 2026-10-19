"""SQLite FTS5 index over knowledge store voor snelle zoekopdrachten."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT
from vit_ai_hub.importing.store import CONVERSATIONS, MEMORIES, PROJECTS

DB_PATH = ROOT / "data" / "knowledge" / "index.sqlite"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
          doc_id, kind, source, title, body, tokenize='porter'
        )
        """
    )
    con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    return con


def rebuild_index() -> dict[str, Any]:
    con = _conn()
    con.execute("DELETE FROM docs_fts")
    n = 0

    def add(doc_id: str, kind: str, source: str, title: str, body: str) -> None:
        nonlocal n
        con.execute(
            "INSERT INTO docs_fts(doc_id, kind, source, title, body) VALUES (?,?,?,?,?)",
            (doc_id, kind, source, title or "", body or ""),
        )
        n += 1

    for path, kind in (
        (MEMORIES, "memory"),
        (PROJECTS, "project"),
        (CONVERSATIONS, "conversation"),
    ):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if kind == "conversation":
                    body = "\n".join(
                        f"{m.get('role')}: {m.get('content')}" for m in (row.get("messages") or [])[-20:]
                    )
                    title = row.get("title") or ""
                elif kind == "memory":
                    body = str(row.get("content") or "")
                    title = str(row.get("key") or "")
                else:
                    body = str(row.get("instructions") or "")
                    for d in row.get("documents") or []:
                        body += "\n" + str(d.get("content") or "")
                    title = str(row.get("name") or "")
                add(str(row.get("id")), kind, str(row.get("source") or ""), title, body[:50000])

    con.execute(
        "INSERT OR REPLACE INTO meta(k,v) VALUES ('rebuilt_at', ?)",
        (str(time.time()),),
    )
    con.commit()
    con.close()
    return {"ok": True, "docs": n, "db": str(DB_PATH)}


def fts_search(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    if not DB_PATH.is_file():
        rebuild_index()
    con = _conn()
    # escape FTS special chars lightly
    safe = " ".join(part for part in q.replace('"', " ").split() if part)
    if not safe:
        return []
    try:
        rows = con.execute(
            """
            SELECT doc_id, kind, source, title, snippet(docs_fts, 4, '[', ']', '…', 12)
            FROM docs_fts WHERE docs_fts MATCH ? LIMIT ?
            """,
            (safe, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # fallback prefix
        rows = con.execute(
            """
            SELECT doc_id, kind, source, title, substr(body,1,400)
            FROM docs_fts WHERE body LIKE ? LIMIT ?
            """,
            (f"%{q}%", limit),
        ).fetchall()
    con.close()
    return [
        {
            "id": r[0],
            "kind": r[1],
            "source": r[2],
            "title": r[3],
            "snippet": r[4],
        }
        for r in rows
    ]
