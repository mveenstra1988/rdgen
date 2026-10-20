from vit_ai_hub.tools.vit_apps import list_vit_apps, open_vit_app, resolve_vit_app


def test_suite_has_core_apps():
    ids = {a["id"] for a in list_vit_apps()["apps"]}
    assert {"mail", "kluis", "backup", "office", "pdf", "remote"} <= ids


def test_resolve_aliases():
    assert resolve_vit_app("bitwarden")["id"] == "kluis"
    assert resolve_vit_app("vaultwarden")["id"] == "kluis"
    assert resolve_vit_app("vit mail")["id"] == "mail"
    assert resolve_vit_app("remote manager")["id"] == "remote"


def test_open_unknown():
    out = open_vit_app("nietbestaand")
    assert out["ok"] is False
    assert "known" in out
