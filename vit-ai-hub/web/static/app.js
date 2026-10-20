const SESSION_ID = (() => {
  const params = new URLSearchParams(location.search);
  let sid = params.get("session") || "";
  if (!sid) {
    sid = `s-${Math.random().toString(36).slice(2, 10)}`;
    params.set("session", sid);
    const url = `${location.pathname}?${params.toString()}${location.hash || ""}`;
    history.replaceState(null, "", url);
  }
  return sid;
})();

const state = {
  models: [],
  messages: [],
  sessionId: SESSION_ID,
};

function chatStorageKey() {
  return `vit_chat_${state.sessionId}`;
}

function loadSessionMessages() {
  try {
    const raw = sessionStorage.getItem(chatStorageKey());
    if (!raw) return;
    const data = JSON.parse(raw);
    if (Array.isArray(data)) state.messages = data;
  } catch (_) {
    /* ignore */
  }
}

function saveSessionMessages() {
  try {
    sessionStorage.setItem(
      chatStorageKey(),
      JSON.stringify(state.messages.filter((m) => m.role === "user" || m.role === "assistant"))
    );
  } catch (_) {
    /* ignore */
  }
}

const els = {
  modelSelect: document.getElementById("model-select"),
  modelFriendly: document.getElementById("model-select-friendly"),
  modelFilter: document.getElementById("model-filter"),
  modelMeta: document.getElementById("model-meta"),
  studioSelect: document.getElementById("studio-select"),
  workspace: document.getElementById("workspace"),
  messages: document.getElementById("messages"),
  emptyState: document.getElementById("empty-state"),
  emptyPresets: document.getElementById("empty-presets"),
  prompt: document.getElementById("prompt"),
  form: document.getElementById("composer"),
  token: document.getElementById("token"),
  tools: document.getElementById("tools-toggle"),
  autoTeam: document.getElementById("auto-team-toggle"),
  tradeoff: document.getElementById("tradeoff-select"),
  health: document.getElementById("health"),
  routeInfo: document.getElementById("route-info"),
  refresh: document.getElementById("refresh-models"),
  newChat: document.getElementById("new-chat"),
  exportContinue: document.getElementById("export-continue"),
  openPenpot: document.getElementById("open-penpot"),
  opsStatusBtn: document.getElementById("ops-status-btn"),
  opsStatusBox: document.getElementById("ops-status-box"),
  importAll: document.getElementById("import-all"),
  importSkills: document.getElementById("import-skills"),
  importFull: document.getElementById("import-full"),
  importStatus: document.getElementById("import-status"),
  importFile: document.getElementById("import-file"),
  importSource: document.getElementById("import-source"),
  importUpload: document.getElementById("import-upload"),
  localDetect: document.getElementById("local-detect"),
  requestExports: document.getElementById("request-exports"),
  waitExports: document.getElementById("wait-exports"),
  chatgptLive: document.getElementById("chatgpt-live"),
  claudeLive: document.getElementById("claude-live"),
  syncStart: document.getElementById("sync-start"),
  syncOnce: document.getElementById("sync-once"),
  settingsDrawer: document.getElementById("settings-drawer"),
  settingsBackdrop: document.getElementById("settings-backdrop"),
  openSettings: document.getElementById("open-settings"),
  closeSettings: document.getElementById("close-settings"),
  appRoot: document.getElementById("app-root"),
};

function friendlyModelLabel(m) {
  if (!m) return "Model";
  if (m.id === "vit/auto" || m.virtual) return "Slim (kiest zelf)";
  if (m.local && /heavy/i.test(m.id + m.name)) return "Lokaal · krachtig";
  if (m.local) return "Lokaal · snel";
  if (/claude/i.test(m.id + (m.name || ""))) return `Claude · ${(m.name || m.id).replace(/^.*\//, "").slice(0, 28)}`;
  if (/deepseek/i.test(m.id)) return "DeepSeek";
  if (/gpt|openai/i.test(m.id + (m.name || ""))) return `GPT · ${(m.name || m.id).slice(0, 24)}`;
  const short = (m.name || m.id).replace(/^[^:]+:/, "").slice(0, 32);
  return short;
}

