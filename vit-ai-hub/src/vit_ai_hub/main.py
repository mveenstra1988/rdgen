from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    import eval_type_backport  # noqa: F401 — Python 3.9 + pydantic
except ImportError:
    pass

from vit_ai_hub import __version__
from vit_ai_hub.catalog import collect_models
from vit_ai_hub.config import ROOT, get_settings
from vit_ai_hub.importing import (
    find_export_zips,
    import_all_one_click,
    import_file,
    knowledge_context_block,
    search_knowledge,
    stats as knowledge_stats,
)
from vit_ai_hub.importing import cursor as cursor_import
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
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    vit_enable_tools: bool = False
    studio: Optional[str] = None
    workspace: Optional[str] = None
    vit_auto_team: Optional[bool] = None  # None = config default; False = nooit auto-team
    vit_skip_orchestrator: bool = False  # True = geen intent/team (interne team-stappen)
    vit_tradeoff: Optional[str] = None  # quality | cost | latency
    vit_critic: Optional[bool] = None  # None = config/auto; False = skip critic
    vit_session_id: Optional[str] = None  # gedeeld geheugen / conversatie over modelwissel
    agent_mode: Optional[str] = None  # agent | plan | ask (Cursor/Claude Code parity)


def _auth(authorization: Optional[str] = Header(default=None), x_api_key: Optional[str] = Header(default=None)) -> None:
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


@app.get("/manifest.webmanifest")
async def pwa_manifest() -> JSONResponse:
    path = WEB_DIR / "manifest.webmanifest"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="manifest ontbreekt")
    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(data, media_type="application/manifest+json")


@app.get("/sw.js")
async def pwa_sw() -> FileResponse:
    path = WEB_DIR / "static" / "sw.js"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="sw ontbreekt")
    return FileResponse(
        path,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__, "ts": time.time()}


def _localhost_only(request: Request) -> None:
    client = request.client.host if request.client else ""
    if client not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="Alleen localhost")


@app.get("/api/setup/status")
async def api_setup_status(request: Request) -> dict[str, Any]:
    from vit_ai_hub.setup_api import setup_status

    client = request.client.host if request.client else ""
    local = client in {"127.0.0.1", "::1", "testclient"}
    return setup_status(include_token=local)


@app.post("/api/setup/secrets")
async def api_setup_secrets(request: Request) -> dict[str, Any]:
    from vit_ai_hub.setup_api import save_secrets

    _localhost_only(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    return save_secrets({str(k): str(v) for k, v in body.items()})


@app.post("/api/setup/complete")
async def api_setup_complete(request: Request) -> dict[str, Any]:
    from vit_ai_hub.setup_api import mark_setup_complete

    _localhost_only(request)
    return mark_setup_complete()


@app.post("/api/setup/bootstrap")
async def api_setup_bootstrap(request: Request) -> dict[str, Any]:
    """Alles in één keer: optionele keys + import + sync + klaar."""
    from vit_ai_hub.setup_api import bootstrap_all, save_secrets

    _localhost_only(request)
    body: dict[str, Any] = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}
    secrets = {str(k): str(v) for k, v in body.get("secrets", {}).items()} if isinstance(body.get("secrets"), dict) else {}
    # also accept flat keys
    for k in (
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "XAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "BRIDGE_API_KEY",
        "OMNIROUTE_API_KEY",
        "VIT_LOCAL_LIGHT_MODEL",
        "VIT_LOCAL_HEAVY_MODEL",
        "VIT_NANO_BANANA_MODEL",
    ):
        if body.get(k):
            secrets[k] = str(body[k])
    if secrets:
        await asyncio.to_thread(save_secrets, secrets)
    return await asyncio.to_thread(bootstrap_all, open_a11y=bool(body.get("open_a11y")))


@app.post("/api/setup/install-auto")
async def api_setup_install_auto(request: Request) -> dict[str, Any]:
    """Auto-install: bridge, migrate, token, Cursor-wire. User only logs in."""
    from vit_ai_hub.setup_api import install_auto

    _localhost_only(request)
    body: dict[str, Any] = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}
    secrets: dict[str, str] = {}
    if isinstance(body.get("secrets"), dict):
        secrets = {str(k): str(v) for k, v in body["secrets"].items()}
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "VIT_NANO_BANANA_MODEL"):
        if body.get(k):
            secrets[k] = str(body[k])
    # Belangrijk: niet de event-loop blokkeren — anders reageren login-knoppen niet
    return await asyncio.to_thread(
        install_auto,
        secrets=secrets or None,
        open_a11y=bool(body.get("open_a11y")),
        mark_complete=bool(body.get("mark_complete")),
    )


@app.post("/api/setup/open-accessibility")
async def api_setup_a11y() -> dict[str, Any]:
    from vit_ai_hub.setup_api import open_accessibility_settings

    return open_accessibility_settings()


