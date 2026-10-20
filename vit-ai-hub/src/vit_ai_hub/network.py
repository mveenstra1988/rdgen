"""LAN / iPhone bereikbaarheid: IP’s, URLs, QR, LAN-modus toggle."""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

from vit_ai_hub.config import SECRET_CANDIDATES, get_settings


def _secret_file() -> Path:
    for path in SECRET_CANDIDATES:
        if path.is_file():
            return path
    path = SECRET_CANDIDATES[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    # UDP trick for primary outbound interface
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and ip not in ips:
            ips.insert(0, ip)
    except Exception:
        pass
    return ips


def network_info() -> dict[str, Any]:
    s = get_settings()
    host = (s.vit_gateway_host or "127.0.0.1").strip()
    port = int(s.vit_gateway_port or 8787)
    lan_on = host in {"0.0.0.0", "::", "[::]"} or os.environ.get("VIT_LAN_ACCESS", "").strip() in {
        "1",
        "true",
        "yes",
    }
    ips = lan_ips()
    token = (s.vit_gateway_token or "").strip()
    urls = []
    if lan_on:
        for ip in ips:
            u = f"http://{ip}:{port}/"
            if token and token != "change-me-local-token":
                u = f"http://{ip}:{port}/?token={token}"
            urls.append({"ip": ip, "url": u})
    else:
        urls.append({"ip": "127.0.0.1", "url": f"http://127.0.0.1:{port}/"})
    return {
        "ok": True,
        "bind_host": host,
        "port": port,
        "lan_enabled": lan_on,
        "lan_ips": ips,
        "urls": urls,
        "token_set": bool(token and token != "change-me-local-token"),
        "pwa_hint": (
            "Op iPhone (zelfde wifi): open de URL in Safari → Deel → Zet op beginscherm."
            if lan_on
            else "Zet LAN-modus aan zodat je iPhone de hub kan bereiken."
        ),
        "restart_needed_note": "Na wijzigen LAN-modus: app sluiten en opnieuw openen.",
    }


def _upsert_env(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    found = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def set_lan_access(enabled: bool) -> dict[str, Any]:
    """Schrijf VIT_GATEWAY_HOST + VIT_LAN_ACCESS; vereist app-herstart."""
    path = _secret_file()
    if enabled:
        s = get_settings()
        token = (s.vit_gateway_token or "").strip()
        if not token or token == "change-me-local-token":
            return {
                "ok": False,
                "error": "Zet eerst een echte gateway-token (niet change-me) vóór LAN-modus.",
            }
        _upsert_env(path, "VIT_GATEWAY_HOST", "0.0.0.0")
        _upsert_env(path, "VIT_LAN_ACCESS", "1")
        os.environ["VIT_GATEWAY_HOST"] = "0.0.0.0"
        os.environ["VIT_LAN_ACCESS"] = "1"
    else:
        _upsert_env(path, "VIT_GATEWAY_HOST", "127.0.0.1")
        _upsert_env(path, "VIT_LAN_ACCESS", "0")
        os.environ["VIT_GATEWAY_HOST"] = "127.0.0.1"
        os.environ["VIT_LAN_ACCESS"] = "0"
    get_settings.cache_clear()
    info = network_info()
    info["ok"] = True
    info["written"] = str(path)
    info["restart_required"] = True
    return info


def qr_svg_for_url(url: str, *, scale: int = 5) -> str:
    """SVG QR; fallback tekst als segno ontbreekt."""
    try:
        import segno

        q = segno.make(url, error="m")
        import io

        buf = io.BytesIO()
        q.save(buf, kind="svg", scale=scale, border=2)
        return buf.getvalue().decode("utf-8")
    except Exception:
        # Minimal fallback: no QR lib — return placeholder SVG with URL text
        safe = (
            url.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120">'
            f'<rect width="100%" height="100%" fill="#f4f6f3"/>'
            f'<text x="12" y="40" font-size="11" fill="#15231c">QR lib ontbreekt</text>'
            f'<text x="12" y="70" font-size="9" fill="#5c6f64">{safe[:48]}</text>'
            f"</svg>"
        )