function syncEmptyState() {
  if (!els.emptyState) return;
  const hasUser = state.messages.some((m) => m.role === "user" || m.role === "assistant");
  els.emptyState.classList.toggle("on", !hasUser);
  if (els.messages) els.messages.style.display = hasUser ? "flex" : "none";
}

function openSettings(on) {
  els.settingsDrawer?.classList.toggle("on", on);
  els.settingsBackdrop?.classList.toggle("on", on);
}

function popWindow(view) {
  const url = new URL(window.location.origin + "/");
  url.searchParams.set("pop", "1");
  url.searchParams.set("view", view || "chat");
  url.searchParams.set("session", `${view || "chat"}-${Date.now().toString(36)}`);
  // Preserve token for auth in new window
  try {
    const t =
      (els.token && els.token.value.trim()) ||
      sessionStorage.getItem("vit_gateway_token") ||
      "";
    if (t) url.searchParams.set("token", t);
  } catch (_) {
    /* ignore */
  }
  const w = view === "teams" ? 1100 : 920;
  const h = view === "teams" ? 800 : 720;
  const features = `popup=yes,width=${w},height=${h},left=${40 + Math.floor(Math.random() * 80)},top=${40 + Math.floor(Math.random() * 60)}`;
  window.open(url.toString(), `vit-${view}-${Date.now()}`, features);
}

try {
  const savedStudio = localStorage.getItem("vit_studio");
  if (savedStudio && els.studioSelect) els.studioSelect.value = savedStudio;
  const savedWs = localStorage.getItem("vit_workspace");
  if (savedWs && els.workspace) els.workspace.value = savedWs;
} catch (_) {
  /* ignore */
}

