# Roadmap status (1.4)

## Ingebouwd
- [x] vit/auto orchestrator: intent → beste model + auto-team + per-rol models (incl. lokaal)
- [x] Strong/weak routing + tradeoff (quality/cost/latency)
- [x] Fallback cascade (fout/leeg → volgende model)
- [x] Maker-checker critic loop (bounded)
- [x] Route-telemetrie (`data/orchestrator.jsonl`)
- [x] Multi-abo pools (bridge/cursor/…) met auto-failover bij rate-limit/quota
- [x] Live sync (`/api/sync/*`, GUI knoppen)
- [x] Claude live AX + ChatGPT live AX
- [x] FTS5 knowledge index (`/api/knowledge/reindex`)
- [x] Incremental-ish imports (hash skip in store)
- [x] Menubar helper (`scripts/menubar_mac.py`, optioneel rumps)
- [x] Grok / xAI backend + pinned models
- [x] Desktop tools: Chrome, Mail, VIT Mail, apps, Spotlight, allowlist shell
- [x] OpenRouter / OmniRoute / Ox Alpha
- [x] PII fail-closed
- [x] One-click Mac package + wizard (0.6+)
- [x] Studio-modi: chat / software / webdesign / apps / design / ops
- [x] Workspace read/write/run (allowlist) — Cursor-achtig in de hub
- [x] Continue.dev export (Cursor-exit pad)
- [x] Penpot open + install-script (Figma-alt)
- [x] Visuele agent-teams (webdesign / apps / infra presets + custom builder + run)
- [x] Full migrate (settings/MCP/rules/prompts/skills mirror + actief profiel)
- [x] Self-improve studio + team
- [x] MCP stdio runtime tools in chat
- [x] Ops layer: Proxmox / Nextcloud / Gromox / Mailcow / ServiceHub / UniFi / Backup / automation-hub

## Later (nog scherper)
- [ ] Native Swift AX sidebar-klik (betrouwbaarder dan pijltjes)
- [ ] Echte embeddings (mlx) i.p.v. alleen FTS
- [ ] VIT Mail deep IPC (niet alleen openen) als app dat expose’t
- [ ] Chrome extension bridge voor volledige tab/DOM
- [ ] Warm-pool light/heavy model op stroom/batterij
- [ ] Inline diff-viewer in GUI (nog dichter bij Cursor)
- [ ] Parallel board-runs (asyncio.gather) i.p.v. sequentieel
