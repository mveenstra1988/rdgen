"""Visual / Canva-alt + site pipeline."""

from __future__ import annotations


def test_visual_templates_and_render(tmp_path):
    from vit_ai_hub.visual import list_templates, render_template

    ids = {t["id"] for t in list_templates()}
    assert "linkedin-post" in ids
    assert "pitch-slide" in ids
    r = render_template(
        "linkedin-post",
        headline="MSP die gewoon werkt",
        sub="Cloud, mail, backup — zonder gedoe.",
        cta="Plan gesprek",
        brand="VIT",
    )
    assert r["ok"]
    assert "MSP die gewoon werkt" in r["html"]
    assert "<svg" in r["svg"]


def test_visual_studio_and_tools():
    from vit_ai_hub.studio import list_studios, studio_system_prompt
    from vit_ai_hub.tools.capabilities import tool_specs

    ids = {s["id"] for s in list_studios()}
    assert "visual" in ids
    assert "Canva" in (studio_system_prompt("visual") or "")
    names = {t["function"]["name"] for t in tool_specs()}
    assert {
        "visual_render",
        "generate_image",
        "describe_image",
        "speak_text",
        "nano_banana",
        "read_document",
    } <= names


def test_classify_visual_and_site():
    from vit_ai_hub.orchestrator import classify_intent

    v = classify_intent("Maak een Canva-achtige LinkedIn carousel met 3 slides")
    assert v.kind == "visual"
    assert v.suggested_studio == "visual"
    assert v.suggested_team == "team-visual"

    s = classify_intent(
        "Bouw een volledige landingspagina met marketing pitch, SEO en hero design end-to-end"
    )
    assert s.multi_agent is True
    assert s.suggested_team == "team-site"


def test_site_and_visual_teams(tmp_path, monkeypatch):
    import vit_ai_hub.agents.store as store

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")
    teams = {t["id"] for t in store.list_teams()}
    assert {"team-visual", "team-site"} <= teams


async def _run_media():
    from vit_ai_hub.tools.media import generate_image, run_media_tool
    import json

    out = await generate_image("Sterke MSP pitch visual", brand="VIT")
    assert out["ok"]
    assert out["mode"] == "local_template"
    raw = await run_media_tool(
        "visual_render",
        {"template": "pitch-slide", "headline": "Hello", "sub": "World", "cta": "Go"},
    )
    data = json.loads(raw)
    assert data["ok"]


def test_media_generate_and_render():
    import asyncio

    asyncio.run(_run_media())
