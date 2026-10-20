from vit_ai_hub.importing import chatgpt
from vit_ai_hub.importing.index_fts import fts_search, rebuild_index
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_fts_index(tmp_path, monkeypatch):
    import vit_ai_hub.importing.store as store
    import vit_ai_hub.importing.index_fts as fts

    data = tmp_path / "knowledge"
    monkeypatch.setattr(store, "DATA", data)
    monkeypatch.setattr(store, "CONVERSATIONS", data / "conversations.jsonl")
    monkeypatch.setattr(store, "MEMORIES", data / "memories.jsonl")
    monkeypatch.setattr(store, "PROJECTS", data / "projects.jsonl")
    monkeypatch.setattr(store, "IMPORT_LOG", data / "imports.jsonl")
    monkeypatch.setattr(fts, "DB_PATH", data / "index.sqlite")
    monkeypatch.setattr(fts, "CONVERSATIONS", data / "conversations.jsonl")
    monkeypatch.setattr(fts, "MEMORIES", data / "memories.jsonl")
    monkeypatch.setattr(fts, "PROJECTS", data / "projects.jsonl")

    chatgpt.import_from_path(FIXTURES / "chatgpt_sample.json")
    info = rebuild_index()
    assert info["docs"] >= 1
    hits = fts_search("WireGuard")
    assert hits
