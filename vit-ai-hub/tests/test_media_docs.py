from vit_ai_hub.tools.media import media_capabilities, read_document


def test_read_document_txt(tmp_path, monkeypatch):
    import vit_ai_hub.workspace as ws

    monkeypatch.setattr(ws, "default_roots", lambda: [tmp_path])
    f = tmp_path / "brief.md"
    f.write_text("# Pitch\nServiceHub is top.\n", encoding="utf-8")
    out = read_document("brief.md", workspace=str(tmp_path))
    assert out["ok"]
    assert "ServiceHub" in out["content"]


def test_media_capabilities_shape():
    caps = media_capabilities()
    assert caps["web_search"] is True
    assert caps["generate_image_local"] is True
    assert caps["video_generate"] is False
    assert "nano_banana" in caps
