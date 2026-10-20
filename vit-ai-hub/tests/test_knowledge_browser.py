from vit_ai_hub.importing import store


def test_list_and_get_conversation(tmp_path, monkeypatch):
    data = tmp_path / "knowledge"
    monkeypatch.setattr(store, "DATA", data)
    monkeypatch.setattr(store, "CONVERSATIONS", data / "conversations.jsonl")
    monkeypatch.setattr(store, "MEMORIES", data / "memories.jsonl")
    monkeypatch.setattr(store, "PROJECTS", data / "projects.jsonl")
    monkeypatch.setattr(store, "SKILLS", data / "skills.jsonl")
    monkeypatch.setattr(store, "SETTINGS_BUNDLE", data / "settings_bundles.jsonl")
    monkeypatch.setattr(store, "IMPORT_LOG", data / "imports.jsonl")

    store.save_conversations(
        [
            {
                "native_id": "c1",
                "title": "ServiceHub pitch",
                "updated_at": 100,
                "messages": [
                    {"role": "user", "content": "Schrijf een pitch"},
                    {"role": "assistant", "content": "Hier is de pitch"},
                ],
            }
        ],
        source="chatgpt",
    )
    items = store.list_conversations(q="pitch")
    assert items and items[0]["title"] == "ServiceHub pitch"
    full = store.get_imported_conversation(items[0]["id"])
    assert full and len(full["messages"]) == 2
