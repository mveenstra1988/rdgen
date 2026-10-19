const state = {
  models: [],
  messages: [],
};

const els = {
  modelSelect: document.getElementById("model-select"),
  modelFilter: document.getElementById("model-filter"),
  modelMeta: document.getElementById("model-meta"),
  messages: document.getElementById("messages"),
  prompt: document.getElementById("prompt"),
  form: document.getElementById("composer"),
  token: document.getElementById("token"),
  tools: document.getElementById("tools-toggle"),
  health: document.getElementById("health"),
  routeInfo: document.getElementById("route-info"),
  refresh: document.getElementById("refresh-models"),
  newChat: document.getElementById("new-chat"),
};

function headers() {
  const h = { "Content-Type": "application/json" };
  const token = els.token.value.trim();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
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
  addBubble("system", "Nieuwe chat. Privacyfilter blijft actief.");
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

addBubble("system", "VIT AI Hub klaar. Kies een specifiek model of vit/auto.");
ping();
loadModels().catch((e) => addBubble("system", `Kon modellen niet laden: ${e}`));