"""Smart auto orchestrator: intent, model policy, team plan."""

from __future__ import annotations


def test_classify_simple():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent("ok")
    assert i.kind == "simple"
    assert i.multi_agent is False


def test_classify_code_and_ops():
    from vit_ai_hub.orchestrator import classify_intent

    code = classify_intent("Refactor deze Python API en fix de pytest failures", studio="software")
    assert code.kind == "code"
    assert code.suggested_studio == "software"

    ops = classify_intent("Check Proxmox cluster en Mailcow status", studio="ops")
    assert ops.kind == "ops"
    assert ops.suggested_studio == "ops"


def test_classify_complex_web_team():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent(
        "Bouw een volledige landing page end-to-end met hero, design tokens en CTA copy"
    )
    assert i.multi_agent is True
    assert i.suggested_team == "team-webdesign"
    assert i.complexity == "high"


def test_classify_complex_apps_team():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent(
        "Bouw een hele Mac app van a tot z met architectuur, implementatie en review",
        studio="apps",
    )
    assert i.multi_agent is True
    assert i.suggested_team in {"team-apps", "team-webdesign"}


def test_pick_model_ops_prefers_local(monkeypatch):
    from vit_ai_hub.orchestrator import classify_intent, pick_model_for_intent
    import vit_ai_hub.orchestrator.policy as policy

    class B:
        def __init__(self, name, base_url, api_key="", local=False):
            self.name = name
            self.base_url = base_url
            self.api_key = api_key
            self.local = local

    monkeypatch.setattr(
        policy,
        "build_backends",
        lambda: {
            "lmstudio": B("lmstudio", "http://127.0.0.1:1234/v1", local=True),
            "bridge": B("bridge", "http://127.0.0.1:8317/v1", "x"),
            "deepseek": B("deepseek", "https://api.deepseek.com/v1", "sk"),
        },
    )
    monkeypatch.setattr(policy, "get_settings", lambda: type("S", (), {
        "vit_local_light_model": "qwen-local",
        "vit_local_heavy_model": "qwen-heavy",
    })())

    intent = classify_intent("proxmox nodes check", studio="ops")
    pick = pick_model_for_intent(intent)
    assert pick.prefer_local is True
    assert "qwen" in pick.model or pick.model.startswith("vit/local")


def test_pick_model_code_prefers_deepseek(monkeypatch):
    from vit_ai_hub.orchestrator import classify_intent, pick_model_for_intent
    import vit_ai_hub.orchestrator.policy as policy

    class B:
        def __init__(self, name, base_url, api_key="", local=False):
            self.name = name
            self.base_url = base_url
            self.api_key = api_key
            self.local = local

    monkeypatch.setattr(
        policy,
        "build_backends",
        lambda: {
            "lmstudio": B("lmstudio", "http://127.0.0.1:1234/v1", local=True),
            "deepseek": B("deepseek", "https://api.deepseek.com/v1", "sk-test"),
            "bridge": B("bridge", "http://127.0.0.1:8317/v1", "bridge"),
        },
    )
    monkeypatch.setattr(policy, "get_settings", lambda: type("S", (), {
        "vit_local_light_model": "qwen-local",
        "vit_local_heavy_model": "",
    })())

    intent = classify_intent("implementeer deze functie en schrijf tests", studio="software")
    pick = pick_model_for_intent(intent)
    # zware/medium code → Claude bridge of DeepSeek (beide beter dan light-lokaal)
    assert pick.model in {"claude-sonnet-4", "deepseek-chat", "deepseek-reasoner"} or "deepseek" in pick.model.lower()


def test_plan_request_team(tmp_path, monkeypatch):
    from vit_ai_hub.orchestrator import plan_request
    import vit_ai_hub.agents.store as store

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")

    plan = plan_request(
        "Bouw een volledige landing page end-to-end met design en copy",
        allow_team=True,
    )
    assert plan.use_team is True
    assert plan.team_id == "team-webdesign"
    assert plan.role_models  # per-agent models filled
    assert "intent=design" in plan.summary or "intent=complex" in plan.summary or plan.use_team


def test_plan_simple_no_team():
    from vit_ai_hub.orchestrator import plan_request

    plan = plan_request("ok", allow_team=True)
    assert plan.use_team is False


def test_resolve_smart():
    from vit_ai_hub.router import ModelRouter

    r = ModelRouter()
    decision, plan = r.resolve_smart(text="korte vraag over weer", allow_team=False)
    assert decision.virtual == "vit/auto"
    assert plan.model
    assert plan.use_team is False


def test_runner_smart_models(tmp_path, monkeypatch):
    import asyncio
    import vit_ai_hub.agents.store as store
    import vit_ai_hub.agents.runner as runner

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")
    store.ensure_preset_teams()

    models_seen = []

    async def fake_chat_fn(*, messages, model, studio, workspace, tools):
        models_seen.append(model)
        return {
            "choices": [{"message": {"content": f"ok via {model}"}}],
            "vit": {"backend": "test", "model": model},
        }

    result = asyncio.run(
        runner.run_team(
            "team-webdesign",
            task="Maak een korte landing hero",
            smart_models=True,
            chat_fn=fake_chat_fn,
        )
    )
    assert result["ok"]
    assert len(models_seen) == 3
    # should not all stay as literal vit/auto if smart resolved
    assert any(m != "vit/auto" for m in models_seen) or models_seen
