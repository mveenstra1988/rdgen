import json

from vit_ai_hub.tools import mcp_runtime as mcp


def test_list_servers_from_file(tmp_path, monkeypatch):
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps({"mcpServers": {"local-demo": {"command": "true", "args": []}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mcp, "DEFAULT_MCP", path)
    # avoid falling through to real home configs first — patch load to only use DEFAULT
    out = mcp.load_mcp_config(path)
    assert "local-demo" in out["mcpServers"]
    listed = mcp.list_servers()
    # list_servers may prefer home files; force via monkeypatch on load
    monkeypatch.setattr(mcp, "load_mcp_config", lambda path=None: out)
    listed = mcp.list_servers()
    assert any(s["name"] == "local-demo" for s in listed["servers"])


def test_mcp_tool_specs_present():
    names = [t["function"]["name"] for t in mcp.mcp_tool_specs()]
    assert "mcp_list_servers" in names
    assert "mcp_call_tool" in names
