from vit_ai_hub.config import get_settings, load_yaml_config
from vit_ai_hub.pii.engine import PiiEngine


def _fresh_engine(tmp_path, monkeypatch) -> PiiEngine:
    monkeypatch.setenv("VIT_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    get_settings.cache_clear()
    load_yaml_config.cache_clear()
    return PiiEngine()


def test_email_blocked_for_cloud(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path, monkeypatch)
    engine.cloud_action = "block"
    result = engine.process("Mail klant jan@voorbeeld.nl even", destination_local=False)
    assert result.has_pii
    assert result.blocked
    assert result.action == "block"


def test_email_allowed_local(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path, monkeypatch)
    engine.local_action = "allow"
    result = engine.process("Mail klant jan@voorbeeld.nl even", destination_local=True)
    assert result.has_pii
    assert not result.blocked
    assert "jan@voorbeeld.nl" in result.text


def test_redact_and_rehydrate(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path, monkeypatch)
    engine.cloud_action = "redact"
    result = engine.process("bel +31612345678 of mail a@b.nl", destination_local=False)
    assert not result.blocked
    assert "a@b.nl" not in result.text
    assert "⟦" in result.text
    restored = engine.rehydrate("Contacteer ⟦EMAIL_1⟧", result.token_map)
    assert "a@b.nl" in restored
