from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vit_ai_hub import __version__
from vit_ai_hub.catalog import collect_models
from vit_ai_hub.config import ROOT, get_settings
from vit_ai_hub.pii import get_pii_engine
from vit_ai_hub.router import ModelRouter, extract_text_from_response
from vit_ai_hub.tools import capabilities_manifest, run_tool, tool_specs

WEB_DIR = ROOT / "web"
app = FastAPI(title="VIT AI Hub", version=__version__)
router_engine = ModelRouter()

if (WEB_DIR / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    vit_enable_tools: bool = False


def _auth(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)) -> None:
    token = get_settings().vit_gateway_token
    if not token:
        return
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()
    provided = bearer or (x_api_key or "")
    if provided != token:
        raise HTTPException(status_code=401, detail="Invalid gateway token")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.is_file():
        return HTMLResponse("<h1>VIT AI Hub</h1><p>GUI ontbreekt.</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__, "ts": time.time()}


@app.get("/api/capabilities")
async def capabilities(_: None = Depends(_auth)) -> dict[str, Any]:
    return capabilities_manifest()


@app.get("/v1/models")
async def list_models(_: None = Depends(_auth)) -> dict[str, Any]:
    models = await collect_models()
    return {"object": "list", "data": models}


@app.get("/api/models")
async def api_models(_: None = Depends(_auth)) -> dict[str, Any]:
    return await list_models()


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, _: None = Depends(_auth)):
    return await _handle_chat(body)


@app.post("/api/chat")
async def api_chat(body: ChatCompletionRequest, _: None = Depends(_auth)):
    # GUI helper: tools on by default
    body.vit_enable_tools = True
    body.stream = False
    return await _handle_chat(body)


async def _handle_chat(body: ChatCompletionRequest):
    pii = get_pii_engine()
    settings = get_settings()
    requested_model = body.model or settings.vit_default_model

    # First pass: assume possibly cloud; if PII blocks, force local
    provisional = router_engine.resolve(requested_model, force_local=False)
    messages = [m.model_dump() for m in body.messages]
    safe_messages, pii_result = pii.process_messages(messages, destination_local=provisional.local)

    force_local = False
    if pii_result.blocked:
        # fail-closed: reroute to local instead of hard error when local exists
        try:
            decision = router_engine.resolve(requested_model, force_local=True)
            force_local = True
            safe_messages, pii_result = pii.process_messages(messages, destination_local=True)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "PII geblokkeerd voor cloud en geen lokale backend beschikbaar",
                    "finding_types": sorted({f.name for f in pii_result.findings}),
                    "hint": str(exc),
                },
            ) from exc
    else:
        decision = provisional
        if not decision.local and pii_result.action == "redact":
            pass  # already redacted

    # If user explicitly picked a cloud model but PII forced local, annotate
    payload: dict[str, Any] = {
        "model": decision.model,
        "messages": safe_messages,
        "stream": bool(body.stream),
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens

    use_tools = body.vit_enable_tools or bool(body.tools)
    if use_tools and not body.stream:
        payload["tools"] = body.tools or tool_specs()
        if body.tool_choice is not None:
            payload["tool_choice"] = body.tool_choice

    if body.stream:
        return StreamingResponse(
            _stream_proxy(decision, payload, pii_result.token_map, force_local=force_local),
            media_type="text/event-stream",
        )

    data = await _chat_with_tools(decision, payload)
    # rehydrate assistant content
    try:
        content = data["choices"][0]["message"].get("content")
        if isinstance(content, str) and pii_result.token_map:
            data["choices"][0]["message"]["content"] = pii.rehydrate(content, pii_result.token_map)
    except Exception:
        pass

    data["vit"] = {
        "backend": decision.backend.name,
        "model": decision.model,
        "requested_model": requested_model,
        "local": decision.local,
        "pii_action": pii_result.action,
        "pii_forced_local": force_local,
        "pii_finding_types": sorted({f.name for f in pii_result.findings}),
    }
    return JSONResponse(data)


async def _chat_with_tools(decision, payload: dict[str, Any], max_rounds: int = 4) -> dict[str, Any]:
    data = await decision.backend.chat_completions(payload)
    for _ in range(max_rounds):
        try:
            message = data["choices"][0]["message"]
        except Exception:
            return data
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return data
        payload["messages"] = list(payload["messages"]) + [message]
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}
            result = await run_tool(name, args)
            payload["messages"].append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or str(uuid.uuid4()),
                    "content": result,
                }
            )
        data = await decision.backend.chat_completions(payload)
    return data


async def _stream_proxy(decision, payload: dict[str, Any], token_map: dict[str, str], force_local: bool = False):
    pii = get_pii_engine()
    # For streaming we rehydrate on the fly best-effort for finished content chunks
    try:
        async for chunk in decision.backend.stream_chat_completions(payload):
            if token_map:
                text = chunk.decode("utf-8", errors="ignore")
                # only touch data lines content fragments lightly
                if '"content":' in text:
                    for token, value in token_map.items():
                        text = text.replace(token, value)
                    yield text.encode("utf-8")
                else:
                    yield chunk
            else:
                yield chunk
    except Exception as exc:
        err = {
            "error": {"message": str(exc), "type": "vit_upstream_error", "forced_local": force_local}
        }
        yield f"data: {json.dumps(err)}\n\n".encode()
        yield b"data: [DONE]\n\n"


@app.post("/v1/messages")
async def anthropic_messages(request: Request, _: None = Depends(_auth)):
    """Minimale Anthropic-compat shim → OpenAI chat completions."""
    body = await request.json()
    model = body.get("model")
    messages = body.get("messages") or []
    system = body.get("system")
    oai_messages = []
    if system:
        oai_messages.append({"role": "system", "content": system})
    for msg in messages:
        oai_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    fake = ChatCompletionRequest(
        model=model,
        messages=[ChatMessage(**m) for m in oai_messages],
        max_tokens=body.get("max_tokens"),
        stream=bool(body.get("stream")),
        temperature=body.get("temperature"),
    )
    result = await _handle_chat(fake)
    if isinstance(result, StreamingResponse):
        return result
    # convert JSONResponse
    data = json.loads(result.body.decode())
    text = extract_text_from_response(data)
    return {
        "id": data.get("id") or f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": data.get("model") or model,
        "stop_reason": "end_turn",
        "vit": data.get("vit"),
    }


@app.post("/api/tools/{name}")
async def api_tool(name: str, request: Request, _: None = Depends(_auth)):
    args = await request.json()
    return JSONResponse(json.loads(await run_tool(name, args)))


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "vit_ai_hub.main:app",
        host=settings.vit_gateway_host,
        port=settings.vit_gateway_port,
        reload=False,
    )


if __name__ == "__main__":
    run()