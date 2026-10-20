from vit_ai_hub.importing.chatgpt_live import _lines_to_conversation, _try_decrypt_blob


def test_lines_to_conversation():
    lines = [
        "AXStaticText|Hoe werkt WireGuard?",
        "AXStaticText|Gebruik wg-quick en een interface.",
        "AXButton|New chat",
    ]
    conv = _lines_to_conversation(lines, "Test")
    assert conv is not None
    assert conv["title"] == "Test"
    assert conv["messages"]


def test_decrypt_rejects_garbage():
    assert _try_decrypt_blob(b"0" * 32, b"not-ciphertext-at-all") is None
