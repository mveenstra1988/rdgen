# Sneller & beter (volgende stappen)

## Nu gedaan
- Accessibility-import: lees ChatGPT terwijl de app open is (zelfde tekst als jij ziet)
- Keychain-decrypt best-effort voor oudere/v2 keys
- Claude Code/Cowork + Cursor lokale harvest
- Export-automatisering + zip-watcher

## High impact next
1. **Continuïteit / live sync**  
   File-watcher + periodieke AX-snapshot terwijl ChatGPT/Claude/Cursor open zijn (delta, niet full rescan).

2. **Betere AX-navigatie**  
   Sidebar-rijen betrouwbaar aanklikken (Swift/AX API i.p.v. pijltjestoetsen), per chat volledige scroll-capture.

3. **Embeddings-index**  
   Lokale vectorsearch (mlx-embeddings / sqlite-vec) over geïmporteerde chats → sneller “weet je nog…” zonder hele JSONL te scannen.

4. **Incremental import**  
   Hash per chat; alleen nieuwe/gewijzigde berichten bijschrijven.

5. **Menu-bar app**  
   `vit-ai-hub` als menubar: één knop Sync, status lampje, geen browser-tab nodig.

6. **Claude live AX**  
   Zelfde Accessibility-pad voor Claude Desktop-venster.

7. **Background agents-koppeling**  
   Cursor Agent transcripts realtime tailen naar knowledge store.

8. **PII-profielen per project**  
   Strenger voor klantrepos, losser voor interne notes.

9. **Model warm-pool**  
   Light model resident; heavy preload op aangesloten stroom; unload bij batterij.

10. **Eval-set**  
   20 vaste VIT-prompts (ServiceHub, mail, VPN) om lokaal vs Claude vs GPT te vergelijken.