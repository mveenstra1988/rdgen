from vit_ai_hub.setup_api import save_secrets, setup_status


def test_setup_status_shape():
    s = setup_status()
    assert "version" in s
    assert "secret_file" in s


def test_save_secrets_filters(tmp_path, monkeypatch):
    import vit_ai_hub.setup_api as setup

    secret = tmp_path / "ai-gateway.env"
    monkeypatch.setattr(setup, "SECRET_FILE", secret)
    out = save_secrets(
        {
            "OPENROUTER_API_KEY": "sk-test",
            "EVIL": "nope",
            "XAI_API_KEY": "xai-1",
        }
    )
    assert out["ok"]
    text = secret.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=sk-test" in text
    assert "XAI_API_KEY=xai-1" in text
    assert "EVIL" not in text
