"""Run een agent-team: pipeline (sequentieel) of board (allen + synthesize)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from vit_ai_hub.agents.store import get_agent, get_team
from vit_ai_hub.studio import studio_system_prompt


async def run_team(
    team_id: str,
    *,
    task: str,
    workspace: str | None = None,
    model_override: str | None = None,
    role_models: dict[str, str] | None = None,
    smart_models: bool = True,
    chat_fn,
) -> dict[str, Any]:
    """
    chat_fn: async (messages, model, studio, workspace, tools) -> dict with content + vit meta
    role_models: optionele map agent_id → model (van orchestrator)
    smart_models: bij vit/auto per agent het beste model kiezen
    """
    team = get_team(team_id)
    if not team:
        return {"ok": False, "error": "team niet gevonden"}
    task = (task or "").strip()
    if not task:
        return {"ok": False, "error": "lege taak"}

    members = sorted(team.get("members") or [], key=lambda m: int(m.get("order", 0)))
    if not members:
        return {"ok": False, "error": "team heeft geen agents"}

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    started = time.time()
    steps: list[dict[str, Any]] = []
    context_bits: list[str] = [f"# Opdracht\n{task}"]
    mode = (team.get("mode") or "pipeline").lower()
    role_models = role_models or {}

    intent = None
    if smart_models and not model_override:
        try:
            from vit_ai_hub.orchestrator import classify_intent

            intent = classify_intent(
                task, studio=team.get("studio"), workspace=workspace
            )
        except Exception:
            intent = None

    def _model_for(agent: dict[str, Any]) -> tuple[str, str | None]:
        aid = agent.get("id") or ""
        if model_override:
            return model_override, "override"
        if aid in role_models:
            return role_models[aid], "orchestrator.role"
        raw = str(agent.get("model") or "vit/auto").strip()
        if smart_models and intent and raw in {"vit/auto", "auto", "vit/smart", ""}:
            from vit_ai_hub.orchestrator import pick_model_for_intent

            pick = pick_model_for_intent(
                intent, role=str(agent.get("role") or agent.get("name") or "")
            )
            return pick.model, pick.reason
        return raw or "vit/auto", None

    async def _run_one(agent_id: str, brief: str, step_label: str) -> dict[str, Any]:
        agent = get_agent(agent_id)
        if not agent:
            return {
                "ok": False,
                "agent_id": agent_id,
                "label": step_label,
                "error": "agent ontbreekt",
            }
        system_parts = [
            f"Je bent agent «{agent.get('name')}» ({agent.get('role') or 'member'}) "
            f"in team «{team.get('name')}».",
            str(agent.get("system") or "").strip(),
        ]
        studio = agent.get("studio") or team.get("studio") or "chat"
        studio_sys = studio_system_prompt(studio)
        if studio_sys:
            system_parts.append(studio_sys)
        if workspace:
            system_parts.append(
                f"Workspace: {workspace}. Gebruik workspace-tools met dit pad waar nodig."
            )
        system_parts.append(
            "Antwoord concreet. Lever output die de volgende teammate kan gebruiken. "
            "Geen klant-PII naar cloud."
        )
        messages = [
            {"role": "system", "content": "\n\n".join(p for p in system_parts if p)},
            {"role": "user", "content": brief},
        ]
        model, model_reason = _model_for(agent)
        try:
            result = await chat_fn(
                messages=messages,
                model=model,
                studio=studio,
                workspace=workspace,
                tools=bool(agent.get("tools", True)),
            )
        except Exception as exc:
            return {
                "ok": False,
                "agent_id": agent_id,
                "agent_name": agent.get("name"),
                "color": agent.get("color"),
                "label": step_label,
                "model": model,
                "model_reason": model_reason,
                "error": str(exc),
            }
        content = ""
        try:
            content = result.get("choices", [{}])[0].get("message", {}).get("content") or ""
        except Exception:
            content = str(result)[:4000]
        return {
            "ok": True,
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "role": agent.get("role"),
            "color": agent.get("color"),
            "label": step_label,
            "model": model,
            "model_reason": model_reason,
            "studio": studio,
            "content": content,
            "vit": result.get("vit"),
        }

    if mode == "board":
        # echte parallelle board-run, daarna lead synthesize
        import asyncio

        async def _board_member(m: dict[str, Any]) -> dict[str, Any]:
            agent = get_agent(m["agent_id"])
            label = m.get("label") or (agent or {}).get("name") or m["agent_id"]
            return await _run_one(
                m["agent_id"],
                f"{task}\n\nGeef jouw specialisten-bijdrage (kort en bruikbaar).",
                label,
            )

        board_results = await asyncio.gather(*[_board_member(m) for m in members])
        board_outs: list[str] = []
        for out in board_results:
            steps.append(out)
            if out.get("ok") and out.get("content"):
                board_outs.append(f"## {out.get('agent_name')}\n{out['content']}")
        lead_id = team.get("lead_agent_id") or members[0]["agent_id"]
        synth_brief = (
            f"{task}\n\n# Bijdragen team\n\n"
            + "\n\n".join(board_outs)
            + "\n\nSynthetiseer tot één eindresultaat / plan / deliverable."
        )
        lead_out = await _run_one(lead_id, synth_brief, "Synthese (lead)")
        steps.append(lead_out)
        final = lead_out.get("content") if lead_out.get("ok") else "\n\n".join(board_outs)
    else:
        # pipeline: elke agent krijgt vorige outputs
        for m in members:
            agent = get_agent(m["agent_id"])
            label = m.get("label") or (agent or {}).get("name") or m["agent_id"]
            brief = "\n\n".join(context_bits) + f"\n\n# Jouw taak als {label}\nLever jouw stuk op basis van het bovenstaande."
            out = await _run_one(m["agent_id"], brief, label)
            steps.append(out)
            if out.get("ok") and out.get("content"):
                context_bits.append(f"# Output — {out.get('agent_name')}\n{out['content']}")
        final = steps[-1].get("content") if steps and steps[-1].get("ok") else ""

    return {
        "ok": True,
        "run_id": run_id,
        "team_id": team_id,
        "team_name": team.get("name"),
        "mode": mode,
        "task": task,
        "workspace": workspace,
        "steps": steps,
        "final": final,
        "elapsed_sec": round(time.time() - started, 2),
    }
