"""Vision, image-gen (lokaal SVG of cloud), TTS — Canva/Figma media-pad."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from vit_ai_hub.visual.templates import list_templates, render_template


def media_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "visual_list_templates",
                "description": "Lijst Canva-alt visual templates (LinkedIn, story, pitch, flyer).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "visual_render",
                "description": (
                    "Render een visual template naar HTML+SVG (Canva-alt). "
                    "Schrijf bestanden naar workspace als path/workspace gezet."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "linkedin-post|instagram-story|carousel-slide|pitch-slide|flyer-a5",
                        },
                        "headline": {"type": "string"},
                        "sub": {"type": "string"},
                        "cta": {"type": "string"},
                        "brand": {"type": "string"},
                        "accent": {"type": "string"},
                        "slide": {"type": "string"},
                        "workspace": {"type": "string"},
                        "write": {"type": "boolean"},
                    },
                    "required": ["template", "headline"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "describe_image",
                "description": "Beschrijf een lokale afbeelding (vision). Pad absoluut of in workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "workspace": {"type": "string"},
                        "prompt": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_image",
                "description": (
                    "Genereer visual. provider=local → SVG/HTML Canva-alt; "
                    "provider=banana → Google Nano Banana (Gemini image, GEMINI_API_KEY); "
                    "cloud=true kiest banana als key gezet is."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "template": {"type": "string"},
                        "headline": {"type": "string"},
                        "sub": {"type": "string"},
                        "cta": {"type": "string"},
                        "brand": {"type": "string"},
                        "workspace": {"type": "string"},
                        "cloud": {"type": "boolean"},
                        "provider": {
                            "type": "string",
                            "description": "local | banana",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "nano_banana",
                "description": (
                    "Google Nano Banana (Gemini image gen/edit). Vereist GEMINI_API_KEY "
                    "of GOOGLE_API_KEY. Schrijft PNG naar workspace indien gezet."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "workspace": {"type": "string"},
                        "filename": {"type": "string"},
                        "model": {
                            "type": "string",
                            "description": "default gemini-nano-banana-2.1",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_document",
                "description": (
                    "Lees/analyseer een lokaal document (txt/md/json/csv/pdf/html). "
                    "PDF: tekstextractie best-effort."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "workspace": {"type": "string"},
                        "max_chars": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "speak_text",
                "description": "macOS tekst-naar-spraak (say). Handig voor pitches nalopen.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "voice": {"type": "string"},
                    },
                    "required": ["text"],
                },
            },
        },
    ]


MEDIA_TOOL_NAMES = {t["function"]["name"] for t in media_tool_specs()}


def _resolve_path(path: str, workspace: str | None) -> Path | None:
    p = Path(path).expanduser()
    if p.is_file():
        return p.resolve()
    if workspace:
        from vit_ai_hub.workspace import resolve_in_workspace

        try:
            cand = resolve_in_workspace(path, workspace=workspace)
            if cand.is_file():
                return cand
        except Exception:
            pass
    return None


async def describe_image(
    path: str,
    *,
    workspace: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    resolved = _resolve_path(path, workspace)
    if not resolved:
        return {"ok": False, "error": f"bestand niet gevonden: {path}"}
    suffix = resolved.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return {"ok": False, "error": f"geen afbeelding: {suffix}"}
    size = resolved.stat().st_size
    meta = {
        "ok": True,
        "path": str(resolved),
        "bytes": size,
        "format": suffix.lstrip("."),
        "mode": "meta",
    }
    # Probe vision via OpenRouter if key present
    key = os.environ.get("OPENROUTER_API_KEY") or ""
    if key and suffix != ".svg" and size < 8_000_000:
        try:
            import httpx

            b64 = base64.b64encode(resolved.read_bytes()).decode("ascii")
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }.get(suffix, "image/png")
            user_prompt = prompt or "Beschrijf deze afbeelding kort voor design/marketing feedback (NL)."
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "qwen/qwen2.5-vl-72b-instruct:free",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": user_prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                                    },
                                ],
                            }
                        ],
                    },
                )
            if r.status_code < 400:
                data = r.json()
                text = data["choices"][0]["message"]["content"]
                meta["mode"] = "vision"
                meta["description"] = text
                return meta
            meta["vision_error"] = r.text[:400]
        except Exception as exc:
            meta["vision_error"] = str(exc)[:400]
    if suffix == ".svg":
        meta["description"] = f"SVG visual ({size} bytes). Open in browser of Penpot."
    else:
        meta["description"] = (
            f"Afbeelding {resolved.name} ({suffix}, {size} bytes). "
            "Zet OPENROUTER_API_KEY voor volledige vision-beschrijving."
        )
    return meta


def _gemini_key() -> str:
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_AI_API_KEY")
        or ""
    ).strip()


def media_capabilities() -> dict[str, Any]:
    return {
        "web_search": True,
        "fetch_url": True,
        "describe_image": True,
        "read_document": True,
        "generate_image_local": True,
        "nano_banana": bool(_gemini_key()),
        "video_generate": False,
        "video_note": "Geen Veo/video-gen in de hub; wel visuals (SVG/Banana) + speak_text.",
        "gemini_key_set": bool(_gemini_key()),
        "openrouter_key_set": bool(os.environ.get("OPENROUTER_API_KEY")),
    }


async def nano_banana(
    prompt: str,
    *,
    workspace: str | None = None,
    filename: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Google Nano Banana via Gemini generateContent (image output)."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "lege prompt"}
    key = _gemini_key()
    if not key:
        return {
            "ok": False,
            "error": "GEMINI_API_KEY of GOOGLE_API_KEY ontbreekt",
            "hint": "Zet key in ~/.config/vit/geheimen/ai-gateway.env — Nano Banana = Gemini image.",
        }
    mid = (model or os.environ.get("VIT_NANO_BANANA_MODEL") or "gemini-nano-banana-2.1").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{mid}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    try:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, params={"key": key}, json=payload)
        if r.status_code >= 400:
            # fallback legacy flash-image id
            if mid == "gemini-nano-banana-2.1":
                alt = "gemini-2.5-flash-image"
                url2 = f"https://generativelanguage.googleapis.com/v1beta/models/{alt}:generateContent"
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post(url2, params={"key": key}, json=payload)
                mid = alt
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"Gemini HTTP {r.status_code}",
                    "detail": (r.text or "")[:600],
                    "model": mid,
                }
        data = r.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400]}

    text_bits: list[str] = []
    image_b64 = None
    mime = "image/png"
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except Exception:
        return {"ok": False, "error": "onverwacht Gemini-antwoord", "raw": str(data)[:400]}
    for part in parts:
        if part.get("text"):
            text_bits.append(str(part["text"]))
        inline = part.get("inlineData") or part.get("inline_data") or {}
        if inline.get("data"):
            image_b64 = inline["data"]
            mime = inline.get("mimeType") or inline.get("mime_type") or mime

    out: dict[str, Any] = {
        "ok": bool(image_b64),
        "provider": "nano_banana",
        "model": mid,
        "prompt": prompt,
        "text": "\n".join(text_bits)[:2000] if text_bits else None,
    }
    if not image_b64:
        out["error"] = "geen image in response (check model/quota)"
        return out

    raw = base64.b64decode(image_b64)
    ext = ".png" if "png" in mime else ".jpg" if "jpeg" in mime or "jpg" in mime else ".bin"
    fname = (filename or f"banana-{abs(hash(prompt)) % 10_000_000:x}{ext}").strip()
    if workspace:
        from vit_ai_hub.workspace import resolve_in_workspace

        try:
            target = resolve_in_workspace(fname if "/" in fname else f"vit-media/{fname}", workspace=workspace)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            out["path"] = str(target)
            out["bytes"] = len(raw)
        except Exception as exc:
            out["write_error"] = str(exc)[:300]
            out["bytes"] = len(raw)
    else:
        # schrijf onder hub data/media
        from vit_ai_hub.config import ROOT

        dest = ROOT / "data" / "media"
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / fname
        target.write_bytes(raw)
        out["path"] = str(target)
        out["bytes"] = len(raw)
    return out


def read_document(
    path: str,
    *,
    workspace: str | None = None,
    max_chars: int = 40_000,
) -> dict[str, Any]:
    resolved = _resolve_path(path, workspace)
    if not resolved:
        return {"ok": False, "error": f"bestand niet gevonden: {path}"}
    suffix = resolved.suffix.lower()
    max_chars = max(1000, min(120_000, int(max_chars or 40_000)))
    if suffix in {".txt", ".md", ".markdown", ".json", ".csv", ".html", ".htm", ".log", ".py", ".js", ".ts"}:
        text = resolved.read_text(encoding="utf-8", errors="replace")
        return {
            "ok": True,
            "path": str(resolved),
            "format": suffix.lstrip("."),
            "chars": len(text),
            "truncated": len(text) > max_chars,
            "content": text[:max_chars],
        }
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(resolved))
            chunks = []
            for page in reader.pages[:40]:
                chunks.append(page.extract_text() or "")
            text = "\n".join(chunks)
            return {
                "ok": True,
                "path": str(resolved),
                "format": "pdf",
                "pages": len(reader.pages),
                "chars": len(text),
                "truncated": len(text) > max_chars,
                "content": text[:max_chars],
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": f"PDF extract mislukt: {exc}",
                "hint": "pip install pypdf of plak tekst; vision/PDF via Gemini kan later",
                "path": str(resolved),
            }
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return {
            "ok": False,
            "error": "dit is een afbeelding — gebruik describe_image",
            "path": str(resolved),
        }
    return {
        "ok": False,
        "error": f"formaat niet ondersteund: {suffix}",
        "path": str(resolved),
        "hint": "Ondersteund: txt/md/json/csv/html/pdf",
    }


async def generate_image(
    prompt: str,
    *,
    template: str = "linkedin-post",
    headline: str | None = None,
    sub: str | None = None,
    cta: str | None = None,
    brand: str = "VIT",
    workspace: str | None = None,
    cloud: bool = False,
    provider: str | None = None,
) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "lege prompt"}
    prov = (provider or "").strip().lower()
    if prov in {"banana", "nano_banana", "nano-banana"} or (cloud and _gemini_key() and prov != "local"):
        return await nano_banana(prompt, workspace=workspace)

    # Local Canva-alt path (always works)
    rendered = render_template(
        template or "linkedin-post",
        headline=headline or prompt[:80],
        sub=sub or prompt,
        cta=cta or "Meer info",
        brand=brand or "VIT",
    )
    out: dict[str, Any] = {
        "ok": True,
        "mode": "local_template",
        "prompt": prompt,
        "template": rendered.get("template"),
        "suggested_paths": rendered.get("suggested_paths"),
    }
    if workspace and rendered.get("ok"):
        from vit_ai_hub.workspace import write_workspace_file

        html_path = rendered["suggested_paths"]["html"]
        svg_path = rendered["suggested_paths"]["svg"]
        wh = write_workspace_file(html_path, rendered["html"], workspace=workspace)
        ws = write_workspace_file(svg_path, rendered["svg"], workspace=workspace)
        out["written"] = {"html": wh, "svg": ws}
    else:
        out["html_preview"] = (rendered.get("html") or "")[:500]
        out["svg"] = rendered.get("svg")

    if cloud and not _gemini_key():
        out["cloud"] = {
            "ok": False,
            "error": "GEMINI_API_KEY ontbreekt voor Nano Banana",
            "hint": "Zet GEMINI_API_KEY voor banana, of gebruik provider=local (SVG).",
        }
    elif cloud and _gemini_key():
        banana = await nano_banana(prompt, workspace=workspace)
        out["banana"] = banana
        if banana.get("ok"):
            out["mode"] = "local_template+banana"
    return out


def speak_text(text: str, *, voice: str | None = None) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "lege tekst"}
    if len(text) > 2000:
        text = text[:2000]
    if os.uname().sysname != "Darwin":
        return {"ok": False, "error": "speak_text alleen op macOS", "text": text[:200]}
    cmd = ["say"]
    if voice:
        cmd.extend(["-v", voice])
    cmd.append(text)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return {"ok": r.returncode == 0, "voice": voice or "default", "error": (r.stderr or "")[:300] or None}


async def run_media_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "visual_list_templates":
        return json.dumps({"templates": list_templates()}, ensure_ascii=False)
    if name == "visual_render":
        rendered = render_template(
            str(arguments.get("template") or "linkedin-post"),
            headline=str(arguments.get("headline") or ""),
            sub=str(arguments.get("sub") or ""),
            cta=str(arguments.get("cta") or ""),
            brand=str(arguments.get("brand") or "VIT"),
            accent=str(arguments.get("accent") or "#c4f04d"),
            slide=str(arguments.get("slide") or ""),
        )
        if arguments.get("write") and arguments.get("workspace") and rendered.get("ok"):
            from vit_ai_hub.workspace import write_workspace_file

            html_path = rendered["suggested_paths"]["html"]
            svg_path = rendered["suggested_paths"]["svg"]
            rendered["written"] = {
                "html": write_workspace_file(
                    html_path, rendered["html"], workspace=str(arguments["workspace"])
                ),
                "svg": write_workspace_file(
                    svg_path, rendered["svg"], workspace=str(arguments["workspace"])
                ),
            }
        # Don't dump huge HTML twice in tool result if written
        if rendered.get("written"):
            slim = {k: v for k, v in rendered.items() if k not in {"html", "svg"}}
            slim["html_bytes"] = len(rendered.get("html") or "")
            slim["svg_bytes"] = len(rendered.get("svg") or "")
            return json.dumps(slim, ensure_ascii=False)
        return json.dumps(rendered, ensure_ascii=False)
    if name == "describe_image":
        return json.dumps(
            await describe_image(
                str(arguments.get("path") or ""),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                prompt=(str(arguments["prompt"]) if arguments.get("prompt") else None),
            ),
            ensure_ascii=False,
        )
    if name == "generate_image":
        return json.dumps(
            await generate_image(
                str(arguments.get("prompt") or ""),
                template=str(arguments.get("template") or "linkedin-post"),
                headline=(str(arguments["headline"]) if arguments.get("headline") else None),
                sub=(str(arguments["sub"]) if arguments.get("sub") else None),
                cta=(str(arguments["cta"]) if arguments.get("cta") else None),
                brand=str(arguments.get("brand") or "VIT"),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                cloud=bool(arguments.get("cloud")),
                provider=(str(arguments["provider"]) if arguments.get("provider") else None),
            ),
            ensure_ascii=False,
        )
    if name == "nano_banana":
        return json.dumps(
            await nano_banana(
                str(arguments.get("prompt") or ""),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                filename=(str(arguments["filename"]) if arguments.get("filename") else None),
                model=(str(arguments["model"]) if arguments.get("model") else None),
            ),
            ensure_ascii=False,
        )
    if name == "read_document":
        return json.dumps(
            read_document(
                str(arguments.get("path") or ""),
                workspace=(str(arguments["workspace"]) if arguments.get("workspace") else None),
                max_chars=int(arguments.get("max_chars") or 40_000),
            ),
            ensure_ascii=False,
        )
    if name == "speak_text":
        return json.dumps(
            speak_text(
                str(arguments.get("text") or ""),
                voice=(str(arguments["voice"]) if arguments.get("voice") else None),
            ),
            ensure_ascii=False,
        )
    return json.dumps({"error": f"onbekende media tool {name}"})
