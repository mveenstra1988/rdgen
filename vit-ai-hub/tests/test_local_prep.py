from vit_ai_hub.orchestrator.local_prep import build_exec_brief, should_local_prep


def test_should_prep_for_cloud():
    assert should_local_prep(
        destination_local=False,
        studio="chat",
        task="Schrijf een pitch voor ServiceHub backup",
    )
    assert not should_local_prep(
        destination_local=True,
        studio="chat",
        task="hoi",
        skip=False,
    )


def test_build_brief_includes_task_and_memory(tmp_path, monkeypatch):
    import vit_ai_hub.orchestrator.local_prep as lp
    import vit_ai_hub.workspace as ws

    monkeypatch.setattr(ws, "default_roots", lambda: [tmp_path])
    (tmp_path / "app.py").write_text("def main():\n    return 42\n", encoding="utf-8")
    monkeypatch.setattr(lp, "prep_enabled", lambda: True)

    brief = build_exec_brief(
        task="Fix main in app.py so it returns 43",
        workspace=str(tmp_path),
        studio="software",
        knowledge="# VIT kennis\n- ServiceHub is het MSP-portaal",
        memory="# VIT gedeeld geheugen\n- Altijd Nederlands antwoorden",
    )
    assert brief["ok"]
    assert "EXEC_BRIEF" in brief["brief"]
    assert "app.py" in brief["brief"] or any("app.py" in str(f.get("path")) for f in brief["files"])
    assert brief["est_tokens"] >= 1
    assert "uit" in brief["system_note"].lower()
