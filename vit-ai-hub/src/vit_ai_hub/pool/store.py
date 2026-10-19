"""Persistente multi-abo accounts + cooldown-state."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

ACCOUNTS_PATH = Path.home() / ".config/vit/geheimen/accounts.json"
STATE_PATH = Path(ROOT) / "data" / "account_state.json"

POOLS = ("bridge", "cursor", "openrouter", "deepseek", "grok", "omniroute")

# Temporary vs hard exhaustion
_HARD = re.compile(
    r"(quota|insufficient|usage.?limit|billing|out of credits|exceeded.?limit|"
    r"payment|subscription.?expired|plan.?limit|credit.?balance)",
    re.I,
)
_SOFT = re.compile(
    r"(rate.?limit|too many requests|429|overloaded|capacity|temporarily|"
    r"try again|throttl)",
    re.I,
)


def list_pools() -> list[str]:
    return list(POOLS)


def _default_doc() -> dict[str, Any]:
    return {p: [] for p in POOLS}


def load_accounts() -> dict[str, list[dict[str, Any]]]:
    doc = _default_doc()
    if ACCOUNTS_PATH.is_file():
        try:
            raw = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for p in POOLS:
                    items = raw.get(p) or []
                    if isinstance(items, list):
                        doc[p] = [a for a in items if isinstance(a, dict) and a.get("id")]
        except Exception:
            pass
    # Merge numbered env vars: BRIDGE_API_KEY_1 + BRIDGE_BASE_URL_1 …
    _merge_env_accounts(doc)
    # Legacy single keys → synthetic account if pool empty
    _merge_legacy_singles(doc)
    return doc


def _merge_env_accounts(doc: dict[str, list[dict[str, Any]]]) -> None:
    for pool in POOLS:
        prefix = pool.upper()
        existing_ids = {a["id"] for a in doc[pool]}
        for i in range(1, 16):
            key = os.environ.get(f"{prefix}_API_KEY_{i}") or os.environ.get(f"{prefix}_KEY_{i}")
            url = os.environ.get(f"{prefix}_BASE_URL_{i}") or os.environ.get(f"{prefix}_URL_{i}")
            if not key and not url:
                continue
            aid = f"env-{pool}-{i}"
            if aid in existing_ids:
                continue
            # defaults
            default_url = {
                "bridge": "http://127.0.0.1:8317/v1",
                "cursor": "http://127.0.0.1:8317/v1",
                "openrouter": "https://openrouter.ai/api/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "grok": "https://api.x.ai/v1",
                "omniroute": "http://127.0.0.1:20128/v1",
            }.get(pool, "")
            # staggered bridge ports: 8317, 8318, …
            if pool in {"bridge", "cursor"} and not url:
                url = f"http://127.0.0.1:{8316 + i}/v1"
            doc[pool].append(
                {
                    "id": aid,
                    "label": f"{pool} #{i} (env)",
                    "base_url": (url or default_url).rstrip("/"),
                    "api_key": key or "",
                    "tags": _default_tags(pool),
                    "enabled": True,
                    "source": "env",
                }
            )


def _merge_legacy_singles(doc: dict[str, list[dict[str, Any]]]) -> None:
    from vit_ai_hub.config import get_settings

    s = get_settings()
    singles = {
        "bridge": (s.bridge_base_url, s.bridge_api_key),
        "cursor": (s.cursor_base_url or s.bridge_base_url, s.cursor_api_key or s.bridge_api_key),
        "openrouter": (s.openrouter_base_url, s.openrouter_api_key),
        "deepseek": (s.deepseek_base_url, s.deepseek_api_key),
        "grok": (s.grok_base_url, s.xai_api_key),
        "omniroute": (s.omniroute_base_url, s.omniroute_api_key),
    }
    for pool, (url, key) in singles.items():
        if doc[pool]:
            continue
        if not url and not key:
            continue
        if pool in {"openrouter", "deepseek", "grok"} and not key:
            continue
        doc[pool].append(
            {
                "id": f"legacy-{pool}",
                "label": f"{pool} (default)",
                "base_url": (url or "").rstrip("/"),
                "api_key": key or "",
                "tags": _default_tags(pool),
                "enabled": True,
                "source": "legacy",
            }
        )


def _default_tags(pool: str) -> list[str]:
    if pool == "bridge":
        return ["claude", "chatgpt"]
    if pool == "cursor":
        return ["cursor"]
    return [pool]


def save_accounts(doc: dict[str, Any]) -> dict[str, Any]:
    ACCOUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = _default_doc()
    for p in POOLS:
        for a in doc.get(p) or []:
            if not isinstance(a, dict):
                continue
            aid = str(a.get("id") or "").strip() or f"{p}-{uuid.uuid4().hex[:8]}"
            # skip pure env-sourced on write? keep user ones; env re-merged on load
            if a.get("source") == "env":
                continue
            clean[p].append(
                {
                    "id": aid,
                    "label": str(a.get("label") or aid)[:80],
                    "base_url": str(a.get("base_url") or "").rstrip("/"),
                    "api_key": str(a.get("api_key") or ""),
                    "tags": [str(t) for t in (a.get("tags") or _default_tags(p))][:12],
                    "enabled": bool(a.get("enabled", True)),
                    "source": "user",
                }
            )
    ACCOUNTS_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(ACCOUNTS_PATH, 0o600)
    except OSError:
        pass
    return {"ok": True, "path": str(ACCOUNTS_PATH), "counts": {p: len(clean[p]) for p in POOLS}}


def list_accounts(pool: str | None = None) -> dict[str, Any]:
    doc = load_accounts()
    state = _load_state()
    if pool:
        return {"pool": pool, "accounts": [_public(a, state) for a in doc.get(pool, [])]}
    return {
        p: [_public(a, state) for a in items]
        for p, items in doc.items()
    }


def _public(a: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    st = state.get(a["id"]) or {}
    key = a.get("api_key") or ""
    return {
        "id": a["id"],
        "label": a.get("label"),
        "base_url": a.get("base_url"),
        "api_key_set": bool(key),
        "api_key_preview": (key[:4] + "…" + key[-2:]) if len(key) > 8 else ("***" if key else ""),
        "tags": a.get("tags") or [],
        "enabled": bool(a.get("enabled", True)),
        "source": a.get("source") or "user",
        "exhausted_until": st.get("exhausted_until"),
        "exhausted_reason": st.get("reason"),
        "healthy": _is_healthy(a, state),
        "use_count": int(st.get("use_count") or 0),
        "last_used": st.get("last_used"),
        "last_error": st.get("last_error"),
    }


def add_account(pool: str, payload: dict[str, Any]) -> dict[str, Any]:
    pool = pool.strip().lower()
    if pool not in POOLS:
        return {"ok": False, "error": f"onbekende pool: {pool}", "known": list(POOLS)}
    doc = load_accounts()
    # drop env/legacy for rewrite of user file
    user_doc = {p: [a for a in doc[p] if a.get("source") == "user"] for p in POOLS}
    aid = str(payload.get("id") or "").strip() or f"{pool}-{uuid.uuid4().hex[:8]}"
    # replace if same id
    user_doc[pool] = [a for a in user_doc[pool] if a["id"] != aid]
    user_doc[pool].append(
        {
            "id": aid,
            "label": str(payload.get("label") or aid)[:80],
            "base_url": str(payload.get("base_url") or "").rstrip("/"),
            "api_key": str(payload.get("api_key") or ""),
            "tags": [str(t) for t in (payload.get("tags") or _default_tags(pool))][:12],
            "enabled": bool(payload.get("enabled", True)),
            "source": "user",
        }
    )
    save_accounts(user_doc)
    return {"ok": True, "account": _public(user_doc[pool][-1], _load_state())}


def delete_account(pool: str, account_id: str) -> dict[str, Any]:
    pool = pool.strip().lower()
    doc = load_accounts()
    user_doc = {p: [a for a in doc[p] if a.get("source") == "user"] for p in POOLS}
    before = len(user_doc.get(pool) or [])
    user_doc[pool] = [a for a in user_doc.get(pool) or [] if a["id"] != account_id]
    if len(user_doc[pool]) == before:
        return {"ok": False, "error": "niet gevonden (env/legacy accounts kun je niet wissen)"}
    save_accounts(user_doc)
    st = _load_state()
    st.pop(account_id, None)
    _save_state(st)
    return {"ok": True, "id": account_id}


def pool_status() -> dict[str, Any]:
    doc = load_accounts()
    state = _load_state()
    out: dict[str, Any] = {}
    for p, items in doc.items():
        healthy = [a for a in items if _is_healthy(a, state)]
        out[p] = {
            "total": len(items),
            "healthy": len(healthy),
            "exhausted": len(items) - len(healthy),
            "accounts": [_public(a, state) for a in items],
        }
    return {"ok": True, "pools": out, "path": str(ACCOUNTS_PATH)}


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_healthy(account: dict[str, Any], state: dict[str, Any]) -> bool:
    if not account.get("enabled", True):
        return False
    if not account.get("base_url"):
        return False
    st = state.get(account["id"]) or {}
    until = float(st.get("exhausted_until") or 0)
    if until and until > time.time():
        return False
    return True


def mark_success(account_id: str) -> None:
    st = _load_state()
    row = st.get(account_id) or {}
    row["last_used"] = time.time()
    row["use_count"] = int(row.get("use_count") or 0) + 1
    row.pop("exhausted_until", None)
    row.pop("reason", None)
    row.pop("last_error", None)
    st[account_id] = row
    _save_state(st)


def mark_failure(account_id: str, error: str, *, status: int | None = None) -> dict[str, Any]:
    """Markeer soft/hard exhaustion; return {exhausted, cooldown_sec, kind}."""
    text = error or ""
    hard = bool(_HARD.search(text) or status in {402})
    soft = bool(_SOFT.search(text) or status == 429)
    # 403 with quota language → hard
    if status == 403 and _HARD.search(text):
        hard = True
    st = _load_state()
    row = st.get(account_id) or {}
    row["last_error"] = text[:500]
    row["last_fail"] = time.time()
    kind = "error"
    cooldown = 0
    if hard:
        cooldown = int(os.environ.get("VIT_ABO_HARD_COOLDOWN_SEC") or 6 * 3600)
        row["exhausted_until"] = time.time() + cooldown
        row["reason"] = "quota/billing"
        kind = "hard"
    elif soft:
        cooldown = int(os.environ.get("VIT_ABO_SOFT_COOLDOWN_SEC") or 300)
        row["exhausted_until"] = time.time() + cooldown
        row["reason"] = "rate_limit"
        kind = "soft"
    st[account_id] = row
    _save_state(st)
    return {"exhausted": kind in {"hard", "soft"}, "kind": kind, "cooldown_sec": cooldown}


def clear_exhaustion(account_id: str | None = None) -> dict[str, Any]:
    st = _load_state()
    if account_id:
        if account_id in st:
            st[account_id].pop("exhausted_until", None)
            st[account_id].pop("reason", None)
        _save_state(st)
        return {"ok": True, "cleared": [account_id]}
    for row in st.values():
        row.pop("exhausted_until", None)
        row.pop("reason", None)
    _save_state(st)
    return {"ok": True, "cleared": "all"}


def pick_account_order(
    pool: str,
    *,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Healthy accounts, tagged match first, then round-robin by least recently used."""
    doc = load_accounts()
    state = _load_state()
    items = [a for a in doc.get(pool, []) if _is_healthy(a, state)]
    if tags:
        tagset = {t.lower() for t in tags}
        preferred = [a for a in items if tagset & {t.lower() for t in (a.get("tags") or [])}]
        others = [a for a in items if a not in preferred]
        items = preferred + others
    items.sort(key=lambda a: float((state.get(a["id"]) or {}).get("last_used") or 0))
    return items


def tags_for_model(model: str) -> list[str] | None:
    m = (model or "").lower()
    if m.startswith("claude") or "anthropic" in m:
        return ["claude"]
    if m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4") or "chatgpt" in m:
        return ["chatgpt"]
    if "composer" in m or m.startswith("cursor"):
        return ["cursor"]
    return None
