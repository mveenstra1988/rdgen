"""HTML/SVG templates als Canva-vervanger voor socials & pitches."""

from __future__ import annotations

import html
import re
from typing import Any

_SLUG = re.compile(r"[^a-z0-9_-]+")

TEMPLATES: dict[str, dict[str, Any]] = {
    "linkedin-post": {
        "id": "linkedin-post",
        "name": "LinkedIn post",
        "blurb": "Vierkante social card 1080×1080",
        "w": 1080,
        "h": 1080,
        "fields": ["headline", "sub", "cta", "brand", "accent"],
    },
    "instagram-story": {
        "id": "instagram-story",
        "name": "Instagram story",
        "blurb": "9:16 story 1080×1920",
        "w": 1080,
        "h": 1920,
        "fields": ["headline", "sub", "cta", "brand", "accent"],
    },
    "carousel-slide": {
        "id": "carousel-slide",
        "name": "Carousel slide",
        "blurb": "LinkedIn/IG carousel 1080×1080",
        "w": 1080,
        "h": 1080,
        "fields": ["headline", "sub", "cta", "brand", "accent", "slide"],
    },
    "pitch-slide": {
        "id": "pitch-slide",
        "name": "Pitch slide",
        "blurb": "16:9 pitch/deck slide",
        "w": 1920,
        "h": 1080,
        "fields": ["headline", "sub", "cta", "brand", "accent"],
    },
    "flyer-a5": {
        "id": "flyer-a5",
        "name": "Flyer A5",
        "blurb": "Eenvoudige print flyer",
        "w": 1240,
        "h": 1748,
        "fields": ["headline", "sub", "cta", "brand", "accent"],
    },
}


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "blurb": t["blurb"],
            "width": t["w"],
            "height": t["h"],
            "fields": t["fields"],
        }
        for t in TEMPLATES.values()
    ]


def _esc(v: str) -> str:
    return html.escape((v or "").strip(), quote=True)


def render_template(
    template_id: str,
    *,
    headline: str = "",
    sub: str = "",
    cta: str = "",
    brand: str = "VIT",
    accent: str = "#c4f04d",
    slide: str = "",
    bg: str = "#0f1410",
    fg: str = "#f2f5f0",
) -> dict[str, Any]:
    tid = _SLUG.sub("-", (template_id or "").strip().lower()).strip("-")
    meta = TEMPLATES.get(tid)
    if not meta:
        return {"ok": False, "error": f"onbekende template: {template_id}", "templates": list(TEMPLATES)}

    w, h = int(meta["w"]), int(meta["h"])
    headline = headline or "Jouw boodschap"
    sub = sub or "Korte ondersteunende zin."
    cta = cta or "Neem contact op"
    brand = brand or "VIT"
    accent = accent if accent.startswith("#") else f"#{accent}"
    slide_bit = f'<div class="slide">#{_esc(slide)}</div>' if slide else ""

    html_doc = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8"/>
<title>{_esc(brand)} · {_esc(meta["name"])}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=DM+Sans:wght@400;600&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {w}px; height: {h}px; overflow: hidden; }}
  body {{
    font-family: "DM Sans", system-ui, sans-serif;
    color: {fg};
    background:
      radial-gradient(1200px 800px at 10% 0%, {accent}33, transparent 55%),
      radial-gradient(900px 700px at 100% 100%, #2a4a3a55, transparent 50%),
      linear-gradient(160deg, {bg}, #1a2420 60%, #0c100e);
  }}
  .frame {{
    width: 100%; height: 100%;
    padding: clamp(48px, 6vw, 96px);
    display: flex; flex-direction: column; justify-content: space-between;
  }}
  .brand {{
    font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    font-size: {max(28, w // 36)}px; color: {accent};
  }}
  h1 {{
    font-family: Fraunces, Georgia, serif;
    font-size: {max(56, w // 14)}px; line-height: 1.05;
    max-width: 92%; margin-top: 8%;
  }}
  .sub {{
    margin-top: 1.2rem; font-size: {max(28, w // 32)}px;
    max-width: 80%; opacity: 0.9; line-height: 1.35;
  }}
  .foot {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
  .cta {{
    display: inline-block; padding: 0.85rem 1.4rem;
    background: {accent}; color: #10140f; font-weight: 600;
    font-size: {max(24, w // 40)}px; border-radius: 4px;
  }}
  .slide {{ opacity: 0.55; font-size: {max(22, w // 48)}px; }}
</style>
</head>
<body>
  <div class="frame">
    <div class="brand">{_esc(brand)}</div>
    <div>
      <h1>{_esc(headline)}</h1>
      <p class="sub">{_esc(sub)}</p>
    </div>
    <div class="foot">
      <span class="cta">{_esc(cta)}</span>
      {slide_bit}
    </div>
  </div>
</body>
</html>
"""
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg}"/>
      <stop offset="100%" stop-color="#1a2420"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <circle cx="{w * 0.1}" cy="{h * 0.05}" r="{min(w, h) * 0.45}" fill="{accent}" fill-opacity="0.18"/>
  <text x="{int(w * 0.07)}" y="{int(h * 0.1)}" fill="{accent}" font-family="Arial, sans-serif"
        font-size="{max(28, w // 36)}" font-weight="700">{_esc(brand)}</text>
  <text x="{int(w * 0.07)}" y="{int(h * 0.42)}" fill="{fg}" font-family="Georgia, serif"
        font-size="{max(48, w // 16)}" font-weight="700">{_esc(headline[:48])}</text>
  <text x="{int(w * 0.07)}" y="{int(h * 0.52)}" fill="{fg}" fill-opacity="0.9"
        font-family="Arial, sans-serif" font-size="{max(24, w // 36)}">{_esc(sub[:80])}</text>
  <rect x="{int(w * 0.07)}" y="{int(h * 0.82)}" width="{int(w * 0.28)}" height="{int(h * 0.07)}"
        rx="6" fill="{accent}"/>
  <text x="{int(w * 0.09)}" y="{int(h * 0.865)}" fill="#10140f" font-family="Arial, sans-serif"
        font-size="{max(22, w // 42)}" font-weight="600">{_esc(cta[:28])}</text>
</svg>
"""
    return {
        "ok": True,
        "template": tid,
        "width": w,
        "height": h,
        "html": html_doc,
        "svg": svg,
        "suggested_paths": {
            "html": f"visual/{tid}.html",
            "svg": f"visual/{tid}.svg",
        },
    }
