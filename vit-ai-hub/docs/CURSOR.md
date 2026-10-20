# Cursor koppelen aan VIT AI Hub

1. Start de hub: `./scripts/start.sh` → `http://127.0.0.1:8787`
2. Cursor → Settings → Models:
   - **Override OpenAI Base URL:** `http://127.0.0.1:8787/v1`
   - **OpenAI API Key:** waarde van `VIT_GATEWAY_TOKEN` (of `vit-local` als token leeg is en auth uit staat)
3. Zet custom models aan en voeg IDs toe die je in `/v1/models` ziet, bijvoorbeeld:
   - `vit/auto`
   - `stealth/ox-alpha`
   - `z-ai/glm-5.3-flash`
   - jouw Claude/GPT IDs via de bridge
   - lokale LM Studio model-IDs

Alle Cursor-requests gaan zo door de privacyfilter.

## Abonnementen
- Claude / ChatGPT: draai een OAuth subscription bridge (bijv. CLIProxyAPI) op `:8317` en zet `BRIDGE_BASE_URL`.
- OpenRouter: `OPENROUTER_API_KEY` in `~/.config/vit/geheimen/ai-gateway.env`
- OmniRoute: lokale OmniRoute op `:20128`
- Cursor-abo: blijf Cursor gebruiken; models via deze base URL + Cursor’s eigen picker waar nodig