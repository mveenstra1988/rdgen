# MacBook Pro M5 Max · 128 GB · 2 TB — beste lokale settings

Research-samenvatting (okt 2026) voor **jouw** machine, verwerkt in VIT AI Hub 2.1.

## Kern

| | Advies |
|---|---|
| Runtime | **LM Studio + MLX** (niet GGUF) — vaak 25–50% sneller, minder RAM |
| Bruikbaar voor weights | ~**96 GB** van 128 GB unified |
| Bandwidth | ~**614 GB/s** (M5 Max) — modelgrootte bepaalt tok/s |
| Hub-model | `vit/auto` dagelijks · **`vit/max`** voor zware kwaliteit |

## Modellen (MLX)

| Rol | Model | Quant | RAM (indicatief) |
|-----|--------|-------|------------------|
| Daily | **Qwen3.6-35B-A3B** | MLX 4- of 6-bit | ~20–30 GB |
| Quality lokaal | **Qwen3.8-27B** | MLX 6-bit | ~23–28 GB |
| Heavy on-demand | gpt-oss-120B / Nemotron 3 Super ~120B | Q4 | ~60–80 GB |
| Code-alt | Qwen3-Coder 30B-A3B | MLX 4/6-bit | ~20 GB |

Daily = altijd geladen. Heavy = laden bij zware taken, daarna unload (`heavy_unload: true`).

## LM Studio

1. Runtime updaten: **⌘⇧R**
2. Backend: **MLX**
3. Context: start **16 384**; lang werk **32 768** (niet meteen max)
4. GPU/memory: **auto**
5. Één model + één request voor pieksnelheid
6. Temperature: chat ~0.7 · code ~0.3 (hub zet dit per studio)
7. Mac **op stroom** bij heavy; sluit zware Chrome/Docker-tabs

## Ollama (API / warm)

```bash
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
```

- Default `num_ctx` 4096; langer alleen als nodig
- Check: `ollama ps` → **100% GPU**
- Q4_K_M voor snelheid

## Hub (VIT)

In `~/.config/vit/geheimen/ai-gateway.env`:

```bash
VIT_LOCAL_LIGHT_MODEL=<exacte LM Studio-id daily Qwen3.6-35B-A3B>
VIT_LOCAL_HEAVY_MODEL=<exacte id Qwen3.8-27B of 120B>
```

- Voorkeur: **Beste kwaliteit**
- Model: **Slim** of **Max kwaliteit** (`vit/max` = critic + second opinion)
- Studio **Code** voor Cursor-achtig werk

## 2 TB schijf

- Budget ~400 GB voor 2–4 MLX-modellen
- Verwijder dubbele GGUF van dezelfde lijn
- Paths: LM Studio Application Support, `~/.ollama`

## Bronnen

- [localmodel.run M5 Max 128GB](https://localmodel.run/best-llm-for/apple-m5-max-128gb)
- [M5 Max multimodal / LM Studio](http://sungsoo.github.io/2026/09/13/local-multimodal-ai-m5-max-lm-studio.html)
- [M5 Pro vs Max bandwidth](https://www.promptquorum.com/local-llms/apple-silicon-m5-local-llm)
- oMLX benchmarks Qwen3.6-35B-A3B op M5 Max 40c

API: `GET /api/mac/profile`
