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


def test_mcp_preset_and_json(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "HUB_MCP", tmp_path / "mcp.json")
    out = ext.add_mcp_preset("filesystem")
    assert out["ok"] and out["name"] == "filesystem"
    batch = ext.import_mcp_json(
        {"mcpServers": {"demo2": {"command": "true", "args": []}}}
    )
    assert batch["ok"] and "demo2" in batch["added"]


def test_skill_template_and_md(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "HUB_SKILLS_DIR", tmp_path / "skills")
    import vit_ai_hub.importing.store as store

    monkeypatch.setattr(store, "SKILLS", tmp_path / "skills.jsonl")
    monkeypatch.setattr(store, "DATA", tmp_path)
    t = ext.add_skill_template("code-review")
    assert t["ok"]
    md = ext.import_skill_markdown(
        "---\nname: FromFile\ndescription: d\n---\n\nBody text\n",
        filename="SKILL.md",
    )
    assert md["ok"] and md["name"] == "FromFile"


def test_app_preset(tmp_path, monkeypatch):
    monkeypatch.setattr(ext, "CUSTOM_APPS", tmp_path / "apps.json")
    out = ext.add_app_preset("Cursor")
    assert out["ok"] and out["app"]["name"] == "Cursor"


def test_overview_has_presets():
    ov = ext.extensions_overview()
    assert ov["presets"]["mcp"]
    assert ov["presets"]["apps"]
    assert ov["presets"]["skills"]
