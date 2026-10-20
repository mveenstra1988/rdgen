"""Hardware-profielen — M5 Max 128GB / 2TB (research Oct 2026)."""

from __future__ import annotations

from typing import Any

# Bronnen: localmodel.run, sungsoo M5 Max LM Studio, promptquorum M5 bandwidth,
# oMLX Qwen3.6-35B-A3B benchmark, aiproductivity M5 Max guide.
M5_MAX_128 = {
    "id": "m5-max-128",
    "name": "MacBook Pro M5 Max · 128 GB · 2 TB",
    "chip": "M5 Max",
    "unified_memory_gb": 128,
    "usable_model_gb_approx": 96,
    "memory_bandwidth_gbs": 614,
    "gpu_cores": 40,
    "storage_tb": 2,
    "runtime": {
        "primary": "LM Studio (MLX)",
        "secondary": "Ollama (API / warm pool)",
        "avoid": "GGUF op Mac als MLX-variant bestaat — MLX ~25–50% sneller, minder RAM",
        "macos_note": "MLX Neural Accelerators: recente stabiele macOS; LM Studio runtime ⌘⇧R updaten",
    },
    "models": {
        "daily": {
            "id_hint": "Qwen3.6-35B-A3B",
            "format": "MLX 4-bit of 6-bit",
            "why": "MoE ~3B active — snel (~100+ tok/s class op M5 Max) + sterk genoeg voor chat/code",
            "ram_gb": "~20–30",
            "vit_slot": "vit/local-light",
        },
        "quality_local": {
            "id_hint": "Qwen3.8-27B",
            "format": "MLX 6-bit (of 8-bit als je kwaliteit wilt)",
            "why": "Dichte 27B voor scherpe antwoorden zonder 70B-latency",
            "ram_gb": "~23–28",
            "vit_slot": "vit/local-heavy",
        },
        "heavy_moe": {
            "id_hint": "gpt-oss-120b of Nemotron 3 Super 120B-A12B",
            "format": "MLX/Q4 — on-demand laden",
            "why": "Past in ~96 GB usable; unload na gebruik (heavy_unload)",
            "ram_gb": "~60–80",
            "vit_slot": "vit/local-heavy",
        },
        "coder_alt": {
            "id_hint": "Qwen3-Coder 30B-A3B",
            "format": "MLX 4/6-bit",
            "why": "Code-gericht MoE naast daily chat-model",
            "ram_gb": "~20",
        },
    },
    "lm_studio": {
        "backend": "MLX (niet GGUF)",
        "context_start": 16384,
        "context_long": 32768,
        "gpu_memory": "auto",
        "concurrent": "één model, één request voor piek-snelheid",
        "thinking": "uit voor snelle extractie; medium voor complexe analyse",
        "temperature_chat": 0.7,
        "temperature_code": 0.3,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "plugged_in": True,
        "close_chrome_tabs": "bij heavy: minder browser/Docker = meer unified memory",
    },
    "ollama": {
        "flash_attention": "OLLAMA_FLASH_ATTENTION=1",
        "kv_cache": "OLLAMA_KV_CACHE_TYPE=q8_0",
        "num_ctx_default": 4096,
        "num_ctx_long": 16384,
        "quant": "Q4_K_M voor snelheid; Q5/Q8 alleen als kwaliteit zichtbaar beter is",
        "check": "ollama ps → PROCESSOR 100% GPU",
    },
    "hub": {
        "default_model": "vit/auto",
        "max_quality_model": "vit/max",
        "tradeoff": "quality",
        "critic": True,
        "critic_rounds": 2,
        "second_opinion": True,
        "reserve_apps_gb": 48,
        "light_env": "VIT_LOCAL_LIGHT_MODEL=<exacte LM Studio model-id daily>",
        "heavy_env": "VIT_LOCAL_HEAVY_MODEL=<exacte LM Studio model-id quality/heavy>",
    },
    "disk_2tb": {
        "models_budget_gb": 400,
        "keep": "2–4 MLX-modellen (daily + quality + 1 heavy + optioneel coder)",
        "purge": "oude GGUF-duplicaten van dezelfde Qwen-lijn",
        "path_hint": "~/Library/Application Support/LM Studio / ~/.cache/lm-studio / ~/.ollama",
    },
    "checklist": [
        "LM Studio → MLX-runtime up-to-date (⌘⇧R)",
        "Daily: Qwen3.6-35B-A3B MLX 4/6-bit, context 16k",
        "Quality lokaal: Qwen3.8-27B MLX 6-bit",
        "Heavy on-demand: 120B-class MoE Q4; unload na gebruik",
        "Hub: vit/auto of vit/max; tradeoff=Beste kwaliteit; critic aan",
        "Zet VIT_LOCAL_LIGHT_MODEL / VIT_LOCAL_HEAVY_MODEL op exacte model-ids",
        "Mac aangesloten op stroom bij zware runs; Activity Monitor → memory pressure",
    ],
}


def list_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": M5_MAX_128["id"],
            "name": M5_MAX_128["name"],
            "chip": M5_MAX_128["chip"],
            "unified_memory_gb": M5_MAX_128["unified_memory_gb"],
        }
    ]


def get_profile(profile_id: str = "m5-max-128") -> dict[str, Any]:
    if profile_id in {"m5-max-128", "m5max128", "default", ""}:
        return dict(M5_MAX_128)
    return dict(M5_MAX_128)


def hub_overrides_for_profile(profile_id: str = "m5-max-128") -> dict[str, Any]:
    """Fragment om in default.yaml / env te mergen."""
    p = get_profile(profile_id)
    return {
        "memory_budget": {
            "reserve_apps_gb": p["hub"]["reserve_apps_gb"],
            "light_model_hint": f"{p['models']['daily']['id_hint']} MLX 4/6-bit (~{p['models']['daily']['ram_gb']}GB)",
            "heavy_model_hint": f"{p['models']['heavy_moe']['id_hint']} on-demand",
            "heavy_unload": True,
            "profile": p["id"],
        },
        "orchestrator": {
            "tradeoff": "quality",
            "critic": True,
            "critic_rounds": 2,
            "second_opinion": True,
            "max_fallbacks": 4,
        },
    }