function headers() {
  const h = { "Content-Type": "application/json" };
  let token = els.token.value.trim();
  if (!token) {
    try {
      token = sessionStorage.getItem("vit_gateway_token") || "";
    } catch (_) {
      token = "";
    }
  }
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function ensureLocalToken() {
  // Token from iPhone/PWA deep link: /?token=…
  try {
    const params = new URLSearchParams(location.search);
    const fromUrl = (params.get("token") || "").trim();
    if (fromUrl) {
      if (els.token) els.token.value = fromUrl;
      sessionStorage.setItem("vit_gateway_token", fromUrl);
      params.delete("token");
      const clean = `${location.pathname}?${params.toString()}`.replace(/\?$/, "");
      history.replaceState(null, "", clean + (location.hash || ""));
    }
  } catch (_) {
    /* ignore */
  }
  try {
    const res = await fetch("/api/setup/status");
    const data = await res.json();
    if (data.gateway_token) {
      if (els.token && !els.token.value) els.token.value = data.gateway_token;
      try {
        sessionStorage.setItem("vit_gateway_token", data.gateway_token);
      } catch (_) {
        /* ignore */
      }
    }
  } catch (_) {
    /* ignore */
  }
}

async function refreshNetwork() {
  const hint = document.getElementById("lan-hint");
  const urlEl = document.getElementById("lan-url");
  const qr = document.getElementById("lan-qr");
  const toggle = document.getElementById("lan-toggle");
  try {
    const res = await fetch("/api/network", { headers: headers() });
    const data = await res.json();
    if (toggle) toggle.checked = !!data.lan_enabled;
    const first = (data.urls && data.urls[0] && data.urls[0].url) || "";
    if (urlEl) {
      urlEl.textContent = data.lan_enabled
        ? `Open op iPhone: ${first}`
        : "LAN uit — alleen deze Mac (127.0.0.1).";
      urlEl.dataset.url = first;
    }
    if (hint) hint.textContent = data.pwa_hint || "";
    if (qr && data.lan_enabled && first) {
      qr.hidden = false;
      try {
        const qrRes = await fetch(`/api/network/qr.svg?url=${encodeURIComponent(first)}`, {
          headers: headers(),
        });
        qr.innerHTML = await qrRes.text();
      } catch (_) {
        qr.innerHTML = `<p class="muted tiny">${first}</p>`;
      }
    } else if (qr) {
      qr.hidden = true;
      qr.innerHTML = "";
    }
  } catch (err) {
    if (urlEl) urlEl.textContent = `Netwerkinfo: ${err}`;
  }
}

function selectedModel() {
  const friendly = els.modelFriendly?.value;
  if (friendly) return friendly;
  return els.modelSelect?.value || "vit/auto";
}

function renderModels(filter = "") {
  const q = filter.trim().toLowerCase();
  const models = state.models.filter((m) => {
    if (!q) return true;
    return `${m.id} ${m.name || ""} ${m.label || ""} ${m.backend || ""}`
      .toLowerCase()
      .includes(q);
  });
  const current = selectedModel();
  if (els.modelSelect) {
    els.modelSelect.innerHTML = "";
    for (const m of models) {
      const opt = document.createElement("option");
      opt.value = m.id;
      const kind = m.local ? "local" : m.virtual ? "vit" : "cloud";
      opt.textContent = `[${m.label || m.backend || kind}] ${m.name || m.id}`;
      els.modelSelect.appendChild(opt);
    }
  }
  // Friendly shortlist: auto + locals + top clouds
  if (els.modelFriendly) {
    const picks = [];
    const auto = state.models.find((m) => m.id === "vit/auto");
    if (auto) picks.push(auto);
    for (const m of state.models) {
      if (m.id === "vit/auto") continue;
      if (m.local || m.virtual) picks.push(m);
      if (picks.length >= 6) break;
    }
    for (const m of state.models) {
      if (picks.includes(m)) continue;
      if (/claude|deepseek|gpt-4|sonnet/i.test(m.id)) picks.push(m);
      if (picks.length >= 10) break;
    }
    els.modelFriendly.innerHTML = "";
    for (const m of picks) {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = friendlyModelLabel(m);
      els.modelFriendly.appendChild(opt);
    }
    // Always allow current even if not in shortlist
    if (current && ![...els.modelFriendly.options].some((o) => o.value === current)) {
      const m = state.models.find((x) => x.id === current);
      const opt = document.createElement("option");
      opt.value = current;
      opt.textContent = friendlyModelLabel(m) || current;
      els.modelFriendly.appendChild(opt);
    }
  }
  const setVal = (el) => {
    if (!el) return;
    if ([...el.options].some((o) => o.value === current)) el.value = current;
    else if ([...el.options].some((o) => o.value === "vit/auto")) el.value = "vit/auto";
  };
  setVal(els.modelSelect);
  setVal(els.modelFriendly);
  updateMeta();
}

function updateMeta() {
  const m = state.models.find((x) => x.id === selectedModel());
  if (!m) {
    if (els.modelMeta) els.modelMeta.textContent = "";
    return;
  }
  if (els.modelMeta) {
    els.modelMeta.textContent = [
      `id: ${m.id}`,
      `backend: ${m.backend || "?"}`,
      `scope: ${m.local ? "lokaal" : m.virtual ? "virtueel" : "cloud"}`,
    ].join("\n");
  }
  if (els.routeInfo) {
    els.routeInfo.textContent = m.virtual
      ? "Slim: kiest model + team voor de beste output"
      : `${friendlyModelLabel(m)} · ${m.local ? "op deze Mac" : "via privacyfilter"}`;
  }
}

function addBubble(role, text, meta = null) {
  if (!els.messages) return;
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  if (meta) {
    const tag = document.createElement("div");
    tag.className = `tag ${meta.local ? "local" : "cloud"}`;
    if (meta.pii_forced_local) tag.classList.add("warn");
    const orch = meta.orchestrator;
    const bits = [
      meta.auto_team ? "team" : null,
      orch?.intent?.kind || null,
      meta.local ? "lokaal" : meta.backend,
      meta.pii_forced_local ? "privacy→lokaal" : null,
    ];
    tag.textContent = bits.filter(Boolean).join(" · ");
    div.appendChild(tag);
  }
  const body = document.createElement("div");
  body.textContent = text;
  div.appendChild(body);
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
  syncEmptyState();
}

async function loadModels() {
  const res = await fetch("/v1/models", { headers: headers() });
  if (!res.ok) throw new Error(`modellen: HTTP ${res.status}`);
  const data = await res.json();
  state.models = data.data || [];
  renderModels(els.modelFilter.value);
}

async function ping() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    els.health.textContent = data.ok ? `online v${data.version}` : "offline";
  } catch {
    els.health.textContent = "offline";
  }
}

