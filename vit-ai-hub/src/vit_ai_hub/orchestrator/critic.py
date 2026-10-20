"""Maker-checker / evaluator-optimizer loop (Azure pattern), bounded."""

from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from vit_ai_hub.config import load_yaml_config
from vit_ai_hub.orchestrator.intent import Intent


def critic_enabled(intent: Intent, *, tradeoff: str | None = None) -> bool:
    cfg = load_yaml_config().get("orchestrator") or {}
    if not cfg.get("critic", True):
        return False
    t = (tradeoff or cfg.get("tradeoff") or "quality").lower()
    # quality-modus: critic vaker aan
    if t == "quality":
        if intent.kind in {"simple"} and intent.complexity == "low":
            return False
        return True
    if intent.kind in {"simple", "chat", "ops"} and intent.complexity == "low":
        return False
    return intent.complexity in {"medium", "high"} or intent.kind in {
        "code",
        "design",
        "complex",
        "self",
        "marketing",
        "socials",
        "seo",
        "visual",
        "write",
    }


def max_rounds() -> int:
    cfg = load_yaml_config().get("orchestrator") or {}
    return max(0, min(3, int(cfg.get("critic_rounds") or 1)))


_PASS = re.compile(r"\b(PASS|GOEDGEKEURD|APPROVED)\b", re.I)
_FAIL = re.compile(r"\b(FAIL|AFGEKEURD|REJECT|REVISE)\b", re.I)


def parse_critic(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    verdict = "revise"
    if _PASS.search(t) and not _FAIL.search(t):
        verdict = "pass"
    elif _FAIL.search(t):
        verdict = "fail"
    # JSON block optional
    m = re.search(r"\{[^{}]+\}", t)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and obj.get("verdict"):
                v = str(obj["verdict"]).lower()
                if v in {"pass", "fail", "revise"}:
                    verdict = v
                return {"verdict": verdict, "feedback": obj.get("feedback") or t, "raw": t}
        except json.JSONDecodeError:
            pass
    return {"verdict": verdict, "feedback": t, "raw": t}


async def run_critic_loop(
    *,
    task: str,
    draft: str,
    intent: Intent,
    chat_once: Callable[[str, list[dict[str, Any]]], Awaitable[str]],
    critic_model: str,
    revise_model: str,
) -> dict[str, Any]:
    """
    chat_once(model, messages) -> assistant text
    Max 1–2 rounds. Bij pass: draft behouden. Bij fail: revise.
    """
    if max_rounds() < 1:
        return {"used": False, "final": draft, "rounds": []}

    current = draft
    rounds: list[dict[str, Any]] = []
    for i in range(max_rounds()):
        critic_msgs = [
            {
                "role": "system",
                "content": (
                    "Je bent een strenge QA-critic. Beoordeel het concept tegen de opdracht. "
                    "Antwoord met JSON: {\"verdict\":\"pass|fail|revise\",\"feedback\":\"…\"} "
                    "en eventueel PASS/FAIL. Wees concreet: wat mist, wat is fout, wat moet anders. "
                    "Geen klant-PII."
                ),
            },
            {
                "role": "user",
                "content": f"# Opdracht\n{task}\n\n# Concept\n{current}\n\nBeoordeel.",
            },
        ]
        critique = await chat_once(critic_model, critic_msgs)
        parsed = parse_critic(critique)
        rounds.append({"round": i + 1, **parsed, "draft_len": len(current)})
        if parsed["verdict"] == "pass":
            return {"used": True, "final": current, "rounds": rounds, "verdict": "pass"}
        # revise
        revise_msgs = [
            {
                "role": "system",
                "content": (
                    "Je herziet je eerdere antwoord op basis van QA-feedback. "
                    "Lever het VOLLEDIGE verbeterde eindantwoord (geen meta-commentaar)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"# Opdracht\n{task}\n\n# Eerdere versie\n{current}\n\n"
                    f"# Feedback\n{parsed.get('feedback')}\n\nHerschrijf het eindantwoord."
                ),
            },
        ]
        current = await chat_once(revise_model, revise_msgs)
    return {"used": True, "final": current, "rounds": rounds, "verdict": "max_rounds"}
