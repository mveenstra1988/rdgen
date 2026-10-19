"""Lokale Mac-desktopacties: apps, Chrome, Mail, VIT Mail, URLs, Spotlight."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

KNOWN_APPS = {
    "chrome": ["Google Chrome", "Chrome"],
    "google chrome": ["Google Chrome"],
    "safari": ["Safari"],
    "mail": ["Mail"],
    "vit mail": ["VIT Mail", "VITMail", "vit-mail"],
    "vitmail": ["VIT Mail", "VITMail"],
    "cursor": ["Cursor"],
    "chatgpt": ["ChatGPT"],
    "claude": ["Claude"],
    "grok": ["Grok", "X"],
    "terminal": ["Terminal"],
    "iterm": ["iTerm", "iTerm2"],
    "finder": ["Finder"],
    "notes": ["Notes"],
    "slack": ["Slack"],
    "zoom": ["zoom.us", "Zoom"],
    "lm studio": ["LM Studio"],
    "penpot": ["Penpot", "penpot-desktop"],
    "figma": ["Figma"],
    "vscode": ["Visual Studio Code", "Code"],
    "code": ["Visual Studio Code", "Code"],
    "zed": ["Zed"],
}


def _darwin() -> bool:
    return os.uname().sysname == "Darwin"


def _run_osascript(script: str) -> tuple[bool, str]:
    if not _darwin():
        return False, "Alleen macOS"
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, out


def open_app(name: str) -> dict[str, Any]:
    key = name.strip().lower()
    candidates = KNOWN_APPS.get(key) or [name]
    if not _darwin():
        return {"ok": False, "error": "Alleen macOS"}
    for app in candidates:
        r = subprocess.run(["open", "-a", app], capture_output=True, text=True)
        if r.returncode == 0:
            return {"ok": True, "app": app}
    # fallback: open by path in ~/Applications or /Applications
    for app in candidates:
        for base in (Path("/Applications"), Path.home() / "Applications"):
            for path in base.glob(f"{app}*"):
                r = subprocess.run(["open", str(path)], capture_output=True, text=True)
                if r.returncode == 0:
                    return {"ok": True, "app": str(path)}
    return {"ok": False, "error": f"App niet gevonden: {name}", "tried": candidates}


def open_url(url: str) -> dict[str, Any]:
    if not url.startswith(("http://", "https://", "mailto:")):
        return {"ok": False, "error": "Alleen http(s)/mailto URLs"}
    if not _darwin():
        return {"ok": False, "error": "Alleen macOS"}
    r = subprocess.run(["open", url], capture_output=True, text=True)
    return {"ok": r.returncode == 0, "url": url, "error": r.stderr.strip() or None}


def chrome_open_url(url: str, *, new_tab: bool = True) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "Ongeldige URL"}
    script = f'''
    tell application "Google Chrome"
      activate
      if (count of windows) = 0 then make new window
      tell window 1
        {"make new tab with properties {{URL:\"%s\"}}" % url if new_tab else 'set URL of active tab to "%s"' % url}
      end tell
    end tell
    '''
    # fix script properly
    if new_tab:
        script = f'''
        tell application "Google Chrome"
          activate
          if (count of windows) = 0 then make new window
          tell window 1
            make new tab with properties {{URL:"{url}"}}
          end tell
        end tell
        '''
    else:
        script = f'''
        tell application "Google Chrome"
          activate
          if (count of windows) = 0 then make new window
          set URL of active tab of window 1 to "{url}"
        end tell
        '''
    ok, out = _run_osascript(script)
    return {"ok": ok, "url": url, "detail": out}


def chrome_list_tabs(limit: int = 30) -> dict[str, Any]:
    script = '''
    tell application "Google Chrome"
      set out to ""
      set lim to 30
      set n to 0
      repeat with w in windows
        repeat with t in tabs of w
          set n to n + 1
          if n > lim then exit repeat
          set out to out & (title of t) & " | " & (URL of t) & linefeed
        end repeat
        if n > lim then exit repeat
      end repeat
      return out
    end tell
    '''
    ok, out = _run_osascript(script)
    tabs = []
    if ok:
        for line in out.splitlines():
            if " | " in line:
                title, _, url = line.partition(" | ")
                tabs.append({"title": title.strip(), "url": url.strip()})
    return {"ok": ok, "tabs": tabs[:limit], "error": None if ok else out}


def mail_compose(to: str = "", subject: str = "", body: str = "") -> dict[str, Any]:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    recipient = ""
    if to.strip():
        recipient = (
            f'make new to recipient at end of to recipients with properties '
            f'{{address:"{esc(to.strip())}"}}'
        )
    script = f'''
    tell application "Mail"
      activate
      set msg to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
      tell msg
        {recipient}
      end tell
    end tell
    '''
    ok, out = _run_osascript(script)
    return {"ok": ok, "to": to, "subject": subject, "detail": out}


def vit_mail_open(action: str = "open") -> dict[str, Any]:
    """Open VIT Mail app; optional deep-ish actions via open URL schemes if present."""
    opened = open_app("vit mail")
    if not opened.get("ok"):
        # try common bundle locations Mike uses
        for path in (
            Path.home() / "Applications/VIT Mail.app",
            Path("/Applications/VIT Mail.app"),
            Path.home() / "Applications/VITMail.app",
        ):
            if path.exists():
                r = subprocess.run(["open", str(path)], capture_output=True, text=True)
                opened = {"ok": r.returncode == 0, "app": str(path)}
                break
    if action.startswith("mailto:"):
        open_url(action)
    return {"ok": opened.get("ok", False), "action": action, "app": opened}


def spotlight_search(query: str) -> dict[str, Any]:
    if not _darwin():
        return {"ok": False, "error": "Alleen macOS"}
    # mdfind is local spotlight
    r = subprocess.run(
        ["mdfind", "-limit", "20", query],
        capture_output=True,
        text=True,
    )
    paths = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][:20]
    return {"ok": r.returncode == 0, "query": query, "paths": paths}


def open_penpot(*, local: bool = True) -> dict[str, Any]:
    """Open Penpot (lokale Docker UI of Penpot cloud) — Figma-alternatief."""
    urls = []
    if local:
        urls.append("http://127.0.0.1:9001")
    urls.append("https://design.penpot.app")
    # probe local first
    if local and _darwin():
        try:
            import urllib.request

            urllib.request.urlopen("http://127.0.0.1:9001", timeout=1.5)
            r = subprocess.run(["open", "http://127.0.0.1:9001"], capture_output=True, text=True)
            return {
                "ok": r.returncode == 0,
                "url": "http://127.0.0.1:9001",
                "mode": "local",
                "hint": "Lokaal Penpot. Start met: bash scripts/install-penpot-mac.sh",
            }
        except Exception:
            pass
    url = urls[-1]
    if not _darwin():
        return {"ok": False, "error": "Alleen macOS open", "url": url, "hint": "Start Penpot via scripts/install-penpot-mac.sh"}
    r = subprocess.run(["open", url], capture_output=True, text=True)
    return {
        "ok": r.returncode == 0,
        "url": url,
        "mode": "cloud",
        "hint": "Cloud Penpot geopend. Voor 100% lokaal: bash scripts/install-penpot-mac.sh (Docker).",
    }


def run_shell_safe(command: str) -> dict[str, Any]:
    """Zeer beperkt: alleen allowlist van veilige lokale commands."""
    allowed_prefixes = (
        "ls ",
        "pwd",
        "date",
        "whoami",
        "uname",
        "df ",
        "sw_vers",
        "pgrep ",
        "open ",
    )
    cmd = command.strip()
    if not any(cmd == p.strip() or cmd.startswith(p) for p in allowed_prefixes):
        return {
            "ok": False,
            "error": "Command niet op allowlist. Gebruik open_app/chrome/mail tools.",
        }
    if not _darwin() and cmd.startswith("sw_vers"):
        return {"ok": False, "error": "sw_vers alleen macOS"}
    r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=30)
    return {
        "ok": r.returncode == 0,
        "stdout": (r.stdout or "")[:8000],
        "stderr": (r.stderr or "")[:2000],
    }


def list_running_apps() -> dict[str, Any]:
    ok, out = _run_osascript(
        'tell application "System Events" to get name of every process whose background only is false'
    )
    apps = [a.strip() for a in out.split(",") if a.strip()] if ok else []
    return {"ok": ok, "apps": apps, "error": None if ok else out}


def desktop_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "open_app",
                "description": "Open een lokale Mac-app (Chrome, Mail, VIT Mail, Cursor, ChatGPT, Claude, Grok, …).",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_url",
                "description": "Open een URL of mailto: in de default handler.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "chrome_open_url",
                "description": "Open URL in Google Chrome (nieuw tabblad).",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "chrome_list_tabs",
                "description": "Lijst open Chrome-tabs (titel + URL).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mail_compose",
                "description": "Open een nieuw Mail.app concept (to/subject/body).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vit_mail_open",
                "description": "Open VIT Mail op deze Mac.",
                "parameters": {
                    "type": "object",
                    "properties": {"action": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "spotlight_search",
                "description": "Lokale Spotlight/mdfind zoekopdracht op bestanden.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_running_apps",
                "description": "Toon draaiende foreground apps op de Mac.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_shell_safe",
                "description": "Beperkte veilige shell (ls/pwd/open/… allowlist).",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_penpot",
                "description": "Open Penpot (Figma-alternatief): lokaal :9001 of design.penpot.app.",
                "parameters": {
                    "type": "object",
                    "properties": {"local": {"type": "boolean"}},
                },
            },
        },
    ]


async def run_desktop_tool(name: str, arguments: dict[str, Any]) -> str:
    dispatch = {
        "open_app": lambda: open_app(str(arguments.get("name", ""))),
        "open_url": lambda: open_url(str(arguments.get("url", ""))),
        "chrome_open_url": lambda: chrome_open_url(str(arguments.get("url", ""))),
        "chrome_list_tabs": lambda: chrome_list_tabs(),
        "mail_compose": lambda: mail_compose(
            to=str(arguments.get("to", "")),
            subject=str(arguments.get("subject", "")),
            body=str(arguments.get("body", "")),
        ),
        "vit_mail_open": lambda: vit_mail_open(str(arguments.get("action", "open"))),
        "spotlight_search": lambda: spotlight_search(str(arguments.get("query", ""))),
        "list_running_apps": lambda: list_running_apps(),
        "run_shell_safe": lambda: run_shell_safe(str(arguments.get("command", ""))),
        "open_penpot": lambda: open_penpot(local=bool(arguments.get("local", True))),
    }
    fn = dispatch.get(name)
    if not fn:
        return json.dumps({"error": f"onbekende desktop tool {name}"})
    return json.dumps(fn(), ensure_ascii=False)
