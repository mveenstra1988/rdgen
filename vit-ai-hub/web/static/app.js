const state = {
  models: [],
  messages: [],
};

const els = {
  modelSelect: document.getElementById("model-select"),
  modelFilter: document.getElementById("model-filter"),
  modelMeta: document.getElementById("model-meta"),
  studioSelect: document.getElementById("studio-select"),
  workspace: document.getElementById("workspace"),
  messages: document.getElementById("messages"),
  prompt: document.getElementById("prompt"),
  form: document.getElementById("composer"),
  token: document.getElementById("token"),
  tools: document.getElementById("tools-toggle"),
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
};

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

function selectedModel() {
  return els.modelSelect.value || "vit/auto";
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
  els.modelSelect.innerHTML = "";
  for (const m of models) {
    const opt = document.createElement("option");
    opt.value = m.id;
    const kind = m.local ? "local" : m.virtual ? "vit" : "cloud";
    opt.textContent = `[${m.label || m.backend || kind}] ${m.name || m.id}`;
    els.modelSelect.appendChild(opt);
  }
  if ([...els.modelSelect.options].some((o) => o.value === current)) {
    els.modelSelect.value = current;
  } else if (models.some((m) => m.id === "vit/auto")) {
    els.modelSelect.value = "vit/auto";
  }
  updateMeta();
}

function updateMeta() {
  const m = state.models.find((x) => x.id === selectedModel());
  if (!m) {
    els.modelMeta.textContent = "";
    return;
  }
  els.modelMeta.textContent = [
    `id: ${m.id}`,
    `backend: ${m.backend || "?"}`,
    `scope: ${m.local ? "lokaal" : m.virtual ? "virtueel" : "cloud"}`,
  ].join("\n");
  els.routeInfo.textContent = m.virtual
    ? "Auto/virtueel model: gateway kiest backend (PII kan forceren naar lokaal)."
    : `Direct: ${m.label || m.backend} · ${m.local ? "blijft op deze Mac" : "via privacyfilter"}`;
}

function addBubble(role, text, meta = null) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  if (meta) {
    const tag = document.createElement("div");
    tag.className = `tag ${meta.local ? "local" : "cloud"}`;
    if (meta.pii_forced_local) tag.classList.add("warn");
    tag.textContent = [
      meta.backend,
      meta.model,
      meta.pii_forced_local ? "PII→lokaal" : meta.pii_action,
    ]
      .filter(Boolean)
      .join(" · ");
    div.appendChild(tag);
  }
  const body = document.createElement("div");
  body.textContent = text;
  div.appendChild(body);
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
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

els.modelFilter.addEventListener("input", () => renderModels(els.modelFilter.value));
els.modelSelect.addEventListener("change", updateMeta);
els.refresh.addEventListener("click", () => loadModels().catch((e) => addBubble("system", String(e))));
els.newChat.addEventListener("click", () => {
  state.messages = [];
  els.messages.innerHTML = "";
  const studio = els.studioSelect?.value || "chat";
  addBubble(
    "system",
    `Nieuwe chat · studio=${studio}` +
      (els.workspace?.value.trim() ? ` · ${els.workspace.value.trim()}` : "") +
      ". Privacyfilter blijft actief."
  );
});

els.studioSelect?.addEventListener("change", () => {
  try {
    localStorage.setItem("vit_studio", els.studioSelect.value);
  } catch (_) {
    /* ignore */
  }
  addBubble("system", `Studio: ${els.studioSelect.value}. Tools schrijven/lezen in je workspace.`);
});

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

addBubble("system", "VIT AI Hub klaar. Kies een model, of importeer ChatGPT/Claude/Cursor-kennis met 1 klik.");
ensureLocalToken().then(() => {
  ping();
  refreshImportStatus();
  loadModels().catch((e) => addBubble("system", `Kon modellen niet laden: ${e}`));
});