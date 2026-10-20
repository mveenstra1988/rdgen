"""Lichte route-telemetrie (lokaal jsonl) voor later tunen van de router."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT, load_yaml_config

LOG_PATH = ROOT / "data" / "orchestrator.jsonl"


def log_route(event: dict[str, Any]) -> None:
    cfg = load_yaml_config().get("orchestrator") or {}
    if cfg.get("telemetry", True) is False:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), **event}
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
