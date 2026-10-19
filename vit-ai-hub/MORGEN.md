# Morgen: 1 pakket, klaar

## Wat je draait
Unzip `dist/VIT-AI-Hub-0.6.0-mac.zip` op je MacBook.

Dubbelklik **VIT AI Hub.app** (of `START.command`).

De wizard regelt:
1. Secrets-bestand + token  
2. Dependencies / gateway  
3. Import + live sync  
4. GUI open

## Optioneel daarna
- Keys invullen in wizard (OpenRouter, Grok, bridge)
- LM Studio starten met light model
- Cursor → OpenAI Base URL `http://127.0.0.1:8787/v1`
- Echte installer: `bash hub/packaging/build-mac-pkg.sh` → `.pkg`
