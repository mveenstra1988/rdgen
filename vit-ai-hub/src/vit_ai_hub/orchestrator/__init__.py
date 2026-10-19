"""Slimme auto-orchestratie: intent → model → optioneel multi-agent team."""

from vit_ai_hub.orchestrator.auto import AutoPlan, plan_request
from vit_ai_hub.orchestrator.intent import Intent, classify_intent
from vit_ai_hub.orchestrator.policy import pick_model_for_intent

__all__ = [
    "AutoPlan",
    "Intent",
    "classify_intent",
    "pick_model_for_intent",
    "plan_request",
]
