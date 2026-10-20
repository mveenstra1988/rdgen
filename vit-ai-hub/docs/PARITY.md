# Feature-parity (okt 2026) — Claude / Claude Code / ChatGPT / Codex / Cursor

Doel van VIT AI Hub: dezelfde of betere **dagelijkse** workflow in één Mac-app. Geen 1:1 IDE-kloon.

## ✅ In de hub (2.5+)

| Capability | Bron | Hub |
|---|---|---|
| Multi-model chat + geheugen over wissel | ChatGPT/Claude | ✅ gedeeld SQLite-geheugen |
| Agent loop (tools, edits, tests, commit) | Cursor / Claude Code / Codex | ✅ tot 28 rondes, search_replace, git_commit |
| Plan / Ask / Agent modi + `/plan` `/ask` `/agent` | Cursor CLI / Claude Code | ✅ |
| AGENTS.md / CLAUDE.md / .cursor/rules | Cursor / Codex / Claude | ✅ project_context inject |
| Skills (SKILL.md) + GUI toevoegen | Claude Code / Cursor | ✅ Uitbreidingen + import |
| MCP stdio (+ hub mcp.json) | allen | ✅ list/call + GUI add |
| Subagents / teams (pipeline + board) | Claude Code / Cursor | ✅ Teams-tab |
| Multi-abo failover | Cursor multi-provider | ✅ bridge/cursor pools |
| Privacy fail-closed | — | ✅ PII vóór cloud |
| Local-prep / token-save | — | ✅ EXEC_BRIEF |
| Beelden (Nano Banana) | Gemini | ✅ wizard Gemini-key |
| VIT-suite (Mail/Kluis/…) | — | ✅ open/handoff |
| Migrate chats/skills/MCP/rules | — | ✅ wizard + één klik |
| Continue.dev export | Cursor-exit | ✅ |

## ⚠️ Bewust anders / later

| Gap | Waarom | Pad |
|---|---|---|
| Inline Tab autocomplete in editor | Hub is geen VS Code-fork | Cursor/Continue naast hub, of later LSP |
| LSP / jump-to-definition | Zelfde | Roadmap IDE/LSP-bridge |
| Cloud Agents (remote VM) | Andere runtime | Later of via Cursor cloud handoff |
| `/batch` worktrees | Zwaar | Parallel teams nu; worktrees later |
| Claude Code checkpoints `/rewind` | Git is onze checkpoint | `git` + chat-hervat |
| Native IDE extension UI | Productkeuze: één hub-GUI | OpenAI-compat `:8787/v1` in Cursor |

## Bewezen settings (M5 Max 128GB)

Zie `docs/MAC_M5_MAX.md`: LM Studio MLX, daily MoE light, heavy on-demand, hub `vit/auto` of `vit/max`.
