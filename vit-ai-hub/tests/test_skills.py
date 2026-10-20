from pathlib import Path

from vit_ai_hub.importing import skills as skills_mod
from vit_ai_hub.importing import store


def test_discover_and_harvest_skills(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Demo Skill\ndescription: Test skill\n---\n\n# Demo\nDoe X en Y.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(skills_mod, "skill_candidate_roots", lambda: [tmp_path / "skills"])
    monkeypatch.setattr(store, "DATA", tmp_path / "knowledge")
    monkeypatch.setattr(store, "SKILLS", tmp_path / "knowledge" / "skills.jsonl")
    monkeypatch.setattr(store, "MEMORIES", tmp_path / "knowledge" / "memories.jsonl")
    monkeypatch.setattr(store, "CONVERSATIONS", tmp_path / "knowledge" / "conversations.jsonl")
    monkeypatch.setattr(store, "PROJECTS", tmp_path / "knowledge" / "projects.jsonl")

    import vit_ai_hub.agents.store as agent_store

    monkeypatch.setattr(agent_store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(agent_store, "TEAMS_PATH", tmp_path / "teams.json")

    found = skills_mod.discover_skills()
    assert len(found) == 1
    assert found[0]["name"] == "Demo Skill"

    out = skills_mod.harvest_skills(promote_agents=True)
    assert out["found"] == 1
    assert out["skills"]["written"] == 1
    assert out["agents_promoted"]["written"] == 1
    assert any(a["name"] == "Demo Skill" for a in agent_store.list_agents())
    assert store.stats()["skills"] == 1
