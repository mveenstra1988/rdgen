"""Checkpoints /rewind — Claude Code / Cursor parity (git stash + hub metadata)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

CP_DIR = ROOT / "data" / "checkpoints"


def _git(workspace: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(Path(workspace).expanduser()),
        capture_output=True,
        text=True,
        timeout=45,
    )


def create_checkpoint(*, workspace: str | None, note: str = "") -> dict[str, Any]:
    CP_DIR.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y%m%d-%H%M%S")
    meta: dict[str, Any] = {
        "name": name,
        "note": note or "checkpoint",
        "created": time.time(),
        "workspace": workspace,
        "git": None,
    }
    if workspace and Path(workspace).expanduser().is_dir():
        # stash including untracked
        r = _git(workspace, "stash", "push", "-u", "-m", f"vit-hub-{name}")
        meta["git"] = {
            "stash_ok": r.returncode == 0,
            "stdout": (r.stdout or "")[:500],
            "stderr": (r.stderr or "")[:500],
        }
        # also record HEAD
        h = _git(workspace, "rev-parse", "HEAD")
        if h.returncode == 0:
            meta["git"]["head"] = (h.stdout or "").strip()
    path = CP_DIR / f"{name}.json"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    msg = f"Checkpoint `{name}` opgeslagen."
    if meta.get("git") and meta["git"].get("stash_ok"):
        msg += " Git-wijzigingen in stash (vit-hub-…)."
    elif workspace:
        msg += " (geen git-stash — clean of geen repo)"
    return {"ok": True, "message": msg, "checkpoint": meta, "path": str(path)}


def list_checkpoints(limit: int = 20) -> dict[str, Any]:
    if not CP_DIR.is_dir():
        return {"ok": True, "items": []}
    items = sorted(CP_DIR.glob("*.json"), reverse=True)[:limit]
    out = []
    for p in items:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            out.append({"name": p.stem, "path": str(p)})
    return {"ok": True, "items": out}


def rewind_checkpoint(*, workspace: str | None, name: str = "") -> dict[str, Any]:
    items = list_checkpoints(limit=50).get("items") or []
    if not items:
        return {"ok": False, "message": "Geen checkpoints. Gebruik eerst `/checkpoint`."}
    target = None
    if name.strip():
        for it in items:
            if it.get("name") == name.strip() or name.strip() in str(it.get("name")):
                target = it
                break
    else:
        target = items[0]
    if not target:
        return {"ok": False, "message": f"Checkpoint niet gevonden: {name}"}
    ws = workspace or target.get("workspace")
    git = target.get("git") or {}
    restored = False
    detail = ""
    if ws and git.get("stash_ok"):
        # pop matching stash
        ls = _git(ws, "stash", "list")
        stash_line = None
        tag = f"vit-hub-{target['name']}"
        for line in (ls.stdout or "").splitlines():
            if tag in line:
                stash_line = line.split(":", 1)[0].strip()
                break
        if stash_line:
            r = _git(ws, "stash", "pop", stash_line)
            restored = r.returncode == 0
            detail = (r.stdout or r.stderr or "")[:800]
        else:
            # try stash@{0}
            r = _git(ws, "stash", "pop")
            restored = r.returncode == 0
            detail = (r.stdout or r.stderr or "")[:800]
    return {
        "ok": True,
        "message": (
            f"Rewind naar `{target.get('name')}`. "
            + ("Git stash teruggezet." if restored else "Geen stash om terug te zetten — chat-context handmatig.")
            + (f"\n{detail}" if detail else "")
        ),
        "checkpoint": target,
        "action": "rewind_hint",
    }
