(function () {
  const state = {
    teams: [],
    agents: [],
    editingTeamId: null,
    editingAgentId: null,
    draftMembers: [],
  };

  function headers() {
    const h = { "Content-Type": "application/json" };
    const tokEl = document.getElementById("token");
    let token = tokEl?.value?.trim() || "";
    if (!token) {
      try {
        token = sessionStorage.getItem("vit_gateway_token") || "";
      } catch (_) {
        /* ignore */
      }
    }
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }

  function workspace() {
    return document.getElementById("workspace")?.value?.trim() || null;
  }

  document.querySelectorAll(".view-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-view");
      document.querySelectorAll(".view-tab").forEach((b) => b.classList.toggle("on", b === btn));
      document.getElementById("view-chat")?.classList.toggle("on", view === "chat");
      document.getElementById("view-teams")?.classList.toggle("on", view === "teams");
      const title = document.getElementById("chat-title");
      const info = document.getElementById("route-info");
      if (view === "teams") {
        if (title) title.textContent = "Agent teams";
        if (info) info.textContent = "Bouw visueel teams (webdesign, apps, …) en run ze.";
        refresh();
      } else {
        if (title) title.textContent = "Chat";
        if (info) info.textContent = "Kies een model en start.";
      }
    });
  });

  async function refresh() {
    const res = await fetch("/api/teams", { headers: headers() });
    if (!res.ok) throw new Error(`teams HTTP ${res.status}`);
    const data = await res.json();
    state.teams = data.teams || [];
    state.agents = data.agents || [];
    renderLists();
    fillAgentSelects();
    if (state.editingTeamId) selectTeam(state.editingTeamId, false);
    if (state.editingAgentId) selectAgent(state.editingAgentId, false);
  }

  function renderLists() {
    const tl = document.getElementById("teams-list");
    const al = document.getElementById("agents-list");
    if (tl) {
      tl.innerHTML = state.teams
        .map(
          (t) => `
        <button type="button" class="team-card ${state.editingTeamId === t.id ? "on" : ""}" data-team="${t.id}" style="--c:${t.color || "#7ec8ff"}">
          <strong>${escapeHtml(t.name)}</strong>
          <span>${escapeHtml(t.blurb || "")}</span>
          <em>${(t.members || []).length} agents · ${t.mode || "pipeline"}</em>
        </button>`
        )
        .join("");
      tl.querySelectorAll("[data-team]").forEach((el) => {
        el.addEventListener("click", () => selectTeam(el.getAttribute("data-team")));
      });
    }
    if (al) {
      al.innerHTML = state.agents
        .map(
          (a) => `
        <button type="button" class="agent-chip ${state.editingAgentId === a.id ? "on" : ""}" data-agent="${a.id}" style="--c:${a.color || "#c4f04d"}">
          <i></i><span>${escapeHtml(a.name)}</span><small>${escapeHtml(a.role || "")}</small>
        </button>`
        )
        .join("");
      al.querySelectorAll("[data-agent]").forEach((el) => {
        el.addEventListener("click", () => selectAgent(el.getAttribute("data-agent")));
      });
    }
  }

  function fillAgentSelects() {
    const lead = document.getElementById("tf-lead");
    const add = document.getElementById("tf-add-agent");
    const opts = state.agents
      .map((a) => `<option value="${a.id}">${escapeHtml(a.name)} — ${escapeHtml(a.role || "")}</option>`)
      .join("");
    if (lead) lead.innerHTML = opts;
    if (add) add.innerHTML = opts;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showTeamForm(show) {
    document.getElementById("team-form")?.classList.toggle("hidden", !show);
    if (show) document.getElementById("agent-form")?.classList.add("hidden");
  }

  function showAgentForm(show) {
    document.getElementById("agent-form")?.classList.toggle("hidden", !show);
    if (show) document.getElementById("team-form")?.classList.add("hidden");
  }

  function selectTeam(id, resetDraft = true) {
    const team = state.teams.find((t) => t.id === id);
    if (!team) return;
    state.editingTeamId = id;
    state.editingAgentId = null;
    if (resetDraft) state.draftMembers = JSON.parse(JSON.stringify(team.members || []));
    showTeamForm(true);
    document.getElementById("editor-title").textContent = team.name;
    document.getElementById("editor-blurb").textContent = team.blurb || "";
    document.getElementById("tf-name").value = team.name || "";
    document.getElementById("tf-blurb").value = team.blurb || "";
    document.getElementById("tf-color").value = team.color || "#c4f04d";
    document.getElementById("tf-studio").value = team.studio || "webdesign";
    document.getElementById("tf-mode").value = team.mode || "pipeline";
    document.getElementById("tf-lead").value = team.lead_agent_id || "";
    renderMembers();
    renderLists();
  }

  function selectAgent(id) {
    const agent = state.agents.find((a) => a.id === id);
    if (!agent) return;
    state.editingAgentId = id;
    state.editingTeamId = null;
    showAgentForm(true);
    document.getElementById("editor-title").textContent = agent.name;
    document.getElementById("editor-blurb").textContent = agent.role || "";
    document.getElementById("af-name").value = agent.name || "";
    document.getElementById("af-role").value = agent.role || "";
    document.getElementById("af-color").value = agent.color || "#7ec8ff";
    document.getElementById("af-studio").value = agent.studio || "chat";
    document.getElementById("af-model").value = agent.model || "vit/auto";
    document.getElementById("af-tools").checked = !!agent.tools;
    document.getElementById("af-system").value = agent.system || "";
    renderLists();
  }

  function renderMembers() {
    const box = document.getElementById("tf-members");
    if (!box) return;
    const sorted = [...state.draftMembers].sort((a, b) => a.order - b.order);
    box.innerHTML = sorted
      .map((m, idx) => {
        const ag = state.agents.find((a) => a.id === m.agent_id);
        const name = ag?.name || m.agent_id;
        return `<div class="member-row" data-idx="${idx}">
          <span class="dot" style="background:${ag?.color || "#888"}"></span>
          <strong>${escapeHtml(name)}</strong>
          <input type="text" class="member-label" value="${escapeHtml(m.label || "")}" placeholder="stap-label" />
          <button type="button" class="ghost tiny-btn" data-up>↑</button>
          <button type="button" class="ghost tiny-btn" data-down>↓</button>
          <button type="button" class="ghost tiny-btn" data-rm>×</button>
        </div>`;
      })
      .join("");
    box.querySelectorAll(".member-row").forEach((row) => {
      const idx = Number(row.getAttribute("data-idx"));
      row.querySelector("[data-up]")?.addEventListener("click", () => moveMember(idx, -1));
      row.querySelector("[data-down]")?.addEventListener("click", () => moveMember(idx, 1));
      row.querySelector("[data-rm]")?.addEventListener("click", () => {
        state.draftMembers.splice(idx, 1);
        reindexMembers();
        renderMembers();
      });
      row.querySelector(".member-label")?.addEventListener("change", (ev) => {
        state.draftMembers[idx].label = ev.target.value;
      });
    });
  }

  function reindexMembers() {
    state.draftMembers.forEach((m, i) => {
      m.order = i;
    });
  }

  function moveMember(idx, delta) {
    const next = idx + delta;
    if (next < 0 || next >= state.draftMembers.length) return;
    const arr = state.draftMembers;
    [arr[idx], arr[next]] = [arr[next], arr[idx]];
    reindexMembers();
    renderMembers();
  }

  document.getElementById("team-new")?.addEventListener("click", () => {
    state.editingTeamId = null;
    state.draftMembers = [];
    showTeamForm(true);
    document.getElementById("editor-title").textContent = "Nieuw team";
    document.getElementById("tf-name").value = "";
    document.getElementById("tf-blurb").value = "";
    document.getElementById("tf-color").value = "#c4f04d";
    document.getElementById("tf-studio").value = "webdesign";
    document.getElementById("tf-mode").value = "pipeline";
    renderMembers();
  });

  document.getElementById("agent-new")?.addEventListener("click", () => {
    state.editingAgentId = null;
    showAgentForm(true);
    document.getElementById("editor-title").textContent = "Nieuwe agent";
    document.getElementById("af-name").value = "";
    document.getElementById("af-role").value = "";
    document.getElementById("af-color").value = "#7ec8ff";
    document.getElementById("af-studio").value = "software";
    document.getElementById("af-model").value = "vit/auto";
    document.getElementById("af-tools").checked = true;
    document.getElementById("af-system").value = "";
  });

  document.getElementById("tf-add-btn")?.addEventListener("click", () => {
    const id = document.getElementById("tf-add-agent")?.value;
    if (!id) return;
    if (state.draftMembers.some((m) => m.agent_id === id)) return;
    state.draftMembers.push({ agent_id: id, order: state.draftMembers.length, label: "" });
    renderMembers();
  });

  document.getElementById("tf-save")?.addEventListener("click", async () => {
    const body = {
      id: state.editingTeamId || undefined,
      name: document.getElementById("tf-name").value.trim(),
      blurb: document.getElementById("tf-blurb").value.trim(),
      color: document.getElementById("tf-color").value,
      studio: document.getElementById("tf-studio").value,
      mode: document.getElementById("tf-mode").value,
      lead_agent_id: document.getElementById("tf-lead").value,
      members: state.draftMembers,
    };
    const res = await fetch("/api/teams", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    state.editingTeamId = data.id;
    await refresh();
    selectTeam(data.id);
  });

  document.getElementById("tf-delete")?.addEventListener("click", async () => {
    if (!state.editingTeamId) return;
    const res = await fetch(`/api/teams/${state.editingTeamId}`, {
      method: "DELETE",
      headers: headers(),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Kan niet verwijderen");
      return;
    }
    state.editingTeamId = null;
    showTeamForm(false);
    await refresh();
  });

  document.getElementById("af-save")?.addEventListener("click", async () => {
    const body = {
      id: state.editingAgentId || undefined,
      name: document.getElementById("af-name").value.trim(),
      role: document.getElementById("af-role").value.trim(),
      color: document.getElementById("af-color").value,
      studio: document.getElementById("af-studio").value,
      model: document.getElementById("af-model").value.trim() || "vit/auto",
      tools: document.getElementById("af-tools").checked,
      system: document.getElementById("af-system").value,
    };
    const res = await fetch("/api/agents", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    state.editingAgentId = data.id;
    await refresh();
    selectAgent(data.id);
  });

  document.getElementById("af-delete")?.addEventListener("click", async () => {
    if (!state.editingAgentId) return;
    const res = await fetch(`/api/agents/${state.editingAgentId}`, {
      method: "DELETE",
      headers: headers(),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Kan niet verwijderen");
      return;
    }
    state.editingAgentId = null;
    showAgentForm(false);
    await refresh();
  });

  document.getElementById("team-run")?.addEventListener("click", async () => {
    const msg = document.getElementById("team-run-msg");
    const out = document.getElementById("team-run-out");
    const btn = document.getElementById("team-run");
    const teamId = state.editingTeamId || state.teams[0]?.id;
    const task = document.getElementById("team-task")?.value?.trim();
    if (!teamId) {
      if (msg) msg.textContent = "Selecteer eerst een team.";
      return;
    }
    if (!task) {
      if (msg) msg.textContent = "Vul een taak in.";
      return;
    }
    btn.disabled = true;
    btn.textContent = "Team draait…";
    if (msg) msg.textContent = "Agents werken na elkaar / board…";
    if (out) out.innerHTML = "";
    try {
      const res = await fetch(`/api/teams/${teamId}/run`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ task, workspace: workspace() }),
      });
      const data = await res.json();
      if (!data.ok) {
        if (msg) msg.textContent = data.error || "Run mislukt";
        return;
      }
      if (msg) msg.textContent = `Klaar in ${data.elapsed_sec}s · ${data.team_name}`;
      if (out) {
        out.innerHTML = (data.steps || [])
          .map((s) => {
            if (!s.ok) {
              return `<article class="run-step err"><header>${escapeHtml(s.label || s.agent_id)}</header><pre>${escapeHtml(s.error)}</pre></article>`;
            }
            return `<article class="run-step" style="--c:${s.color || "#c4f04d"}">
              <header><span class="dot"></span><strong>${escapeHtml(s.agent_name)}</strong>
              <small>${escapeHtml(s.label || "")} · ${escapeHtml(s.model || "")}</small></header>
              <pre>${escapeHtml(s.content || "")}</pre>
            </article>`;
          })
          .join("");
        if (data.final) {
          out.innerHTML += `<article class="run-step final"><header><strong>Eindresultaat</strong></header><pre>${escapeHtml(data.final)}</pre></article>`;
        }
      }
    } catch (e) {
      if (msg) msg.textContent = String(e);
    } finally {
      btn.disabled = false;
      btn.textContent = "Run team";
    }
  });

  // preload when teams tab first shown; also warm presets
  refresh().catch(() => {});
})();
