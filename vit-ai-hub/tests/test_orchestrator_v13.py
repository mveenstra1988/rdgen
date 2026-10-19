"""1.3: fallbacks, strength/weak, critic parse, cascade."""

from __future__ import annotations

import asyncio


def test_strength_score_ordering():
    from vit_ai_hub.orchestrator import classify_intent, strength_score

    simple = strength_score(classify_intent("ok"))
    code = strength_score(
        classify_intent("Refactor deze API en fix alle pytest failures end-to-end", studio="software")
    )
    assert simple < code


def test_fallback_chain_has_primary_and_alts(monkeypatch, tmp_path):
    from vit_ai_hub.orchestrator import classify_intent, pick_model_for_intent
    from vit_ai_hub.orchestrator.fallback import build_fallback_chain
    import vit_ai_hub.orchestrator.policy as policy
    import vit_ai_hub.orchestrator.fallback as fb

    class B:
        def __init__(self, name, base_url, api_key="", local=False):
            self.name = name
            self.base_url = base_url
            self.api_key = api_key
            self.local = local

    backends = {
        "lmstudio": B("lmstudio", "http://127.0.0.1:1234/v1", local=True),
        "deepseek": B("deepseek", "https://api.deepseek.com/v1", "sk"),
        "bridge": B("bridge", "http://127.0.0.1:8317/v1", "x"),
        "openrouter": B("openrouter", "https://openrouter.ai/api/v1", "sk-or"),
    }
    monkeypatch.setattr(policy, "build_backends", lambda: backends)
    monkeypatch.setattr(fb, "build_backends", lambda: backends)
    monkeypatch.setattr(
        policy,
        "get_settings",
        lambda: type("S", (), {"vit_local_light_model": "qwen", "vit_local_heavy_model": "qwen-h"})(),
    )

    intent = classify_intent("implementeer feature X", studio="software")
    pick = pick_model_for_intent(intent)
    chain = build_fallback_chain(pick, intent)
    assert chain[0] == pick.model
    assert len(chain) >= 2


def test_critic_parse():
    from vit_ai_hub.orchestrator.critic import parse_critic

    assert parse_critic('{"verdict":"pass","feedback":"ok"}')["verdict"] == "pass"
    assert parse_critic("FAIL — mist tests")["verdict"] == "fail"
    assert parse_critic("PASS alles goed")["verdict"] == "pass"


def test_cascade_tries_next():
    from vit_ai_hub.orchestrator.cascade import cascade_chat

    class Dec:
        def __init__(self, model, local=True):
            self.model = model
            self.local = local
            self.backend = type("B", (), {"name": "test"})()

    calls = []

    async def chat_fn(decision, payload):
        calls.append(decision.model)
        if decision.model == "bad":
            raise RuntimeError("down")
        if decision.model == "empty":
            return {"choices": [{"message": {"content": ""}}]}
        return {"choices": [{"message": {"content": f"ok from {decision.model}"}}]}

    data, meta = asyncio.run(
        cascade_chat(
            models=["bad", "empty", "good"],
            resolve=lambda m: Dec(m),
            chat_fn=chat_fn,
            payload={"messages": []},
            intent_kind="code",
        )
    )
    assert meta["used_model"] == "good"
    assert meta["fallback_index"] == 2
    assert "ok from good" in data["choices"][0]["message"]["content"]


def test_plan_includes_fallbacks_and_strength(tmp_path, monkeypatch):
    from vit_ai_hub.orchestrator import plan_request
    import vit_ai_hub.agents.store as store

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "a.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "t.json")

    plan = plan_request("ok", allow_team=False, tradeoff="cost")
    assert plan.fallbacks
    assert plan.strength >= 0
    assert plan.tradeoff == "cost"
    assert "strength=" in plan.summary


def test_critic_loop_pass():
    from vit_ai_hub.orchestrator import classify_intent
    from vit_ai_hub.orchestrator.critic import run_critic_loop

    intent = classify_intent("schrijf een korte functie met tests", studio="software")

    async def chat_once(model, messages):
        if "strenge QA" in (messages[0].get("content") or ""):
            return '{"verdict":"pass","feedback":"prima"}'
        return "revised"

    out = asyncio.run(
        run_critic_loop(
            task="schrijf functie",
            draft="def f(): pass",
            intent=intent,
            chat_once=chat_once,
            critic_model="c",
            revise_model="r",
        )
    )
    assert out["used"] is True
    assert out["verdict"] == "pass"
    assert out["final"] == "def f(): pass"
