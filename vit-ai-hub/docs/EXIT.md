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

**2.0 in de hub:** studio **Code** = lange agent-loop (zoek → patch → test → commit), parallel teams, geen force-git. Dat dekt veel dagelijks agent-werk.

Nog niet: inline diffs in een IDE, LSP, breakpoints. Voor editor-diepte: Continue/Zed → hub (`vit/auto`).

**Pad naar exit:**
1. Hub draaien (`:8787`)
2. Studio **Code** + projectpad — of knop **Continue→hub**
3. VS Code/**Zed** + Continue als je tabs/LSP wilt

**Opzeggen Cursor** als Code-studio (of Continue→hub) je refs/edits/tests dekt.

## Figma

| Optie | Wanneer |
|-------|---------|
| **Design-in-code** (studio Webdesign) | Sites/landings — vaak sneller dan Figma |
| **FigCraft (ArtCraft)** | Gratis open-source Figma-achtig (Rust); knop FigCraft / `open_figcraft` — nog alpha |
| **Penpot** lokaal (`scripts/install-penpot-mac.sh`) | Volwassener voor teams/cloud |
| Penpot cloud | Snel proberen zonder Docker |

Figma-abo is zelden nodig als je vooral zelf bouwt. FigCraft = ArtCraft’s Figma-kloon (geen Figma Inc.).

## Aanbevolen volgorde

1. Week 1: hub als primaire chat → ChatGPT/Claude web minder
2. Week 2: Continue/Zed op hub → Cursor minder
3. Webdesign-studio + Penpot → Figma alleen als klant het eist
4. OpenRouter houden als “cloud boost”; lokale MoE als default
