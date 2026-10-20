from vit_ai_hub.mac_profile import get_profile, hub_overrides_for_profile, list_profiles
from vit_ai_hub.orchestrator.quality import pick_opinion_model, quality_system_addon, want_second_opinion
from vit_ai_hub.orchestrator.intent import Intent


def test_m5_profile():
    p = get_profile("m5-max-128")
    assert p["unified_memory_gb"] == 128
    assert "Qwen" in p["models"]["daily"]["id_hint"]
    assert p["lm_studio"]["backend"].startswith("MLX")
    assert list_profiles()
    ov = hub_overrides_for_profile()
    assert ov["orchestrator"]["second_opinion"] is True
    assert ov["orchestrator"]["critic_rounds"] == 2


def test_quality_stack_flags():
    intent = Intent(
        kind="code",
        complexity="high",
        confidence=0.9,
        multi_agent=False,
        suggested_team=None,
        suggested_studio="software",
    )
    assert want_second_opinion(intent, tradeoff="quality", use_team=False)
    assert not want_second_opinion(intent, tradeoff="latency", use_team=False)
    addon = quality_system_addon(studio="software", tradeoff="quality")
    assert "quality stack" in addon.lower()
    assert pick_opinion_model("claude-sonnet", ["deepseek-chat", "claude-sonnet"]) == "deepseek-chat"
