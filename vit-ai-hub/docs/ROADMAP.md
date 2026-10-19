# Roadmap status (0.8)

## Ingebouwd
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
- [x] Studio-modi: chat / software / webdesign / apps / design
- [x] Workspace read/write/run (allowlist) — Cursor-achtig in de hub
- [x] Continue.dev export (Cursor-exit pad)
- [x] Penpot open + install-script (Figma-alt)
- [x] Visuele agent-teams (webdesign / apps presets + custom builder + run)

## Later (nog scherper)
- [ ] Native Swift AX sidebar-klik (betrouwbaarder dan pijltjes)
- [ ] Echte embeddings (mlx) i.p.v. alleen FTS
- [ ] VIT Mail deep IPC (niet alleen openen) als app dat expose’t
- [ ] Chrome extension bridge voor volledige tab/DOM
- [ ] Warm-pool light/heavy model op stroom/batterij
- [ ] Inline diff-viewer in GUI (nog dichter bij Cursor)
- [ ] Parallel board-runs (asyncio.gather) i.p.v. sequentieel
