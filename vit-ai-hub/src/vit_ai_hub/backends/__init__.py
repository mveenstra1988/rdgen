from __future__ import annotations

from typing import Any

from vit_ai_hub.backends.openai_compat import OpenAICompatBackend
from vit_ai_hub.config import backend_overrides, load_yaml_config


def build_backends() -> dict[str, OpenAICompatBackend]:
    cfg = load_yaml_config().get("backends", {})
    overrides = backend_overrides()
    backends: dict[str, OpenAICompatBackend] = {}
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
        backends[name] = OpenAICompatBackend(
            name=name,
            base_url=base_url,
            api_key=over.get("api_key", ""),
            local=bool(raw.get("local")),
            label=str(raw.get("label") or name),
        )
    return backends


def pinned_openrouter_models() -> list[dict[str, Any]]:
    cfg = load_yaml_config().get("backends", {}).get("openrouter", {})
    out = []
    for item in cfg.get("pinned_models", []):
        out.append(
            {
                "id": item["id"],
                "object": "model",
                "owned_by": "openrouter",
                "backend": "openrouter",
                "local": False,
                "label": "OpenRouter",
                "name": item.get("name") or item["id"],
                "pinned": True,
            }
        )
    return out