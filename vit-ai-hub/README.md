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

1. Open `dist/VIT-AI-Hub-1.8.0-mac.dmg` → sleep **VIT AI Hub** naar Applications  
   (of unzip `VIT-AI-Hub-1.8.0-mac.zip`)
2. Eventueel: `xattr -dr com.apple.quarantine "/Applications/VIT AI Hub.app"`
3. Dubbelklik **VIT AI Hub** → hub start + browser (wizard alleen eerste keer)
4. **Sluiten (Cmd+Q)** stopt de hub — één app, geen losse tools
5. Chat: **vit/auto** · Growth/Visual/Site via studio of auto-router

Echte `.pkg` op de Mac: `bash hub/packaging/build-mac-pkg.sh`

## iPhone (PWA) & multi-venster

1. In de hub: **⚙ Instellingen → iPhone / PWA → LAN-modus aan**
2. App **herstarten** (Cmd+Q → opnieuw openen)
3. Scan QR of kopieer de link op je iPhone (zelfde wifi)
4. Safari → Deel → **Zet op beginscherm**

Desktop: **⧉** opent een **nieuwe onafhankelijke chat** in een apart venster; **▦** doet hetzelfde voor Teams. Meerdere vensters naast elkaar = parallel werken.

## vit/auto (slimmer dan Cursor Auto)

Met model **vit/auto** (default):
1. Classificeert de opdracht (code / design / ops / marketing / socials / seo / write / research / complex)
2. **Strong/weak** routing (RouteLLM-achtig) + tradeoff quality/cost/latency
3. Kiest het beste beschikbare model (lokaal, Claude bridge, DeepSeek, OpenRouter free, …)
4. **Fallback cascade** bij fout/lege output (OpenRouter-style ordered models)
5. **Critic loop** (maker-checker) bij code/design/complex — 1 revise-ronde
6. Bij complexe multi-stap taken: auto agent-team met **per rol een ander model**
7. **Growth router**: pitches/sites → Marketing / Socials / SEO-GEO of `team-growth`
8. Telemetrie in `data/orchestrator.jsonl` · PII fail-closed blijft

Preview: `POST /api/orchestrator/plan` met `{"text":"…","tradeoff":"cost"}`.

## Multi-abo pools (3× Claude / 3× ChatGPT / 3× Cursor)

Pools: `bridge`, `cursor`, `openrouter`, `deepseek`, `grok`.  
Opslaan in `~/.config/vit/geheimen/accounts.json` (of env `BRIDGE_BASE_URL_1` … `_3`).

- Round-robin over gezonde abos (least-recently-used)
- Tags: `claude` / `chatgpt` / `cursor` — Claude-modellen prefereren Claude-tags
- Bij 429/rate-limit → soft cooldown (~5 min) → volgende abo
- Bij quota/billing → hard cooldown (~6 u) → volgende abo
- GUI: sidebar **Abo-pools** · API: `GET/POST /api/accounts/{pool}`

## Ops / Infra

Studio **Ops / Infra** + team **Infra**. Secrets: `~/.config/vit/geheimen/ops.env` (template via knop **Ops status** of `ops_ensure_env`).
VPN voor Proxmox/UniFi. Tools zijn read-first; VM start/stop/reboot alleen met `confirm=true`.

| Service | Tools |
|---------|--------|
| Proxmox | `proxmox_status`, `proxmox_vms`, `proxmox_vm_action` |
| Nextcloud / Gromox / Mailcow | `*_status` / `gromox_health` |
| ServiceHub / UniFi / Backup / automation-hub | status + disk SSH (allowlist) |

API (localhost): `GET /api/ops/status`, `POST /api/ops/action`.

## Agent teams

In de GUI: **Agent teams**. Presets: Webdesign, Applicatie, Infra, Self-improve, Marketing, Socials, SEO/GEO, **Growth**. Zelf agents/teams maken, volgorde zetten, pipeline of board+synthese, daarna **Run team**.

## Marketing / Socials / SEO-GEO / Visual / Site

| Studio | Voor | Team |
|--------|------|------|
| Marketing | Pitch, positionering, GTM, funnels | `team-marketing` |
| Socials | LinkedIn/IG posts, kalender, scripts | `team-socials` |
| SEO / GEO | Keywords, on-page, local, AEO/GEO | `team-seo` |
| Visual | Canva-alt: social cards, pitch slides, flyers (HTML/SVG) | `team-visual` |
| (auto) | Pitch + site + socials | `team-growth` |
| (auto) | Landing end-to-end | `team-site` |

**Figma:** Penpot + design-in-code (geen Figma-abo nodig voor eigen sites).  
**Canva:** studio Visual + `visual_render` / `generate_image` (geen Canva-abo).

Laat **vit/auto** staan: “campagne”, “Canva carousel”, “bouw landing” → juiste studio/team.

## Claude / ChatGPT / Cursor eruit?

Zie `docs/EXIT.md`. Kort:
- **Chat:** studio Chat + lokaal/OpenRouter
- **Code:** studio Software + workspace, of VS Code/Zed + Continue → hub
- **Design:** studio Webdesign (design-in-code) of Penpot (`scripts/install-penpot-mac.sh`)
- **Pitches/sites:** Marketing + SEO/GEO + Webdesign (of team-growth)

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
