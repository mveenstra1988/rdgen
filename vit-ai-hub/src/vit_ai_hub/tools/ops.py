"""Ops tools: Proxmox, Nextcloud, Gromox, Mailcow, ServiceHub, UniFi, Backup, automation-hub."""

from __future__ import annotations

import json
from typing import Any

from vit_ai_hub.ops.providers import run_ops_action


def ops_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "ops_status",
                "description": "Toon welke ops-services geconfigureerd zijn (ops.env) en of tokens aanwezig zijn.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ops_overview",
                "description": "Health-sweep over alle geconfigureerde ops-services (Proxmox, Nextcloud, Mailcow, …).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ops_action",
                "description": (
                    "Voer een VIT ops-actie uit (read-first). "
                    "Acties: ops_status, ops_overview, proxmox_nodes, proxmox_status, proxmox_vms, "
                    "proxmox_vm_action, nextcloud_status, gromox_health, mailcow_status, "
                    "servicehub_status, unifi_status, automation_hub_disk, vit_backup_status, ops_ensure_env. "
                    "Mutaties (VM start/stop/reboot) eisen confirm=true."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "node": {"type": "string"},
                        "vmid": {"type": "integer"},
                        "kind": {"type": "string", "description": "qemu of lxc"},
                        "vm_action": {
                            "type": "string",
                            "description": "status|start|stop|shutdown|reboot (voor proxmox_vm_action)",
                        },
                        "confirm": {"type": "boolean"},
                    },
                    "required": ["action"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "proxmox_status",
                "description": "Proxmox cluster/version/storage status (VPN + PVE token vereist).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "proxmox_vms",
                "description": "Lijst QEMU/LXC workloads op Proxmox-nodes.",
                "parameters": {
                    "type": "object",
                    "properties": {"node": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "nextcloud_status",
                "description": "Nextcloud OCS capabilities + user (app-password).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mailcow_status",
                "description": "Mailcow API: versie + domains (read).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "gromox_health",
                "description": "Gromox health via HTTP en/of allowlisted SSH.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "servicehub_status",
                "description": "ServiceHub health (/up of /api/health).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "unifi_status",
                "description": "UniFi OS sites/login check (VPN).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "automation_hub_disk",
                "description": "automation-hub disk/uptime/docker via allowlisted SSH.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vit_backup_status",
                "description": "VIT Backup API status/health.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


OPS_TOOL_NAMES = {t["function"]["name"] for t in ops_tool_specs()}


async def run_ops_tool(name: str, arguments: dict[str, Any]) -> str:
    args = arguments or {}
    if name == "ops_action":
        action = str(args.get("action") or "").strip()
        payload: dict[str, Any] = {}
        if args.get("node") is not None:
            payload["node"] = args.get("node")
        if args.get("vmid") is not None:
            payload["vmid"] = args.get("vmid")
        if args.get("kind") is not None:
            payload["kind"] = args.get("kind")
        if args.get("vm_action") is not None:
            payload["action"] = args.get("vm_action")
        elif action == "proxmox_vm_action" and args.get("action") and args.get("action") != "proxmox_vm_action":
            # allow nested action via same key when calling via ops_action only
            pass
        if "confirm" in args:
            payload["confirm"] = bool(args.get("confirm"))
        # When using ops_action with proxmox_vm_action, prefer vm_action for the VM verb
        if action == "proxmox_vm_action" and "action" not in payload and args.get("vm_action"):
            payload["action"] = args["vm_action"]
        result = run_ops_action(action, payload)
        return json.dumps(result, ensure_ascii=False)

    # Direct tool name → same action id
    payload = dict(args)
    if name == "proxmox_vm_action" and "vm_action" in payload:
        payload["action"] = payload.pop("vm_action")
    result = run_ops_action(name, payload)
    return json.dumps(result, ensure_ascii=False)
