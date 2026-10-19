#!/usr/bin/env python3
"""Minimale macOS menubar voor VIT AI Hub (optioneel: pip install rumps)."""

from __future__ import annotations

import subprocess
import sys
import urllib.request

GATEWAY = "http://127.0.0.1:8787"


def _get(path: str) -> str:
    try:
        with urllib.request.urlopen(GATEWAY + path, timeout=3) as r:
            return r.read().decode()[:200]
    except Exception as exc:
        return f"error:{exc}"


def main() -> int:
    try:
        import rumps
    except ImportError:
        print("Installeer rumps: pip install rumps", file=sys.stderr)
        print("Fallback: open GUI in browser")
        subprocess.run(["open", GATEWAY], check=False)
        return 1

    class VitBar(rumps.App):
        def __init__(self) -> None:
            super().__init__("VIT", quit_button="Quit")
            self.menu = [
                rumps.MenuItem("Open GUI", callback=self.open_gui),
                rumps.MenuItem("Sync nu", callback=self.sync_now),
                rumps.MenuItem("Health", callback=self.health),
            ]

        def open_gui(self, _):
            subprocess.run(["open", GATEWAY], check=False)

        def sync_now(self, _):
            req = urllib.request.Request(GATEWAY + "/api/sync/once", method="POST")
            try:
                urllib.request.urlopen(req, timeout=120)
                rumps.notification("VIT AI Hub", "Sync", "Klaar")
            except Exception as exc:
                rumps.notification("VIT AI Hub", "Sync fout", str(exc))

        def health(self, _):
            rumps.alert(_get("/health"))

    VitBar().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())