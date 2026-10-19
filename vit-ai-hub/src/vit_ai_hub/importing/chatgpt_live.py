"""ChatGPT op dezelfde Mac uitlezen zoals jij hem ziet.

Pad A: Accessibility (AX) terwijl de ChatGPT-app open is en chats toont.
Pad B: Keychain-sleutel + decrypt van *.data (werkt alleen als macOS de key
       nog als leesbare keychain-item blootgeeft; v3 is vaak app-held).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


def _is_darwin() -> bool:
    return os.uname().sysname == "Darwin"


def chatgpt_running() -> bool:
    if not _is_darwin():
        return False
    r = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to (name of processes) contains "ChatGPT"'],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip().lower() == "true"


def probe_keychain() -> dict[str, Any]:
    """Probeer bekende Keychain labels (vraagt macOS-toestemming aan de user)."""
    if not _is_darwin():
        return {"ok": False, "error": "alleen macOS", "keys_found": []}
    labels = [
        "com.openai.chat.conversations_v2_cache",
        "com.openai.chat.conversations_v3_cache",
        "conversations_v2_cache",
        "conversations_v3_cache",
        "com.openai.chat",
    ]
    found = []
    for label in labels:
        for flag in ("-s", "-l"):
            r = subprocess.run(
                ["security", "find-generic-password", flag, label, "-w"],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                found.append({"label": label, "via": flag, "bytes": len(r.stdout.strip())})
                break
    return {"ok": bool(found), "keys_found": found}


def _try_decrypt_blob(key: bytes, blob: bytes) -> bytes | None:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
    except ImportError:
        return None

    candidates: list[bytes] = []
    # AES-GCM: nonce 12 voorop
    if len(blob) > 12 + 16:
        try:
            candidates.append(AESGCM(key[:32] if len(key) >= 32 else key.ljust(32, b"\0")).decrypt(blob[:12], blob[12:], None))
        except Exception:
            pass
        try:
            k = key[:16] if len(key) >= 16 else key.ljust(16, b"\0")
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            # skip naive CBC unless looks promising
            _ = (Cipher, algorithms, modes, k)
        except Exception:
            pass
    if len(key) >= 32 and len(blob) > 12 + 16:
        try:
            candidates.append(ChaCha20Poly1305(key[:32]).decrypt(blob[:12], blob[12:], None))
        except Exception:
            pass
    for plain in candidates:
        if plain[:1] in (b"{", b"[") or plain[:2] == b"\x1f\x8b" or b"mapping" in plain[:200]:
            return plain
    return None


def harvest_via_keychain(max_files: int = 400) -> dict[str, Any]:
    """Best-effort decrypt van Application Support conversations-*.data."""
    from vit_ai_hub.importing.store import save_conversations

    if not _is_darwin():
        return {"source": "chatgpt_keychain", "ok": False, "error": "alleen macOS"}

    probe = probe_keychain()
    if not probe.get("keys_found"):
        return {
            "source": "chatgpt_keychain",
            "ok": False,
            "probe": probe,
            "error": "Geen leesbare Keychain-key. Gebruik Accessibility-import terwijl ChatGPT open staat.",
            "conversations": {"written": 0, "skipped": 0},
        }

    # haal eerste key-bytes
    label = probe["keys_found"][0]["label"]
    flag = probe["keys_found"][0]["via"]
    r = subprocess.run(
        ["security", "find-generic-password", flag, label, "-w"],
        capture_output=True,
        text=True,
    )
    secret = r.stdout.strip()
    key = secret.encode("utf-8")
    # hex?
    if re.fullmatch(r"[0-9a-fA-F]+", secret) and len(secret) % 2 == 0:
        try:
            key = bytes.fromhex(secret)
        except ValueError:
            pass

    support = Path.home() / "Library/Application Support/com.openai.chat"
    conversations = []
    decrypted = 0
    failed = 0
    for path in list(support.glob("conversations-*/*.data"))[:max_files]:
        blob = path.read_bytes()
        plain = _try_decrypt_blob(key, blob)
        if not plain:
            failed += 1
            continue
        if plain[:2] == b"\x1f\x8b":
            import gzip

            try:
                plain = gzip.decompress(plain)
            except Exception:
                failed += 1
                continue
        try:
            data = json.loads(plain.decode("utf-8"))
        except Exception:
            failed += 1
            continue
        from vit_ai_hub.importing.chatgpt import parse_conversations_payload

        if isinstance(data, list):
            conversations.extend(parse_conversations_payload(data))
        elif isinstance(data, dict):
            conversations.extend(parse_conversations_payload([data]))
        decrypted += 1

    stats = save_conversations(conversations, source="chatgpt_keychain")
    return {
        "source": "chatgpt_keychain",
        "ok": decrypted > 0,
        "probe": probe,
        "decrypted_files": decrypted,
        "failed_files": failed,
        "conversations": stats,
    }


_AX_DUMP_SCRIPT = r'''
tell application "ChatGPT" to activate
delay 0.6
tell application "System Events"
  if not (exists process "ChatGPT") then
    return "ERROR:ChatGPT niet gestart"
  end if
  tell process "ChatGPT"
    set frontmost to true
    delay 0.4
    set outText to ""
    try
      set uiElems to entire contents of window 1
      repeat with e in uiElems
        try
          set r to role of e
          set v to value of e
          if v is missing value then set v to name of e
          if v is not missing value and (r is "AXStaticText" or r is "AXTextField" or r is "AXTextArea" or r is "AXButton" or r is "AXHeading") then
            set outText to outText & r & "|" & (v as text) & linefeed
          end if
        end try
      end repeat
    on error errMsg
      return "ERROR:" & errMsg
    end try
    return outText
  end tell
end tell
'''


_AX_SIDEBAR_CLICK_SCRIPT = r'''
on run argv
  set idx to item 1 of argv as integer
  tell application "ChatGPT" to activate
  delay 0.4
  tell application "System Events"
    tell process "ChatGPT"
      set frontmost to true
      delay 0.3
      try
        set rows to buttons of window 1 whose name is not ""
        if (count of rows) < idx then
          set rows to UI elements of window 1
        end if
        -- fallback: click via keyboard navigation is handled in Python
        return "ok"
      on error errMsg
        return "ERROR:" & errMsg
      end try
    end tell
  end tell
end run
'''


def dump_ax_window() -> dict[str, Any]:
    if not _is_darwin():
        return {"ok": False, "error": "alleen macOS"}
    if not chatgpt_running():
        # try launch
        subprocess.run(["open", "-a", "ChatGPT"], check=False)
        time.sleep(2)
    r = subprocess.run(["osascript", "-e", _AX_DUMP_SCRIPT], capture_output=True, text=True)
    text = r.stdout or ""
    if text.startswith("ERROR:") or r.returncode != 0:
        return {
            "ok": False,
            "error": text.strip() or (r.stderr or "AX dump mislukt"),
            "hint": "Geef Terminal/VIT AI Hub toestemming: Systeeminstellingen → Privacy → Toegankelijkheid.",
        }
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return {"ok": True, "lines": lines, "count": len(lines)}


def _lines_to_conversation(lines: list[str], title: str) -> dict[str, Any] | None:
    messages = []
    buf_role = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, buf_role
        if buf_role and buf:
            messages.append({"role": buf_role, "content": "\n".join(buf).strip()})
        buf = []
        buf_role = None

    for ln in lines:
        if "|" not in ln:
            continue
        role_ax, _, val = ln.partition("|")
        val = val.strip()
        if not val or len(val) < 2:
            continue
        low = val.lower()
        # heuristiek: knoppen in sidebar overslaan als te kort
        if role_ax == "AXButton" and len(val) < 80:
            continue
        if any(x in low for x in ("new chat", "nieuwe chat", "settings", "instellingen", "search")):
            continue
        # ChatGPT UI heeft vaak geen duidelijke role; groepeer als assistant-blokken
        if buf_role is None:
            buf_role = "assistant"
        buf.append(val)
    flush()
    # split long assistant wall into rough user/assistant by question marks patterns
    if not messages:
        return None
    # If only one giant assistant message, keep it
    return {
        "native_id": f"ax-{abs(hash(title + str(len(lines))) % 10**12)}",
        "title": title or "ChatGPT AX",
        "messages": messages,
        "meta": {"via": "accessibility"},
    }


def harvest_via_accessibility(*, max_chats: int = 40) -> dict[str, Any]:
    """Lees wat ChatGPT op het scherm toont (zelfde wat jij leest)."""
    from vit_ai_hub.importing.store import save_conversations, save_memories

    if not _is_darwin():
        return {"source": "chatgpt_ax", "ok": False, "error": "alleen macOS"}

    dump = dump_ax_window()
    if not dump.get("ok"):
        return {
            "source": "chatgpt_ax",
            "ok": False,
            "error": dump.get("error"),
            "hint": dump.get("hint"),
            "conversations": {"written": 0, "skipped": 0},
        }

    lines = dump["lines"]
    # Sidebar-achtige titels: korte AXButton/AXStaticText
    titles = []
    for ln in lines:
        if "|" not in ln:
            continue
        role, _, val = ln.partition("|")
        val = val.strip()
        if role in {"AXButton", "AXStaticText", "AXHeading"} and 4 <= len(val) <= 80:
            if val.lower() not in {"chatgpt", "new chat", "search", "settings"}:
                titles.append(val)
    # uniek behouden volgorde
    seen = set()
    uniq_titles = []
    for t in titles:
        if t in seen:
            continue
        seen.add(t)
        uniq_titles.append(t)

    conversations = []
    # Eerste dump = huidige open chat
    current = _lines_to_conversation(lines, uniq_titles[0] if uniq_titles else "Huidige ChatGPT chat")
    if current:
        conversations.append(current)

    # Navigeer met pijltjes door sidebar (werkt vaak in ChatGPT Mac)
    for i in range(1, min(max_chats, max(1, len(uniq_titles)))):
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "ChatGPT" to activate\n'
                'delay 0.2\n'
                'tell application "System Events"\n'
                'key code 125 using {command down}\n'  # often no-op; try down arrow
                "end tell",
            ],
            capture_output=True,
        )
        # Prefer Option/Ctrl shortcuts unreliable; use Down arrow in chat list focus
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to key code 125',
            ],
            capture_output=True,
        )
        time.sleep(0.55)
        d2 = dump_ax_window()
        if not d2.get("ok"):
            break
        title = uniq_titles[i] if i < len(uniq_titles) else f"ChatGPT chat {i+1}"
        conv = _lines_to_conversation(d2["lines"], title)
        if conv and conv["messages"]:
            # skip near-duplicates
            if conversations and conv["messages"][-1]["content"] == conversations[-1]["messages"][-1]["content"]:
                continue
            conversations.append(conv)

    # Also store raw dump as memory snapshot
    memories = [
        {
            "native_id": f"ax-raw-{int(time.time())}",
            "key": "chatgpt-ax-snapshot",
            "content": "\n".join(lines)[:12000],
        }
    ]
    cstats = save_conversations(conversations, source="chatgpt_ax")
    mstats = save_memories(memories, source="chatgpt_ax")
    return {
        "source": "chatgpt_ax",
        "ok": cstats.get("written", 0) > 0 or mstats.get("written", 0) > 0,
        "sidebar_titles_seen": uniq_titles[:max_chats],
        "conversations": cstats,
        "memories": mstats,
        "note": "Geïmporteerd via Accessibility terwijl ChatGPT open stond (zelfde tekst die jij ziet).",
    }


def harvest_chatgpt_readable() -> dict[str, Any]:
    """Probeer eerst Keychain-decrypt, altijd ook AX als ChatGPT open kan."""
    results: dict[str, Any] = {"keychain": None, "accessibility": None}
    results["keychain"] = harvest_via_keychain()
    results["accessibility"] = harvest_via_accessibility()
    results["ok"] = bool(results["keychain"].get("ok") or results["accessibility"].get("ok"))
    results["running"] = chatgpt_running()
    return results
