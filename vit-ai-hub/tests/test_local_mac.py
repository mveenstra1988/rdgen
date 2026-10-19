from vit_ai_hub.importing.local_mac import detect_local_apps, harvest_all_local


def test_detect_local_apps_shape():
    info = detect_local_apps()
    assert "chatgpt_app" in info
    assert "claude_desktop" in info
    assert "claude_code_transcripts" in info


def test_harvest_all_local_runs(tmp_path, monkeypatch):
    import vit_ai_hub.importing.store as store

    data = tmp_path / "knowledge"
    monkeypatch.setattr(store, "DATA", data)
    monkeypatch.setattr(store, "CONVERSATIONS", data / "conversations.jsonl")
    monkeypatch.setattr(store, "MEMORIES", data / "memories.jsonl")
    monkeypatch.setattr(store, "PROJECTS", data / "projects.jsonl")
    monkeypatch.setattr(store, "IMPORT_LOG", data / "imports.jsonl")
    result = harvest_all_local()
    assert "detection" in result
    assert "claude_code" in result
    assert "chatgpt_local" in result
