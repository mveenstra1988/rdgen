# Morgen — VIT AI Hub 2.6.3

**Fix:** login-knoppen deden niets omdat `install-auto` de server blokkeerde.

1. Quit AI Hub (Cmd+Q)
2. Pull of open nieuwe DMG `VIT-AI-Hub-2.6.3-mac.dmg`
3. Opnieuw openen → Inloggen → knoppen tonen «Bezig…» en openen browser

Of in Terminal:
```bash
curl -fsSL https://raw.githubusercontent.com/mveenstra1988/rdgen/cursor/vit-ai-hub-a440/vit-ai-hub/scripts/pull-to-ai-projecten.sh | bash
# daarna app opnieuw starten vanuit Applications of ~/AI-projecten/VIT-ai-hub
```
