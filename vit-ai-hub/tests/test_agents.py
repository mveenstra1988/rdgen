import vit_ai_hub.agents.store as store


def test_presets_and_custom_team(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")

    teams = store.list_teams()
    agents = store.list_agents()
    assert any(t["id"] == "team-webdesign" for t in teams)
    assert any(t["id"] == "team-apps" for t in teams)
    assert any(t["id"] == "team-infra" for t in teams)
    assert any(t["id"] == "team-growth" for t in teams)
    assert len(agents) >= 15

    agent = store.save_agent(
        {
            "name": "Copy Extra",
            "role": "Extra writer",
            "studio": "webdesign",
            "system": "Schrijf kort.",
            "model": "vit/auto",
        }
    )
    assert agent["id"].startswith("agent-")
    team = store.save_team(
        {
            "name": "Mijn web team",
            "studio": "webdesign",
            "mode": "pipeline",
            "members": [
                {"agent_id": "agent-design-lead", "order": 0, "label": "Brief"},
                {"agent_id": agent["id"], "order": 1, "label": "Copy"},
            ],
        }
    )
    assert team["name"] == "Mijn web team"
    assert len(team["members"]) == 2

    # preset delete blocked
    assert store.delete_team("team-webdesign")["ok"] is False
    assert store.delete_team(team["id"])["ok"] is True


def test_run_team_pipeline(tmp_path, monkeypatch):
    import asyncio

    import vit_ai_hub.agents.runner as runner

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")
    store.ensure_preset_teams()

    calls = []

    async def fake_chat_fn(*, messages, model, studio, workspace, tools):
        calls.append({"model": model, "studio": studio, "tools": tools})
        who = messages[0]["content"][:40]
        return {
            "choices": [{"message": {"content": f"OK from {who}"}}],
            "vit": {"backend": "test", "local": True},
        }

    result = asyncio.run(
        runner.run_team(
            "team-webdesign",
            task="Maak een landing voor VIT",
            workspace=None,
            chat_fn=fake_chat_fn,
        )
    )
    assert result["ok"]
    assert len(result["steps"]) == 3
    assert len(calls) == 3
    assert result["final"]