els.modelFilter?.addEventListener("input", () => renderModels(els.modelFilter.value));
els.modelSelect?.addEventListener("change", () => {
  if (els.modelFriendly) els.modelFriendly.value = els.modelSelect.value;
  updateMeta();
});
els.modelFriendly?.addEventListener("change", () => {
  if (els.modelSelect) els.modelSelect.value = els.modelFriendly.value;
  updateMeta();
});
els.refresh?.addEventListener("click", () => loadModels().catch((e) => addBubble("system", String(e))));
els.newChat?.addEventListener("click", () => {
  state.messages = [];
  if (els.messages) els.messages.innerHTML = "";
  saveSessionMessages();
  syncEmptyState();
  if (els.routeInfo) els.routeInfo.textContent = "Nieuwe chat — privacyfilter blijft aan.";
  els.prompt?.focus();
});

document.getElementById("lan-refresh")?.addEventListener("click", () => refreshNetwork());
document.getElementById("lan-copy")?.addEventListener("click", async () => {
  const urlEl = document.getElementById("lan-url");
  const u = urlEl?.dataset?.url || "";
  if (!u) return;
  try {
    await navigator.clipboard.writeText(u);
    if (els.routeInfo) els.routeInfo.textContent = "Link gekopieerd — plak in Safari op je iPhone.";
  } catch (_) {
    if (els.routeInfo) els.routeInfo.textContent = u;
  }
});
document.getElementById("lan-toggle")?.addEventListener("change", async (ev) => {
  const on = !!ev.target.checked;
  try {
    const res = await fetch("/api/network/lan", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ enabled: on }),
    });
    const data = await res.json();
    if (!data.ok) {
      ev.target.checked = !on;
      alert(data.error || "LAN wijzigen mislukt");
      return;
    }
    await refreshNetwork();
    if (data.restart_required) {
      alert("LAN gewijzigd. Sluit de VIT AI Hub-app en open opnieuw zodat iPhone kan verbinden.");
    }
  } catch (err) {
    ev.target.checked = !on;
    alert(String(err));
  }
});

els.studioSelect?.addEventListener("change", () => {
  try {
    localStorage.setItem("vit_studio", els.studioSelect.value);
  } catch (_) {
    /* ignore */
  }
  const labels = {
    chat: "Algemeen",
    software: "Code",
    webdesign: "Website",
    marketing: "Marketing",
    socials: "Socials",
    seo: "SEO / GEO",
    visual: "Visual",
    ops: "Ops",
    self: "Hub verbeteren",
  };
  if (els.routeInfo) {
    els.routeInfo.textContent = `Modus: ${labels[els.studioSelect.value] || els.studioSelect.value}`;
  }
});

els.openSettings?.addEventListener("click", () => openSettings(true));
els.closeSettings?.addEventListener("click", () => openSettings(false));
els.settingsBackdrop?.addEventListener("click", () => openSettings(false));
document.getElementById("pop-chat")?.addEventListener("click", () => popWindow("chat"));
document.getElementById("pop-teams")?.addEventListener("click", () => popWindow("teams"));

els.workspace?.addEventListener("change", () => {
  try {
    localStorage.setItem("vit_workspace", els.workspace.value.trim());
  } catch (_) {
    /* ignore */
  }
});

els.exportContinue?.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/workspace/export-continue", { method: "POST", headers: headers() });
    const data = await res.json();
    addBubble(
      "system",
      data.ok
        ? `Continue-config geschreven: ${data.path}\n${(data.next || []).join("\n")}`
        : JSON.stringify(data)
    );
  } catch (err) {
    addBubble("system", String(err));
  }
});

