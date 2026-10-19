from __future__ import annotations

from typing import Any, AsyncIterator

import httpx


class OpenAICompatBackend:
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str = "",
        local: bool = False,
        label: str = "",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.local = local
        self.label = label or name
        self.extra_headers = extra_headers or {}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.name == "openrouter":
            headers.setdefault("HTTP-Referer", "https://vit.local/ai-hub")
            headers.setdefault("X-Title", "VIT AI Hub")
        return headers

    async def list_models(self) -> list[dict[str, Any]]:
        if not self.base_url:
            return []
        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code >= 400:
                    return []
                data = resp.json()
        except Exception:
            return []
        items = data.get("data") if isinstance(data, dict) else data
        out: list[dict[str, Any]] = []
        if not isinstance(items, list):
            return out
        for item in items:
            if not isinstance(item, dict):
                continue
            mid = item.get("id") or item.get("name")
            if not mid:
                continue
            out.append(
                {
                    "id": str(mid),
                    "object": "model",
                    "owned_by": self.name,
                    "backend": self.name,
                    "local": self.local,
                    "label": self.label,
                    "name": item.get("name") or str(mid),
                }
            )
        return out

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"{self.name} error {resp.status_code}: {resp.text[:800]}")
            return resp.json()

    async def stream_chat_completions(self, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", url, headers=self._headers(), json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"{self.name} error {resp.status_code}: {body.decode('utf-8', 'ignore')[:800]}"
                    )
                async for chunk in resp.aiter_bytes():
                    yield chunk