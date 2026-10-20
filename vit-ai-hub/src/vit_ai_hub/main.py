from __future__ import annotations

import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    vit_enable_tools: bool = False
    studio: str | None = None
    workspace: str | None = None
    vit_auto_team: bool | None = None  # None = config default; False = nooit auto-team
    vit_skip_orchestrator: bool = False  # True = geen intent/team (interne team-stappen)
    vit_tradeoff: str | None = None  # quality | cost | latency
    vit_critic: bool | None = None  # None = config/auto; False = skip critic


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
        "BRIDGE_API_KEY",
        "OMNIROUTE_API_KEY",
        "VIT_LOCAL_LIGHT_MODEL",
        "VIT_LOCAL_HEAVY_MODEL",
    ):
        if body.get(k):
            secrets[k] = str(body[k])
    if secrets:
        save_secrets(secrets)
    return bootstrap_all(open_a11y=bool(body.get("open_a11y")))


@app.post("/api/setup/open-accessibility")
async def api_setup_a11y() -> dict[str, Any]:
    from vit_ai_hub.setup_api import open_accessibility_settings

    return open_accessibility_settings()


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
    return open_guide(target)


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
    from vit_ai_hub.config import get_settings

    settings = get_settings()
    dest = Path.home() / ".continue" / "config.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    cfg = {
        "models": [
            {
                "title": "VIT AI Hub (auto)",
                "provider": "openai",
                "model": "vit/auto",
                "apiBase": "http://127.0.0.1:8787/v1",
                "apiKey": settings.vit_gateway_token or "vit-local",
            },
            {
                "title": "VIT local light",
                "provider": "openai",
                "model": "vit/local-light",
                "apiBase": "http://127.0.0.1:8787/v1",
                "apiKey": settings.vit_gateway_token or "vit-local",
            },
        ],
        "tabAutocompleteModel": {
            "title": "VIT autocomplete",
            "provider": "openai",
            "model": "vit/local-light",
            "apiBase": "http://127.0.0.1:8787/v1",
            "apiKey": settings.vit_gateway_token or "vit-local",
        },
        "allowAnonymousTelemetry": False,
    }
    dest.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "path": str(dest),
        "next": [
            "Installeer VS Code of Cursor-alternatief Zed",
            "Installeer Continue-extensie",
            "Herstart editor — model 'VIT AI Hub (auto)' kiezen",
            "Cursor-abo kun je daarna opzeggen als dit bevalt",
        ],
    }


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
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content")
            last_user = content if isinstance(content, str) else str(content)
            break

    auto_plan = None
    is_auto = (requested_model or "").strip().lower() in {"vit/auto", "auto", "vit/smart", ""}
    if is_auto and not body.vit_skip_orchestrator:
        try:
            _, auto_plan = router_engine.resolve_smart(
                text=last_user,
                studio=body.studio,
                workspace=body.workspace,
                force_local=False,
                allow_team=body.vit_auto_team,
                tradeoff=body.vit_tradeoff,
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
    prefix: list[dict[str, Any]] = []
    from vit_ai_hub.studio import studio_system_prompt

    studio_prompt = studio_system_prompt(body.studio)
    if studio_prompt:
        prefix.append({"role": "system", "content": studio_prompt})
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
            prefix.append({"role": "system", "content": migrated})
    except Exception:
        pass
    if body.workspace:
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
    if knowledge:
        prefix.append({"role": "system", "content": knowledge})
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

    cascade_meta: dict[str, Any] = {}
    critic_meta: dict[str, Any] | None = None
    models_chain = [decision.model]
    if auto_plan and auto_plan.fallbacks:
        models_chain = list(auto_plan.fallbacks)

    if auto_plan and len(models_chain) > 1 and not body.vit_skip_orchestrator:
        from vit_ai_hub.orchestrator.cascade import cascade_chat

        async def _one(dec, pl):
            return await _chat_with_tools(dec, pl)

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
            data = await _chat_with_tools(decision, payload)
    else:
        data = await _chat_with_tools(decision, payload)

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
    from vit_ai_hub.importing.store import list_skills, stats

    return {"skills": list_skills(), "knowledge": stats()}


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
    from vit_ai_hub.tools.mcp_runtime import list_servers

    return list_servers()


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