els.openPenpot?.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/tools/open_penpot", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ local: true }),
    });
    const data = await res.json();
    addBubble("system", typeof data === "string" ? data : JSON.stringify(data, null, 2));
  } catch (err) {
    addBubble("system", String(err));
  }
});

els.opsStatusBtn?.addEventListener("click", async () => {
  try {
    await fetch("/api/ops/ensure-env", { method: "POST", headers: headers() });
    const res = await fetch("/api/ops/status", { headers: headers() });
    const data = await res.json();
    const cfg = data.configured || {};
    const lines = Object.entries(cfg).map(([k, v]) => `${v ? "✓" : "○"} ${k}`);
    const text = [`Ops · ${data.env_file || ""}`, ...lines, data.hint || ""].join("\n");
    if (els.opsStatusBox) {
      els.opsStatusBox.hidden = false;
      els.opsStatusBox.textContent = text;
    }
    addBubble("system", text);
    if (els.studioSelect && els.studioSelect.value !== "ops") {
      /* hint only */
    }
  } catch (err) {
    addBubble("system", String(err));
  }
});

els.form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = els.prompt.value.trim();
  if (!text) return;
  els.prompt.value = "";
  state.messages.push({ role: "user", content: text });
  addBubble("user", text);
  saveSessionMessages();
  const sendBtn = document.getElementById("send");
  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        model: selectedModel(),
        messages: state.messages,
        vit_enable_tools: els.tools.checked,
        vit_auto_team: els.autoTeam ? els.autoTeam.checked : true,
        vit_tradeoff: els.tradeoff?.value || "quality",
        stream: false,
        studio: els.studioSelect?.value || "chat",
        workspace: els.workspace?.value.trim() || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      const detail = data.detail || data.error || data;
      addBubble("system", typeof detail === "string" ? detail : JSON.stringify(detail, null, 2));
      return;
    }
    const content = data.choices?.[0]?.message?.content || "(leeg antwoord)";
    state.messages.push({ role: "assistant", content });
    addBubble("assistant", content, data.vit || null);
    saveSessionMessages();
    if (data.vit?.orchestrator?.summary && els.routeInfo) {
      els.routeInfo.textContent = data.vit.orchestrator.summary;
    }
  } catch (err) {
    addBubble("system", String(err));
  } finally {
    sendBtn.disabled = false;
  }
});

async function refreshImportStatus() {
  try {
    const res = await fetch("/api/import/status", { headers: headers() });
    const data = await res.json();
    const k = data.knowledge || {};
    els.importStatus.textContent =
      `${k.conversations || 0} chats · ${k.memories || 0} memories · ${k.projects || 0} projects · ${k.skills || 0} skills` +
      (data.export_zips?.chatgpt?.length || data.export_zips?.claude?.length
        ? ` · zips klaar: GPT ${data.export_zips.chatgpt?.length || 0} / Claude ${data.export_zips.claude?.length || 0}`
        : "");
    const loc = data.local_apps || {};
    els.localDetect.textContent =
      `Mac: ChatGPT-app ${loc.chatgpt_app ? "ja" : "nee"}` +
      (loc.chatgpt_encrypted_conversations
        ? ` (${loc.chatgpt_encrypted_conversations} encrypted)`
        : "") +
      ` · Claude Desktop ${loc.claude_desktop ? "ja" : "nee"}` +
      ` · Claude Code ${loc.claude_code_transcripts || 0} transcripts` +
      ` · cache ${loc.chatgpt_cache_files || 0}`;
  } catch {
    els.importStatus.textContent = "Status onbekend";
  }
}

