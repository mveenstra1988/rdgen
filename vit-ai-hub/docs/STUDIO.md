# Studio: software, webdesign, apps, Penpot

## Modi in de GUI

| Studio | Vervangt | Wat het doet |
|--------|----------|--------------|
| Chat | ChatGPT/Claude chat | Algemeen |
| Software | Cursor / Claude Code | Lees/schrijf/run in workspace |
| Webdesign | Figma+Dev voor sites | Design-in-code, sterke UI-regels |
| Apps | Product/app bouw | Mac/web/mobile flows |
| Design | Figma | Penpot + design-to-code |

Zet **Workspace** op je project (`~/Projects/foo`). Tools blijven binnen allowlist (`VIT_WORKSPACE_ROOTS`).

## Webdesign zonder Figma

1. Studio → **Webdesign**
2. Vraag: “bouw landing voor X, merk Y, CTA Z”
3. Hub schrijft HTML/CSS/React in je workspace
4. Optioneel: Penpot voor moodboards/exports

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
