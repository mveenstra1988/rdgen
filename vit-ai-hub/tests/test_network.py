"""LAN / PWA network helpers."""

from __future__ import annotations


def test_network_info_and_lan_toggle(tmp_path, monkeypatch):
    import vit_ai_hub.network as net
    from vit_ai_hub import config

    env = tmp_path / "ai-gateway.env"
    env.write_text("VIT_GATEWAY_TOKEN=vit-test-token-abc\nVIT_GATEWAY_HOST=127.0.0.1\n", encoding="utf-8")
    monkeypatch.setattr(net, "SECRET_CANDIDATES", [env])
    monkeypatch.setattr(config, "SECRET_CANDIDATES", [env])
    config.get_settings.cache_clear()

    info = net.network_info()
    assert info["ok"] is True
    assert "port" in info

    # without real token should fail — use our token
    monkeypatch.setenv("VIT_GATEWAY_TOKEN", "vit-test-token-abc")
    config.get_settings.cache_clear()
    out = net.set_lan_access(True)
    assert out["ok"] is True
    assert out["lan_enabled"] is True
    assert "0.0.0.0" in env.read_text()

    out2 = net.set_lan_access(False)
    assert out2["ok"] is True
    assert out2["lan_enabled"] is False


def test_qr_svg():
    from vit_ai_hub.network import qr_svg_for_url

    svg = qr_svg_for_url("http://192.168.1.10:8787/?token=x")
    assert "<svg" in svg.lower()
