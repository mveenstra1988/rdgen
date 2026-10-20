"""Ops layer: config, allowlist, tools, mocked HTTP."""

from __future__ import annotations

import json


def test_ops_status_and_template(tmp_path, monkeypatch):
    import vit_ai_hub.ops.client as client

    ops_env = tmp_path / "ops.env"
    monkeypatch.setattr(client, "OPS_ENV", ops_env)
    monkeypatch.delenv("PVE_HOSTS", raising=False)

    created = client.ensure_ops_env_template()
    assert created["ok"] is True
    assert created["created"] is True
    assert ops_env.is_file()

    again = client.ensure_ops_env_template()
    assert again["created"] is False

    from vit_ai_hub.ops.providers import ops_status

    st = ops_status()
    assert st["ok"] is True
    assert "configured" in st
    assert st["configured"]["proxmox"] is False


def test_configured_services_from_env(monkeypatch, tmp_path):
    import vit_ai_hub.ops.client as client

    monkeypatch.setattr(client, "OPS_ENV", tmp_path / "missing.env")
    monkeypatch.setenv("PVE_HOSTS", "https://10.20.1.123:8006")
    monkeypatch.setenv("PVE_TOKEN_ID", "vit@pve!hub")
    monkeypatch.setenv("PVE_TOKEN_SECRET", "secret")
    monkeypatch.setenv("MAILCOW_URL", "https://eas.example.nl")
    monkeypatch.setenv("MAILCOW_API_KEY", "key")
    cfg = client.configured_services()
    assert cfg["proxmox"] is True
    assert cfg["mailcow"] is True
    assert cfg["nextcloud"] is False


def test_ssh_allowlist_blocks(monkeypatch, tmp_path):
    import vit_ai_hub.ops.client as client

    monkeypatch.setattr(client, "OPS_ENV", tmp_path / "ops.env")
    (tmp_path / "ops.env").write_text("AUTOMATION_HUB_SSH=user@10.20.1.209\n", encoding="utf-8")
    bad = client.ssh_run("root@evil.example", "uptime")
    assert bad["ok"] is False
    assert "allowlist" in bad["error"].lower()

    blocked = client.ssh_run("user@10.20.1.209", "rm -rf /")
    assert blocked["ok"] is False


def test_proxmox_vm_action_requires_confirm(monkeypatch, tmp_path):
    import vit_ai_hub.ops.client as client
    import vit_ai_hub.ops.providers as providers

    monkeypatch.setattr(client, "OPS_ENV", tmp_path / "ops.env")
    (tmp_path / "ops.env").write_text(
        "PVE_HOSTS=https://10.20.1.123:8006\nPVE_TOKEN_ID=a\nPVE_TOKEN_SECRET=b\n",
        encoding="utf-8",
    )
    out = providers.proxmox_vm_action(node="pve", vmid=100, action="stop", confirm=False)
    assert out["ok"] is False
    assert "confirm" in out["error"].lower()


def test_proxmox_status_mocked(monkeypatch, tmp_path):
    import vit_ai_hub.ops.client as client
    import vit_ai_hub.ops.providers as providers

    monkeypatch.setattr(client, "OPS_ENV", tmp_path / "ops.env")
    (tmp_path / "ops.env").write_text(
        "PVE_HOSTS=https://10.20.1.123:8006\nPVE_TOKEN_ID=a\nPVE_TOKEN_SECRET=b\n",
        encoding="utf-8",
    )

    def fake_http(method, url, **kwargs):
        return {"ok": True, "status": 200, "url": url, "data": {"data": [{"node": "pve01"}]}}

    monkeypatch.setattr(providers, "http_json", fake_http)
    out = providers.proxmox_nodes()
    assert out["ok"] is True
    assert out["nodes"]


def test_mailcow_and_nextcloud_mocked(monkeypatch, tmp_path):
    import vit_ai_hub.ops.client as client
    import vit_ai_hub.ops.providers as providers

    monkeypatch.setattr(client, "OPS_ENV", tmp_path / "ops.env")
    (tmp_path / "ops.env").write_text(
        "\n".join(
            [
                "MAILCOW_URL=https://eas.example.nl",
                "MAILCOW_API_KEY=k",
                "NEXTCLOUD_URL=https://cloud.example.nl",
                "NEXTCLOUD_USER=u",
                "NEXTCLOUD_APP_PASSWORD=p",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_http(method, url, **kwargs):
        return {"ok": True, "status": 200, "url": url, "data": {"ok": True}}

    monkeypatch.setattr(providers, "http_json", fake_http)
    assert providers.mailcow_status()["ok"] is True
    assert providers.nextcloud_status()["ok"] is True


def test_run_ops_action_unknown():
    from vit_ai_hub.ops.providers import run_ops_action

    out = run_ops_action("nope_xyz")
    assert out["ok"] is False
    assert "known" in out


def test_ops_tools_wired():
    import asyncio

    from vit_ai_hub.tools.ops import OPS_TOOL_NAMES, ops_tool_specs, run_ops_tool

    names = {t["function"]["name"] for t in ops_tool_specs()}
    assert "ops_status" in names
    assert "ops_action" in names
    assert names == OPS_TOOL_NAMES

    raw = asyncio.run(run_ops_tool("ops_status", {}))
    data = json.loads(raw)
    assert data.get("ok") is True


def test_tool_specs_include_ops():
    from vit_ai_hub.tools.capabilities import capabilities_manifest, tool_specs

    names = [t["function"]["name"] for t in tool_specs()]
    assert "ops_overview" in names
    assert "proxmox_status" in names
    man = capabilities_manifest()
    assert man.get("ops") is True
    assert "ops" in man["studios"]


def test_ops_studio_and_infra_team(tmp_path, monkeypatch):
    from vit_ai_hub.studio import list_studios, studio_system_prompt
    import vit_ai_hub.agents.store as store

    ids = {s["id"] for s in list_studios()}
    assert "ops" in ids
    assert "read-first" in (studio_system_prompt("ops") or "").lower() or "ops" in (
        studio_system_prompt("ops") or ""
    ).lower()

    monkeypatch.setattr(store, "AGENTS_PATH", tmp_path / "agents.json")
    monkeypatch.setattr(store, "TEAMS_PATH", tmp_path / "teams.json")
    teams = store.list_teams()
    assert any(t["id"] == "team-infra" for t in teams)
    agents = store.list_agents()
    assert any(a["id"] == "agent-proxmox" for a in agents)


def test_redact_secrets():
    from vit_ai_hub.ops.client import redact

    out = redact({"token": "supersecret", "ok": True, "nested": {"password": "x"}})
    assert out["token"] == "***"
    assert out["nested"]["password"] == "***"
    assert out["ok"] is True
