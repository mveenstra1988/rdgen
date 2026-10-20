from pathlib import Path

from vit_ai_hub.tools.vit_apps import (
    handoff_file,
    list_vit_apps,
    open_vit_app,
    resolve_vit_app,
    vit_app_tool_specs,
)


def test_suite_has_core_apps():
    ids = {a["id"] for a in list_vit_apps()["apps"]}
    assert {"mail", "kluis", "backup", "office", "pdf", "remote"} <= ids


def test_list_exposes_actions():
    mail = next(a for a in list_vit_apps()["apps"] if a["id"] == "mail")
    assert "compose" in mail["actions"]
    kluis = next(a for a in list_vit_apps()["apps"] if a["id"] == "kluis")
    assert "search" in kluis["actions"]


def test_resolve_aliases():
    assert resolve_vit_app("bitwarden")["id"] == "kluis"
    assert resolve_vit_app("vaultwarden")["id"] == "kluis"
    assert resolve_vit_app("vit mail")["id"] == "mail"
    assert resolve_vit_app("remote manager")["id"] == "remote"
    assert resolve_vit_app("xlsx")["id"] == "rekenbladen"


def test_open_unknown():
    out = open_vit_app("nietbestaand")
    assert out["ok"] is False
    assert "known" in out


def test_handoff_routes_by_extension(tmp_path, monkeypatch):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    docx = tmp_path / "y.docx"
    docx.write_bytes(b"PK")
    xlsx = tmp_path / "z.xlsx"
    xlsx.write_bytes(b"PK")

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("vit_ai_hub.tools.vit_apps.subprocess.run", fake_run)
    monkeypatch.setattr("vit_ai_hub.tools.vit_apps._darwin", lambda: True)
    monkeypatch.setattr(
        "vit_ai_hub.tools.vit_apps._find_installed",
        lambda entry: {"installed": True, "paths": [f"/Applications/{entry['name']}.app"], "running": False},
    )

    out_pdf = handoff_file(str(pdf))
    assert out_pdf["ok"] and out_pdf.get("routed") == "pdf"
    out_doc = handoff_file(str(docx))
    assert out_doc["ok"] and out_doc.get("routed") == "office"
    out_xls = handoff_file(str(xlsx))
    assert out_xls["ok"] and out_xls.get("routed") == "rekenbladen"
    assert any("open" in c for c in calls)


def test_handoff_missing_file():
    out = handoff_file("/tmp/vit-hub-does-not-exist-xyz.pdf")
    assert out["ok"] is False


def test_tool_specs_include_handoff():
    names = {t["function"]["name"] for t in vit_app_tool_specs()}
    assert names == {"vit_apps_list", "vit_app_open", "vit_app_handoff"}
