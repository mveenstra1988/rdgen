# Studio: software, webdesign, apps, Penpot, growth

## Modi in de GUI

| Studio | Vervangt | Wat het doet |
|--------|----------|--------------|
| Chat | ChatGPT/Claude chat | Algemeen |
| Software | Cursor / Claude Code | Lees/schrijf/run in workspace |
| Webdesign | Figma+Dev voor sites | Design-in-code, sterke UI-regels |
| Apps | Product/app bouw | Mac/web/mobile flows |
| Design | Figma | Penpot + design-to-code |
| Marketing | Pitch/GTM tools | Positionering, pitches, funnels |
| Socials | Buffer/Later + copywriter | LinkedIn/IG posts & kalender |
| SEO / GEO | SEO suites + AEO | Zoek + generative-engine citeerbaarheid |
| Ops | Infra chat | Proxmox/Mail/Cloud read-first |
| Self-improve | — | Hub past zichzelf aan |

Zet **Workspace** op je project (`~/Projects/foo`). Tools blijven binnen allowlist (`VIT_WORKSPACE_ROOTS`).

## Growth router (vit/auto)

Met **vit/auto** classificeert de hub marketing / socials / seo en start zo nodig:

- `team-marketing` — strat → pitch
- `team-socials` — plan → posts
- `team-seo` — SEO/GEO → content briefs
- `team-growth` — marketing + SEO + socials + site-copy (pistes & sites)

Studio handmatig kiezen forceert die modus; anders routet vit/auto.

## Webdesign zonder Figma

1. Studio → **Webdesign**
2. Vraag: “bouw landing voor X, merk Y, CTA Z”
3. Hub schrijft HTML/CSS/React in je workspace
4. Optioneel: Penpot voor moodboards/exports
5. Voor pitch+SEO+posts in één: studio Marketing of vraag “campagne end-to-end” → team-growth

## Penpot (Figma-alt)

```bash
bash scripts/install-penpot-mac.sh   # Docker → :9001
```

Of knop **Penpot** in de GUI (opent lokaal of cloud).

## Cursor eruit

```bash
bash scripts/export-continue-config.sh
# of GUI: Continue→hub
```

VS Code/Zed + Continue → `http://127.0.0.1:8787/v1`.