@app.get("/api/commands")
async def api_commands_list(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.slash import list_commands

    return list_commands()


@app.post("/api/commands/run")
async def api_commands_run(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.slash import run_local

    return run_local(
        str(body.get("cmd") or body.get("command") or ""),
        args=str(body.get("args") or ""),
        workspace=str(body.get("workspace") or "") or None,
    )


@app.get("/api/checkpoints")
async def api_checkpoints(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.checkpoints import list_checkpoints

    return list_checkpoints()


@app.get("/api/bridge/status")
async def api_bridge_status(request: Request) -> dict[str, Any]:
    """Claude/ChatGPT bridge status (localhost setup + authenticated)."""
    from vit_ai_hub.bridge import bridge_status

    _localhost_only(request)
    return bridge_status()


@app.post("/api/bridge/bootstrap")
async def api_bridge_bootstrap(request: Request) -> dict[str, Any]:
    """Installeer CLIProxyAPI, schrijf keys, start bridge — zonder handmatige bridge-key."""
    from vit_ai_hub.bridge import bootstrap_bridge

    _localhost_only(request)
    return await asyncio.to_thread(bootstrap_bridge)


@app.post("/api/bridge/login")
async def api_bridge_login(request: Request) -> dict[str, Any]:
    """Start OAuth: body.provider = claude | chatgpt."""
    from vit_ai_hub.bridge import start_login, start_bridge, bridge_status, bootstrap_bridge

    _localhost_only(request)
    body: dict[str, Any] = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}
    provider = str(body.get("provider") or "claude")

    def _run() -> dict[str, Any]:
        # Zorg dat binary/config er is vóór OAuth (snel pad, los van install-auto)
        boot = bootstrap_bridge()
        out = start_login(provider)
        if out.get("ok"):
            try:
                start_bridge()
            except Exception:
                pass
        out["bootstrap"] = {
            "ok": boot.get("ok"),
            "installed": (boot.get("status") or {}).get("installed"),
        }
        out["status"] = bridge_status()
        return out

    return await asyncio.to_thread(_run)


@app.post("/api/bridge/start")
async def api_bridge_start(request: Request) -> dict[str, Any]:
    from vit_ai_hub.bridge import start_bridge, bridge_status

    _localhost_only(request)

    def _run() -> dict[str, Any]:
        out = start_bridge()
        out["status"] = bridge_status()
        return out

    return await asyncio.to_thread(_run)


@app.post("/api/setup/open-guide")
async def api_setup_open_guide(request: Request) -> dict[str, Any]:
    from vit_ai_hub.setup_api import open_guide

    _localhost_only(request)
    body: dict[str, Any] = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}
    target = str(body.get("target") or request.query_params.get("target") or "")
    return await asyncio.to_thread(open_guide, target)


@app.get("/api/setup/probe")
async def api_setup_probe(request: Request) -> dict[str, Any]:
    from vit_ai_hub.setup_api import probe_providers

    _localhost_only(request)
    return probe_providers()


@app.get("/api/capabilities")
async def capabilities(_: None = Depends(_auth)) -> dict[str, Any]:
    return capabilities_manifest()


@app.get("/api/accounts")
async def api_accounts_status(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.pool import pool_status

    _localhost_only(request)
    return pool_status()


@app.post("/api/accounts/{pool}")
async def api_add_account(pool: str, request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.pool import add_account

    _localhost_only(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    out = add_account(pool, body)
    router_engine.refresh()
    return out


@app.delete("/api/accounts/{pool}/{account_id}")
async def api_delete_account(
    pool: str, account_id: str, request: Request, _: None = Depends(_auth)
) -> dict[str, Any]:
    from vit_ai_hub.pool import delete_account

    _localhost_only(request)
    out = delete_account(pool, account_id)
    router_engine.refresh()
    return out


@app.post("/api/accounts/clear-cooldown")
async def api_clear_cooldown(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.pool.store import clear_exhaustion

    _localhost_only(request)
    body: dict[str, Any] = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}
    out = clear_exhaustion(str(body.get("account_id") or "") or None)
    router_engine.refresh()
    return out


@app.post("/api/orchestrator/plan")
async def api_orchestrator_plan(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    """Preview: welk model/team Auto zou kiezen (geen LLM-call)."""
    from vit_ai_hub.orchestrator import plan_request

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    plan = plan_request(
        str(body.get("text") or body.get("task") or ""),
        studio=str(body.get("studio") or "") or None,
        workspace=str(body.get("workspace") or "") or None,
        force_local=bool(body.get("force_local")),
        allow_team=body.get("allow_team"),
        tradeoff=str(body.get("tradeoff") or "") or None,
    )
    return {"ok": True, "plan": plan.to_dict()}


@app.get("/api/studios")
async def api_studios() -> dict[str, Any]:
    from vit_ai_hub.studio import list_studios

    return {"studios": list_studios()}


@app.get("/api/network")
async def api_network(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.network import network_info

    return network_info()


@app.post("/api/network/lan")
async def api_network_lan(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.network import set_lan_access

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    return set_lan_access(bool(body.get("enabled")))


@app.get("/api/network/qr.svg")
async def api_network_qr(url: str = "", _: None = Depends(_auth)) -> HTMLResponse:
    from vit_ai_hub.network import network_info, qr_svg_for_url

    target = (url or "").strip()
    if not target:
        info = network_info()
        urls = info.get("urls") or []
        target = (urls[0]["url"] if urls else "") or "http://127.0.0.1:8787/"
    if not target.startswith("http://") and not target.startswith("https://"):
        raise HTTPException(status_code=400, detail="Ongeldige URL")
    svg = qr_svg_for_url(target)
    return HTMLResponse(svg, media_type="image/svg+xml")


@app.get("/api/app/status")
async def api_app_status() -> dict[str, Any]:
    """Lifecycle info voor de Mac-app / health UI."""
    from vit_ai_hub import __version__

    run_dir = ROOT / "data" / "run"
    hub_pid = None
    session_pid = None
    try:
        p = run_dir / "hub.pid"
        if p.is_file():
            hub_pid = int(p.read_text().strip() or "0") or None
    except Exception:
        pass
    try:
        p = run_dir / "session.pid"
        if p.is_file():
            session_pid = int(p.read_text().strip() or "0") or None
    except Exception:
        pass
    return {
        "ok": True,
        "version": __version__,
        "hub_pid": hub_pid,
        "session_pid": session_pid,
        "lifecycle": "app-session",
        "hint": "Open VIT AI Hub.app om te starten; Cmd+Q stopt de hub.",
    }


@app.get("/api/presets")
async def api_presets() -> dict[str, Any]:
    """Snelle starters (research-upgrade: slash-achtige presets)."""
    return {
        "presets": [
            {
                "id": "pitch",
                "label": "Pitch",
                "studio": "marketing",
                "text": "Schrijf een scherpe 30s + 2min pitch met positionering en CTA voor ",
            },
            {
                "id": "landing",
                "label": "Landing",
                "studio": "webdesign",
                "text": "Bouw een volledige landingspagina end-to-end met hero, SEO en CTA voor ",
            },
            {
                "id": "linkedin",
                "label": "LinkedIn",
                "studio": "socials",
                "text": "Maak 5 LinkedIn posts + mini-kalender over ",
            },
            {
                "id": "canva",
                "label": "Visual",
                "studio": "visual",
                "text": "Render Canva-alt LinkedIn carousel (3 slides) over ",
            },
            {
                "id": "seo",
                "label": "SEO / GEO",
                "studio": "seo",
                "text": "SEO + GEO plan met keyword clusters en FAQ schema voor ",
            },
        ]
    }


@app.get("/api/visual/templates")
async def api_visual_templates() -> dict[str, Any]:
    from vit_ai_hub.visual import list_templates

    return {"templates": list_templates()}


@app.post("/api/visual/render")
async def api_visual_render(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.visual import render_template

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    result = render_template(
        str(body.get("template") or "linkedin-post"),
        headline=str(body.get("headline") or ""),
        sub=str(body.get("sub") or ""),
        cta=str(body.get("cta") or ""),
        brand=str(body.get("brand") or "VIT"),
        accent=str(body.get("accent") or "#c4f04d"),
        slide=str(body.get("slide") or ""),
    )
    if body.get("write") and body.get("workspace") and result.get("ok"):
        from vit_ai_hub.workspace import write_workspace_file

        ws = str(body["workspace"])
        result["written"] = {
            "html": write_workspace_file(
                result["suggested_paths"]["html"], result["html"], workspace=ws
            ),
            "svg": write_workspace_file(
                result["suggested_paths"]["svg"], result["svg"], workspace=ws
            ),
        }
    return result


@app.get("/api/agents")
async def api_list_agents(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import list_agents

    return {"agents": list_agents()}


@app.post("/api/agents")
async def api_save_agent(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import save_agent

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    return save_agent(body)


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import delete_agent

    return delete_agent(agent_id)


@app.get("/api/teams")
async def api_list_teams(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import list_agents, list_teams

    return {"teams": list_teams(), "agents": list_agents()}


@app.post("/api/teams")
async def api_save_team(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import save_team

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    return save_team(body)


@app.delete("/api/teams/{team_id}")
async def api_delete_team(team_id: str, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import delete_team

    return delete_team(team_id)


@app.post("/api/teams/{team_id}/run")
async def api_run_team(team_id: str, request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.agents import run_team

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    task = str(body.get("task") or "").strip()
    workspace = str(body.get("workspace") or "").strip() or None
    model_override = str(body.get("model") or "").strip() or None

    async def chat_fn(*, messages, model, studio, workspace, tools):
        fake = ChatCompletionRequest(
            model=model,
            messages=[ChatMessage(**m) for m in messages],
            vit_enable_tools=bool(tools),
            studio=studio,
            workspace=workspace,
            stream=False,
            vit_skip_orchestrator=True,
            vit_auto_team=False,
        )
        result = await _handle_chat(fake)
        if isinstance(result, JSONResponse):
            return json.loads(result.body.decode())
        if isinstance(result, dict):
            return result
        raise RuntimeError("onverwacht chat-antwoord")

    return await run_team(
        team_id,
        task=task,
        workspace=workspace,
        model_override=model_override,
        smart_models=not bool(model_override),
        chat_fn=chat_fn,
    )


@app.get("/api/workspace/status")
async def api_workspace_status(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.workspace import workspace_status

    return workspace_status()


@app.post("/api/workspace/export-continue")
async def api_export_continue(request: Request) -> dict[str, Any]:
    """Schrijf Continue.dev config die naar deze hub wijst (Cursor-exit)."""
    _localhost_only(request)
    from vit_ai_hub.setup_api import export_continue_config

    out = export_continue_config()
    out["next"] = [
        "Installeer VS Code of Cursor-alternatief Zed",
        "Installeer Continue-extensie",
        "Herstart editor — model 'VIT AI Hub (auto)' kiezen",
        "Cursor-abo kun je daarna opzeggen als dit bevalt",
    ]
    return out


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

    messages = [m.model_dump() for m in body.messages]
    last_user = ""
    last_user_idx: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") == "user":
            content = m.get("content")
            last_user = content if isinstance(content, str) else str(content)
            last_user_idx = i
            break

    # Slash-commands (Claude Code / Cursor / Codex parity)
    from vit_ai_hub.agent_modes import normalize_mode, parse_leading_slash
    from vit_ai_hub.slash import llm_prompt_for, parse_slash, run_local

    slash_cmd, slash_args = parse_slash(last_user)
    if slash_cmd and slash_cmd not in {"/plan", "/ask", "/agent", "/debug", "/compact", "/review"}:
        local = run_local(slash_cmd, args=slash_args, workspace=body.workspace)
        if not local.get("passthrough"):
            return {
                "id": f"slash-{slash_cmd.strip('/')}",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": local.get("message") or ""},
                        "finish_reason": "stop",
                    }
                ],
                "vit": {
                    "slash": slash_cmd,
                    "action": local.get("action"),
                    "ok": local.get("ok"),
                    "session_id": body.vit_session_id,
                },
            }

    slash_mode, remainder = parse_leading_slash(last_user)
    agent_mode = normalize_mode(slash_mode or body.agent_mode)
    body.agent_mode = agent_mode
    if slash_mode is not None and last_user_idx is not None:
        last_user = remainder or f"(modus {agent_mode})"
        messages[last_user_idx] = {**messages[last_user_idx], "content": last_user}
    elif slash_cmd in {"/compact", "/review"} and last_user_idx is not None:
        prompted = llm_prompt_for(slash_cmd, slash_args, workspace=body.workspace) or last_user
        last_user = prompted
        messages[last_user_idx] = {**messages[last_user_idx], "content": last_user}
        if slash_cmd == "/review":
            body.studio = "software"
            body.vit_critic = True
            agent_mode = "ask"
            body.agent_mode = "ask"
        if slash_cmd == "/compact":
            agent_mode = "ask"
            body.agent_mode = "ask"
    if agent_mode == "plan":
        body.studio = body.studio or "software"
        body.vit_enable_tools = True
    elif agent_mode in {"ask", "debug"}:
        body.vit_enable_tools = True
        if agent_mode == "debug":
            body.studio = body.studio or "software"

    auto_plan = None
    req_l = (requested_model or "").strip().lower()
    is_max = req_l == "vit/max"
    is_auto = req_l in {"vit/auto", "auto", "vit/smart", "vit/max", ""}
    if is_max and not body.vit_tradeoff:
        body.vit_tradeoff = "quality"
    if is_max and body.vit_critic is None:
        body.vit_critic = True
    if is_auto and not body.vit_skip_orchestrator:
        try:
            _, auto_plan = router_engine.resolve_smart(
                text=last_user,
                studio=body.studio,
                workspace=body.workspace,
                force_local=False,
                allow_team=body.vit_auto_team,
                tradeoff=body.vit_tradeoff or ("quality" if is_max else None),
            )
            # Auto multi-agent: complexe taken → team met per-rol model
            if auto_plan.use_team and auto_plan.team_id and not body.stream:
                return await _handle_auto_team(body, last_user, auto_plan)
            requested_model = auto_plan.model
            if auto_plan.studio and not body.studio:
                body.studio = auto_plan.studio
        except Exception:
            auto_plan = None

    # First pass: assume possibly cloud; if PII blocks, force local
    provisional = router_engine.resolve(requested_model, force_local=False)
    knowledge = knowledge_context_block(last_user, limit=8)
    shared_memory = None
    try:
        from vit_ai_hub.memory import context_block as memory_context_block

        shared_memory = memory_context_block(last_user, limit=8)
    except Exception:
        shared_memory = None

    # Lokale prep: repo/kennis/geheugen → EXEC_BRIEF (minder tokens voor Claude/GPT)
    prep_meta: dict[str, Any] | None = None
    use_prep = False
    try:
        from vit_ai_hub.orchestrator.local_prep import build_exec_brief, should_local_prep

        use_prep = should_local_prep(
            destination_local=bool(provisional.local),
            studio=body.studio,
            task=last_user,
            skip=bool(body.vit_skip_orchestrator),
        )
        # Ook prep als auto/max naar cloud kan (provisional nog niet final)
        if not use_prep and is_auto and not provisional.local:
            use_prep = should_local_prep(
                destination_local=False,
                studio=body.studio,
                task=last_user,
                skip=bool(body.vit_skip_orchestrator),
            )
        if use_prep:
            recent_users = [
                m.get("content")
                for m in messages
                if m.get("role") == "user" and isinstance(m.get("content"), str)
            ][-4:]
            prep_meta = build_exec_brief(
                task=last_user,
                workspace=body.workspace,
                studio=body.studio,
                knowledge=knowledge,
                memory=shared_memory,
                recent_user_turns=[str(x) for x in recent_users if x],
            )
    except Exception as exc:
        prep_meta = {"ok": False, "error": str(exc)}
        use_prep = False

    prefix: list[dict[str, Any]] = []
    from vit_ai_hub.studio import studio_system_prompt

    studio_prompt = studio_system_prompt(body.studio)
    if studio_prompt:
        prefix.append({"role": "system", "content": studio_prompt})
    try:
        from vit_ai_hub.agent_modes import mode_system_prompt

        mode_prompt = mode_system_prompt(agent_mode)
        if mode_prompt:
            prefix.append({"role": "system", "content": mode_prompt})
    except Exception:
        pass
    try:
        from vit_ai_hub.project_context import project_system_block

        proj = project_system_block(body.workspace)
        if proj:
            # token-save with prep
            if use_prep and prep_meta and prep_meta.get("ok"):
                proj = proj[:3000] + ("…" if len(proj) > 3000 else "")
            prefix.append({"role": "system", "content": proj})
    except Exception:
        pass
    try:
        from vit_ai_hub.orchestrator.quality import quality_system_addon

        tradeoff_eff = (
            (body.vit_tradeoff or (auto_plan.tradeoff if auto_plan else None) or "quality")
        )
        q_addon = quality_system_addon(studio=body.studio, tradeoff=tradeoff_eff)
        if q_addon:
            prefix.append({"role": "system", "content": q_addon})
    except Exception:
        pass
    prefix.append(
        {
            "role": "system",
            "content": (
                "Gedeeld geheugen is model-agnostisch: bij wisselen van model blijft "
                "conversatie + opgeslagen feiten bestaan. Gebruik memory_write voor "
                "blijvende voorkeuren; noem geen geheugenverlies bij modelwissel."
            ),
        }
    )
    if auto_plan and not body.vit_skip_orchestrator:
        prefix.append(
            {
                "role": "system",
                "content": (
                    "VIT Auto-orchestrator actief. "
                    f"Plan: {auto_plan.summary}. "
                    "Gebruik tools waar dat sneller/accurater is. Geen klant-PII naar cloud."
                ),
            }
        )
    try:
        from vit_ai_hub.importing.full_migrate import runtime_system_addons

        migrated = runtime_system_addons()
        if migrated:
            # Met prep: migratie-addons inkorten (tokens sparen voor cloud)
            if use_prep and prep_meta and prep_meta.get("ok"):
                migrated = migrated[:2500] + ("…" if len(migrated) > 2500 else "")
            prefix.append({"role": "system", "content": migrated})
    except Exception:
        pass
    if body.workspace and not (use_prep and prep_meta and prep_meta.get("ok")):
        prefix.append(
            {
                "role": "system",
                "content": (
                    f"Actieve workspace: {body.workspace}. "
                    "Gebruik list_workspace / read_workspace_file / write_workspace_file / run_in_workspace "
                    "met workspace= dit pad."
                ),
            }
        )
    # Self-improve: altijd hub-root noemen als studio self of user daarom vraagt
    if (body.studio or "") == "self" or "verbeter" in last_user.lower() or "pas jezelf" in last_user.lower():
        prefix.append(
            {
                "role": "system",
                "content": (
                    f"Self-improve actief. Hub-root: {ROOT}. "
                    "Je mag hub-bestanden lezen/schrijven/testen via workspace-tools. "
                    "Wijzig gericht, run pytest waar nuttig, vat daarna samen wat er veranderde."
                ),
            }
        )
    if use_prep and prep_meta and prep_meta.get("ok") and prep_meta.get("brief"):
        prefix.append({"role": "system", "content": prep_meta["system_note"]})
        prefix.append({"role": "system", "content": prep_meta["brief"]})
        # Brief bevat al geheugen/kennis-kern — geen dubbele dump
    else:
        if shared_memory:
            prefix.append({"role": "system", "content": shared_memory})
        if knowledge:
            prefix.append({"role": "system", "content": knowledge})
    # Cloud/token-save: houd alleen recente turns + laatst user (prefix apart)
    if use_prep and prep_meta and prep_meta.get("ok") and not provisional.local:
        slim: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") in {"user", "assistant"}:
                slim.append(m)
        messages = slim[-8:] if len(slim) > 8 else slim
    if prefix:
        messages = [*prefix, *messages]
    safe_messages, pii_result = pii.process_messages(messages, destination_local=provisional.local)

    force_local = False
    if pii_result.blocked:
        # fail-closed: reroute to local instead of hard error when local exists
        try:
            if is_auto and not body.vit_skip_orchestrator:
                decision, auto_plan = router_engine.resolve_smart(
                    text=last_user,
                    studio=body.studio,
                    workspace=body.workspace,
                    force_local=True,
                    allow_team=False,
                )
            else:
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
    else:
        # M5/coding defaults: code strakker, chat creatiever
        st = (body.studio or "").lower()
        if st in {"software", "self", "ops"}:
            payload["temperature"] = 0.3
        elif st in {"marketing", "socials", "visual", "webdesign"}:
            payload["temperature"] = 0.7
        else:
            payload["temperature"] = 0.55
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens

    use_tools = body.vit_enable_tools or bool(body.tools)
    if use_tools and not body.stream:
        from vit_ai_hub.agent_modes import filter_tools_for_mode

        raw_tools = body.tools or tool_specs()
        payload["tools"] = filter_tools_for_mode(raw_tools, agent_mode) or []
        if agent_mode in {"plan", "ask"} and not payload["tools"]:
            use_tools = False
            payload.pop("tools", None)
        if body.tool_choice is not None and payload.get("tools"):
            payload["tool_choice"] = body.tool_choice

    if body.stream:
        return StreamingResponse(
            _stream_proxy(decision, payload, pii_result.token_map, force_local=force_local),
            media_type="text/event-stream",
        )

    cascade_meta: dict[str, Any] = {}
    critic_meta: dict[str, Any] | None = None
    models_chain = [decision.model]
    if auto_plan and auto_plan.fallbacks:
        models_chain = list(auto_plan.fallbacks)

    if auto_plan and len(models_chain) > 1 and not body.vit_skip_orchestrator:
        from vit_ai_hub.orchestrator.cascade import cascade_chat

        async def _one(dec, pl):
            return await _chat_with_tools(dec, pl, studio=body.studio)

        def _res(mid: str):
            return router_engine.resolve(mid, force_local=force_local)

        try:
            data, cascade_meta = await cascade_chat(
                models=models_chain,
                resolve=_res,
                chat_fn=_one,
                payload=payload,
                intent_kind=auto_plan.intent.kind if auto_plan else None,
                force_local=force_local,
            )
            decision = _res(cascade_meta.get("used_model") or decision.model)
        except Exception:
            data = await _chat_with_tools(decision, payload, studio=body.studio)
    else:
        data = await _chat_with_tools(decision, payload, studio=body.studio)

    # Maker-checker (critic) — Azure evaluator-optimizer pattern
    want_critic = False
    if auto_plan and not body.vit_skip_orchestrator:
        want_critic = auto_plan.use_critic if body.vit_critic is None else bool(body.vit_critic)
    if want_critic:
        try:
            from vit_ai_hub.orchestrator.critic import run_critic_loop

            draft = ""
            try:
                draft = data["choices"][0]["message"].get("content") or ""
            except Exception:
                draft = ""

            async def chat_once(model: str, messages: list[dict[str, Any]]) -> str:
                fake = ChatCompletionRequest(
                    model=model,
                    messages=[ChatMessage(**m) for m in messages],
                    vit_enable_tools=False,
                    stream=False,
                    vit_skip_orchestrator=True,
                    vit_auto_team=False,
                    vit_critic=False,
                )
                out = await _handle_chat(fake)
                if isinstance(out, JSONResponse):
                    out = json.loads(out.body.decode())
                try:
                    return out["choices"][0]["message"].get("content") or ""
                except Exception:
                    return ""

            critic_model = "vit/local-light"
            if not decision.local:
                critic_model = "deepseek-reasoner" if "deepseek" in (decision.model or "") else decision.model
            # prefer a different model for critic when possible
            if auto_plan and auto_plan.fallbacks:
                for cand in auto_plan.fallbacks:
                    if cand != decision.model:
                        critic_model = cand
                        break

            critic_meta = await run_critic_loop(
                task=last_user,
                draft=draft,
                intent=auto_plan.intent,
                chat_once=chat_once,
                critic_model=critic_model,
                revise_model=decision.model,
            )
            if critic_meta.get("used") and critic_meta.get("final"):
                data["choices"][0]["message"]["content"] = critic_meta["final"]
        except Exception as exc:
            critic_meta = {"used": False, "error": str(exc)}

    # Second opinion (quality stack) — ander model verbetert concept
    second_meta: dict[str, Any] | None = None
    if (
        auto_plan
        and not body.vit_skip_orchestrator
        and not body.stream
        and not (auto_plan.use_team if auto_plan else False)
    ):
        try:
            from vit_ai_hub.orchestrator.quality import (
                pick_opinion_model,
                run_second_opinion,
                want_second_opinion,
            )

            if want_second_opinion(
                auto_plan.intent,
                tradeoff=auto_plan.tradeoff or body.vit_tradeoff or "quality",
                use_team=bool(auto_plan.use_team),
            ) or is_max:
                draft2 = ""
                try:
                    draft2 = data["choices"][0]["message"].get("content") or ""
                except Exception:
                    draft2 = ""

                async def chat_once2(model: str, messages: list[dict[str, Any]]) -> str:
                    fake = ChatCompletionRequest(
                        model=model,
                        messages=[ChatMessage(**m) for m in messages],
                        vit_enable_tools=False,
                        stream=False,
                        vit_skip_orchestrator=True,
                        vit_auto_team=False,
                        vit_critic=False,
                    )
                    out = await _handle_chat(fake)
                    if isinstance(out, JSONResponse):
                        out = json.loads(out.body.decode())
                    try:
                        return out["choices"][0]["message"].get("content") or ""
                    except Exception:
                        return ""

                opinion_model = pick_opinion_model(
                    decision.model, auto_plan.fallbacks if auto_plan else None
                )
                if opinion_model:
                    second_meta = await run_second_opinion(
                        task=last_user,
                        draft=draft2,
                        opinion_model=opinion_model,
                        chat_once=chat_once2,
                    )
                    if second_meta.get("used") and second_meta.get("final"):
                        data["choices"][0]["message"]["content"] = second_meta["final"]
        except Exception as exc:
            second_meta = {"used": False, "error": str(exc)}

    # rehydrate assistant content
    try:
        content = data["choices"][0]["message"].get("content")
        if isinstance(content, str) and pii_result.token_map:
            data["choices"][0]["message"]["content"] = pii.rehydrate(content, pii_result.token_map)
    except Exception:
        pass

    session_id = (body.vit_session_id or "").strip() or None
    memory_save: dict[str, Any] | None = None
    if session_id:
        try:
            from vit_ai_hub.memory import save_conversation

            reply = ""
            try:
                reply = data["choices"][0]["message"].get("content") or ""
            except Exception:
                reply = ""
            # Original user turns (without injected system prefix)
            user_turns = [m.model_dump() for m in body.messages if m.role in {"user", "assistant"}]
            if reply:
                user_turns = [*user_turns, {"role": "assistant", "content": reply}]
            memory_save = save_conversation(
                session_id,
                user_turns,
                model=decision.model,
                studio=body.studio,
            )
        except Exception as exc:
            memory_save = {"ok": False, "error": str(exc)}

    tool_trace = data.pop("_vit_tool_trace", None)
    tool_rounds = data.pop("_vit_tool_rounds", None)
    data["vit"] = {
        "backend": decision.backend.name,
        "model": decision.model,
        "requested_model": body.model or settings.vit_default_model,
        "local": decision.local,
        "pii_action": pii_result.action,
        "pii_forced_local": force_local,
        "pii_finding_types": sorted({f.name for f in pii_result.findings}),
        "studio": body.studio,
        "workspace": body.workspace,
        "orchestrator": auto_plan.to_dict() if auto_plan else None,
        "cascade": cascade_meta or None,
        "critic": critic_meta,
        "session_id": session_id,
        "shared_memory": bool(shared_memory),
        "memory_save": memory_save,
        "agent_rounds": tool_rounds,
        "tool_trace": tool_trace[-40:] if isinstance(tool_trace, list) else None,
        "agent_max_rounds": _tool_max_rounds(body.studio),
        "second_opinion": second_meta,
        "local_prep": (
            {
                "used": bool(use_prep and prep_meta and prep_meta.get("ok")),
                "files": (prep_meta or {}).get("files"),
                "est_tokens": (prep_meta or {}).get("est_tokens"),
                "est_tokens_without_prep": (prep_meta or {}).get("est_tokens_without_prep"),
                "chars": (prep_meta or {}).get("chars"),
            }
            if prep_meta
            else None
        ),
        "quality_stack": {
            "critic": bool(critic_meta and critic_meta.get("used")),
            "second_opinion": bool(second_meta and second_meta.get("used")),
            "shared_memory": bool(shared_memory),
            "knowledge": bool(knowledge),
            "max_mode": is_max,
            "local_prep": bool(use_prep and prep_meta and prep_meta.get("ok")),
        },
    }
    return JSONResponse(data)


async def _handle_auto_team(body: ChatCompletionRequest, task: str, auto_plan) -> JSONResponse:
    """Voer orchestrator-team uit en verpak als chat-completion."""
    from vit_ai_hub.agents import run_team

    async def chat_fn(*, messages, model, studio, workspace, tools):
        fake = ChatCompletionRequest(
            model=model,
            messages=[ChatMessage(**m) for m in messages],
            vit_enable_tools=bool(tools),
            studio=studio,
            workspace=workspace,
            stream=False,
            vit_skip_orchestrator=True,
            vit_auto_team=False,
        )
        result = await _handle_chat(fake)
        if isinstance(result, JSONResponse):
            return json.loads(result.body.decode())
        if isinstance(result, dict):
            return result
        raise RuntimeError("onverwacht chat-antwoord")

    team_result = await run_team(
        auto_plan.team_id,
        task=task,
        workspace=body.workspace,
        role_models=auto_plan.role_models or None,
        smart_models=True,
        chat_fn=chat_fn,
    )
    final = team_result.get("final") or ""
    if not final and team_result.get("steps"):
        parts = [
            f"### {s.get('agent_name') or s.get('label')}\n{s.get('content')}"
            for s in team_result["steps"]
            if s.get("ok") and s.get("content")
        ]
        final = "\n\n".join(parts)
    header = (
        f"_VIT Auto · team `{auto_plan.team_id}` · {auto_plan.summary}_\n\n"
        if auto_plan.summary
        else ""
    )
    content = header + (final or "(geen team-output)")
    session_id = (body.vit_session_id or "").strip() or None
    memory_save: dict[str, Any] | None = None
    if session_id:
        try:
            from vit_ai_hub.memory import save_conversation

            user_turns = [m.model_dump() for m in body.messages if m.role in {"user", "assistant"}]
            user_turns = [*user_turns, {"role": "assistant", "content": content}]
            memory_save = save_conversation(
                session_id,
                user_turns,
                model="vit/auto",
                studio=auto_plan.studio or body.studio,
            )
        except Exception as exc:
            memory_save = {"ok": False, "error": str(exc)}
    data = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "model": "vit/auto",
        "vit": {
            "backend": "orchestrator",
            "model": "vit/auto",
            "requested_model": body.model or "vit/auto",
            "local": False,
            "studio": auto_plan.studio or body.studio,
            "workspace": body.workspace,
            "auto_team": True,
            "session_id": session_id,
            "memory_save": memory_save,
            "team": {
                "id": team_result.get("team_id"),
                "name": team_result.get("team_name"),
                "steps": [
                    {
                        "agent": s.get("agent_name"),
                        "role": s.get("role"),
                        "model": s.get("model"),
                        "model_reason": s.get("model_reason"),
                        "ok": s.get("ok"),
                        "error": s.get("error"),
                    }
                    for s in (team_result.get("steps") or [])
                ],
                "elapsed_sec": team_result.get("elapsed_sec"),
            },
            "orchestrator": auto_plan.to_dict(),
        },
    }
    return JSONResponse(data)


def _tool_max_rounds(studio: str | None, model: str | None = None) -> int:
    """Software/self/apps: lange Cursor-achtige agent-loop; overig korter."""
    s = (studio or "").strip().lower()
    if s in {"software", "self", "apps", "webdesign"}:
        return 28
    if s in {"ops", "visual"}:
        return 12
    return 8


async def _chat_with_tools(
    decision,
    payload: dict[str, Any],
    max_rounds: int | None = None,
    *,
    studio: str | None = None,
) -> dict[str, Any]:
    rounds = max_rounds if max_rounds is not None else _tool_max_rounds(studio)
    data = await decision.backend.chat_completions(payload)
    tool_trace: list[dict[str, Any]] = []
    for i in range(rounds):
        try:
            message = data["choices"][0]["message"]
        except Exception:
            data["_vit_tool_trace"] = tool_trace
            return data
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            data["_vit_tool_trace"] = tool_trace
            data["_vit_tool_rounds"] = i
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
            entry: dict[str, Any] = {
                "round": i + 1,
                "tool": name,
                "ok": '"error"' not in (result or "")[:120] and "'error'" not in (result or "")[:80],
            }
            if name in {"search_replace", "write_workspace_file", "read_workspace_file"}:
                entry["path"] = str(args.get("path") or "")[:200]
            if name == "search_replace":
                old_s = str(args.get("old_str") or "")
                new_s = str(args.get("new_str") or "")
                entry["diff"] = {
                    "path": entry.get("path"),
                    "old": old_s[:2000],
                    "new": new_s[:2000],
                }
            tool_trace.append(entry)
            payload["messages"].append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or str(uuid.uuid4()),
                    "content": result,
                }
            )
        data = await decision.backend.chat_completions(payload)
    data["_vit_tool_trace"] = tool_trace
    data["_vit_tool_rounds"] = rounds
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


@app.get("/api/ops/status")
async def api_ops_status(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.ops import ops_status

    _localhost_only(request)
    return ops_status()


@app.post("/api/ops/ensure-env")
async def api_ops_ensure_env(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.ops.client import ensure_ops_env_template

    _localhost_only(request)
    return ensure_ops_env_template()


@app.post("/api/ops/action")
async def api_ops_action(request: Request, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.ops import run_ops_action

    _localhost_only(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object verwacht")
    action = str(body.get("action") or "").strip()
    if not action:
        raise HTTPException(status_code=400, detail="action verplicht")
    args = body.get("arguments") if isinstance(body.get("arguments"), dict) else {
        k: v for k, v in body.items() if k != "action"
    }
    return run_ops_action(action, args)


@app.get("/api/import/status")
async def import_status(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.local_mac import detect_local_apps

    found = find_export_zips()
    return {
        "knowledge": knowledge_stats(),
        "cursor_roots": [str(p) for p in cursor_import.candidate_roots()],
        "local_apps": detect_local_apps(),
        "export_zips": {
            "chatgpt": [str(p) for p in found.get("chatgpt") or []],
            "claude": [str(p) for p in found.get("claude") or []],
        },
    }


@app.post("/api/import/all")
async def import_all(_: None = Depends(_auth)) -> dict[str, Any]:
    """Één klik: Cursor + lokale Mac-apps + skills + nieuwste ChatGPT/Claude zips."""
    return import_all_one_click()


@app.get("/api/skills")
async def api_list_skills(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import list_hub_skills

    return list_hub_skills()


@app.post("/api/skills")
async def api_add_skill(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import add_skill

    return add_skill(
        name=str(body.get("name") or ""),
        description=str(body.get("description") or ""),
        content=str(body.get("content") or ""),
        promote_agent=bool(body.get("promote_agent", True)),
    )


@app.post("/api/skills/template")
async def api_skill_template(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import add_skill_template

    return add_skill_template(str(body.get("id") or body.get("template") or ""))


@app.post("/api/skills/upload")
async def api_skill_upload(
    file: UploadFile = File(...),
    _: None = Depends(_auth),
) -> dict[str, Any]:
    from vit_ai_hub.extensions import import_skill_markdown

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return import_skill_markdown(text, filename=file.filename or "")


@app.post("/api/import/skills")
async def api_import_skills(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.skills import harvest_skills

    return harvest_skills(promote_agents=True)


@app.post("/api/import/full")
async def api_import_full(_: None = Depends(_auth)) -> dict[str, Any]:
    """Alles van Claude/ChatGPT/Cursor: mirror + settings/MCP/rules/prompts/skills/chats."""
    from vit_ai_hub.importing.full_migrate import migrate_everything

    return migrate_everything(promote_skills=True)


@app.get("/api/migrate/profile")
async def api_migrate_profile(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.full_migrate import load_active_profile

    return {"profile": load_active_profile()}


@app.get("/api/mcp/servers")
async def api_mcp_servers(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import list_mcp_managed

    return list_mcp_managed()


@app.post("/api/mcp/servers")
async def api_mcp_add(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import add_mcp_server, add_mcp_preset, import_mcp_json

    # preset: {"preset":"filesystem"}
    if body.get("preset"):
        return add_mcp_preset(
            str(body["preset"]),
            extra_args=str(body.get("extra_args") or ""),
            env=body.get("env") if isinstance(body.get("env"), dict) else None,
        )
    # paste Cursor mcp.json
    if body.get("mcpServers") or body.get("json"):
        raw = body.get("json") if body.get("json") else body
        return import_mcp_json(raw if isinstance(raw, (dict, str)) else str(raw))

    args = body.get("args")
    return add_mcp_server(
        name=str(body.get("name") or ""),
        command=str(body.get("command") or ""),
        args=args if isinstance(args, (list, str)) else str(body.get("args") or ""),
        url=str(body.get("url") or ""),
        env=body.get("env") if isinstance(body.get("env"), dict) else None,
    )


@app.delete("/api/mcp/servers/{name}")
async def api_mcp_remove(name: str, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import remove_mcp_server

    return remove_mcp_server(name)


@app.get("/api/extensions")
async def api_extensions(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import extensions_overview

    return extensions_overview()


@app.get("/api/extensions/apps")
async def api_ext_apps(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import list_custom_apps

    return list_custom_apps()


@app.post("/api/extensions/apps")
async def api_ext_apps_add(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import add_app_preset, add_custom_app

    if body.get("preset"):
        return add_app_preset(str(body["preset"]))
    return add_custom_app(
        name=str(body.get("name") or ""),
        app_name=str(body.get("app_name") or body.get("app") or ""),
        aliases=body.get("aliases"),
        web=str(body.get("web") or ""),
    )


@app.delete("/api/extensions/apps/{app_id}")
async def api_ext_apps_remove(app_id: str, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.extensions import remove_custom_app

    return remove_custom_app(app_id)


@app.post("/api/import/cursor")
async def import_cursor(_: None = Depends(_auth)) -> dict[str, Any]:
    return cursor_import.import_local()


@app.get("/api/import/local-detect")
async def import_local_detect(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.local_mac import detect_local_apps

    return detect_local_apps()


@app.post("/api/import/local-mac")
async def import_local_mac(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.local_mac import harvest_all_local

    return harvest_all_local()


@app.post("/api/import/request-exports")
async def import_request_exports(_: None = Depends(_auth)) -> dict[str, Any]:
    """Open ChatGPT/Claude export-schermen op de Mac (osascript + URLs)."""
    from vit_ai_hub.importing.local_mac import request_official_exports

    return request_official_exports()


@app.post("/api/import/wait-exports")
async def import_wait_exports(
    timeout_sec: int = 120,
    _: None = Depends(_auth),
) -> dict[str, Any]:
    """Wacht op nieuwe export-zips in Downloads/Desktop en importeer ze."""
    from vit_ai_hub.importing.local_mac import wait_and_import_exports

    # keep request bounded for API responsiveness; GUI can call again
    timeout_sec = max(5, min(int(timeout_sec or 120), 600))
    return wait_and_import_exports(timeout_sec=timeout_sec, poll_sec=3)


@app.post("/api/import/chatgpt-live")
async def import_chatgpt_live(_: None = Depends(_auth)) -> dict[str, Any]:
    """Lees ChatGPT zoals jij hem ziet (Accessibility + optionele Keychain-decrypt)."""
    from vit_ai_hub.importing.chatgpt_live import harvest_chatgpt_readable

    return harvest_chatgpt_readable()


@app.post("/api/import/claude-live")
async def import_claude_live(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.claude_live import harvest_via_accessibility

    return harvest_via_accessibility()


@app.post("/api/sync/once")
async def sync_once_api(include_ax: bool = False, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.sync import sync_once

    return sync_once(include_ax=include_ax)


@app.post("/api/sync/start")
async def sync_start(interval_sec: int = 300, include_ax: bool = False, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.sync import start_sync

    return start_sync(interval_sec=interval_sec, include_ax=include_ax)


@app.post("/api/sync/stop")
async def sync_stop(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.sync import stop_sync

    return stop_sync()


@app.get("/api/sync/status")
async def sync_status(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.sync import get_sync_status

    return get_sync_status()


@app.post("/api/knowledge/reindex")
async def knowledge_reindex(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.index_fts import rebuild_index

    return rebuild_index()


@app.post("/api/import/upload")
async def import_upload(
    file: UploadFile = File(...),
    source: str | None = Form(default=None),
    _: None = Depends(_auth),
) -> dict[str, Any]:
    suffix = Path(file.filename or "export.bin").suffix or ".zip"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        return import_file(tmp_path, source=source or None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/api/knowledge/search")
async def api_knowledge_search(q: str = "", _: None = Depends(_auth)) -> dict[str, Any]:
    return {"query": q, "hits": search_knowledge(q, limit=20)}


@app.get("/api/knowledge/conversations")
async def api_knowledge_conversations(
    q: str = "",
    source: str = "",
    limit: int = 40,
    _: None = Depends(_auth),
) -> dict[str, Any]:
    from vit_ai_hub.importing.store import list_conversations

    return {
        "ok": True,
        "items": list_conversations(limit=limit, source=source or None, q=q or None),
    }


@app.get("/api/knowledge/conversations/{conv_id}")
async def api_knowledge_conversation_get(conv_id: str, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.importing.store import get_imported_conversation

    row = get_imported_conversation(conv_id)
    if not row:
        raise HTTPException(status_code=404, detail="conversatie niet gevonden")
    return {"ok": True, "conversation": row}


@app.post("/api/import/zips-now")
async def import_zips_now(_: None = Depends(_auth)) -> dict[str, Any]:
    """Importeer alle gevonden ChatGPT/Claude export-zips nu (zonder wachten)."""
    from vit_ai_hub.importing.pipeline import find_export_zips, import_file

    found = find_export_zips()
    out: dict[str, Any] = {"ok": True, "chatgpt": [], "claude": [], "errors": []}
    for label in ("chatgpt", "claude"):
        for path in (found.get(label) or [])[:5]:
            try:
                out[label].append({"file": str(path), **import_file(path, source=label)})
            except Exception as exc:
                out["errors"].append({"source": label, "file": str(path), "error": str(exc)})
    return out


@app.get("/api/mac/profile")
async def api_mac_profile(profile: str = "m5-max-128", _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.mac_profile import get_profile, hub_overrides_for_profile, list_profiles

    return {
        "ok": True,
        "profiles": list_profiles(),
        "active": get_profile(profile),
        "hub_overrides": hub_overrides_for_profile(profile),
    }


@app.get("/api/media/status")
async def api_media_status(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.tools.media import media_capabilities

    return {"ok": True, **media_capabilities()}


@app.get("/api/vit-apps")
async def api_vit_apps(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.tools.vit_apps import list_vit_apps

    return list_vit_apps()


@app.post("/api/vit-apps/{app_id}/open")
async def api_vit_app_open(app_id: str, body: dict[str, Any] | None = None, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.tools.vit_apps import open_vit_app

    body = body or {}
    return open_vit_app(
        app_id,
        action=str(body.get("action") or "open"),
        to=str(body.get("to") or ""),
        subject=str(body.get("subject") or ""),
        body=str(body.get("body") or ""),
        path=str(body.get("path") or ""),
        query=str(body.get("query") or ""),
        host=str(body.get("host") or ""),
        prefer_web=bool(body.get("prefer_web")),
    )


@app.post("/api/vit-apps/handoff")
async def api_vit_app_handoff(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.tools.vit_apps import handoff_file

    return handoff_file(
        str(body.get("path") or ""),
        prefer_app=str(body.get("prefer_app") or ""),
    )


@app.get("/docs/MAC_M5_MAX.md")
async def docs_mac_m5() -> FileResponse:
    path = ROOT / "docs" / "MAC_M5_MAX.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="doc ontbreekt")
    return FileResponse(path, media_type="text/markdown; charset=utf-8")


@app.get("/api/memory/stats")
async def api_memory_stats(_: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.memory import memory_stats

    return {"ok": True, **memory_stats()}


@app.get("/api/memory/search")
async def api_memory_search(q: str = "", _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.memory import search_memories

    return {"query": q, "items": search_memories(q, limit=30)}


@app.post("/api/memory/pin")
async def api_memory_pin(body: dict[str, Any], _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.memory import pin_memory

    content = str(body.get("content") or body.get("value") or "").strip()
    tags = str(body.get("tags") or body.get("key") or "").strip()
    pii = get_pii_engine()
    scanned = pii.process(content, destination_local=False)
    if scanned.has_pii:
        raise HTTPException(status_code=400, detail="Memory weigert PII/secrets")
    return pin_memory(content, kind=str(body.get("kind") or "fact"), tags=tags)


@app.get("/api/memory/conversation/{session_id}")
async def api_memory_conversation(session_id: str, _: None = Depends(_auth)) -> dict[str, Any]:
    from vit_ai_hub.memory import get_conversation

    conv = get_conversation(session_id)
    if not conv:
        return {"ok": False, "session_id": session_id, "messages": []}
    return {"ok": True, **conv}


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