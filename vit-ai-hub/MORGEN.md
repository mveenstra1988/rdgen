# Morgen: 1 pakket, klaar

## Wat je draait
1. Unzip `dist/VIT-AI-Hub-0.6.1-mac.zip` (of de artifact)
2. Eventueel: `xattr -dr com.apple.quarantine "VIT AI Hub.app" hub`
3. Dubbelklik **VIT AI Hub.app**
4. Klik **Alles nu regelen**

Klaar: GUI op http://127.0.0.1:8787 met import + sync.

## Optioneel daarna
- Keys in wizard (OpenRouter, Grok, bridge)
- LM Studio met light model
- Cursor → OpenAI Base URL `http://127.0.0.1:8787/v1`
- Echte installer: `bash hub/packaging/build-mac-pkg.sh` → `.pkg`
