import json
from pathlib import Path

from vit_ai_hub.importing import chatgpt, claude
from vit_ai_hub.importing.store import search_knowledge, stats

FIXTURES = Path(__file__).parent / "fixtures"


def _isolate_store(tmp_path, monkeypatch):
    import vit_ai_hub.importing.store as store

    data = tmp_path / "knowledge"
    monkeypatch.setattr(store, "DATA", data)
    monkeypatch.setattr(store, "CONVERSATIONS", data / "conversations.jsonl")
    monkeypatch.setattr(store, "MEMORIES", data / "memories.jsonl")
    monkeypatch.setattr(store, "PROJECTS", data / "projects.jsonl")
    monkeypatch.setattr(store, "IMPORT_LOG", data / "imports.jsonl")


def test_chatgpt_import(tmp_path, monkeypatch):
    _isolate_store(tmp_path, monkeypatch)
    summary = chatgpt.import_from_path(FIXTURES / "chatgpt_sample.json")
    assert summary["conversations"]["written"] == 1
    assert stats()["conversations"] == 1
    hits = search_knowledge("WireGuard")
    assert hits


def test_claude_import(tmp_path, monkeypatch):
    _isolate_store(tmp_path, monkeypatch)
    # wrap as conversations-only json file named conversations style via import_from_path json
    # claude import_from_path on bare list json uses filename; copy as conversations.json
    path = tmp_path / "conversations.json"
    path.write_text((FIXTURES / "claude_sample.json").read_text(encoding="utf-8"), encoding="utf-8")
    memories = tmp_path / "memories.json"
    memories.write_text(
        json.dumps([{"uuid": "mem1", "content": "Mike preferert git push production main"}]),
        encoding="utf-8",
    )
    # zip both
    import zipfile

    zpath = tmp_path / "claude-export.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(path, "conversations.json")
        zf.write(memories, "memories.json")
        zf.writestr(
            "projects.json",
            json.dumps(
                [
                    {
                        "uuid": "p1",
                        "name": "VIT",
                        "instructions": "Geen klantwachtwoorden resetten zonder akkoord.",
                    }
                ]
            ),
        )
    summary = claude.import_from_path(zpath)
    assert summary["conversations"]["written"] == 1
    assert summary["memories"]["written"] >= 1
    assert summary["projects"]["written"] == 1
    assert search_knowledge("wachtwoorden")
