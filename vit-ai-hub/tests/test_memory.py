"""Model-agnostisch gedeeld geheugen (SQLite)."""

from __future__ import annotations

import vit_ai_hub.memory.store as store


def _patch_db(tmp_path, monkeypatch):
    db = tmp_path / "vit_memory.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LEGACY_JSONL", tmp_path / "memory.jsonl")
    flag = tmp_path / ".memory_migrated"
    # ensure migrate flag path under tmp
    monkeypatch.setattr(store, "DB_PATH", db)


def test_pin_search_and_context(tmp_path, monkeypatch):
    _patch_db(tmp_path, monkeypatch)
    r = store.pin_memory("Mijn naam is Mike", kind="preference", tags="naam", model="claude")
    assert r["ok"]
    store.pin_memory("Voorkeur: kort antwoorden", tags="stijl", model="gpt")
    hits = store.search_memories("Mike")
    assert any("Mike" in h["content"] for h in hits)
    block = store.context_block("naam")
    assert block and "Mike" in block
    assert "elk model" in block.lower() or "modelwissel" in block.lower()


def test_conversation_survives_model_switch(tmp_path, monkeypatch):
    _patch_db(tmp_path, monkeypatch)
    sid = "s-test-switch"
    store.save_conversation(
        sid,
        [
            {"role": "user", "content": "Onthoud: project heet ServiceHub"},
            {"role": "assistant", "content": "Ok, ServiceHub genoteerd."},
        ],
        model="claude-sonnet",
        studio="chat",
    )
    store.save_conversation(
        sid,
        [
            {"role": "user", "content": "Onthoud: project heet ServiceHub"},
            {"role": "assistant", "content": "Ok, ServiceHub genoteerd."},
            {"role": "user", "content": "Hoe heet het project?"},
            {"role": "assistant", "content": "ServiceHub"},
        ],
        model="gpt-4o",
        studio="chat",
    )
    conv = store.get_conversation(sid)
    assert conv is not None
    assert "claude-sonnet" in conv["models"]
    assert "gpt-4o" in conv["models"]
    assert any("ServiceHub" in m["content"] for m in conv["messages"])
    # auto-pin from "Onthoud"
    pinned = store.search_memories("ServiceHub")
    assert pinned


def test_memory_tools_use_sqlite(tmp_path, monkeypatch):
    _patch_db(tmp_path, monkeypatch)
    import json
    import asyncio
    import vit_ai_hub.tools.capabilities as caps

    monkeypatch.setattr(caps, "MEMORY_PATH", tmp_path / "memory.jsonl")

    async def _run():
        w = json.loads(
            await caps.run_tool("memory_write", {"key": "pref", "value": "Altijd Nederlands antwoorden"})
        )
        assert w.get("ok") is True
        assert w.get("shared") is True
        r = json.loads(await caps.run_tool("memory_read", {"query": "Nederlands"}))
        assert any("Nederlands" in (i.get("value") or "") for i in r.get("items") or [])

    asyncio.run(_run())


def test_legacy_jsonl_migrate(tmp_path, monkeypatch):
    legacy = tmp_path / "memory.jsonl"
    legacy.write_text(
        '{"ts": 1, "key": "x", "value": "Legacy feit over WireGuard"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "vit_memory.db")
    monkeypatch.setattr(store, "LEGACY_JSONL", legacy)
    store.ensure_db()
    hits = store.search_memories("WireGuard")
    assert hits
