"""Modelkeuze per intent — lokaal-first waar het kan, cloud waar het telt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vit_ai_hub.backends import build_backends
from vit_ai_hub.config import get_settings, load_yaml_config
from vit_ai_hub.orchestrator.intent import Intent


@dataclass
class ModelPick:
    model: str
    reason: str
    prefer_local: bool
    role: str | None = None  # optional agent role hint


def _cfg() -> dict[str, Any]:
    return load_yaml_config().get("orchestrator") or {}


def _has_key(backends: dict, name: str) -> bool:
    b = backends.get(name)
    if not b:
        return False
    if name in {"lmstudio", "ollama"}:
        return bool(b.base_url)
    if name == "bridge":
        return bool(b.base_url)  # bridge may work with local OAuth even zonder key string
    key = getattr(b, "api_key", "") or ""
    return bool(b.base_url and key and key not in {"", "bridge", "omniroute", "lmstudio", "ollama"})


def _local_available(backends: dict) -> bool:
    for name in ("lmstudio", "ollama"):
        b = backends.get(name)
        if b and b.base_url:
            return True
    return False


def _local_model(*, heavy: bool = False) -> str:
    s = get_settings()
    if heavy:
        return s.vit_local_heavy_model or s.vit_local_light_model or "vit/local-heavy"
    return s.vit_local_light_model or "vit/local-light"


def _overrides() -> dict[str, str]:
    raw = _cfg().get("models") or {}
    return {str(k): str(v) for k, v in raw.items() if v}


def pick_model_for_intent(
    intent: Intent,
    *,
    force_local: bool = False,
    role: str | None = None,
) -> ModelPick:
    """Kies het beste beschikbare model voor deze intent (+ optionele agent-rol)."""
    backends = build_backends()
    ov = _overrides()
    local_ok = _local_available(backends)
    bridge_ok = bool(backends.get("bridge") and backends["bridge"].base_url)
    or_ok = _has_key(backends, "openrouter")
    ds_ok = _has_key(backends, "deepseek")
    grok_ok = _has_key(backends, "grok")

    prefer_local_kinds = set(_cfg().get("prefer_local_for") or ["ops", "simple", "privacy"])
    kind = intent.kind
    role_l = (role or "").lower()

    if force_local:
        heavy = kind in {"code", "complex", "self"} or intent.complexity == "high"
        return ModelPick(
            model=_local_model(heavy=heavy),
            reason="PII/fail-closed → lokaal",
            prefer_local=True,
            role=role,
        )

    # Role-specific overrides inside teams
    if role_l:
        if any(x in role_l for x in ("qa", "test", "review")):
            if ds_ok:
                return ModelPick("deepseek-reasoner", "QA → DeepSeek reasoner", False, role)
            if bridge_ok:
                return ModelPick("claude-sonnet-4", "QA → Claude via bridge", False, role)
            if or_ok:
                return ModelPick("deepseek/deepseek-r1", "QA → R1 via OpenRouter", False, role)
        if any(x in role_l for x in ("copy", "ux", "schrijf", "tekst")):
            if bridge_ok:
                return ModelPick("claude-sonnet-4", "Copy → Claude", False, role)
            if or_ok:
                return ModelPick(
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "Copy → Llama free",
                    False,
                    role,
                )
            if local_ok:
                return ModelPick(_local_model(), "Copy → lokaal", True, role)
        if any(x in role_l for x in ("design", "art", "frontend")):
            if bridge_ok:
                return ModelPick("claude-sonnet-4", "Design/FE → Claude", False, role)
            if or_ok:
                return ModelPick("openrouter:anthropic/claude-sonnet-4", "Design → OR Claude", False, role)
            if local_ok:
                return ModelPick(_local_model(heavy=True), "Design → lokaal heavy", True, role)
        if any(x in role_l for x in ("architect", "plan", "triage", "lead")):
            if bridge_ok:
                return ModelPick("claude-sonnet-4", "Lead/architect → Claude", False, role)
            if ds_ok:
                return ModelPick("deepseek-reasoner", "Lead → DeepSeek reasoner", False, role)
            if or_ok:
                return ModelPick("deepseek/deepseek-r1", "Lead → R1", False, role)
        if any(x in role_l for x in ("engineer", "implement", "proxmox", "mail", "infra", "hub improver")):
            if kind == "ops" or "proxmox" in role_l or "mail" in role_l or "infra" in role_l:
                if local_ok:
                    return ModelPick(_local_model(), "Ops-rol → lokaal (privacy)", True, role)
            if ds_ok:
                return ModelPick("deepseek-chat", "Engineer → DeepSeek", False, role)
            if bridge_ok:
                return ModelPick("claude-sonnet-4", "Engineer → Claude", False, role)
            if local_ok:
                return ModelPick(_local_model(heavy=True), "Engineer → lokaal heavy", True, role)

    # Explicit config override per kind
    if kind in ov:
        return ModelPick(ov[kind], f"config override ({kind})", kind in prefer_local_kinds, role)

    # Intent policies
    if kind in prefer_local_kinds and local_ok:
        return ModelPick(
            _local_model(heavy=kind == "ops" and intent.complexity == "high"),
            f"{kind} → lokaal-first",
            True,
            role,
        )

    if kind == "simple" and local_ok:
        return ModelPick(_local_model(), "simpele vraag → lokaal light", True, role)

    if kind == "ops":
        if local_ok:
            return ModelPick(_local_model(), "ops → lokaal (secrets/VPN context)", True, role)
        if bridge_ok:
            return ModelPick("claude-sonnet-4", "ops → Claude (geen lokaal)", False, role)

    if kind == "code":
        # Code: DeepSeek sterk & goedkoop; Claude via bridge als quality; lokaal heavy als fallback
        if intent.complexity == "high":
            if bridge_ok:
                return ModelPick("claude-sonnet-4", "zware code → Claude bridge", False, role)
            if ds_ok:
                return ModelPick("deepseek-reasoner", "zware code → DeepSeek reasoner", False, role)
        if ds_ok:
            return ModelPick("deepseek-chat", "code → DeepSeek chat", False, role)
        if bridge_ok:
            return ModelPick("claude-sonnet-4", "code → Claude bridge", False, role)
        if or_ok:
            return ModelPick("deepseek/deepseek-chat", "code → DeepSeek via OR", False, role)
        if local_ok:
            return ModelPick(_local_model(heavy=True), "code → lokaal heavy", True, role)

    if kind == "design":
        if bridge_ok:
            return ModelPick("claude-sonnet-4", "design → Claude (visueel/taal)", False, role)
        if or_ok:
            return ModelPick(
                "google/gemma-3-27b-it:free",
                "design → Gemma free",
                False,
                role,
            )
        if local_ok:
            return ModelPick(_local_model(heavy=True), "design → lokaal heavy", True, role)

    if kind == "write":
        if bridge_ok:
            return ModelPick("claude-sonnet-4", "schrijven → Claude", False, role)
        if or_ok:
            return ModelPick(
                "meta-llama/llama-3.3-70b-instruct:free",
                "schrijven → Llama free",
                False,
                role,
            )
        if local_ok:
            return ModelPick(_local_model(), "schrijven → lokaal", True, role)

    if kind == "research":
        if or_ok:
            return ModelPick(
                "meta-llama/llama-3.3-70b-instruct:free",
                "research → OR + tools",
                False,
                role,
            )
        if bridge_ok:
            return ModelPick("claude-sonnet-4", "research → Claude", False, role)
        if grok_ok:
            return ModelPick("grok-3-mini", "research → Grok mini", False, role)
        if local_ok:
            return ModelPick(_local_model(), "research → lokaal + tools", True, role)

    if kind in {"complex", "self"}:
        if bridge_ok:
            return ModelPick("claude-sonnet-4", f"{kind} → Claude lead", False, role)
        if ds_ok:
            return ModelPick("deepseek-reasoner", f"{kind} → DeepSeek reasoner", False, role)
        if or_ok:
            return ModelPick("deepseek/deepseek-r1", f"{kind} → R1", False, role)
        if local_ok:
            return ModelPick(_local_model(heavy=True), f"{kind} → lokaal heavy", True, role)

    # chat default: local light if possible, else cheapest smart cloud
    if local_ok:
        return ModelPick(_local_model(), "chat → lokaal light", True, role)
    if bridge_ok:
        return ModelPick("claude-sonnet-4", "chat → Claude bridge", False, role)
    if or_ok:
        return ModelPick(
            "meta-llama/llama-3.3-70b-instruct:free",
            "chat → free OR",
            False,
            role,
        )
    if ds_ok:
        return ModelPick("deepseek-chat", "chat → DeepSeek", False, role)
    return ModelPick("vit/local-light", "fallback virtual local", True, role)


def pick_models_for_team_roles(
    intent: Intent,
    roles: list[tuple[str, str | None]],
    *,
    force_local: bool = False,
) -> dict[str, ModelPick]:
    """roles: list of (agent_id, role_label)."""
    return {
        agent_id: pick_model_for_intent(intent, force_local=force_local, role=role)
        for agent_id, role in roles
    }
