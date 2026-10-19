# VIT AI Hub

Lokale GUI + privacy gateway voor je Mac (M5 Max 128GB-ready).

Één app met **echte modelpicker** voor:

- Lokale modellen (LM Studio / Ollama, MLX)
- Claude + ChatGPT via subscription bridge (OAuth/abo)
- Cursor (zelfde gateway als OpenAI-compat provider)
- OpenRouter (incl. **Ox Alpha** `stealth/ox-alpha` en `z-ai/glm-5.3-flash`)
- OmniRoute

Plus: privacyfilter (fail-closed), tools (web/memory/files), OpenAI- én Anthropic-compat endpoints,
en **1-klik import** van ChatGPT + Claude + Cursor kennis/geheugen.

## Snel starten (Mac)

```bash
cd vit-ai-hub
chmod +x scripts/*.sh
./scripts/install-mac.sh
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787)

Secrets: `~/.config/vit/geheimen/ai-gateway.env` (template uit `.env.example`).

## Architectuur

```
GUI / Cursor / clients
        ↓
  VIT Gateway :8787   ← privacyfilter
        ↓
 LM Studio | Bridge(Claude/GPT) | Cursor-pad | OpenRouter | OmniRoute
```

## Belangrijke endpoints

| Pad | Functie |
|-----|---------|
| `GET /` | Lokale GUI |
| `GET /v1/models` | Samengevoegde modelcatalogus |
| `POST /v1/chat/completions` | OpenAI-compat chat |
| `POST /v1/messages` | Anthropic-compat shim |
| `GET /api/capabilities` | Tool/pariteit-manifest |
| `POST /api/chat` | GUI-chat met tools aan |

## Kennis & geheugen importeren (1 klik)

In de GUI: **Importeer alles (1 klik)**.

Dat doet:
1. **Cursor** lokaal scannen (`~/.cursor`, Application Support, Agent Store/geheugen)
2. Nieuwste **ChatGPT**- en **Claude**-exportzips in `~/Downloads` of `~/Desktop` importeren
3. Alles opslaan onder `data/knowledge/` (chats, memories, projects)
4. Bij elke chat wordt relevante kennis automatisch in de context gezet

Handmatig:
- ChatGPT: Settings → Data controls → Export → zip downloaden → in Downloads zetten of uploaden
- Claude: Settings → Privacy → Export → zip downloaden → in Downloads zetten of uploaden
- API: `POST /api/import/all`, `POST /api/import/upload`, `GET /api/knowledge/search?q=`

## Privacy

Cloud-requests met gedetecteerde klant-PII worden **geblokkeerd of naar lokaal geforceerd**.
Audit zonder raw secrets: `data/audit.jsonl`.

## RAM-beleid (M5 Max)

- Light MoE lokaal resident (~20GB)
- Heavy alleen on-demand
- Cloud kost geen model-RAM
- Houd ~48GB vrij voor Cursor/apps

Zie `config/default.yaml` en `docs/CURSOR.md`.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
pytest -q
./scripts/start.sh
```
