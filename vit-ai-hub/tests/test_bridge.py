from vit_ai_hub import bridge as br


def test_ensure_config(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "BRIDGE_HOME", tmp_path / "bridge")
    monkeypatch.setattr(br, "CONFIG_PATH", tmp_path / "bridge" / "config.yaml")
    monkeypatch.setattr(br, "AUTH_DIR", tmp_path / "auth")
    out = br.ensure_config()
    assert out["ok"]
    assert out["api_key"].startswith("vit-")
    text = br.CONFIG_PATH.read_text(encoding="utf-8")
    assert "8317" in text
    assert out["api_key"] in text
    # second call keeps key
    out2 = br.ensure_config()
    assert out2["api_key"] == out["api_key"]


def test_wire_hub_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "BRIDGE_HOME", tmp_path / "bridge")
    monkeypatch.setattr(br, "CONFIG_PATH", tmp_path / "bridge" / "config.yaml")
    monkeypatch.setattr(br, "AUTH_DIR", tmp_path / "auth")

    import vit_ai_hub.setup_api as setup
    import vit_ai_hub.pool.store as store

    monkeypatch.setattr(setup, "SECRET_FILE", tmp_path / "ai-gateway.env")
    monkeypatch.setattr(store, "ACCOUNTS_PATH", tmp_path / "accounts.json")

    cfg = br.ensure_config()
    wired = br.wire_hub_secrets(cfg["api_key"])
    assert wired["secrets"]["ok"]
    secrets = tmp_path.joinpath("ai-gateway.env").read_text(encoding="utf-8")
    assert "BRIDGE_BASE_URL=" in secrets
    assert cfg["api_key"] in secrets
    assert wired["account"]["ok"]


def test_bridge_status_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "BRIDGE_HOME", tmp_path / "bridge")
    monkeypatch.setattr(br, "CONFIG_PATH", tmp_path / "bridge" / "config.yaml")
    monkeypatch.setattr(br, "AUTH_DIR", tmp_path / "auth")
    monkeypatch.setattr(br, "bridge_binary", lambda: None)
    monkeypatch.setattr(br, "is_running", lambda: False)
    st = br.bridge_status()
    assert st["ok"]
    assert st["installed"] is False
    assert "claude_logged_in" in st


def test_auth_files_detect(tmp_path, monkeypatch):
    auth = tmp_path / "auth"
    auth.mkdir()
    (auth / "claude-user.json").write_text("{}", encoding="utf-8")
    (auth / "codex-abc.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(br, "AUTH_DIR", auth)
    files = br._auth_files()
    assert files["claude"]
    assert files["codex"]


def test_start_login_non_darwin(monkeypatch):
    monkeypatch.setattr(br, "_darwin", lambda: False)
    out = br.start_login("claude")
    assert out["ok"] is False