els.importAll?.addEventListener("click", async () => {
  els.importAll.disabled = true;
  els.importAll.textContent = "Bezig…";
  try {
    const res = await fetch("/api/import/all", { method: "POST", headers: headers() });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    const k = data.knowledge || {};
    addBubble(
      "system",
      `Import klaar (${data.elapsed_sec}s): ${k.conversations || 0} chats, ${k.memories || 0} memories, ${k.projects || 0} projects, ${k.skills || 0} skills` +
        (data.skills?.agents_promoted
          ? ` · ${data.skills.agents_promoted.written || 0} skills → agents/bots`
          : "") +
        (data.hints?.length ? `\n${data.hints.join("\n")}` : "")
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Import mislukt: ${err}`);
  } finally {
    els.importAll.disabled = false;
    els.importAll.textContent = "Migreer ALLES (Claude/GPT/Cursor)";
  }
});

els.importFull?.addEventListener("click", async () => {
  els.importFull.disabled = true;
  els.importFull.textContent = "Mirror…";
  try {
    const res = await fetch("/api/import/full", { method: "POST", headers: headers() });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    const src = data.profile?.sources || {};
    addBubble(
      "system",
      `Volledige migratie (${data.elapsed_sec}s): ${src.mirrored_files || 0} files · ` +
        `MCP [${(data.profile?.mcp_servers || []).join(", ") || "geen"}] · ` +
        `skills ${data.skills?.found || 0}. Rules/prompts actief in chats.` +
        (data.honest_limits?.length ? `\n\nLimits:\n- ${data.honest_limits.join("\n- ")}` : "")
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Full migrate mislukt: ${err}`);
  } finally {
    els.importFull.disabled = false;
    els.importFull.textContent = "Volledige mirror + MCP/rules";
  }
});

els.importSkills?.addEventListener("click", async () => {
  els.importSkills.disabled = true;
  els.importSkills.textContent = "Skills zoeken…";
  try {
    const res = await fetch("/api/import/skills", { method: "POST", headers: headers() });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    addBubble(
      "system",
      `Skills: ${data.found || 0} gevonden · ${data.skills?.written || 0} nieuw · ` +
        `${data.agents_promoted?.written || 0} als agent/bot. Zie tab Agent teams.`
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Skills-import mislukt: ${err}`);
  } finally {
    els.importSkills.disabled = false;
    els.importSkills.textContent = "Importeer Claude/Cursor skills";
  }
});

els.chatgptLive?.addEventListener("click", async () => {
  els.chatgptLive.disabled = true;
  els.chatgptLive.textContent = "ChatGPT lezen…";
  addBubble("system", "ChatGPT openen/lezen via Accessibility. Sta Toegankelijkheid toe als macOS dat vraagt.");
  try {
    const res = await fetch("/api/import/chatgpt-live", { method: "POST", headers: headers() });
    const data = await res.json();
    const ax = data.accessibility || {};
    const kc = data.keychain || {};
    addBubble(
      "system",
      `ChatGPT live: AX ${ax.ok ? "ok" : "nee"} (${ax.conversations?.written || 0} chats)` +
        ` · Keychain ${kc.ok ? "ok" : "nee"} (${kc.decrypted_files || 0} files)` +
        (ax.error || kc.error ? `\n${ax.error || kc.error}` : "") +
        (ax.hint ? `\n${ax.hint}` : "")
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `ChatGPT live mislukt: ${err}`);
  } finally {
    els.chatgptLive.disabled = false;
    els.chatgptLive.textContent = "Lees ChatGPT (app open)";
  }
});

els.claudeLive?.addEventListener("click", async () => {
  els.claudeLive.disabled = true;
  els.claudeLive.textContent = "Claude lezen…";
  try {
    const res = await fetch("/api/import/claude-live", { method: "POST", headers: headers() });
    const data = await res.json();
    addBubble(
      "system",
      `Claude live: ${data.ok ? "ok" : "nee"} · ${data.conversations?.written || 0} chats` +
        (data.error ? `\n${data.error}` : "") +
        (data.hint ? `\n${data.hint}` : "")
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Claude live mislukt: ${err}`);
  } finally {
    els.claudeLive.disabled = false;
    els.claudeLive.textContent = "Lees Claude (app open)";
  }
});

