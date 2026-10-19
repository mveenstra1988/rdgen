"""Auto-plan: single-model of multi-agent team met per-rol modelkeuze + fallbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vit_ai_hub.config import load_yaml_config
from vit_ai_hub.orchestrator.critic import critic_enabled
from vit_ai_hub.orchestrator.fallback import build_fallback_chain
from vit_ai_hub.orchestrator.intent import Intent, classify_intent, intent_to_dict, strength_score
from vit_ai_hub.orchestrator.policy import ModelPick, pick_model_for_intent, pick_models_for_team_roles
from vit_ai_hub.orchestrator.telemetry import log_route


@dataclass
class AutoPlan:
    intent: Intent
    model: str
    model_reason: str
    use_team: bool
    team_id: str | None
    studio: str | None
    role_models: dict[str, str] = field(default_factory=dict)
    role_reasons: dict[str, str] = field(default_factory=dict)
    fallbacks: list[str] = field(default_factory=list)
    tradeoff: str = "quality"
    use_critic: bool = False
    strength: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": intent_to_dict(self.intent),
            "model": self.model,
            "model_reason": self.model_reason,
            "use_team": self.use_team,
            "team_id": self.team_id,
            "studio": self.studio,
            "role_models": self.role_models,
            "role_reasons": self.role_reasons,
            "fallbacks": self.fallbacks,
            "tradeoff": self.tradeoff,
            "use_critic": self.use_critic,
            "strength": round(self.strength, 3),
            "summary": self.summary,
        }


def _orch_cfg() -> dict[str, Any]:
    return load_yaml_config().get("orchestrator") or {}


def plan_request(
    text: str,
    *,
    studio: str | None = None,
    workspace: str | None = None,
    force_local: bool = False,
    allow_team: bool | None = None,
    tradeoff: str | None = None,
) -> AutoPlan:
    cfg = _orch_cfg()
    enabled = cfg.get("enabled", True)
    auto_team = cfg.get("auto_team", True) if allow_team is None else allow_team
    tradeoff = (tradeoff or cfg.get("tradeoff") or "quality").lower()
    if tradeoff not in {"quality", "cost", "latency"}:
        tradeoff = "quality"

    intent = classify_intent(text, studio=studio, workspace=workspace)
    pick = pick_model_for_intent(intent, force_local=force_local, tradeoff=tradeoff)
    strength = strength_score(intent)
    fallbacks = build_fallback_chain(
        pick, intent, force_local=force_local, tradeoff=tradeoff
    )

    use_team = bool(
        enabled
        and auto_team
        and intent.multi_agent
        and intent.suggested_team
        and intent.complexity in {"medium", "high"}
    )

    if intent.kind == "simple":
        use_team = False
    if intent.confidence < 0.35 and not studio:
        use_team = False

    role_models: dict[str, str] = {}
    role_reasons: dict[str, str] = {}
    if use_team and intent.suggested_team:
        try:
            from vit_ai_hub.agents.store import get_team, list_agents, ensure_preset_teams

            ensure_preset_teams()
            team = get_team(intent.suggested_team)
            if team:
                agents_by_id = {a["id"]: a for a in list_agents()}
                roles = []
                for m in team.get("members") or []:
                    aid = m["agent_id"]
                    ag = agents_by_id.get(aid) or {}
                    roles.append((aid, ag.get("role") or ag.get("name") or aid))
                picks = pick_models_for_team_roles(
                    intent, roles, force_local=force_local, tradeoff=tradeoff
                )
                role_models = {k: v.model for k, v in picks.items()}
                role_reasons = {k: v.reason for k, v in picks.items()}
            else:
                use_team = False
        except Exception:
            use_team = False

    use_critic = bool(enabled and not use_team and critic_enabled(intent))
    studio_out = intent.suggested_studio or studio
    summary = _summarize(intent, pick, use_team, fallbacks, tradeoff, use_critic, strength)

    plan = AutoPlan(
        intent=intent,
        model=pick.model,
        model_reason=pick.reason,
        use_team=use_team,
        team_id=intent.suggested_team if use_team else None,
        studio=studio_out,
        role_models=role_models,
        role_reasons=role_reasons,
        fallbacks=fallbacks,
        tradeoff=tradeoff,
        use_critic=use_critic,
        strength=strength,
        summary=summary,
    )
    log_route({"event": "plan", **plan.to_dict()})
    return plan


def _summarize(
    intent: Intent,
    pick: ModelPick,
    use_team: bool,
    fallbacks: list[str],
    tradeoff: str,
    use_critic: bool,
    strength: float,
) -> str:
    bits = [
        f"intent={intent.kind}/{intent.complexity}",
        f"strength={strength:.2f}",
        f"tradeoff={tradeoff}",
        f"model={pick.model} ({pick.reason})",
    ]
    if use_team and intent.suggested_team:
        bits.append(f"team={intent.suggested_team}")
    else:
        bits.append("mode=single")
    if len(fallbacks) > 1:
        bits.append(f"fallbacks={len(fallbacks)}")
    if use_critic:
        bits.append("critic=on")
    return " · ".join(bits)
