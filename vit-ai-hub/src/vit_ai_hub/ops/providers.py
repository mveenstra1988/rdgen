"""Read-first ops acties: Proxmox, Nextcloud, Gromox, Mailcow, ServiceHub, UniFi, Backup, automation-hub."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from vit_ai_hub.ops.client import (
    configured_services,
    ensure_ops_env_template,
    http_json,
    load_ops_env,
    ssh_run,
)


def ops_status() -> dict[str, Any]:
    ensure_ops_env_template()
    cfg = configured_services()
    return {
        "ok": True,
        "configured": cfg,
        "env_file": str(__import__("pathlib").Path.home() / ".config/vit/geheimen/ops.env"),
        "hint": "Vul tokens in ops.env (VPN nodig voor PVE/UniFi). Tools zijn read-first; mutaties eisen confirm=true.",
    }


def _pve_headers(env: dict[str, str]) -> dict[str, str]:
    tid = env.get("PVE_TOKEN_ID", "")
    secret = env.get("PVE_TOKEN_SECRET", "")
    return {"Authorization": f"PVEAPIToken={tid}={secret}"}


def _pve_hosts(env: dict[str, str]) -> list[str]:
    raw = env.get("PVE_HOSTS") or ""
    return [h.strip().rstrip("/") for h in raw.split(",") if h.strip()]


def proxmox_nodes() -> dict[str, Any]:
    env = load_ops_env()
    if not configured_services()["proxmox"]:
        return {"ok": False, "error": "Proxmox niet geconfigureerd in ops.env"}
    verify = (env.get("PVE_VERIFY_SSL") or "false").lower() in {"1", "true", "yes"}
    results = []
    for host in _pve_hosts(env):
        r = http_json("GET", f"{host}/api2/json/nodes", headers=_pve_headers(env), verify=verify)
        results.append({"host": host, **r})
    return {"ok": any(x.get("ok") for x in results), "nodes": results}


def proxmox_status() -> dict[str, Any]:
    env = load_ops_env()
    if not configured_services()["proxmox"]:
        return {"ok": False, "error": "Proxmox niet geconfigureerd"}
    verify = (env.get("PVE_VERIFY_SSL") or "false").lower() in {"1", "true", "yes"}
    out = {"cluster": [], "storage": [], "version": []}
    for host in _pve_hosts(env):
        h = _pve_headers(env)
        out["version"].append(http_json("GET", f"{host}/api2/json/version", headers=h, verify=verify))
        out["cluster"].append(http_json("GET", f"{host}/api2/json/cluster/status", headers=h, verify=verify))
        out["storage"].append(http_json("GET", f"{host}/api2/json/storage", headers=h, verify=verify))
    return {"ok": True, "proxmox": out}


def proxmox_vms(*, node: str | None = None) -> dict[str, Any]:
    env = load_ops_env()
    if not configured_services()["proxmox"]:
        return {"ok": False, "error": "Proxmox niet geconfigureerd"}
    verify = (env.get("PVE_VERIFY_SSL") or "false").lower() in {"1", "true", "yes"}
    headers = _pve_headers(env)
    items = []
    for host in _pve_hosts(env):
        nodes_resp = http_json("GET", f"{host}/api2/json/nodes", headers=headers, verify=verify)
        if not nodes_resp.get("ok"):
            items.append({"host": host, "error": nodes_resp})
            continue
        node_list = (nodes_resp.get("data") or {}).get("data") or []
        for n in node_list:
            nname = n.get("node") if isinstance(n, dict) else None
            if not nname:
                continue
            if node and nname != node:
                continue
            qemu = http_json("GET", f"{host}/api2/json/nodes/{nname}/qemu", headers=headers, verify=verify)
            lxc = http_json("GET", f"{host}/api2/json/nodes/{nname}/lxc", headers=headers, verify=verify)
            items.append({"host": host, "node": nname, "qemu": qemu, "lxc": lxc})
    return {"ok": True, "workloads": items}


def proxmox_vm_action(
    *,
    node: str,
    vmid: int,
    kind: str = "qemu",
    action: str = "status",
    confirm: bool = False,
) -> dict[str, Any]:
    """action: status|start|stop|shutdown|reboot — mutaties alleen met confirm=true."""
    env = load_ops_env()
    if not configured_services()["proxmox"]:
        return {"ok": False, "error": "Proxmox niet geconfigureerd"}
    kind = "lxc" if kind == "lxc" else "qemu"
    mutate = action in {"start", "stop", "shutdown", "reboot"}
    if mutate and not confirm:
        return {"ok": False, "error": "Mutatie geweigerd zonder confirm=true"}
    verify = (env.get("PVE_VERIFY_SSL") or "false").lower() in {"1", "true", "yes"}
    headers = _pve_headers(env)
    path_action = "status/current" if action == "status" else f"status/{action}"
    method = "GET" if action == "status" else "POST"
    last: dict[str, Any] = {"ok": False, "error": "geen host"}
    for host in _pve_hosts(env):
        url = f"{host}/api2/json/nodes/{quote(node)}/{kind}/{int(vmid)}/{path_action}"
        last = http_json(method, url, headers=headers, verify=verify)
        if last.get("ok"):
            return {"ok": True, "host": host, "node": node, "vmid": vmid, "action": action, "result": last}
    return last


def nextcloud_status() -> dict[str, Any]:
    env = load_ops_env()
    if not configured_services()["nextcloud"]:
        return {"ok": False, "error": "Nextcloud niet geconfigureerd"}
    base = env["NEXTCLOUD_URL"].rstrip("/")
    auth = (env["NEXTCLOUD_USER"], env["NEXTCLOUD_APP_PASSWORD"])
    headers = {"OCS-APIRequest": "true", "Accept": "application/json"}
    caps = http_json("GET", f"{base}/ocs/v2.php/cloud/capabilities", headers=headers, auth=auth)
    user = http_json("GET", f"{base}/ocs/v2.php/cloud/user", headers=headers, auth=auth)
    return {"ok": caps.get("ok") or user.get("ok"), "capabilities": caps, "user": user}


def gromox_health() -> dict[str, Any]:
    env = load_ops_env()
    out: dict[str, Any] = {}
    if env.get("GROMOX_URL"):
        out["http"] = http_json("GET", env["GROMOX_URL"].rstrip("/") + "/")
    if env.get("GROMOX_SSH"):
        out["ssh"] = ssh_run(
            env["GROMOX_SSH"],
            "systemctl is-active gromox-http gromox-zcore 2>/dev/null; df -h / /var 2>/dev/null | head -20",
        )
    if not out:
        return {"ok": False, "error": "GROMOX_SSH of GROMOX_URL ontbreekt"}
    ok = any(v.get("ok") for v in out.values() if isinstance(v, dict))
    return {"ok": ok, "gromox": out}


def mailcow_status() -> dict[str, Any]:
    env = load_ops_env()
    if not configured_services()["mailcow"]:
        return {"ok": False, "error": "Mailcow niet geconfigureerd"}
    base = env["MAILCOW_URL"].rstrip("/")
    headers = {"X-API-Key": env["MAILCOW_API_KEY"], "Accept": "application/json"}
    # status + domains (read)
    st = http_json("GET", f"{base}/api/v1/get/status/version", headers=headers)
    domains = http_json("GET", f"{base}/api/v1/get/domain/all", headers=headers)
    return {"ok": st.get("ok") or domains.get("ok"), "version": st, "domains": domains}


def servicehub_status() -> dict[str, Any]:
    env = load_ops_env()
    if not env.get("SERVICEHUB_URL"):
        return {"ok": False, "error": "SERVICEHUB_URL ontbreekt"}
    base = env["SERVICEHUB_URL"].rstrip("/")
    headers = {}
    if env.get("SERVICEHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {env['SERVICEHUB_TOKEN']}"
        headers["X-Api-Key"] = env["SERVICEHUB_TOKEN"]
    health = http_json("GET", f"{base}/up", headers=headers)
    if not health.get("ok"):
        health = http_json("GET", f"{base}/api/health", headers=headers)
    if not health.get("ok"):
        health = http_json("GET", base + "/", headers=headers)
    return {"ok": bool(health.get("ok")), "servicehub": health}


def unifi_status() -> dict[str, Any]:
    env = load_ops_env()
    if not configured_services()["unifi"]:
        return {"ok": False, "error": "UniFi niet geconfigureerd"}
    base = env["UNIFI_URL"].rstrip("/")
    verify = False
    if env.get("UNIFI_API_KEY"):
        headers = {"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"}
        info = http_json("GET", f"{base}/proxy/network/integration/v1/sites", headers=headers, verify=verify)
        return {"ok": info.get("ok"), "unifi": info}
    # legacy login
    user, pw = env.get("UNIFI_USER", ""), env.get("UNIFI_PASSWORD", "")
    login = http_json(
        "POST",
        f"{base}/api/auth/login",
        json_body={"username": user, "password": pw},
        verify=verify,
    )
    return {"ok": login.get("ok"), "unifi_login": login}


def automation_hub_disk() -> dict[str, Any]:
    env = load_ops_env()
    target = env.get("AUTOMATION_HUB_SSH")
    if not target:
        return {"ok": False, "error": "AUTOMATION_HUB_SSH ontbreekt"}
    return {
        "ok": True,
        "check": ssh_run(target, "df -h; echo '---'; uptime; echo '---'; docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | head -30"),
    }


def vit_backup_status() -> dict[str, Any]:
    env = load_ops_env()
    if not env.get("VIT_BACKUP_URL"):
        return {"ok": False, "error": "VIT_BACKUP_URL ontbreekt"}
    base = env["VIT_BACKUP_URL"].rstrip("/")
    headers = {}
    if env.get("VIT_BACKUP_TOKEN"):
        headers["Authorization"] = f"Bearer {env['VIT_BACKUP_TOKEN']}"
    r = http_json("GET", f"{base}/api/status", headers=headers)
    if not r.get("ok"):
        r = http_json("GET", f"{base}/health", headers=headers)
    return {"ok": bool(r.get("ok")), "backup": r}


def ops_overview() -> dict[str, Any]:
    """Snelle health-sweep over alles wat geconfigureerd is."""
    cfg = configured_services()
    results: dict[str, Any] = {"configured": cfg}
    if cfg["proxmox"]:
        results["proxmox"] = proxmox_status()
    if cfg["nextcloud"]:
        results["nextcloud"] = nextcloud_status()
    if cfg["gromox"]:
        results["gromox"] = gromox_health()
    if cfg["mailcow"]:
        results["mailcow"] = mailcow_status()
    if cfg["servicehub"]:
        results["servicehub"] = servicehub_status()
    if cfg["unifi"]:
        results["unifi"] = unifi_status()
    if cfg["automation_hub"]:
        results["automation_hub"] = automation_hub_disk()
    if cfg["vit_backup"]:
        results["vit_backup"] = vit_backup_status()
    results["ok"] = True
    return results


def run_ops_action(action: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    table = {
        "ops_status": lambda: ops_status(),
        "ops_overview": lambda: ops_overview(),
        "proxmox_nodes": proxmox_nodes,
        "proxmox_status": proxmox_status,
        "proxmox_vms": lambda: proxmox_vms(node=args.get("node")),
        "proxmox_vm_action": lambda: proxmox_vm_action(
            node=str(args.get("node") or ""),
            vmid=int(args.get("vmid") or 0),
            kind=str(args.get("kind") or "qemu"),
            action=str(args.get("action") or "status"),
            confirm=bool(args.get("confirm")),
        ),
        "nextcloud_status": nextcloud_status,
        "gromox_health": gromox_health,
        "mailcow_status": mailcow_status,
        "servicehub_status": servicehub_status,
        "unifi_status": unifi_status,
        "automation_hub_disk": automation_hub_disk,
        "vit_backup_status": vit_backup_status,
        "ops_ensure_env": ensure_ops_env_template,
    }
    fn = table.get(action)
    if not fn:
        return {"ok": False, "error": f"onbekende ops action: {action}", "known": sorted(table)}
    try:
        return fn()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "action": action}
