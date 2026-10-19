from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vit_ai_hub.backends import build_backends
from vit_ai_hub.backends.openai_compat import OpenAICompatBackend
from vit_ai_hub.config import get_settings, load_yaml_config


@dataclass
class RouteDecision:
    backend: OpenAICompatBackend
    model: str
    local: bool
    virtual: str | None = None


class ModelRouter:
    def __init__(self) -> None:
        self.backends = build_backends()
        self.cfg = load_yaml_config()

    def refresh(self) -> None:
        self.backends = build_backends()

    def _first_local(self) -> OpenAICompatBackend | None:
        for name in ("lmstudio", "ollama"):
            backend = self.backends.get(name)
            if backend and backend.base_url:
                return backend
        return None

    def _pick_cloud_for_model(self, model: str) -> OpenAICompatBackend | None:
        lower = model.lower()
        if model.startswith("openrouter:") or "/" in model and not model.startswith("vit/"):
            # OpenRouter style provider/model, or explicit
            if model.startswith("openrouter:"):
                return self.backends.get("openrouter")
            if self.backends.get("openrouter") and self.backends["openrouter"].api_key:
                # prefer openrouter for provider/model slugs
                if any(
                    lower.startswith(p)
                    for p in (
                        "stealth/",
                        "z-ai/",
                        "anthropic/",
                        "openai/",
                        "google/",
                        "meta-llama/",
                        "x-ai/",
                        "deepseek/",
                        "qwen/",
                        "mistralai/",
                    )
                ):
                    return self.backends.get("openrouter")
        if lower.startswith("omniroute:"):
            return self.backends.get("omniroute")
        if lower.startswith("deepseek"):
            ds = self.backends.get("deepseek")
            if ds and ds.api_key:
                return ds
            if self.backends.get("openrouter") and self.backends["openrouter"].api_key:
                return self.backends.get("openrouter")
            return ds
        if lower.startswith("grok") or lower.startswith("xai/") or lower.startswith("x-ai/"):
            if self.backends.get("grok") and self.backends["grok"].api_key:
                return self.backends.get("grok")
            if self.backends.get("openrouter") and self.backends["openrouter"].api_key:
                return self.backends.get("openrouter")
            return self.backends.get("grok")
        if lower.startswith("cursor:") or "composer" in lower or lower.startswith("cursor-"):
            return self.backends.get("cursor") or self.backends.get("bridge")
        bridge = self.backends.get("bridge")
        hints = (
            self.cfg.get("backends", {}).get("bridge", {}).get("prefix_hints")
            or ["claude", "gpt-", "o1", "o3", "o4", "chatgpt"]
        )
        if bridge and any(lower.startswith(h) or f":{h}" in lower for h in hints):
            return bridge
        if self.backends.get("omniroute"):
            # OmniRoute often knows many IDs
            return self.backends.get("omniroute")
        if self.backends.get("openrouter") and self.backends["openrouter"].api_key:
            return self.backends.get("openrouter")
        return bridge

    def resolve(self, model: str | None, *, force_local: bool = False) -> RouteDecision:
        settings = get_settings()
        requested = (model or settings.vit_default_model or "vit/auto").strip()
        local = self._first_local()

        if requested in {"vit/auto", "auto"}:
            if force_local:
                if not local:
                    raise RuntimeError("Geen lokale backend beschikbaar voor fail-closed route")
                target = settings.vit_local_light_model or "local-model"
                return RouteDecision(backend=local, model=target, local=True, virtual="vit/auto")
            # default: local light if configured/available, else bridge/openrouter
            if local:
                target = settings.vit_local_light_model or "local-model"
                return RouteDecision(backend=local, model=target, local=True, virtual="vit/auto")
            cloud = self.backends.get("bridge") or self.backends.get("openrouter")
            if not cloud:
                raise RuntimeError("Geen backend voor vit/auto")
            return RouteDecision(backend=cloud, model="claude-sonnet-4", local=False, virtual="vit/auto")

        if requested == "vit/local-light":
            if not local:
                raise RuntimeError("Geen lokale backend")
            target = settings.vit_local_light_model or "local-model"
            return RouteDecision(backend=local, model=target, local=True, virtual=requested)

        if requested == "vit/local-heavy":
            if not local:
                raise RuntimeError("Geen lokale backend")
            target = settings.vit_local_heavy_model or settings.vit_local_light_model or "local-model"
            return RouteDecision(backend=local, model=target, local=True, virtual=requested)

        # strip backend prefix if present
        upstream = requested
        chosen: OpenAICompatBackend | None = None
        if ":" in requested and requested.split(":", 1)[0] in self.backends:
            bname, upstream = requested.split(":", 1)
            chosen = self.backends.get(bname)

        if force_local:
            if not local:
                raise RuntimeError("Geen lokale backend voor PII fail-closed")
            return RouteDecision(backend=local, model=upstream, local=True)

        if chosen is None:
            # local model ids often plain names from LM Studio
            if local and not any(c in upstream for c in "/"):
                # prefer local for unqualified names when lmstudio/ollama likely
                chosen = local
                # but if looks like cloud model, override
                cloud = self._pick_cloud_for_model(upstream)
                if cloud and any(
                    upstream.lower().startswith(h)
                    for h in [
                        "claude",
                        "gpt-",
                        "o1",
                        "o3",
                        "o4",
                        "stealth/",
                        "z-ai/",
                        "deepseek",
                        "meta-llama/",
                        "qwen/",
                        "mistralai/",
                        "google/",
                    ]
                ):
                    chosen = cloud
            else:
                chosen = self._pick_cloud_for_model(upstream) or local

        if chosen is None:
            raise RuntimeError(f"Geen backend voor model {requested}")

        # Native DeepSeek API expects bare ids (deepseek-chat), not openrouter slugs
        if chosen.name == "deepseek" and "/" in upstream:
            upstream = upstream.rsplit("/", 1)[-1]
            if upstream.endswith(":free"):
                upstream = upstream[: -len(":free")]

        return RouteDecision(backend=chosen, model=upstream, local=chosen.local)


def extract_text_from_response(data: dict[str, Any]) -> str:
    try:
        return data["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""