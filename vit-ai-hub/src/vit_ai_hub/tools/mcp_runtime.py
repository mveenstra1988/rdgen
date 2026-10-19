"""Draai gemigreerde MCP-servers (stdio) als hub-tools."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

DEFAULT_MCP = ROOT / "data" / "migrated" / "mcp.json"


def load_mcp_config(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_MCP
    # also accept ~/.cursor/mcp.json live
    candidates = [
        p,
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".claude" / "mcp.json",
    ]
    for c in candidates:
        if c.is_file():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                continue
            servers = data.get("mcpServers") or data.get("servers") or {}
            if isinstance(servers, dict) and servers:
                return {"path": str(c), "mcpServers": servers}
    return {"path": str(p), "mcpServers": {}}


class _StdioSession:
    def __init__(self, name: str, cfg: dict[str, Any]):
        self.name = name
        self.cfg = cfg
        self.proc: subprocess.Popen | None = None
        self._id = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        cmd = self.cfg.get("command")
        if not cmd:
            raise RuntimeError(f"MCP {self.name}: geen command (alleen stdio ondersteund)")
        args = self.cfg.get("args") or []
        env = {**os.environ, **{str(k): str(v) for k, v in (self.cfg.get("env") or {}).items()}}
        self.proc = subprocess.Popen(
            [str(cmd), *[str(a) for a in args]],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 20.0) -> Any:
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            raise RuntimeError("MCP niet gestart")
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        line = json.dumps(msg, ensure_ascii=False)
        with self._lock:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            deadline = time.time() + timeout
            while time.time() < deadline:
                out = self.proc.stdout.readline()
                if not out:
                    if self.proc.poll() is not None:
                        err = (self.proc.stderr.read() if self.proc.stderr else "")[:2000]
                        raise RuntimeError(f"MCP exit: {err}")
                    continue
                out = out.strip()
                if not out:
                    continue
                try:
                    data = json.loads(out)
                except json.JSONDecodeError:
                    continue
                if data.get("id") != req_id:
                    continue
                if "error" in data:
                    raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))
                return data.get("result")
        raise TimeoutError(f"MCP timeout op {method}")


def _with_server(name: str, fn, timeout: float = 25.0) -> Any:
    cfg_all = load_mcp_config()
    servers = cfg_all.get("mcpServers") or {}
    if name not in servers:
        raise KeyError(f"onbekende MCP server: {name}")
    cfg = servers[name]
    if cfg.get("url") and not cfg.get("command"):
        raise RuntimeError(f"MCP {name} is URL/SSE — start die server apart; stdio-bridge ondersteunt command-servers")
    session = _StdioSession(name, cfg)
    try:
        session.start()
        # initialize handshake (best-effort)
        try:
            session.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "vit-ai-hub", "version": "1.0"},
                },
                timeout=min(timeout, 15),
            )
            # notifications/initialized (ignore failures)
            if session.proc and session.proc.stdin:
                session.proc.stdin.write(
                    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
                )
                session.proc.stdin.flush()
        except Exception:
            pass
        return fn(session)
    finally:
        session.close()


def list_servers() -> dict[str, Any]:
    cfg = load_mcp_config()
    servers = []
    for name, c in (cfg.get("mcpServers") or {}).items():
        servers.append(
            {
                "name": name,
                "command": c.get("command"),
                "args": c.get("args") or [],
                "has_url": bool(c.get("url")),
                "transport": "stdio" if c.get("command") else ("sse" if c.get("url") else "unknown"),
            }
        )
    return {"path": cfg.get("path"), "servers": servers}


def list_tools(server: str) -> dict[str, Any]:
    def _run(session: _StdioSession):
        result = session.request("tools/list", {}) or {}
        return {"server": server, "tools": result.get("tools") or result}

    try:
        return _with_server(server, _run)
    except Exception as exc:
        return {"server": server, "error": str(exc), "tools": []}


def call_tool(server: str, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    def _run(session: _StdioSession):
        result = session.request(
            "tools/call",
            {"name": tool, "arguments": arguments or {}},
            timeout=60,
        )
        return {"server": server, "tool": tool, "result": result}

    try:
        return _with_server(server, _run)
    except Exception as exc:
        return {"server": server, "tool": tool, "error": str(exc)}


def mcp_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "mcp_list_servers",
                "description": "Lijst gemigreerde/actieve MCP-servers (uit Cursor/Claude mcp.json).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_list_tools",
                "description": "Lijst tools van één MCP-server (stdio).",
                "parameters": {
                    "type": "object",
                    "properties": {"server": {"type": "string"}},
                    "required": ["server"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_call_tool",
                "description": "Roep een MCP-tool aan op een stdio-server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "server": {"type": "string"},
                        "tool": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["server", "tool"],
                },
            },
        },
    ]


async def run_mcp_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "mcp_list_servers":
        return json.dumps(list_servers(), ensure_ascii=False)
    if name == "mcp_list_tools":
        return json.dumps(list_tools(str(arguments.get("server") or "")), ensure_ascii=False)
    if name == "mcp_call_tool":
        return json.dumps(
            call_tool(
                str(arguments.get("server") or ""),
                str(arguments.get("tool") or ""),
                arguments.get("arguments") if isinstance(arguments.get("arguments"), dict) else {},
            ),
            ensure_ascii=False,
        )
    return json.dumps({"error": f"onbekende mcp tool {name}"})
