from vit_ai_hub.router import ModelRouter


def test_resolve_openrouter_ox_alpha():
    r = ModelRouter()
    # may have no API key; still should pick openrouter backend object if enabled
    decision = r.resolve("stealth/ox-alpha")
    assert decision.model == "stealth/ox-alpha"
    assert decision.backend.name in {"openrouter", "omniroute", "bridge", "lmstudio", "ollama"}


def test_resolve_virtual_auto():
    r = ModelRouter()
    decision = r.resolve("vit/auto")
    assert decision.virtual == "vit/auto"