from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from vit_ai_hub.importing import chatgpt, claude, cursor
from vit_ai_hub.importing.store import log_import, stats


def detect_source(path: Path) -> str:
    path = Path(path)
    name = path.name.lower()
    if "claude" in name:
        return "claude"
    if "chatgpt" in name or "openai" in name:
        return "chatgpt"
    # peek zip/json
    try:
        if path.suffix.lower() == ".json":
            text = path.read_text(encoding="utf-8", errors="replace")[:2000].lower()
            if "chat_messages" in text or '"sender": "human"' in text:
                return "claude"
            if "mapping" in text and "current_node" in text:
                return "chatgpt"
        if path.suffix.lower() == ".zip":
            import zipfile

            with zipfile.ZipFile(path) as zf:
                names = {Path(n).name.lower() for n in zf.namelist()}
                if "memories.json" in names or "projects.json" in names:
                    return "claude"
                if any(n == "conversations.json" or n.startswith("conversations-") for n in names):
                    # both have conversations.json; prefer claude if projects present
                    if "projects.json" in names:
                        return "claude"
                    return "chatgpt"
    except Exception:
        pass
    return "chatgpt"


def import_file(path: Path, source: str | None = None) -> dict[str, Any]:
    path = Path(path)
    src = source or detect_source(path)
    if src == "claude":
        return claude.import_from_path(path)
    if src == "chatgpt":
        return chatgpt.import_from_path(path)
    if src == "cursor":
        return cursor.import_local([path] if path.is_dir() else None)
    raise ValueError(f"Onbekende bron: {src}")


def find_export_zips(download_dirs: list[Path] | None = None) -> dict[str, list[Path]]:
    home = Path.home()
    dirs = download_dirs or [
        home / "Downloads",
        home / "Desktop",
        home / "Download",
    ]
    found = {"chatgpt": [], "claude": []}
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[:80]:
            name = path.name.lower()
            try:
                src = detect_source(path)
            except Exception:
                continue
            if "claude" in name or src == "claude":
                found["claude"].append(path)
            elif "chatgpt" in name or "openai" in name or src == "chatgpt":
                found["chatgpt"].append(path)
    # dedupe keep newest first
    for k in found:
        seen = set()
        uniq = []
        for p in found[k]:
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)
        found[k] = uniq[:5]
    return found


def import_all_one_click() -> dict[str, Any]:
    """Cursor + lokale Mac-apps + nieuwste ChatGPT/Claude export-zips."""
    started = time.time()
    results: dict[str, Any] = {
        "cursor": None,
        "local_mac": None,
        "chatgpt": [],
        "claude": [],
        "errors": [],
    }

    try:
        results["cursor"] = cursor.import_local()
    except Exception as exc:
        results["errors"].append({"source": "cursor", "error": str(exc)})

    try:
        from vit_ai_hub.importing.local_mac import harvest_all_local

        results["local_mac"] = harvest_all_local()
    except Exception as exc:
        results["errors"].append({"source": "local_mac", "error": str(exc)})

    found = find_export_zips()
    for path in found.get("chatgpt") or []:
        try:
            results["chatgpt"].append(chatgpt.import_from_path(path))
            break  # nieuwste is genoeg voor one-click
        except Exception as exc:
            results["errors"].append({"source": "chatgpt", "file": str(path), "error": str(exc)})
    for path in found.get("claude") or []:
        try:
            results["claude"].append(claude.import_from_path(path))
            break
        except Exception as exc:
            results["errors"].append({"source": "claude", "file": str(path), "error": str(exc)})

    try:
        from vit_ai_hub.importing.index_fts import rebuild_index

        results["fts"] = rebuild_index()
    except Exception as exc:
        results["errors"].append({"source": "fts", "error": str(exc)})

    results["knowledge"] = stats()
    results["elapsed_sec"] = round(time.time() - started, 2)
    results["hints"] = []
    det = (results.get("local_mac") or {}).get("detection") or {}
    if det.get("chatgpt_encrypted_conversations") and not results["chatgpt"]:
        results["hints"].append(
            f"ChatGPT-app gevonden ({det['chatgpt_encrypted_conversations']} encrypted chats). "
            "Die zijn niet plain-text leesbaar. Gebruik 'Start export vanuit apps' of zet de officiële zip in Downloads."
        )
    elif not results["chatgpt"]:
        results["hints"].append(
            "Geen volledige ChatGPT-history. Start export vanuit apps, of upload de export-zip."
        )
    if not results["claude"] and not (
        (results.get("local_mac") or {}).get("claude_code", {}).get("conversations", {}).get("written")
    ):
        results["hints"].append(
            "Geen Claude.ai export-zip. Lokale Claude Code/Cowork is wél meegenomen als die er is. "
            "Voor claude.ai-webchats: Privacy → Export, of knop 'Start export vanuit apps'."
        )
    if not (results.get("cursor") or {}).get("files_scanned"):
        results["hints"].append("Geen Cursor-mappen gevonden op deze machine (normaal in deze cloud-VM).")
    log_import(
        {
            "source": "all",
            "summary": {
                k: results[k]
                for k in ("cursor", "local_mac", "chatgpt", "claude", "knowledge")
            },
        }
    )
    return results
