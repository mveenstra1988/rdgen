"""Persistente agents & teams (visueel te bouwen in de GUI)."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

AGENTS_PATH = ROOT / "data" / "agents.json"
TEAMS_PATH = ROOT / "data" / "teams.json"

_SLUG = re.compile(r"[^a-z0-9_-]+")


def _slug(name: str) -> str:
    s = _SLUG.sub("-", (name or "").strip().lower()).strip("-")
    return s[:48] or uuid.uuid4().hex[:8]


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_agents() -> list[dict[str, Any]]:
    ensure_preset_teams()
    items = list(_load(AGENTS_PATH).values())
    return sorted(items, key=lambda a: (a.get("preset") is not True, a.get("name") or ""))


def get_agent(agent_id: str) -> dict[str, Any] | None:
    return _load(AGENTS_PATH).get(agent_id)


def save_agent(payload: dict[str, Any]) -> dict[str, Any]:
    agents = _load(AGENTS_PATH)
    agent_id = str(payload.get("id") or "").strip() or f"agent-{_slug(str(payload.get('name') or 'agent'))}"
    now = time.time()
    prev = agents.get(agent_id) or {}
    agent = {
        "id": agent_id,
        "name": str(payload.get("name") or prev.get("name") or agent_id).strip()[:80],
        "role": str(payload.get("role") or prev.get("role") or "").strip()[:120],
        "color": str(payload.get("color") or prev.get("color") or "#c4f04d").strip()[:32],
        "model": str(payload.get("model") or prev.get("model") or "vit/auto").strip()[:120],
        "studio": str(payload.get("studio") or prev.get("studio") or "chat").strip()[:40],
        "system": str(payload.get("system") or prev.get("system") or "").strip()[:8000],
        "tools": bool(payload.get("tools", prev.get("tools", True))),
        "preset": bool(prev.get("preset")) if "preset" not in payload else bool(payload.get("preset")),
        "created_at": prev.get("created_at") or now,
        "updated_at": now,
    }
    agents[agent_id] = agent
    _save(AGENTS_PATH, agents)
    return agent


def delete_agent(agent_id: str) -> dict[str, Any]:
    agents = _load(AGENTS_PATH)
    if agent_id not in agents:
        return {"ok": False, "error": "niet gevonden"}
    if agents[agent_id].get("preset"):
        return {"ok": False, "error": "preset-agent kan niet weg (wel bewerken)"}
    del agents[agent_id]
    _save(AGENTS_PATH, agents)
    # remove from teams
    teams = _load(TEAMS_PATH)
    changed = False
    for tid, team in list(teams.items()):
        members = [m for m in (team.get("members") or []) if m.get("agent_id") != agent_id]
        if len(members) != len(team.get("members") or []):
            team["members"] = members
            team["updated_at"] = time.time()
            teams[tid] = team
            changed = True
    if changed:
        _save(TEAMS_PATH, teams)
    return {"ok": True, "id": agent_id}


def list_teams() -> list[dict[str, Any]]:
    ensure_preset_teams()
    items = list(_load(TEAMS_PATH).values())
    return sorted(items, key=lambda t: (t.get("preset") is not True, t.get("name") or ""))


def get_team(team_id: str) -> dict[str, Any] | None:
    return _load(TEAMS_PATH).get(team_id)


def save_team(payload: dict[str, Any]) -> dict[str, Any]:
    teams = _load(TEAMS_PATH)
    team_id = str(payload.get("id") or "").strip() or f"team-{_slug(str(payload.get('name') or 'team'))}"
    now = time.time()
    prev = teams.get(team_id) or {}
    members_in = payload.get("members")
    if members_in is None:
        members_in = prev.get("members") or []
    members: list[dict[str, Any]] = []
    for i, m in enumerate(members_in):
        if not isinstance(m, dict):
            continue
        aid = str(m.get("agent_id") or "").strip()
        if not aid:
            continue
        members.append(
            {
                "agent_id": aid,
                "order": int(m.get("order", i)),
                "label": str(m.get("label") or "").strip()[:80],
            }
        )
    members.sort(key=lambda x: x["order"])
    team = {
        "id": team_id,
        "name": str(payload.get("name") or prev.get("name") or team_id).strip()[:80],
        "blurb": str(payload.get("blurb") or prev.get("blurb") or "").strip()[:240],
        "color": str(payload.get("color") or prev.get("color") or "#7ec8ff").strip()[:32],
        "studio": str(payload.get("studio") or prev.get("studio") or "chat").strip()[:40],
        "mode": str(payload.get("mode") or prev.get("mode") or "pipeline").strip()[:32],
        "lead_agent_id": str(payload.get("lead_agent_id") or prev.get("lead_agent_id") or "").strip()[:80],
        "members": members,
        "preset": bool(prev.get("preset")) if "preset" not in payload else bool(payload.get("preset")),
        "created_at": prev.get("created_at") or now,
        "updated_at": now,
    }
    if not team["lead_agent_id"] and members:
        team["lead_agent_id"] = members[0]["agent_id"]
    teams[team_id] = team
    _save(TEAMS_PATH, teams)
    return team


def delete_team(team_id: str) -> dict[str, Any]:
    teams = _load(TEAMS_PATH)
    if team_id not in teams:
        return {"ok": False, "error": "niet gevonden"}
    if teams[team_id].get("preset"):
        return {"ok": False, "error": "preset-team kan niet weg (wel bewerken)"}
    del teams[team_id]
    _save(TEAMS_PATH, teams)
    return {"ok": True, "id": team_id}


def _preset_agents() -> list[dict[str, Any]]:
    return [
        {
            "id": "agent-self-improve",
            "name": "Hub Improver",
            "role": "Self-improve",
            "color": "#c4f04d",
            "model": "vit/auto",
            "studio": "self",
            "system": (
                "Je past VIT AI Hub zelf aan op verzoek. Lees hub-bestanden, wijzig gericht, "
                "run pytest, vat samen. Geen secrets aanpassen."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-design-lead",
            "name": "Design Lead",
            "role": "Art direction",
            "color": "#c4f04d",
            "model": "vit/auto",
            "studio": "webdesign",
            "system": (
                "Je bent design lead. Bepaal merk, typografie, sfeer en hero-richting. "
                "Geen paars-op-wit clichés. Lever een kort brief + tokens (kleuren/fonts)."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-frontend",
            "name": "Frontend",
            "role": "HTML/CSS/React",
            "color": "#7ec8ff",
            "model": "vit/auto",
            "studio": "webdesign",
            "system": (
                "Je bent frontend engineer. Bouw werkende UI uit het design-brief. "
                "Full-bleed hero, expressieve fonts, mobile+desktop. Schrijf echte code."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-ux-copy",
            "name": "UX Copy",
            "role": "Teksten & CTA",
            "color": "#ffb454",
            "model": "vit/auto",
            "studio": "webdesign",
            "system": (
                "Je bent UX-writer. Scherp headline, sub, CTA. Nederlands tenzij gevraagd. "
                "Kort, merkbaar, geen marketing-fluff."
            ),
            "tools": False,
            "preset": True,
        },
        {
            "id": "agent-app-architect",
            "name": "App Architect",
            "role": "Architectuur",
            "color": "#c4f04d",
            "model": "vit/auto",
            "studio": "apps",
            "system": (
                "Je bent applicatie-architect. Schets modules, dataflow, API’s en risico’s. "
                "Kies pragmatisch; respecteer bestaande VIT-stack waar relevant."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-app-engineer",
            "name": "App Engineer",
            "role": "Implementatie",
            "color": "#7ec8ff",
            "model": "vit/auto",
            "studio": "software",
            "system": (
                "Je bent senior engineer. Implementeer in de workspace: lees, wijzig, test. "
                "Kleine diffs, echte code, geen waffle."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-qa",
            "name": "QA",
            "role": "Test & review",
            "color": "#ff6b6b",
            "model": "vit/auto",
            "studio": "software",
            "system": (
                "Je bent QA. Zoek bugs, edge cases, a11y en regressies. "
                "Geef checklist + concrete fixes (niet alleen meningen)."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-infra-lead",
            "name": "Infra Lead",
            "role": "Ops triage",
            "color": "#7ec8ff",
            "model": "vit/auto",
            "studio": "ops",
            "system": (
                "Je bent infra lead voor VIT. Start met ops_status/ops_overview. "
                "Prioriteer: cluster health, mail, cloud, backup. Read-first; geen mutaties zonder bevestiging."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-proxmox",
            "name": "Proxmox",
            "role": "Hypervisor",
            "color": "#c4f04d",
            "model": "vit/auto",
            "studio": "ops",
            "system": (
                "Je bewaakt Proxmox: nodes, VMs/LXC, storage. Gebruik proxmox_* tools. "
                "VM start/stop alleen met confirm=true na expliciete user-OK."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-mail-cloud",
            "name": "Mail & Cloud",
            "role": "Mailcow / Nextcloud / Gromox",
            "color": "#ffb454",
            "model": "vit/auto",
            "studio": "ops",
            "system": (
                "Je checkt Mailcow, Nextcloud en Gromox via ops-tools. "
                "Rapporteer versie/domains/health; geen mailbox-mutaties."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-marketing-strat",
            "name": "Marketing Strat",
            "role": "Positionering & GTM",
            "color": "#c4f04d",
            "model": "vit/auto",
            "studio": "marketing",
            "system": (
                "Je bent marketing-strateeg voor VIT/B2B. ICP, positionering, message house, "
                "funnel/GTM. Scherp, geen fluff. Lever pitch + bewijs + CTA."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-pitch-writer",
            "name": "Pitch Writer",
            "role": "Pitch & sales copy",
            "color": "#ffb454",
            "model": "vit/auto",
            "studio": "marketing",
            "system": (
                "Je schrijft pitches, one-pagers en landingscopy. 30s + 2min versies. "
                "Spreekbaar NL, merkbaar, concrete CTA. Geen buzzwords."
            ),
            "tools": False,
            "preset": True,
        },
        {
            "id": "agent-social-lead",
            "name": "Social Lead",
            "role": "Social strategy",
            "color": "#7ec8ff",
            "model": "vit/auto",
            "studio": "socials",
            "system": (
                "Je plant social strategie: kanaalkeuze, kalender, hoeken. "
                "LinkedIn B2B eerst tenzij anders gevraagd. Platform-native."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-social-copy",
            "name": "Social Copy",
            "role": "Posts & scripts",
            "color": "#ffb454",
            "model": "vit/auto",
            "studio": "socials",
            "system": (
                "Je schrijft posts/scripts: sterke hook, één idee, subtiele CTA. "
                "Batches van 5 + korte kalenderregels. Max 3–5 hashtags of geen."
            ),
            "tools": False,
            "preset": True,
        },
        {
            "id": "agent-seo-lead",
            "name": "SEO Lead",
            "role": "SEO / GEO strategy",
            "color": "#c4f04d",
            "model": "vit/auto",
            "studio": "seo",
            "system": (
                "Je bent SEO/GEO lead. Intent map, keyword clusters, on-page + "
                "generative-engine citeerbaarheid (AEO). Local SEO NL waar relevant. Geen black-hat."
            ),
            "tools": True,
            "preset": True,
        },
        {
            "id": "agent-seo-content",
            "name": "SEO Content",
            "role": "Content briefs",
            "color": "#7ec8ff",
            "model": "vit/auto",
            "studio": "seo",
            "system": (
                "Je levert SEO/GEO content briefs: title/H1/H2, FAQ, schema-hints, "
                "interne links. Quotable feiten voor AI-engines. Geen keyword stuffing."
            ),
            "tools": False,
            "preset": True,
        },
    ]


def _preset_teams() -> list[dict[str, Any]]:
    return [
        {
            "id": "team-self",
            "name": "Self-improve team",
            "blurb": "Hub Improver — pas de app aan als je dat vraagt.",
            "color": "#c4f04d",
            "studio": "self",
            "mode": "pipeline",
            "lead_agent_id": "agent-self-improve",
            "members": [
                {"agent_id": "agent-self-improve", "order": 0, "label": "Improve"},
            ],
            "preset": True,
        },
        {
            "id": "team-webdesign",
            "name": "Webdesign team",
            "blurb": "Design lead → frontend → UX copy. Sites & landings.",
            "color": "#c4f04d",
            "studio": "webdesign",
            "mode": "pipeline",
            "lead_agent_id": "agent-design-lead",
            "members": [
                {"agent_id": "agent-design-lead", "order": 0, "label": "Brief"},
                {"agent_id": "agent-frontend", "order": 1, "label": "Bouwen"},
                {"agent_id": "agent-ux-copy", "order": 2, "label": "Teksten"},
            ],
            "preset": True,
        },
        {
            "id": "team-apps",
            "name": "Applicatie team",
            "blurb": "Architect → engineer → QA. Product & Mac/web apps.",
            "color": "#7ec8ff",
            "studio": "apps",
            "mode": "pipeline",
            "lead_agent_id": "agent-app-architect",
            "members": [
                {"agent_id": "agent-app-architect", "order": 0, "label": "Plan"},
                {"agent_id": "agent-app-engineer", "order": 1, "label": "Bouwen"},
                {"agent_id": "agent-qa", "order": 2, "label": "Review"},
            ],
            "preset": True,
        },
        {
            "id": "team-infra",
            "name": "Infra team",
            "blurb": "Ops triage → Proxmox → Mail/Cloud. Read-first health.",
            "color": "#7ec8ff",
            "studio": "ops",
            "mode": "pipeline",
            "lead_agent_id": "agent-infra-lead",
            "members": [
                {"agent_id": "agent-infra-lead", "order": 0, "label": "Triage"},
                {"agent_id": "agent-proxmox", "order": 1, "label": "PVE"},
                {"agent_id": "agent-mail-cloud", "order": 2, "label": "Mail/Cloud"},
            ],
            "preset": True,
        },
        {
            "id": "team-marketing",
            "name": "Marketing team",
            "blurb": "Strat → pitch copy. Pitches, propositie, GTM.",
            "color": "#c4f04d",
            "studio": "marketing",
            "mode": "pipeline",
            "lead_agent_id": "agent-marketing-strat",
            "members": [
                {"agent_id": "agent-marketing-strat", "order": 0, "label": "Strat"},
                {"agent_id": "agent-pitch-writer", "order": 1, "label": "Pitch"},
            ],
            "preset": True,
        },
        {
            "id": "team-socials",
            "name": "Socials team",
            "blurb": "Social lead → posts/scripts. LinkedIn & contentkalender.",
            "color": "#7ec8ff",
            "studio": "socials",
            "mode": "pipeline",
            "lead_agent_id": "agent-social-lead",
            "members": [
                {"agent_id": "agent-social-lead", "order": 0, "label": "Plan"},
                {"agent_id": "agent-social-copy", "order": 1, "label": "Posts"},
            ],
            "preset": True,
        },
        {
            "id": "team-seo",
            "name": "SEO / GEO team",
            "blurb": "SEO lead → content briefs. Zoek + AI-citeerbaarheid.",
            "color": "#ffb454",
            "studio": "seo",
            "mode": "pipeline",
            "lead_agent_id": "agent-seo-lead",
            "members": [
                {"agent_id": "agent-seo-lead", "order": 0, "label": "Strategie"},
                {"agent_id": "agent-seo-content", "order": 1, "label": "Brief"},
            ],
            "preset": True,
        },
        {
            "id": "team-growth",
            "name": "Growth team",
            "blurb": "Marketing → SEO → Socials → UX copy. Pitches & sites top.",
            "color": "#c4f04d",
            "studio": "marketing",
            "mode": "pipeline",
            "lead_agent_id": "agent-marketing-strat",
            "members": [
                {"agent_id": "agent-marketing-strat", "order": 0, "label": "Positionering"},
                {"agent_id": "agent-seo-lead", "order": 1, "label": "SEO/GEO"},
                {"agent_id": "agent-social-copy", "order": 2, "label": "Socials"},
                {"agent_id": "agent-ux-copy", "order": 3, "label": "Site-copy"},
            ],
            "preset": True,
        },
    ]


def ensure_preset_teams() -> None:
    """Seed preset agents/teams once; laat user-edits staan."""
    agents = _load(AGENTS_PATH)
    changed_a = False
    for preset in _preset_agents():
        if preset["id"] not in agents:
            preset = {**preset, "created_at": time.time(), "updated_at": time.time()}
            agents[preset["id"]] = preset
            changed_a = True
    if changed_a:
        _save(AGENTS_PATH, agents)

    teams = _load(TEAMS_PATH)
    changed_t = False
    for preset in _preset_teams():
        if preset["id"] not in teams:
            preset = {**preset, "created_at": time.time(), "updated_at": time.time()}
            teams[preset["id"]] = preset
            changed_t = True
    if changed_t:
        _save(TEAMS_PATH, teams)
