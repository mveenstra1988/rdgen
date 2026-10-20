from vit_ai_hub.agent_modes import (
    filter_tools_for_mode,
    normalize_mode,
    parse_leading_slash,
)
from vit_ai_hub.project_context import load_project_instructions


def test_normalize_and_slash():
    assert normalize_mode("PLAN") == "plan"
    assert normalize_mode(None) == "agent"
    mode, rest = parse_leading_slash("/plan bouw auth")
    assert mode == "plan" and rest == "bouw auth"
    mode2, rest2 = parse_leading_slash("gewoon tekst")
    assert mode2 is None and rest2 == "gewoon tekst"


def test_filter_tools():
    tools = [
        {"type": "function", "function": {"name": "read_workspace_file"}},
        {"type": "function", "function": {"name": "search_replace"}},
        {"type": "function", "function": {"name": "codebase_search"}},
    ]
    ask = filter_tools_for_mode(tools, "ask")
    names = {(t.get("function") or {}).get("name") for t in ask}
    assert "search_replace" not in names
    assert "read_workspace_file" in names
    plan = filter_tools_for_mode(tools, "plan")
    pnames = {(t.get("function") or {}).get("name") for t in plan}
    assert "search_replace" not in pnames
    assert "codebase_search" in pnames


def test_project_context(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Rules\nUse pnpm\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("Be concise\n", encoding="utf-8")
    out = load_project_instructions(str(tmp_path))
    assert out["ok"]
    assert "AGENTS.md" in out["text"]
    assert "pnpm" in out["text"]
