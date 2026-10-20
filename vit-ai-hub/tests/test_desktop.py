from vit_ai_hub.tools.desktop import run_shell_safe


def test_shell_allowlist_blocks():
    out = run_shell_safe("rm -rf /")
    assert out["ok"] is False
    assert "allowlist" in out.get("error", "").lower() or "niet" in out.get("error", "").lower()


def test_shell_allowlist_pwd_shape():
    # may run in cloud linux; pwd is allowlisted
    out = run_shell_safe("pwd")
    assert "ok" in out
