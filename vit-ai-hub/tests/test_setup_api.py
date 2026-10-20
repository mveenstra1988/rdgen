from vit_ai_hub.setup_api import bootstrap_all, save_secrets, setup_status


def test_setup_status_shape():
    s = setup_status()
    assert "version" in s
    assert "secret_file" in s
    assert "gateway_token" not in s


def test_open_guide_known_targets():
    from vit_ai_hub.setup_api import GUIDE_TARGETS, open_guide

    assert "openrouter_keys" in GUIDE_TARGETS
    assert "bridge_docs" in GUIDE_TARGETS
    assert "gemini_keys" in GUIDE_TARGETS
    assert "vit_kluis" in GUIDE_TARGETS
    assert "kluis_web" in GUIDE_TARGETS
    # non-darwin returns structured error, not crash
    out = open_guide("openrouter_keys")
    assert "ok" in out


def test_probe_includes_gemini_and_vit(monkeypatch):
    from vit_ai_hub.setup_api import probe_providers
    import vit_ai_hub.setup_api as setup

    monkeypatch.setattr(setup, "_read_secret_map", lambda: {"GEMINI_API_KEY": "AIza-test"})
    monkeypatch.setattr(
        setup,
        "setup_status",
        lambda include_token=False: {
            "version": "test",
            "setup_complete": False,
            "lmstudio_up": False,
            "ollama_up": False,
        },
    )
    out = probe_providers()
    assert out["gemini_key"] is True
    assert "vit_apps" in out
    assert "vit_apps_installed" in out


def test_setup_status_can_include_token(tmp_path, monkeypatch):
    import vit_ai_hub.setup_api as setup

    secret = tmp_path / "ai-gateway.env"
    secret.write_text("VIT_GATEWAY_TOKEN=vit-abc123\n", encoding="utf-8")
    monkeypatch.setattr(setup, "SECRET_FILE", secret)
    s = setup_status(include_token=True)
    assert s["gateway_token"] == "vit-abc123"


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


def test_bootstrap_all(tmp_path, monkeypatch):
    import vit_ai_hub.setup_api as setup

    marker = tmp_path / ".setup-complete"
    monkeypatch.setattr(setup, "SETUP_MARKER", marker)

    def fake_migrate(**_kwargs):
        return {
            "ok": True,
            "knowledge_import": {"knowledge": {"conversations": 1, "memories": 0, "projects": 0}},
            "profile": {"mcp_servers": []},
        }

    monkeypatch.setattr(
        "vit_ai_hub.importing.full_migrate.migrate_everything",
        fake_migrate,
    )

    class SyncMod:
        @staticmethod
        def sync_once(**_kwargs):
            return {"ok": True}

        @staticmethod
        def start_sync(**_kwargs):
            return {"running": True}

    import sys
    import types

    sync_mod = types.ModuleType("vit_ai_hub.importing.sync")
    sync_mod.sync_once = SyncMod.sync_once
    sync_mod.start_sync = SyncMod.start_sync
    monkeypatch.setitem(sys.modules, "vit_ai_hub.importing.sync", sync_mod)

    out = bootstrap_all(open_a11y=False)
    assert out["ok"]
    assert marker.is_file()
    assert out["knowledge"]["conversations"] == 1
