"""Heuristic intent classifier — snel, deterministisch, geen extra LLM-rondje."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    kind: str  # simple|chat|code|design|ops|write|research|complex|self
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
    r"volledig (project|app|site|systeem))\b",
    re.I,
)
_SIMPLE = re.compile(
    r"^(ok(é|e)?|ja|nee|thanks|dank|korte vraag|even|snel|wat is \d|1\+1)[\s.!?]*$",
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
    domains = sum(1 for k in ("code", "design", "ops", "write") if scores[k] >= 0.35)
    if domains >= 2:
        scores["complex"] += 0.4
        signals.append("multi_domain")

    kind = max(scores, key=scores.get)
    confidence = min(0.98, scores[kind])

    multi = False
    team = None
    sug_studio = studio
    complexity = "low"

    if kind == "complex" or (kind in {"code", "design", "apps"} and scores["complex"] >= 0.35):
        multi = True
        complexity = "high"
        if scores["design"] >= scores["code"] and scores["design"] >= 0.3:
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
    }
