# VIT AI Hub

Lokale GUI + privacy gateway voor je Mac (M5 Max 128GB-ready).

Één app met **echte modelpicker** voor:

- Lokale modellen (LM Studio / Ollama, MLX)
- Claude + ChatGPT via subscription bridge (OAuth/abo)
- **Grok / xAI** (`XAI_API_KEY`)
- Cursor (zelfde gateway als OpenAI-compat provider)
- OpenRouter (incl. **Ox Alpha** `stealth/ox-alpha` en `z-ai/glm-5.3-flash`)
- OmniRoute

Plus: privacyfilter, desktop-tools (Chrome, Mail, **VIT Mail**, apps, Spotlight),
live sync, FTS-kennisindex, ChatGPT/Claude live-lees (Accessibility),
OpenAI- én Anthropic-compat endpoints.

## Morgen / één pakket (Mac)

1. Download `dist/VIT-AI-Hub-0.9.0-mac.zip` (of uit de PR-artifacts)
2. Unzip → eventueel `xattr -dr com.apple.quarantine "VIT AI Hub.app" hub`
3. Dubbelklik **VIT AI Hub.app** → wizard → **Migreer ALLES** (settings/MCP/rules/prompts/skills/chats)
4. Tab **Agent teams** · studio **Self-improve** om de hub zelf te laten aanpassen

Echte `.pkg` op de Mac: `bash hub/packaging/build-mac-pkg.sh`

## Agent teams

In de GUI: **Agent teams**. Presets: Webdesign team (design → frontend → copy) en Applicatie team (architect → engineer → QA). Zelf agents/teams maken, volgorde zetten, pipeline of board+synthese, daarna **Run team**.

## Claude / ChatGPT / Cursor eruit?

Zie `docs/EXIT.md`. Kort:
- **Chat:** studio Chat + lokaal/OpenRouter
- **Code:** studio Software + workspace, of VS Code/Zed + Continue → hub
- **Design:** studio Webdesign (design-in-code) of Penpot (`scripts/install-penpot-mac.sh`)

Details: `docs/STUDIO.md`

Zie ook `MORGEN.md`.

## Snel starten (dev)

```bash
cd vit-ai-hub
chmod +x scripts/*.sh
./scripts/one-shot-setup.sh
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

## Kennis & geheugen van dezelfde Mac

In de GUI:

1. **Importeer alles van deze Mac**  
   Cursor + Claude Code/Cowork + Claude Desktop local sessions + ChatGPT-cache/fragmenten + eventuele export-zips in Downloads.
2. **Start export vanuit apps**  
   Opent ChatGPT Data Controls + Claude Privacy (osascript/URLs). Jij klikt eenmaal Export.
3. **Wacht op zips & importeer**  
   Watcht Downloads/Desktop en importeert automatisch.

### Wat wél / niet lokaal leesbaar is
| Bron | Op de Mac |
|------|-----------|
| Cursor / Agent Store | Ja |
| Claude Code (`~/.claude`) | Ja (JSONL + memory) |
| Claude/Cursor **skills** (`SKILL.md`) | Ja → kennis + agents/bots |
| MCP / rules / prompts / settings / hooks | Ja (full migrate mirror + actief profiel) |
| Custom GPTs / Claude.ai cloud-only bots | Alleen wat lokaal/export is → verder via Agent teams |
| Hub self-improve | Studio **Self-improve** + workspace-write op hub-root |
| Claude Cowork / local-agent | Ja (waar aanwezig) |
| Claude.ai webchats in Desktop-app | Meestal **niet** (server-side) → export |
| ChatGPT Mac-app (open op scherm) | **Ja via Accessibility** (knop “Lees ChatGPT”) + Keychain-decrypt best-effort |
| ChatGPT `*.data` at rest | Encrypted; volledige offline dump nog steeds via officiële export |

Dus: zelfde Mac, ja. Maar ChatGPT encrypt zijn app-history; daarvoor is de officiële export de betrouwbare volledige dump. De hub automatiseert dat pad zoveel mogelijk.

API: `POST /api/import/all`, `/api/import/local-mac`, `/api/import/request-exports`, `/api/import/wait-exports`, `/api/import/upload`

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
