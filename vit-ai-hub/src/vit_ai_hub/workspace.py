"""Allowlisted project workspaces for software/webdesign (Cursor-vervanging in de hub)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from vit_ai_hub.config import ROOT

# Alleen deze command-prefixen via run_in_workspace
_SAFE_PREFIXES = (
    "pytest",
    "python",
    "python3",
    "npm ",
    "npm\t",
    "npx ",
    "pnpm ",
    "yarn ",
    "node ",
    "cargo ",
    "go ",
    "make ",
    "swift ",
    "xcodebuild",
    "git status",
    "git diff",
    "git log",
    "ls ",
    "ls\t",
    "rg ",
    "find ",
)

_DENIED_WRITE = re.compile(
    r"(^|/)\.(env|git)(/|$)|credentials|id_rsa|\.pem$|\.key$",
    re.I,
)


def default_roots() -> list[Path]:
    env = os.environ.get("VIT_WORKSPACE_ROOTS", "").strip()
    roots: list[Path] = [ROOT.resolve()]
    if env:
        for part in env.split(":"):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    else:
        home = Path.home()
        for name in ("Developer", "Projects", "code", "src", "werk", "VIT"):
            p = (home / name).resolve()
            if p.is_dir():
                roots.append(p)
        # always allow creating under ~/Projects even if missing yet
        roots.append((home / "Projects").resolve())
    # unique, preserve order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def resolve_in_workspace(path: str, *, workspace: str | None = None) -> Path:
    """Resolve path under an allowlisted root. Absolute paths must stay inside a root."""
    roots = default_roots()
    raw = (path or "").strip()
    if not raw:
        raise ValueError("leeg pad")

    if workspace:
        ws = Path(workspace).expanduser().resolve()
        if not any(ws == r or str(ws).startswith(str(r) + os.sep) for r in roots):
            # workspace zelf moet een root zijn of erbinnen
            if ws not in roots and not any(str(ws).startswith(str(r) + os.sep) for r in roots):
                raise PermissionError(f"workspace niet in allowlist: {ws}")
        base = ws
        p = Path(raw).expanduser()
        target = (base / p).resolve() if not p.is_absolute() else p.resolve()
        if not (target == base or str(target).startswith(str(base) + os.sep)):
            raise PermissionError("pad buiten gekozen workspace")
        return target

    p = Path(raw).expanduser()
    if p.is_absolute():
        target = p.resolve()
    else:
        # relative: prefer first existing Projects-like root that contains it, else ROOT
        target = (ROOT / p).resolve()
        for r in roots:
            cand = (r / p).resolve()
            if cand.exists():
                target = cand
                break

    if not any(target == r or str(target).startswith(str(r) + os.sep) for r in roots):
        raise PermissionError("pad buiten allowlist")
    return target


def list_workspace_dir(path: str = ".", *, workspace: str | None = None, limit: int = 200) -> dict[str, Any]:
    try:
        target = resolve_in_workspace(path or ".", workspace=workspace)
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    if not target.exists():
        return {"error": "niet gevonden", "path": str(target)}
    if target.is_file():
        return {"path": str(target), "type": "file", "size": target.stat().st_size}
    entries = []
    try:
        children = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except OSError as exc:
        return {"error": str(exc)}
    for child in children[:limit]:
        if child.name.startswith(".") and child.name not in {".env.example", ".gitignore"}:
            continue
        entries.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "path": str(child),
            }
        )
    return {"path": str(target), "type": "dir", "entries": entries, "roots": [str(r) for r in default_roots()]}


def read_workspace_file(path: str, *, workspace: str | None = None, max_chars: int = 80_000) -> dict[str, Any]:
    try:
        target = resolve_in_workspace(path, workspace=workspace)
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    if not target.is_file():
        return {"error": "bestand niet gevonden", "path": str(target)}
    text = target.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return {"path": str(target), "content": text, "truncated": len(text) >= max_chars}


def write_workspace_file(
    path: str,
    content: str,
    *,
    workspace: str | None = None,
    create_dirs: bool = True,
) -> dict[str, Any]:
    try:
        target = resolve_in_workspace(path, workspace=workspace)
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    if _DENIED_WRITE.search(str(target)):
        return {"error": "schrijven naar dit pad geweigerd (secrets/git)"}
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    # never overwrite huge binaries by mistake
    if target.exists() and target.stat().st_size > 2_000_000:
        return {"error": "bestaand bestand te groot om te overschrijven"}
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target), "bytes": len(content.encode("utf-8"))}


def run_in_workspace(
    command: str,
    *,
    workspace: str | None = None,
    timeout_sec: int = 60,
) -> dict[str, Any]:
    cmd = (command or "").strip()
    if not cmd:
        return {"error": "leeg commando"}
    if any(x in cmd for x in (";", "&&", "||", "|", "`", "$(", "\n", "\r")):
        return {"error": "shell-ketens/pipes niet toegestaan"}
    lowered = cmd if cmd.startswith("git ") else cmd
    ok = False
    for prefix in _SAFE_PREFIXES:
        if lowered == prefix.strip() or lowered.startswith(prefix):
            ok = True
            break
    if not ok:
        return {"error": "commando niet in allowlist", "allowed_prefixes": list(_SAFE_PREFIXES)}

    try:
        cwd = resolve_in_workspace(".", workspace=workspace) if workspace else resolve_in_workspace(".")
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}

    if not cwd.is_dir():
        return {"error": f"cwd bestaat niet: {cwd}"}

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=max(5, min(timeout_sec, 180)),
            env={**os.environ, "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "cwd": str(cwd)}
    except OSError as exc:
        return {"error": str(exc)}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "cwd": str(cwd),
        "stdout": (proc.stdout or "")[-20_000:],
        "stderr": (proc.stderr or "")[-10_000:],
    }


def workspace_status() -> dict[str, Any]:
    roots = default_roots()
    return {
        "roots": [
            {"path": str(r), "exists": r.is_dir()}
            for r in roots
        ],
        "hint": "Zet VIT_WORKSPACE_ROOTS=/pad1:/pad2 in ai-gateway.env om projectmappen toe te voegen.",
    }
