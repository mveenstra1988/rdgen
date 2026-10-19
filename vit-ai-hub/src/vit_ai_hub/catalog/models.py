from __future__ import annotations

import asyncio
from typing import Any

from vit_ai_hub.backends import (
    build_backends,
    pinned_deepseek_models,
    pinned_grok_models,
    pinned_openrouter_models,
)
from vit_ai_hub.config import get_settings, load_yaml_config


async def collect_models() -> list[dict[str, Any]]:
    backends = build_backends()
    virtual = []
    for item in load_yaml_config().get("virtual_models", []):
        virtual.append(
            {
                "id": item["id"],
                "object": "model",
                "owned_by": "vit",
                "backend": "vit",
                "local": item["id"].startswith("vit/local"),
                "label": "VIT",
                "name": item.get("name") or item["id"],
                "virtual": True,
            }
        )

    tasks = [backend.list_models() for backend in backends.values() if backend.base_url]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: dict[str, dict[str, Any]] = {m["id"]: m for m in virtual}
    for pinned in pinned_openrouter_models() + pinned_deepseek_models() + pinned_grok_models():
        merged[pinned["id"]] = pinned
    for result in results:
        if isinstance(result, Exception):
            continue
        for model in result:
            # prefix with backend if collision across providers
            key = model["id"]
            if key in merged and merged[key].get("backend") != model.get("backend"):
                key = f"{model['backend']}:{model['id']}"
                model = {**model, "id": key, "upstream_id": model["id"]}
            merged[key] = model

    # ensure light/heavy aliases resolve to something listed
    settings = get_settings()
    if settings.vit_local_light_model:
        merged.setdefault(
            settings.vit_local_light_model,
            {
                "id": settings.vit_local_light_model,
                "object": "model",
                "owned_by": "lmstudio",
                "backend": "lmstudio",
                "local": True,
                "label": "Lokaal",
                "name": settings.vit_local_light_model,
            },
        )
    return sorted(merged.values(), key=lambda m: (not m.get("virtual"), m.get("label", ""), m["id"]))