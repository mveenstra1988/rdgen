from pathlib import Path

from vit_ai_hub.workspace import list_workspace_dir, read_workspace_file, run_in_workspace, write_workspace_file


def test_write_read_roundtrip(tmp_path, monkeypatch):
    import vit_ai_hub.workspace as ws

    monkeypatch.setattr(ws, "default_roots", lambda: [tmp_path])
    out = write_workspace_file("demo.txt", "hallo", workspace=str(tmp_path))
    assert out["ok"]
    got = read_workspace_file("demo.txt", workspace=str(tmp_path))
    assert got["content"] == "hallo"


def test_blocks_outside_root(tmp_path, monkeypatch):
    import vit_ai_hub.workspace as ws

    monkeypatch.setattr(ws, "default_roots", lambda: [tmp_path])
    out = write_workspace_file("/etc/passwd", "x", workspace=str(tmp_path))
    assert "error" in out


def test_list_dir(tmp_path, monkeypatch):
    import vit_ai_hub.workspace as ws

    monkeypatch.setattr(ws, "default_roots", lambda: [tmp_path])
    (tmp_path / "a.py").write_text("1\n", encoding="utf-8")
    listed = list_workspace_dir(".", workspace=str(tmp_path))
    assert any(e["name"] == "a.py" for e in listed["entries"])


def test_run_allowlist(tmp_path, monkeypatch):
    import vit_ai_hub.workspace as ws

    monkeypatch.setattr(ws, "default_roots", lambda: [tmp_path])
    bad = run_in_workspace("rm -rf /", workspace=str(tmp_path))
    assert "error" in bad
    ok = run_in_workspace("python3 -c 'print(2+2)'", workspace=str(tmp_path))
    assert ok.get("ok") is True
    assert "4" in ok.get("stdout", "")


def test_studio_list():
    from vit_ai_hub.studio import list_studios, studio_system_prompt

    ids = {s["id"] for s in list_studios()}
    assert "software" in ids and "webdesign" in ids and "design" in ids
    assert "Penpot" in (studio_system_prompt("design") or "")