els.syncStart?.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/sync/start?interval_sec=300", { method: "POST", headers: headers() });
    const data = await res.json();
    addBubble("system", `Live sync: ${data.ok ? "aan" : "fout"} (elke ${data.interval_sec || 300}s)`);
  } catch (err) {
    addBubble("system", `Sync start mislukt: ${err}`);
  }
});

els.syncOnce?.addEventListener("click", async () => {
  els.syncOnce.disabled = true;
  try {
    const res = await fetch("/api/sync/once", { method: "POST", headers: headers() });
    const data = await res.json();
    const k = data.knowledge || {};
    addBubble(
      "system",
      `Sync klaar: ${k.conversations || 0} chats · ${k.memories || 0} memories · FTS ${data.fts?.docs ?? "?"}`
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Sync mislukt: ${err}`);
  } finally {
    els.syncOnce.disabled = false;
  }
});

els.requestExports?.addEventListener("click", async () => {
  els.requestExports.disabled = true;
  try {
    const res = await fetch("/api/import/request-exports", { method: "POST", headers: headers() });
    const data = await res.json();
    addBubble(
      "system",
      data.next ||
        JSON.stringify(data) +
          "\nBevestig Export in ChatGPT/Claude. Klik daarna 'Wacht op zips & importeer'."
    );
  } catch (err) {
    addBubble("system", `Export starten mislukt: ${err}`);
  } finally {
    els.requestExports.disabled = false;
  }
});

els.waitExports?.addEventListener("click", async () => {
  els.waitExports.disabled = true;
  els.waitExports.textContent = "Wachten…";
  addBubble("system", "Watching Downloads/Desktop (max ~2 min per ronde)…");
  try {
    const res = await fetch("/api/import/wait-exports?timeout_sec=120", {
      method: "POST",
      headers: headers(),
    });
    const data = await res.json();
    addBubble(
      "system",
      `Wait-import: ${data.imported?.length || 0} bestand(en), ${data.elapsed_sec}s` +
        (data.timed_out ? " (timeout, opnieuw klikken als zip later binnenkomt)" : "")
    );
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Wait-import mislukt: ${err}`);
  } finally {
    els.waitExports.disabled = false;
    els.waitExports.textContent = "Wacht op zips & importeer";
  }
});

