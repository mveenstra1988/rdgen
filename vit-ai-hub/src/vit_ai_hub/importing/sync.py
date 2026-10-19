"""Live sync: periodiek Cursor/Claude/ChatGPT lokale bronnen + FTS rebuild."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

STATE_PATH = ROOT / "data" / "sync_state.json"
_thread: threading.Thread | None = None
_stop = threading.Event()
_status: dict[str, Any] = {"running": False, "last_run": None, "last_result": None}


def _load_state() -> dict[str, Any]:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_once(*, include_ax: bool = False) -> dict[str, Any]:
    from vit_ai_hub.importing import cursor
    from vit_ai_hub.importing.index_fts import rebuild_index
    from vit_ai_hub.importing.local_mac import harvest_chatgpt_cache, harvest_claude_code, harvest_claude_desktop
    from vit_ai_hub.importing.store import stats

    result: dict[str, Any] = {"ts": time.time()}
    try:
        result["cursor"] = cursor.import_local(max_files=1500)
    except Exception as exc:
        result["cursor_error"] = str(exc)
    try:
        result["claude_code"] = harvest_claude_code()
        result["claude_desktop"] = harvest_claude_desktop()
        result["chatgpt_cache"] = harvest_chatgpt_cache()
    except Exception as exc:
        result["local_error"] = str(exc)
    if include_ax:
        try:
            from vit_ai_hub.importing.chatgpt_live import harvest_via_accessibility
            from vit_ai_hub.importing.claude_live import harvest_via_accessibility as claude_ax

            result["chatgpt_ax"] = harvest_via_accessibility(max_chats=8)
            result["claude_ax"] = claude_ax(max_steps=8)
        except Exception as exc:
            result["ax_error"] = str(exc)
    try:
        result["fts"] = rebuild_index()
    except Exception as exc:
        result["fts_error"] = str(exc)
    result["knowledge"] = stats()
    state = _load_state()
    state["last_sync"] = result["ts"]
    _save_state(state)
    _status["last_run"] = result["ts"]
    _status["last_result"] = {
        "knowledge": result.get("knowledge"),
        "fts": result.get("fts"),
        "errors": [k for k in result if k.endswith("_error")],
    }
    return result


def _loop(interval_sec: int, include_ax: bool) -> None:
    _status["running"] = True
    while not _stop.is_set():
        try:
            sync_once(include_ax=include_ax)
        except Exception as exc:
            _status["last_result"] = {"error": str(exc)}
        _stop.wait(interval_sec)
    _status["running"] = False


def start_sync(*, interval_sec: int = 300, include_ax: bool = False) -> dict[str, Any]:
    global _thread
    if _status.get("running") and _thread and _thread.is_alive():
        return {"ok": True, "already_running": True, "status": get_sync_status()}
    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        kwargs={"interval_sec": max(60, interval_sec), "include_ax": include_ax},
        daemon=True,
        name="vit-ai-sync",
    )
    _thread.start()
    # first kick immediately in background already via loop
    return {"ok": True, "started": True, "interval_sec": max(60, interval_sec)}


def stop_sync() -> dict[str, Any]:
    _stop.set()
    return {"ok": True, "stopping": True}


def get_sync_status() -> dict[str, Any]:
    return {
        **_status,
        "state_file": str(STATE_PATH),
        "state": _load_state(),
    }
