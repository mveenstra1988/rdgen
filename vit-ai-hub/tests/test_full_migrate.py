import json
from pathlib import Path

from vit_ai_hub.importing import full_migrate as fm
from vit_ai_hub.importing import store


def test_migrate_everything_builds_profile(tmp_path, monkeypatch):
    home = tmp_path / "home"
    claude = home / ".claude"
    cursor = home / ".cursor"
    (claude / "skills" / "x").mkdir(parents=True)
    (claude / "skills" / "x" / "SKILL.md").write_text(
        "---\nname: MigSkill\ndescription: d\n---\n\nBody\n", encoding="utf-8"
    )
    (claude / "settings.json").write_text('{"theme":"dark"}', encoding="utf-8")
    cursor.mkdir(parents=True)
    (cursor / "mcp.json").write_text(
        json.dumps({"mcpServers": {"demo": {"command": "echo", "args": ["hi"]}}}),
        encoding="utf-8",
    )
    (cursor / "rules").mkdir()
    (cursor / "rules" / "a.mdc").write_text("# Rule A\nAlways test.\n", encoding="utf-8")

    monkeypatch.setattr(fm, "_home", lambda: home)
    monkeypatch.setattr(fm, "MIGRATE_ROOT", tmp_path / "migrated")
    monkeypatch.setattr(fm, "PROFILE_PATH", tmp_path / "migrated" / "active_profile.json")

    monkeypatch.setattr(store, "DATA", tmp_path / "knowledge")
    monkeypatch.setattr(store, "SKILLS", tmp_path / "knowledge" / "skills.jsonl")
    monkeypatch.setattr(store, "MEMORIES", tmp_path / "knowledge" / "memories.jsonl")
    monkeypatch.setattr(store, "CONVERSATIONS", tmp_path / "knowledge" / "conversations.jsonl")
    monkeypatch.setattr(store, "PROJECTS", tmp_path / "knowledge" / "projects.jsonl")
    monkeypatch.setattr(store, "SETTINGS_BUNDLE", tmp_path / "knowledge" / "settings_bundles.jsonl")

    import vit_ai_hub.agents.store as agent_store
    import vit_ai_hub.importing.skills as skills_mod

    monkeypatch.setattr(agent_store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(agent_store, "TEAMS_PATH", tmp_path / "teams.json")
    monkeypatch.setattr(skills_mod, "skill_candidate_roots", lambda: [claude / "skills"])

    # avoid walking huge real disks via import_all
    monkeypatch.setattr(
        "vit_ai_hub.importing.pipeline.import_all_one_click",
        lambda: {"knowledge": {"conversations": 0, "memories": 0, "projects": 0, "skills": 0}},
    )

    out = fm.migrate_everything(promote_skills=True)
    assert out["ok"]
    profile = fm.load_active_profile()
    assert profile.get("mcp_servers") == ["demo"]
    assert Path(profile["rules_path"]).is_file()
    assert "Rule A" in Path(profile["rules_path"]).read_text(encoding="utf-8")
    addons = fm.runtime_system_addons()
    assert "Rule A" in addons
    assert "Self-improve" in addons or "self-improve" in addons.lower()
