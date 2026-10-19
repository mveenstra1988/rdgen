from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "default.yaml"
SECRET_CANDIDATES = [
    Path.home() / ".config/vit/geheimen/ai-gateway.env",
    ROOT / ".env",
]


def _load_env_file() -> None:
    for path in SECRET_CANDIDATES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            os.environ.setdefault(key, value)
        break


_load_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    vit_gateway_host: str = "127.0.0.1"
    vit_gateway_port: int = 8787
    vit_gateway_token: str = ""

    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    bridge_base_url: str = "http://127.0.0.1:8317/v1"
    bridge_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    omniroute_base_url: str = "http://127.0.0.1:20128/v1"
    omniroute_api_key: str = ""
    cursor_base_url: str = ""
    cursor_api_key: str = ""
    xai_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"

    vit_pii_mode: str = "fail_closed"
    vit_pii_cloud_action: str = "block"
    vit_audit_log: str = str(ROOT / "data" / "audit.jsonl")
    vit_default_model: str = "vit/auto"
    vit_local_light_model: str = ""
    vit_local_heavy_model: str = ""
    vit_config_path: str = str(DEFAULT_CONFIG)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_yaml_config() -> dict[str, Any]:
    path = Path(get_settings().vit_config_path)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def backend_overrides() -> dict[str, dict[str, Any]]:
    s = get_settings()
    return {
        "lmstudio": {"base_url": s.lmstudio_base_url.rstrip("/"), "api_key": "lmstudio"},
        "ollama": {"base_url": s.ollama_base_url.rstrip("/"), "api_key": "ollama"},
        "bridge": {"base_url": s.bridge_base_url.rstrip("/"), "api_key": s.bridge_api_key or "bridge"},
        "openrouter": {
            "base_url": s.openrouter_base_url.rstrip("/"),
            "api_key": s.openrouter_api_key,
        },
        "omniroute": {
            "base_url": s.omniroute_base_url.rstrip("/"),
            "api_key": s.omniroute_api_key or "omniroute",
        },
        "cursor": {
            "base_url": (s.cursor_base_url or s.bridge_base_url).rstrip("/"),
            "api_key": s.cursor_api_key or s.bridge_api_key or "cursor",
        },
        "grok": {
            "base_url": s.grok_base_url.rstrip("/"),
            "api_key": s.xai_api_key,
        },
    }