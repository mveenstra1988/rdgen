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
    "git show",
    "git branch",
    "git add ",
    "git commit ",
    "git checkout ",
    "git switch ",
    "git pull",
    "git fetch",
    "git push",
    "ls ",
    "ls\t",
    "rg ",
    "find ",
)

_GIT_DENY = re.compile(
    r"(--force|-f\b)|reset\s+--hard|clean\s+-|push\s+.*--force|"
    r"filter-branch|rebase\s+.*-i|push\s+.*:|checkout\s+--\s+\.|checkout\s+\.",
    re.I,
)

_DENIED_WRITE = re.compile(
    r"(^|/)\.(env|git)(/|$)|credentials|id_rsa|\.pem$|\.key$",
    re.I,
)


def default_roots() -> list[Path]:
    env = os.environ.get("VIT_WORKSPACE_ROOTS", "").strip()
    roots: list[Path] = [ROOT.resolve()]
    # self-improve + migratie-spiegel altijd bereikbaar
    migrated = (ROOT / "data" / "migrated").resolve()
    roots.append(migrated)
    if env:
        for part in env.split(":"):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    else:
        home = Path.home()
        for name in ("Developer", "Projects", "code", "src", "werk", "VIT", ".claude", ".cursor"):
            p = (home / name).resolve()
            if p.exists():
                roots.append(p)
        roots.append((home / "Projects").resolve())
        # Cursor/Claude app support (read/write allowlist for migrate repairs)
        for p in (
            home / "Library/Application Support/Cursor",
            home / "Library/Application Support/Claude",
            home / "Library/Application Support/com.openai.chat",
        ):
            if p.exists():
                roots.append(p.resolve())
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


def search_replace(
    path: str,
    old_str: str,
    new_str: str,
    *,
    workspace: str | None = None,
    replace_all: bool = False,
) -> dict[str, Any]:
    """Gerichte patch (Cursor-achtig) i.p.v. heel bestand herschrijven."""
    if not old_str:
        return {"error": "old_str mag niet leeg zijn"}
    try:
        target = resolve_in_workspace(path, workspace=workspace)
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    if _DENIED_WRITE.search(str(target)):
        return {"error": "schrijven naar dit pad geweigerd (secrets/git)"}
    if not target.is_file():
        return {"error": "bestand niet gevonden", "path": str(target)}
    text = target.read_text(encoding="utf-8", errors="replace")
    count = text.count(old_str)
    if count == 0:
        return {"error": "old_str niet gevonden", "path": str(target)}
    if count > 1 and not replace_all:
        return {
            "error": f"old_str komt {count}x voor — maak unieker of zet replace_all=true",
            "path": str(target),
            "matches": count,
        }
    if replace_all:
        updated = text.replace(old_str, new_str)
        n = count
    else:
        updated = text.replace(old_str, new_str, 1)
        n = 1
    target.write_text(updated, encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "replacements": n,
        "bytes": len(updated.encode("utf-8")),
    }


def codebase_search(
    query: str,
    *,
    workspace: str | None = None,
    glob: str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    """@codebase-achtig: ripgrep over workspace (geen embeddings)."""
    q = (query or "").strip()
    if not q:
        return {"error": "lege query"}
    try:
        cwd = resolve_in_workspace(".", workspace=workspace) if workspace else resolve_in_workspace(".")
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    if not cwd.is_dir():
        return {"error": f"cwd bestaat niet: {cwd}"}
    limit = max(1, min(80, limit))
    cmd = ["rg", "-n", "--hidden", "--glob", "!.git", "--glob", "!node_modules", "--glob", "!.venv", "-m", "5", q]
    if glob:
        cmd.extend(["--glob", glob])
    cmd.append(str(cwd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(cwd),
        )
    except FileNotFoundError:
        # fallback: python walk
        return _codebase_search_py(q, cwd, limit=limit, glob=glob)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()][:limit]
    hits = []
    for ln in lines:
        # path:line:text
        parts = ln.split(":", 2)
        if len(parts) >= 3:
            hits.append({"path": parts[0], "line": parts[1], "text": parts[2][:400]})
        else:
            hits.append({"raw": ln[:500]})
    return {"ok": True, "query": q, "cwd": str(cwd), "hits": hits, "count": len(hits)}


def _codebase_search_py(query: str, cwd: Path, *, limit: int, glob: str | None) -> dict[str, Any]:
    q_lower = query.lower()
    hits: list[dict[str, Any]] = []
    skip_dirs = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for name in files:
            if len(hits) >= limit:
                break
            if glob and not Path(name).match(glob.replace("**/", "")):
                continue
            path = Path(root) / name
            if path.suffix.lower() not in {
                ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".swift",
                ".md", ".json", ".toml", ".yml", ".yaml", ".css", ".html", ".sh",
            }:
                continue
            try:
                if path.stat().st_size > 400_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if q_lower in line.lower():
                    hits.append({"path": str(path), "line": str(i), "text": line[:400]})
                    if len(hits) >= limit:
                        break
        if len(hits) >= limit:
            break
    return {"ok": True, "query": query, "cwd": str(cwd), "hits": hits, "count": len(hits), "engine": "py"}


def git_commit(
    message: str,
    *,
    workspace: str | None = None,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    """Veilige git add + commit (geen force/reset)."""
    msg = (message or "").strip()
    if not msg or len(msg) < 3:
        return {"error": "commit message te kort"}
    if _GIT_DENY.search(msg):
        return {"error": "ongeoorloofde tokens in message"}
    try:
        cwd = resolve_in_workspace(".", workspace=workspace) if workspace else resolve_in_workspace(".")
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    if not (cwd / ".git").exists() and not any((p / ".git").exists() for p in cwd.parents):
        # allow if git rev-parse works
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            return {"error": "geen git repo", "cwd": str(cwd)}
    add_cmd = ["git", "add", "--"]
    if paths:
        for p in paths:
            try:
                resolved = resolve_in_workspace(p, workspace=workspace or str(cwd))
            except (ValueError, PermissionError) as exc:
                return {"error": str(exc)}
            add_cmd.append(str(resolved))
    else:
        add_cmd.append("-A")
    add = subprocess.run(add_cmd, cwd=str(cwd), capture_output=True, text=True)
    if add.returncode != 0:
        return {"error": "git add mislukt", "stderr": (add.stderr or "")[-4000:]}
    commit = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return {
        "ok": commit.returncode == 0,
        "returncode": commit.returncode,
        "cwd": str(cwd),
        "stdout": (commit.stdout or "")[-8000:],
        "stderr": (commit.stderr or "")[-4000:],
    }


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
    if cmd.startswith("git ") and _GIT_DENY.search(cmd):
        return {"error": "gevaarlijke git-vlag geweigerd (force/hard reset/clean)"}
    lowered = cmd
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
            timeout=max(5, min(timeout_sec, 300)),
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
