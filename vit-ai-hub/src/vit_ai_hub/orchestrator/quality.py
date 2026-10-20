"""Maximale output-kwaliteit: stack alle hub-trucjes (critic, second opinion, prompt)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from vit_ai_hub.config import load_yaml_config
from vit_ai_hub.orchestrator.intent import Intent


def quality_cfg() -> dict[str, Any]:
    return load_yaml_config().get("orchestrator") or {}


def want_second_opinion(intent: Intent, *, tradeoff: str, use_team: bool) -> bool:
    cfg = quality_cfg()
    if use_team:
        return False
    if not cfg.get("second_opinion", True):
        return False
    if (tradeoff or "quality").lower() != "quality":
        return False
    if intent.complexity == "low" and intent.kind in {"simple", "chat", "ops"}:
        return False
    return intent.complexity in {"medium", "high"} or intent.kind in {
        "code",
        "design",
        "complex",
        "marketing",
        "write",
        "seo",
        "self",
        "visual",
    }


def quality_system_addon(*, studio: str | None, tradeoff: str) -> str:
    """Extra system-instructies die alle slimme lagen activeren in het model."""
    bits = [
        "# VIT quality stack (actief)",
        "Je combineert het beste van ChatGPT + Claude + Cursor-werkstijl:",
        "- Lever af: concrete output eerst, korte toelichting daarna.",
        "- Gebruik tools (codebase_search, search_replace, memory, knowledge) i.p.v. gissen.",
        "- Wees scherp: geen filler, geen ‘als AI-model…’, geen valse zekerheid.",
        "- Bij twijfel: noem aannames in één regel, kies de sterkste optie.",
    ]
    if (tradeoff or "").lower() == "quality":
        bits.append("- Tradeoff=quality: liever 10% dieper dan 10% sneller.")
    s = (studio or "").lower()
    if s == "software":
        bits.append("- Code: patch klein, test als het kan, commit alleen op verzoek.")
    if s in {"marketing", "socials", "seo"}:
        bits.append("- Growth: merkbaar, platform-native, geen generieke AI-taal.")
    return "\n".join(bits)


async def run_second_opinion(
    *,
    task: str,
    draft: str,
    opinion_model: str,
    chat_once: Callable[[str, list[dict[str, Any]]], Awaitable[str]],
) -> dict[str, Any]:
    """Tweede model verbetert het concept (NotDiamond/ensemble-achtig, 1 ronde)."""
    if not draft.strip() or not opinion_model:
        return {"used": False, "final": draft}
    msgs = [
        {
            "role": "system",
            "content": (
                "Je bent een second-opinion editor. Verbeter het concept tot een "
                "scherper, completer eindantwoord. Behoud feiten; snijd fluff. "
                "Lever ALLEEN het verbeterde eindantwoord."
            ),
        },
        {
            "role": "user",
            "content": f"# Opdracht\n{task}\n\n# Concept\n{draft}\n\nVerbeter.",
        },
    ]
    try:
        improved = await chat_once(opinion_model, msgs)
    except Exception as exc:
        return {"used": False, "final": draft, "error": str(exc)}
    if not (improved or "").strip() or len(improved.strip()) < 20:
        return {"used": False, "final": draft, "reason": "empty"}
    # Prefer longer only if clearly better; always take improved if substantially different
    if improved.strip() == draft.strip():
        return {"used": False, "final": draft, "reason": "unchanged"}
    return {
        "used": True,
        "final": improved.strip(),
        "model": opinion_model,
        "draft_len": len(draft),
        "final_len": len(improved),
    }


def pick_opinion_model(primary: str, fallbacks: list[str] | None) -> str | None:
    """Kies een ander model dan primary voor second opinion."""
    for cand in fallbacks or []:
        if cand and cand != primary and not cand.startswith("vit/local"):
            return cand
    for cand in fallbacks or []:
        if cand and cand != primary:
            return cand
    # cloud/local alternates
    if primary.startswith("vit/local") or "qwen" in primary.lower():
        return "deepseek-chat"
    return "vit/local-light"
