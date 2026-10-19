"""Heuristic intent classifier — snel, deterministisch, geen extra LLM-rondje."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    kind: str  # simple|chat|code|design|ops|write|research|marketing|socials|seo|complex|self
    confidence: float
    signals: list[str] = field(default_factory=list)
    multi_agent: bool = False
    suggested_team: str | None = None
    suggested_studio: str | None = None
    complexity: str = "low"  # low|medium|high


_CODE = re.compile(
    r"\b(code|refactor|bug|fix|pytest|typescript|python|swift|react|api|pr\b|commit|"
    r"implementeer|debug|stacktrace|compile|typeerror|unittest|dockerfile|git\b|"
    r"functie|class\b|endpoint|sql|migratie)\b",
    re.I,
)
_DESIGN = re.compile(
    r"\b(design|ui|ux|landing|hero|css|figma|penpot|layout|typografie|kleur|brand|"
    r"webdesign|wireframe|mockup|frontend.?visueel)\b",
    re.I,
)
_OPS = re.compile(
    r"\b(proxmox|pve|lxc|vm\b|mailcow|nextcloud|gromox|unifi|backup|servicehub|"
    r"automation.?hub|cluster|vpn|ssh|infra|ops\b|container|disk|storage)\b",
    re.I,
)
_WRITE = re.compile(
    r"\b(schrijf|copy|cta|headline|tekst|email|mail\b|blog|documentatie|docs|"
    r"samenvatting|vertaal|herschrijf)\b",
    re.I,
)
_MARKETING = re.compile(
    r"\b(marketing|pitch|propositie|positionering|positioning|gtm|go.?to.?market|"
    r"funnel|campagne|campaign|icp|persona|value proposition|usp\b|sales.?deck|"
    r"one.?pager|brochure|merkverhaal|brand story|aanbod|offerte.?tekst|"
    r"leadgen|lead.?gen|conversion|conversie)\b",
    re.I,
)
_SOCIALS = re.compile(
    r"\b(socials?|linkedin|instagram|tiktok|reels?|stories|facebook|threads|"
    r"content.?kalender|content.?calendar|hashtag|carousel|post\b|posts\b|"
    r"social media|social.?post)\b",
    re.I,
)
_SEO = re.compile(
    r"\b(seo\b|geo\b|aeo\b|serp|zoekmachine|keywords?|zoekwoorden?|meta.?description|"
    r"schema\.?org|structured data|local seo|google business|gbp\b|"
    r"generative engine|citeerbaar|rank(ing|en)?|indexatie|sitemap|"
    r"on.?page|backlinks?|eeat|e-?e-?a-?t)\b",
    re.I,
)
_RESEARCH = re.compile(
    r"\b(zoek|research|vergelijk|wat is|hoe werkt|documentatie|bronnen|actueel|"
    r"nieuws|prijs|benchmark)\b",
    re.I,
)
_SELF = re.compile(
    r"\b(pas jezelf aan|self.?improve|verbeter de hub|wijzig de hub|hub.?code)\b",
    re.I,
)
_COMPLEX = re.compile(
    r"\b(bouw (een |de )?(hele |volledige )?|end.?to.?end|van a tot z|meerdere stappen|"
    r"architectuur|team|pipeline|plan én|plan en|en daarna|review en|"
    r"volledig (project|app|site|systeem|campagne|funnel))\b",
    re.I,
)
_SIMPLE = re.compile(
    r"^(ok(é|e)?|ja|nee|thanks|dank|korte vraag|even|snel|wat is \d|1\+1)[\s.!?]*$",
    re.I,
)
_SITE_PITCH = re.compile(
    r"\b(site|website|landing|pitch.?deck|sales.?page|landingspagina)\b",
    re.I,
)


def classify_intent(
    text: str,
    *,
    studio: str | None = None,
    workspace: str | None = None,
) -> Intent:
    t = (text or "").strip()
    studio = (studio or "").strip().lower() or None
    signals: list[str] = []
    scores: dict[str, float] = {
        "simple": 0.0,
        "chat": 0.15,
        "code": 0.0,
        "design": 0.0,
        "ops": 0.0,
        "write": 0.0,
        "marketing": 0.0,
        "socials": 0.0,
        "seo": 0.0,
        "research": 0.0,
        "complex": 0.0,
        "self": 0.0,
    }

    if studio == "software":
        scores["code"] += 0.55
        signals.append("studio:software")
    elif studio == "webdesign" or studio == "design":
        scores["design"] += 0.55
        signals.append(f"studio:{studio}")
    elif studio == "ops":
        scores["ops"] += 0.7
        signals.append("studio:ops")
    elif studio == "self":
        scores["self"] += 0.8
        signals.append("studio:self")
    elif studio == "apps":
        scores["code"] += 0.35
        scores["complex"] += 0.25
        signals.append("studio:apps")
    elif studio == "marketing":
        scores["marketing"] += 0.7
        signals.append("studio:marketing")
    elif studio == "socials":
        scores["socials"] += 0.7
        signals.append("studio:socials")
    elif studio == "seo":
        scores["seo"] += 0.7
        signals.append("studio:seo")

    if workspace:
        scores["code"] += 0.15
        signals.append("workspace")

    if not t:
        return Intent(kind="chat", confidence=0.4, signals=["empty"], suggested_studio=studio)

    if _SIMPLE.search(t) and len(t) < 80:
        scores["simple"] += 0.9
        signals.append("simple_phrase")

    for kind, rx, w in (
        ("code", _CODE, 0.45),
        ("design", _DESIGN, 0.45),
        ("ops", _OPS, 0.55),
        ("marketing", _MARKETING, 0.5),
        ("socials", _SOCIALS, 0.5),
        ("seo", _SEO, 0.5),
        ("write", _WRITE, 0.35),
        ("research", _RESEARCH, 0.35),
        ("self", _SELF, 0.7),
        ("complex", _COMPLEX, 0.5),
    ):
        if rx.search(t):
            scores[kind] += w
            signals.append(kind)

    # length / structure heuristics
    if len(t) > 600 or t.count("\n") >= 8:
        scores["complex"] += 0.25
        signals.append("long_prompt")
    if t.count("```") >= 2 or "def " in t or "function " in t:
        scores["code"] += 0.3
        signals.append("code_fence")

    # multi-domain → complex
    growth_domains = sum(1 for k in ("marketing", "socials", "seo") if scores[k] >= 0.35)
    other_domains = sum(1 for k in ("code", "design", "ops", "write") if scores[k] >= 0.35)
    if growth_domains >= 2 or (growth_domains >= 1 and other_domains >= 1):
        scores["complex"] += 0.45
        signals.append("multi_domain_growth")
    elif other_domains >= 2:
        scores["complex"] += 0.4
        signals.append("multi_domain")

    kind = max(scores, key=scores.get)
    confidence = min(0.98, scores[kind])

    multi = False
    team = None
    sug_studio = studio
    complexity = "low"

    def _pick_growth_team() -> str:
        if growth_domains >= 2 or (scores["marketing"] >= 0.35 and (_SITE_PITCH.search(t) or scores["design"] >= 0.3)):
            return "team-growth"
        if scores["seo"] >= scores["marketing"] and scores["seo"] >= scores["socials"] and scores["seo"] >= 0.35:
            return "team-seo"
        if scores["socials"] >= scores["marketing"] and scores["socials"] >= 0.35:
            return "team-socials"
        return "team-marketing"

    if kind == "complex" or (
        kind in {"code", "design", "marketing", "socials", "seo"} and scores["complex"] >= 0.35
    ):
        multi = True
        complexity = "high"
        if growth_domains >= 1 and (
            growth_domains >= 2
            or scores["marketing"] >= 0.35
            or scores["socials"] >= 0.35
            or scores["seo"] >= 0.35
        ):
            team = _pick_growth_team()
            sug_studio = sug_studio or (
                "seo"
                if team == "team-seo"
                else "socials"
                if team == "team-socials"
                else "marketing"
            )
        elif scores["design"] >= scores["code"] and scores["design"] >= 0.3:
            team = "team-webdesign"
            sug_studio = sug_studio or "webdesign"
        elif scores["ops"] >= 0.4:
            team = "team-infra"
            sug_studio = sug_studio or "ops"
        elif scores["self"] >= 0.4:
            team = "team-self"
            sug_studio = "self"
        else:
            team = "team-apps" if scores.get("code", 0) >= 0.3 else "team-webdesign"
            sug_studio = sug_studio or ("apps" if team == "team-apps" else "webdesign")
    elif kind == "ops":
        complexity = "medium"
        sug_studio = sug_studio or "ops"
        if scores["complex"] >= 0.25 or "overview" in t.lower() or "alles" in t.lower():
            multi = True
            team = "team-infra"
            complexity = "high"
    elif kind == "self":
        multi = True
        team = "team-self"
        sug_studio = "self"
        complexity = "medium"
    elif kind == "code":
        complexity = "medium" if len(t) > 200 else "low"
        sug_studio = sug_studio or "software"
    elif kind == "design":
        complexity = "medium"
        sug_studio = sug_studio or "webdesign"
        if len(t) > 280 or "landing" in t.lower() or "site" in t.lower():
            multi = True
            team = "team-webdesign"
            complexity = "high"
    elif kind == "marketing":
        complexity = "medium"
        sug_studio = sug_studio or "marketing"
        if len(t) > 220 or scores["complex"] >= 0.2 or _SITE_PITCH.search(t):
            multi = True
            team = _pick_growth_team()
            complexity = "high"
            if team == "team-growth" and not sug_studio:
                sug_studio = "marketing"
    elif kind == "socials":
        complexity = "medium"
        sug_studio = sug_studio or "socials"
        if len(t) > 200 or "kalender" in t.lower() or "calendar" in t.lower() or scores["complex"] >= 0.2:
            multi = True
            team = "team-socials"
            complexity = "high"
    elif kind == "seo":
        complexity = "medium"
        sug_studio = sug_studio or "seo"
        if len(t) > 200 or "site" in t.lower() or "cluster" in t.lower() or scores["complex"] >= 0.2:
            multi = True
            team = "team-seo"
            complexity = "high"
    elif kind == "simple":
        complexity = "low"
    else:
        complexity = "low" if len(t) < 200 else "medium"

    return Intent(
        kind=kind if kind != "apps" else "code",
        confidence=confidence,
        signals=signals,
        multi_agent=multi,
        suggested_team=team,
        suggested_studio=sug_studio,
        complexity=complexity,
    )


def intent_to_dict(intent: Intent) -> dict[str, Any]:
    return {
        "kind": intent.kind,
        "confidence": round(intent.confidence, 3),
        "signals": intent.signals,
        "multi_agent": intent.multi_agent,
        "suggested_team": intent.suggested_team,
        "suggested_studio": intent.suggested_studio,
        "complexity": intent.complexity,
        "strength": round(strength_score(intent), 3),
    }


def strength_score(intent: Intent) -> float:
    """0=weak/cheap genoeg, 1=strong model nodig (RouteLLM-achtig)."""
    base = {"low": 0.25, "medium": 0.55, "high": 0.85}.get(intent.complexity, 0.5)
    bump = {
        "simple": -0.2,
        "chat": 0.0,
        "ops": -0.05,
        "write": 0.05,
        "research": 0.1,
        "socials": 0.12,
        "seo": 0.15,
        "marketing": 0.18,
        "design": 0.15,
        "code": 0.2,
        "self": 0.25,
        "complex": 0.3,
    }.get(intent.kind, 0.0)
    if intent.multi_agent:
        bump += 0.1
    return max(0.0, min(1.0, base + bump))
