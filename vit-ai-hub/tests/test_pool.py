"""Multi-abo account pools + failover."""

from __future__ import annotations

import asyncio
import time


def _empty_settings():
    return type(
        "S",
        (),
        {
            "bridge_base_url": "",
            "bridge_api_key": "",
            "cursor_base_url": "",
            "cursor_api_key": "",
            "openrouter_base_url": "",
            "openrouter_api_key": "",
            "deepseek_base_url": "",
            "deepseek_api_key": "",
            "grok_base_url": "",
            "xai_api_key": "",
            "omniroute_base_url": "",
            "omniroute_api_key": "",
        },
    )()


def test_add_list_delete_accounts(tmp_path, monkeypatch):
    import vit_ai_hub.config as config
    import vit_ai_hub.pool.store as store

    monkeypatch.setattr(store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    config.get_settings.cache_clear()
    monkeypatch.setattr(config, "get_settings", _empty_settings)
    for k in list(__import__("os").environ.keys()):
        if any(k.startswith(p) for p in ("BRIDGE_", "CURSOR_", "OPENROUTER_", "DEEPSEEK_", "GROK_", "OMNIROUTE_")):
            monkeypatch.delenv(k, raising=False)

    out = store.add_account(
        "bridge",
        {
            "label": "Claude 1",
            "base_url": "http://127.0.0.1:8317/v1",
            "api_key": "k1",
            "tags": ["claude"],
        },
    )
    assert out["ok"]
    store.add_account(
        "bridge",
        {
            "id": "b2",
            "label": "Claude 2",
            "base_url": "http://127.0.0.1:8318/v1",
            "api_key": "k2",
            "tags": ["claude", "chatgpt"],
        },
    )
    st = store.pool_status()
    assert st["pools"]["bridge"]["total"] == 2
    assert st["pools"]["bridge"]["healthy"] == 2

    order = store.pick_account_order("bridge", tags=["claude"])
    assert len(order) == 2

    assert store.delete_account("bridge", "b2")["ok"]
    assert store.pool_status()["pools"]["bridge"]["total"] == 1


def test_exhaustion_failover_order(tmp_path, monkeypatch):
    import vit_ai_hub.config as config
    import vit_ai_hub.pool.store as store

    monkeypatch.setattr(store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    config.get_settings.cache_clear()
    monkeypatch.setattr(config, "get_settings", _empty_settings)

    store.add_account(
        "bridge",
        {"id": "a1", "label": "A1", "base_url": "http://127.0.0.1:8317/v1", "api_key": "1"},
    )
    store.add_account(
        "bridge",
        {"id": "a2", "label": "A2", "base_url": "http://127.0.0.1:8318/v1", "api_key": "2"},
    )
    info = store.mark_failure("a1", "error 429: rate_limit exceeded", status=429)
    assert info["exhausted"] is True
    order = store.pick_account_order("bridge")
    assert len(order) == 1
    assert order[0]["id"] == "a2"

    store.clear_exhaustion("a1")
    assert len(store.pick_account_order("bridge")) == 2


def test_pooled_backend_skips_exhausted(tmp_path, monkeypatch):
    import vit_ai_hub.config as config
    import vit_ai_hub.pool.store as store
    import vit_ai_hub.pool.backend as backend

    monkeypatch.setattr(store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    config.get_settings.cache_clear()
    monkeypatch.setattr(config, "get_settings", _empty_settings)

    store.add_account(
        "bridge",
        {"id": "bad", "label": "bad", "base_url": "http://bad/v1", "api_key": "x", "tags": ["claude"]},
    )
    store.add_account(
        "bridge",
        {"id": "good", "label": "good", "base_url": "http://good/v1", "api_key": "y", "tags": ["claude"]},
    )

    pool = backend.PooledBackend(name="bridge", label="Bridge")

    async def fake_chat(self, payload):
        if "bad" in self.base_url:
            raise RuntimeError("bridge error 429: rate_limit")
        return {"choices": [{"message": {"content": "ok"}}], "model": payload.get("model")}

    monkeypatch.setattr(backend.OpenAICompatBackend, "chat_completions", fake_chat)

    data = asyncio.run(pool.chat_completions({"model": "claude-sonnet-4", "messages": []}))
    assert data["choices"][0]["message"]["content"] == "ok"
    assert data["vit_pool"]["account_id"] == "good"


def test_tags_for_model():
    from vit_ai_hub.pool.store import tags_for_model

    assert tags_for_model("claude-sonnet-4") == ["claude"]
    assert tags_for_model("gpt-4o") == ["chatgpt"]
    assert tags_for_model("cursor:composer") == ["cursor"]
