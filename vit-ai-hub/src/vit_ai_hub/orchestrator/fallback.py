"""Ordered model fallback chains (OpenRouter-style + lokale safety net)."""

from __future__ import annotations

from typing import Any

from vit_ai_hub.backends import build_backends
from vit_ai_hub.config import load_yaml_config
from vit_ai_hub.orchestrator.intent import Intent
from vit_ai_hub.orchestrator.policy import (
    ModelPick,
    has_backend_key,
    local_available,
    local_model_id,
)


def _cfg() -> dict[str, Any]:
    return load_yaml_config().get("orchestrator") or {}


def build_fallback_chain(
    primary: ModelPick,
    intent: Intent,
    *,
    force_local: bool = False,
    tradeoff: str = "quality",
) -> list[str]:
    """Primary eerst, daarna goedgekeurde alternatieven (max attempt budget)."""
    cfg = _cfg()
    max_fallbacks = int(cfg.get("max_fallbacks") or 3)
    backends = build_backends()
    local_ok = local_available(backends)
    bridge_ok = bool(backends.get("bridge") and backends["bridge"].base_url)
    or_ok = has_backend_key(backends, "openrouter")
    ds_ok = has_backend_key(backends, "deepseek")

    chain: list[str] = [primary.model]
    seen = {primary.model}

    def add(mid: str | None) -> None:
        if not mid or mid in seen or len(chain) > max_fallbacks:
            return
        seen.add(mid)
        chain.append(mid)

    if force_local:
        add(local_model_id(heavy=True))
        add(local_model_id(heavy=False))
        return chain[: max_fallbacks + 1]

    if intent.kind == "code":
        if ds_ok:
            add("deepseek-chat")
            add("deepseek-reasoner")
        if bridge_ok:
            add("claude-sonnet-4")
        if or_ok:
            add("deepseek/deepseek-chat")
            add("qwen/qwen3-32b:free")
        if local_ok:
            add(local_model_id(heavy=True))
    elif intent.kind in {"design", "write"}:
        if bridge_ok:
            add("claude-sonnet-4")
        if or_ok:
            add("meta-llama/llama-3.3-70b-instruct:free")
            add("google/gemma-3-27b-it:free")
        if local_ok:
            add(local_model_id(heavy=True))
    elif intent.kind == "ops":
        if local_ok:
            add(local_model_id(heavy=False))
            add(local_model_id(heavy=True))
        if bridge_ok:
            add("claude-sonnet-4")
    elif intent.kind in {"complex", "self", "research"}:
        if bridge_ok:
            add("claude-sonnet-4")
        if ds_ok:
            add("deepseek-reasoner")
        if or_ok:
            add("deepseek/deepseek-r1")
            add("meta-llama/llama-3.3-70b-instruct:free")
        if local_ok:
            add(local_model_id(heavy=True))
    else:
        if tradeoff in {"cost", "latency"}:
            if local_ok:
                add(local_model_id())
            if or_ok:
                add("meta-llama/llama-3.3-70b-instruct:free")
            if ds_ok:
                add("deepseek-chat")
        else:
            if local_ok:
                add(local_model_id())
            if bridge_ok:
                add("claude-sonnet-4")
            if or_ok:
                add("meta-llama/llama-3.3-70b-instruct:free")

    if local_ok and not force_local:
        add(local_model_id(heavy=intent.complexity == "high"))

    for extra in cfg.get("fallback_extra") or []:
        add(str(extra))

    return chain[: max_fallbacks + 1]