els.importUpload?.addEventListener("click", async () => {
  const file = els.importFile.files?.[0];
  if (!file) {
    addBubble("system", "Kies eerst een ChatGPT- of Claude-export (zip/json).");
    return;
  }
  const fd = new FormData();
  fd.append("file", file);
  if (els.importSource.value) fd.append("source", els.importSource.value);
  const h = {};
  const token = els.token.value.trim();
  if (token) h.Authorization = `Bearer ${token}`;
  els.importUpload.disabled = true;
  try {
    const res = await fetch("/api/import/upload", { method: "POST", headers: h, body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    addBubble("system", `Upload geïmporteerd (${data.source}): ${JSON.stringify(data.conversations || data)}`);
    await refreshImportStatus();
  } catch (err) {
    addBubble("system", `Upload-import mislukt: ${err}`);
  } finally {
    els.importUpload.disabled = false;
  }
});

async function refreshAccounts() {
  const box = document.getElementById("accounts-status");
  const list = document.getElementById("accounts-list");
  try {
    const res = await fetch("/api/accounts", { headers: headers() });
    const data = await res.json();
    const pools = data.pools || {};
    let healthy = 0;
    let total = 0;
    const detail = [];
    for (const [p, info] of Object.entries(pools)) {
      healthy += info.healthy || 0;
      total += info.total || 0;
      for (const a of info.accounts || []) {
        const mark = a.healthy ? "✓" : "○";
        detail.push(
          `${mark} ${a.label || a.id} · ${p}` +
            (a.exhausted_reason ? ` · ${a.exhausted_reason}` : "")
        );
      }
    }
    if (box) box.textContent = total ? `${healthy}/${total}` : "0";
    if (list) list.textContent = detail.join("\n") || "Nog geen abos — voeg hieronder toe.";
  } catch (e) {
    if (box) box.textContent = "!";
  }
}

document.getElementById("acc-refresh")?.addEventListener("click", () => refreshAccounts());
document.getElementById("acc-clear-cd")?.addEventListener("click", async () => {
  await fetch("/api/accounts/clear-cooldown", { method: "POST", headers: headers(), body: "{}" });
  addBubble("system", "Abo-cooldowns gereset.");
  refreshAccounts();
});
document.getElementById("acc-add")?.addEventListener("click", async () => {
  const pool = document.getElementById("acc-pool")?.value || "bridge";
  const label = document.getElementById("acc-label")?.value || "";
  const base_url = document.getElementById("acc-url")?.value || "";
  const api_key = document.getElementById("acc-key")?.value || "";
  const tags = (document.getElementById("acc-tags")?.value || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  if (!base_url.trim()) {
    addBubble("system", "Base URL verplicht voor een abo.");
    return;
  }
  const res = await fetch(`/api/accounts/${pool}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ label, base_url, api_key, tags: tags.length ? tags : undefined }),
  });
  const data = await res.json();
  addBubble("system", data.ok ? `Abo toegevoegd aan pool ${pool}` : JSON.stringify(data));
  refreshAccounts();
});

function applyPreset(p) {
  if (els.studioSelect && p.studio) {
    els.studioSelect.value = p.studio;
    try {
      localStorage.setItem("vit_studio", p.studio);
    } catch (_) {}
  }
  if (els.prompt) {
    els.prompt.value = p.text || "";
    els.prompt.focus();
  }
}

async function loadPresets() {
  const targets = [els.emptyPresets, document.getElementById("presets")].filter(Boolean);
  if (!targets.length) return;
  try {
    const res = await fetch("/api/presets", { headers: headers() });
    const data = await res.json();
    const blurb = {
      Pitch: "30s + 2min",
      Landing: "site end-to-end",
      LinkedIn: "5 posts",
      Visual: "Canva-alt",
      "SEO / GEO": "zoek + AI",
      "SEO/GEO": "zoek + AI",
    };
    for (const box of targets) {
      box.innerHTML = "";
      for (const p of data.presets || []) {
        const b = document.createElement("button");
        b.type = "button";
        b.title = p.text;
        if (box === els.emptyPresets) {
          b.innerHTML = `${p.label}<small>${blurb[p.label] || "start hier"}</small>`;
        } else {
          b.textContent = p.label;
        }
        b.addEventListener("click", () => applyPreset(p));
        box.appendChild(b);
      }
    }
  } catch (_) {
    /* ignore */
  }
}

function applyPopMode() {
  const params = new URLSearchParams(location.search);
  if (params.get("pop") === "1") {
    els.appRoot?.classList.add("pop-mode");
    document.title = params.get("view") === "teams" ? "VIT Teams" : "VIT Chat";
  }
  const view = params.get("view");
  if (view === "teams" || view === "chat") {
    document.querySelectorAll(".view-tab").forEach((t) => {
      t.classList.toggle("on", t.dataset.view === view);
    });
    document.querySelectorAll(".view-pane").forEach((p) => {
      p.classList.toggle("on", p.id === `view-${view}`);
    });
  }
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

ensureLocalToken().then(() => {
  applyPopMode();
  loadSessionMessages();
  // re-render saved messages
  if (els.messages && state.messages.length) {
    els.messages.innerHTML = "";
    for (const m of state.messages) {
      if (m.role === "user" || m.role === "assistant") addBubble(m.role, m.content);
    }
  }
  syncEmptyState();
  if (document.getElementById("chat-title") && state.sessionId) {
    const short = state.sessionId.replace(/^s-/, "").slice(0, 6);
    if (new URLSearchParams(location.search).get("pop") === "1") {
      document.getElementById("chat-title").textContent =
        new URLSearchParams(location.search).get("view") === "teams"
          ? "Teams"
          : `Chat · ${short}`;
    }
  }
  ping();
  refreshImportStatus();
  refreshAccounts();
  refreshNetwork();
  loadPresets();
  loadModels().catch((e) => {
    if (els.routeInfo) els.routeInfo.textContent = `Modellen laden mislukt: ${e}`;
  });
});