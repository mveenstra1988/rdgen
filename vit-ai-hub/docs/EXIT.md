# Abonnementen opzeggen — wanneer wel / niet

Doel: Claude.ai, ChatGPT Plus en Cursor zo ver mogelijk vervangen door **VIT AI Hub + lokaal model + (optioneel) OpenRouter**.

## ChatGPT / Claude (chat)

| Nodig | Status in hub |
|-------|----------------|
| Chat GUI + modelpicker | Ja |
| Tools (web, files, memory) | Ja |
| Kennisimport oude chats | Ja |
| Vision / zware redenering | Lokaal heavy of OpenRouter |

**Opzeggen kan** als je 1–2 weken primair in de hub werkt en LM Studio (light) + eventueel OpenRouter voldoende voelt. Bridge (`:8317`) houdt Claude/GPT-abo modellen beschikbaar zonder hun websites.

## Cursor (IDE-agent)

De hub-GUI is géén volledige Cursor-vervanger (geen inline diffs in je editor).

**Pad naar exit:**
1. Hub draaien (`:8787`)
2. Knop **Continue→hub** of `scripts/export-continue-config.sh`
3. VS Code of **Zed** + Continue-extensie → model `vit/auto`
4. Studio **Software** + workspace `~/Projects/...` voor agent-achtig werk in de hub zelf

**Opzeggen Cursor** pas als Continue/Zed + studio Software je dagelijkse flow dekt (refs, edits, tests).

## Figma

| Optie | Wanneer |
|-------|---------|
| **Design-in-code** (studio Webdesign) | Sites/landings — vaak beter dan Figma |
| **Penpot** lokaal (`scripts/install-penpot-mac.sh`) | Design files / met designers delen |
| Penpot cloud | Snel proberen zonder Docker |

Figma-abo is zelden nodig als je vooral zelf bouwt.

## Aanbevolen volgorde

1. Week 1: hub als primaire chat → ChatGPT/Claude web minder
2. Week 2: Continue/Zed op hub → Cursor minder
3. Webdesign-studio + Penpot → Figma alleen als klant het eist
4. OpenRouter houden als “cloud boost”; lokale MoE als default
