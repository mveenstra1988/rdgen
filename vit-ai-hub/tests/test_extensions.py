from vit_ai_hub import extensions as ext


def test_add_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "HUB_SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(ext, "CUSTOM_APPS", tmp_path / "custom_apps.json")

    import vit_ai_hub.importing.store as store

    monkeypatch.setattr(store, "SKILLS", tmp_path / "skills.jsonl")
    monkeypatch.setattr(store, "DATA", tmp_path)

    out = ext.add_skill(
        name="Demo Skill",
        description="test",
        content="Doe X en Y.",
        promote_agent=False,
    )
    assert out["ok"]
    assert (tmp_path / "skills" / "demo-skill" / "SKILL.md").is_file()


def test_add_mcp(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "HUB_MCP", tmp_path / "mcp.json")
    out = ext.add_mcp_server(name="demo", command="npx", args="-y demo-mcp")
    assert out["ok"]
    assert out["name"] == "demo"
    listed = ext.list_mcp_managed()
    assert "demo" in listed["hub_servers"]
    rem = ext.remove_mcp_server("demo")
    assert rem["ok"]
    assert "demo" not in ext.list_mcp_managed()["hub_servers"]


def test_custom_app(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "CUSTOM_APPS", tmp_path / "apps.json")
    out = ext.add_custom_app(name="Slack", app_name="Slack", aliases="chat,slack")
    assert out["ok"]
    assert out["app"]["id"] == "slack"
    apps = ext.list_custom_apps()["apps"]
    assert any(a["id"] == "slack" for a in apps)

    from vit_ai_hub.tools.vit_apps import resolve_vit_app

    assert resolve_vit_app("slack")["id"] == "slack"
    rem = ext.remove_custom_app("slack")
    assert rem["ok"]
