"""Pooled OpenAI-compat backend: probeert volgende abo bij uitputting."""

from __future__ import annotations

from typing import Any, AsyncIterator

from vit_ai_hub.backends.openai_compat import OpenAICompatBackend
from vit_ai_hub.pool.store import (
    mark_failure,
    mark_success,
    pick_account_order,
    tags_for_model,
)


def _parse_status(err: str) -> int | None:
    # "... error 429: ..."
    import re

    m = re.search(r"\berror\s+(\d{3})\b", err)
    if m:
        return int(m.group(1))
    m = re.search(r"\b([45]\d{2})\b", err)
    return int(m.group(1)) if m else None


class PooledBackend:
    """Zelfde interface als OpenAICompatBackend, met multi-abo failover."""

    def __init__(
        self,
        *,
        name: str,
        local: bool = False,
        label: str = "",
        fallback_single: OpenAICompatBackend | None = None,
    ) -> None:
        self.name = name
        self.local = local
        self.label = label or name
        self.fallback_single = fallback_single
        self._last_account_id: str | None = None

    @property
    def base_url(self) -> str:
        order = pick_account_order(self.name)
        if order:
            return order[0].get("base_url") or ""
        if self.fallback_single:
            return self.fallback_single.base_url
        return ""

    @property
    def api_key(self) -> str:
        order = pick_account_order(self.name)
        if order:
            return order[0].get("api_key") or ""
        if self.fallback_single:
            return self.fallback_single.api_key
        return ""

    def _members(self, model: str | None = None) -> list[OpenAICompatBackend]:
        tags = tags_for_model(model or "") if model else None
        # For bridge, tag filter; for others ignore unless cursor
        if self.name not in {"bridge", "cursor"}:
            tags = None
        accounts = pick_account_order(self.name, tags=tags)
        out: list[OpenAICompatBackend] = []
        for a in accounts:
            out.append(
                OpenAICompatBackend(
                    name=self.name,
                    base_url=a.get("base_url") or "",
                    api_key=a.get("api_key") or "",
                    local=self.local,
                    label=str(a.get("label") or self.label),
                )
            )
            # stash id on instance for marking
            setattr(out[-1], "_pool_account_id", a["id"])
        if not out and self.fallback_single and self.fallback_single.base_url:
            out.append(self.fallback_single)
            setattr(out[-1], "_pool_account_id", f"legacy-{self.name}")
        return out

    async def list_models(self) -> list[dict[str, Any]]:
        # try first healthy member
        for member in self._members():
            try:
                models = await member.list_models()
                if models:
                    return models
            except Exception:
                continue
        return []

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = str(payload.get("model") or "")
        members = self._members(model)
        if not members:
            raise RuntimeError(f"Geen gezonde {self.name}-abos in de pool")
        errors: list[str] = []
        for member in members:
            aid = getattr(member, "_pool_account_id", None) or "unknown"
            try:
                data = await member.chat_completions(payload)
                mark_success(aid)
                self._last_account_id = aid
                if isinstance(data, dict):
                    data.setdefault("vit_pool", {})
                    if isinstance(data["vit_pool"], dict):
                        data["vit_pool"] = {
                            "pool": self.name,
                            "account_id": aid,
                            "label": member.label,
                        }
                return data
            except Exception as exc:
                err = str(exc)
                errors.append(f"{aid}: {err[:200]}")
                status = _parse_status(err)
                info = mark_failure(aid, err, status=status)
                # non-exhaustion errors (400 bad request) → don't burn whole pool; still try next if connection
                if status and status < 400:
                    continue
                if not info.get("exhausted") and status and 400 <= status < 500 and status not in {401, 403, 408, 429}:
                    # client error on this account — try next anyway for 401
                    if status not in {401, 403}:
                        raise
                continue
        raise RuntimeError(
            f"{self.name} pool uitgeput of faalde ({len(errors)} abos). "
            + " | ".join(errors[:5])
        )

    async def stream_chat_completions(self, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        model = str(payload.get("model") or "")
        members = self._members(model)
        if not members:
            raise RuntimeError(f"Geen gezonde {self.name}-abos in de pool")
        last_err: Exception | None = None
        for member in members:
            aid = getattr(member, "_pool_account_id", None) or "unknown"
            try:
                # collect first chunk to detect early failure? stream yields — mark success on start
                agen = member.stream_chat_completions(payload)
                first = True
                async for chunk in agen:
                    if first:
                        mark_success(aid)
                        self._last_account_id = aid
                        first = False
                    yield chunk
                return
            except Exception as exc:
                last_err = exc
                err = str(exc)
                status = _parse_status(err)
                mark_failure(aid, err, status=status)
                continue
        raise RuntimeError(str(last_err) if last_err else f"{self.name} pool stream faalde")


def wrap_pooled(
    name: str,
    single: OpenAICompatBackend | None,
    *,
    local: bool = False,
    label: str = "",
) -> PooledBackend | OpenAICompatBackend:
    """Gebruik pool als er ≥1 account is; anders single backend."""
    accounts = pick_account_order(name)
    if len(accounts) >= 1:
        return PooledBackend(
            name=name,
            local=local,
            label=label or (single.label if single else name),
            fallback_single=single,
        )
    if single:
        return single
    return PooledBackend(name=name, local=local, label=label, fallback_single=None)
