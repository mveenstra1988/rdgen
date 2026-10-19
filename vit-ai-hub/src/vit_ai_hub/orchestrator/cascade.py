"""Cascade: probeer fallback-modellen bij fout/lege output (attempt budget)."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from vit_ai_hub.orchestrator.telemetry import log_route


ChatFn = Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]]
ResolveFn = Callable[[str], Any]


async def cascade_chat(
    *,
    models: list[str],
    resolve: ResolveFn,
    chat_fn: ChatFn,
    payload: dict[str, Any],
    intent_kind: str | None = None,
    force_local: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Probeert models in volgorde. Stopt bij bruikbaar antwoord.
    chat_fn(decision, payload) -> response dict
    resolve(model_id) -> RouteDecision
    """
    attempts: list[dict[str, Any]] = []
    last_err: str | None = None
    started = time.time()

    for i, mid in enumerate(models):
        t0 = time.time()
        try:
            decision = resolve(mid)
            if force_local and not decision.local:
                attempts.append(
                    {
                        "model": mid,
                        "ok": False,
                        "error": "skip non-local under force_local",
                        "ms": 0,
                    }
                )
                continue
            pl = {**payload, "model": decision.model}
            data = await chat_fn(decision, pl)
            content = ""
            try:
                content = data["choices"][0]["message"].get("content") or ""
            except Exception:
                content = ""
            # empty / obvious failure → try next
            bad = (
                not content.strip()
                or content.strip().lower().startswith("(geen")
                or "error" in (data.get("error") or {})
            )
            elapsed = int((time.time() - t0) * 1000)
            if bad and i < len(models) - 1:
                attempts.append(
                    {
                        "model": mid,
                        "backend": decision.backend.name,
                        "ok": False,
                        "error": "empty_or_useless",
                        "ms": elapsed,
                    }
                )
                continue
            attempts.append(
                {
                    "model": mid,
                    "backend": decision.backend.name,
                    "ok": True,
                    "ms": elapsed,
                    "fallback_index": i,
                }
            )
            meta = {
                "used_model": decision.model,
                "used_backend": decision.backend.name,
                "local": decision.local,
                "fallback_index": i,
                "attempts": attempts,
                "elapsed_ms": int((time.time() - started) * 1000),
            }
            log_route(
                {
                    "event": "cascade_ok",
                    "intent": intent_kind,
                    "primary": models[0],
                    "used": decision.model,
                    "fallback_index": i,
                    "attempts": len(attempts),
                }
            )
            return data, meta
        except Exception as exc:
            last_err = str(exc)
            attempts.append(
                {
                    "model": mid,
                    "ok": False,
                    "error": last_err[:400],
                    "ms": int((time.time() - t0) * 1000),
                }
            )
            continue

    log_route(
        {
            "event": "cascade_fail",
            "intent": intent_kind,
            "primary": models[0] if models else None,
            "attempts": len(attempts),
            "error": last_err,
        }
    )
    raise RuntimeError(
        f"Alle cascade-modellen faalden ({len(attempts)} pogingen). Laatste: {last_err}"
    )
