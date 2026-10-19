"""Claude Desktop live lezen via Accessibility (zelfde idee als ChatGPT live)."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any


def _darwin() -> bool:
    return os.uname().sysname == "Darwin"


def claude_running() -> bool:
    if not _darwin():
        return False
    r = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to (name of processes) contains "Claude"'],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip().lower() == "true"


_AX_DUMP = r'''
tell application "Claude" to activate
delay 0.5
tell application "System Events"
  if not (exists process "Claude") then return "ERROR:Claude niet gestart"
  tell process "Claude"
    set frontmost to true
    delay 0.3
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


def harvest_via_accessibility(*, max_steps: int = 25) -> dict[str, Any]:
    from vit_ai_hub.importing.chatgpt_live import _lines_to_conversation
    from vit_ai_hub.importing.store import save_conversations, save_memories

    if not _darwin():
        return {"source": "claude_ax", "ok": False, "error": "alleen macOS"}
    if not claude_running():
        subprocess.run(["open", "-a", "Claude"], check=False)
        time.sleep(2)

    conversations = []
    for i in range(max_steps):
        r = subprocess.run(["osascript", "-e", _AX_DUMP], capture_output=True, text=True)
        text = r.stdout or ""
        if text.startswith("ERROR:") or r.returncode != 0:
            if i == 0:
                return {
                    "source": "claude_ax",
                    "ok": False,
                    "error": text.strip() or r.stderr,
                    "hint": "Geef Toegankelijkheid-rechten aan Terminal/VIT AI Hub.",
                    "conversations": {"written": 0, "skipped": 0},
                }
            break
        lines = [ln for ln in text.splitlines() if ln.strip()]
        conv = _lines_to_conversation(lines, f"Claude chat {i+1}")
        if conv and conv.get("messages"):
            if not conversations or conv["messages"][-1]["content"] != conversations[-1]["messages"][-1]["content"]:
                conversations.append(conv)
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to key code 125'],
            capture_output=True,
        )
        time.sleep(0.45)

    memories = []
    if conversations:
        memories.append(
            {
                "native_id": f"claude-ax-{int(time.time())}",
                "key": "claude-ax-snapshot",
                "content": conversations[0]["messages"][-1]["content"][:4000],
            }
        )
    return {
        "source": "claude_ax",
        "ok": bool(conversations),
        "conversations": save_conversations(conversations, source="claude_ax"),
        "memories": save_memories(memories, source="claude_ax"),
    }
