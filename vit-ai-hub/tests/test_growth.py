"""Marketing / Socials / SEO-GEO studios + growth router."""

from __future__ import annotations


def test_growth_studios_exist():
    from vit_ai_hub.studio import list_studios, studio_system_prompt

    ids = {s["id"] for s in list_studios()}
    assert {"marketing", "socials", "seo"} <= ids
    assert "positionering" in (studio_system_prompt("marketing") or "").lower()
    assert "linkedin" in (studio_system_prompt("socials") or "").lower()
    assert "generative" in (studio_system_prompt("seo") or "").lower()


def test_classify_marketing_pitch():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent(
        "Schrijf een scherpe pitch en positionering voor onze MSP-propositie, inclusief sales deck outline"
    )
    assert i.kind == "marketing"
    assert i.suggested_studio == "marketing"
    assert i.multi_agent is True
    assert i.suggested_team in {"team-marketing", "team-growth"}


def test_classify_socials_calendar():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent(
        "Maak een LinkedIn content kalender met 5 posts over VIT Backup",
        studio="socials",
    )
    assert i.kind == "socials"
    assert i.suggested_studio == "socials"
    assert i.suggested_team == "team-socials"


def test_classify_seo_geo():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent(
        "SEO en GEO plan: keyword clusters, schema.org FAQ en local SEO voor Amersfoort IT"
    )
    assert i.kind == "seo"
    assert i.suggested_studio == "seo"
    assert i.multi_agent is True
    assert i.suggested_team == "team-seo"


def test_classify_growth_router_multi_domain():
    from vit_ai_hub.orchestrator import classify_intent

    i = classify_intent(
        "Bouw een volledige campagne: marketing pitch, SEO landingspagina en LinkedIn posts end-to-end"
    )
    assert i.multi_agent is True
    # Landing + marketing/SEO → site pipeline (sterker dan plain growth)
    assert i.suggested_team in {"team-site", "team-growth"}
    assert i.complexity == "high"


def test_growth_preset_teams(tmp_path, monkeypatch):
    import vit_ai_hub.agents.store as store

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")

    teams = {t["id"] for t in store.list_teams()}
    agents = {a["id"] for a in store.list_agents()}
    assert {"team-marketing", "team-socials", "team-seo", "team-growth"} <= teams
    assert "agent-marketing-strat" in agents
    assert "agent-seo-lead" in agents
    assert "agent-social-copy" in agents


def test_plan_routes_growth():
    from vit_ai_hub.orchestrator.auto import plan_request

    plan = plan_request(
        "Schrijf een marketing pitch en positionering met CTA voor onze MSP-propositie",
        allow_team=True,
        tradeoff="quality",
    )
    assert plan.intent.kind in {"marketing", "complex", "write"}
    assert (plan.studio or plan.intent.suggested_studio) in {
        "marketing",
        "webdesign",
        None,
    } or plan.team_id in {"team-marketing", "team-growth", "team-site", None}
