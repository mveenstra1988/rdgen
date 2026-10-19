from __future__ import annotations

from typing import Any

from vit_ai_hub.backends.openai_compat import OpenAICompatBackend
from vit_ai_hub.config import backend_overrides, load_yaml_config


def build_backends() -> dict[str, OpenAICompatBackend]:
    cfg = load_yaml_config().get("backends", {})
    overrides = backend_overrides()
    backends: dict[str, Any] = {}
    for name, raw in cfg.items():
        if not raw.get("enabled", True):
            continue
        over = overrides.get(name, {})
        base_url = over.get("base_url") or raw.get("base_url") or ""
        if name == "cursor" and not base_url:
            continue
        if name == "openrouter" and not over.get("api_key"):
            # still register for pinned catalog; calls fail until key set
            pass
        single = OpenAICompatBackend(
            name=name,
            base_url=base_url,
            api_key=over.get("api_key", ""),
            local=bool(raw.get("local")),
            label=str(raw.get("label") or name),
        )
        # Multi-abo pool for cloud/subscription backends
        if name in {"bridge", "cursor", "openrouter", "deepseek", "grok", "omniroute"}:
            try:
                from vit_ai_hub.pool.backend import wrap_pooled

                backends[name] = wrap_pooled(
                    name,
                    single,
                    local=bool(raw.get("local")),
                    label=str(raw.get("label") or name),
                )
                continue
            except Exception:
                pass
        backends[name] = single
    return backends


def pinned_models_for(backend_name: str, label: str | None = None) -> list[dict[str, Any]]:
    cfg = load_yaml_config().get("backends", {}).get(backend_name, {})
    out = []
    for item in cfg.get("pinned_models", []):
        out.append(
            {
                "id": item["id"],
                "object": "model",
                "owned_by": backend_name,
                "backend": backend_name,
                "local": False,
                "label": label or cfg.get("label") or backend_name,
                "name": item.get("name") or item["id"],
                "pinned": True,
            }
        )
    return out


def pinned_openrouter_models() -> list[dict[str, Any]]:
    return pinned_models_for("openrouter", "OpenRouter")


def pinned_deepseek_models() -> list[dict[str, Any]]:
    return pinned_models_for("deepseek", "DeepSeek")


def pinned_grok_models() -> list[dict[str, Any]]:
    return pinned_models_for("grok", "Grok (xAI)")
