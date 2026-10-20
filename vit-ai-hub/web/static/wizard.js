(function () {
  const overlay = document.getElementById("wizard");
  if (!overlay) return;

  const params = new URLSearchParams(location.search);
  const force = params.get("wizard") === "1";
  let step = 0;
  const steps = [...overlay.querySelectorAll("[data-step]")];
  const titles = [
    "Welkom",
    "Lokaal",
    "Cloud",
    "Gemini",
    "OmniRoute",
    "Claude/GPT",
    "Cursor",
    "VIT-apps",
    "Import",
    "Klaar",
  ];

  function showStep(i) {
    step = Math.max(0, Math.min(steps.length - 1, i));
    steps.forEach((el, idx) => el.classList.toggle("active", idx === step));
    overlay.querySelector("#wiz-progress").textContent = `${step + 1} / ${steps.length}`;
    const rail = overlay.querySelector("#wiz-rail");
    if (rail) {
      rail.innerHTML = titles
        .map(
          (t, idx) =>
            `<li class="${idx === step ? "on" : idx < step ? "done" : ""}">${idx + 1}. ${t}</li>`
        )
        .join("");
    }
    if (step === steps.length - 1) refreshProbe();
    // VIT-apps step index (0-based): welkom=0 … vit=7
    if (titles[step] === "VIT-apps") refreshVitWizard();
  }

  function collectSecrets() {
    return {
      OPENROUTER_API_KEY: overlay.querySelector("#wiz-openrouter")?.value || "",
      DEEPSEEK_API_KEY: overlay.querySelector("#wiz-deepseek")?.value || "",
      XAI_API_KEY: overlay.querySelector("#wiz-xai")?.value || "",
      GEMINI_API_KEY: overlay.querySelector("#wiz-gemini")?.value || "",
      VIT_NANO_BANANA_MODEL: overlay.querySelector("#wiz-banana-model")?.value || "",
      BRIDGE_API_KEY: overlay.querySelector("#wiz-bridge")?.value || "",
      OMNIROUTE_API_KEY: overlay.querySelector("#wiz-omni")?.value || "",
      VIT_LOCAL_LIGHT_MODEL: overlay.querySelector("#wiz-light")?.value || "",
      VIT_LOCAL_HEAVY_MODEL: overlay.querySelector("#wiz-heavy")?.value || "",
    };
  }

  function applyToken(data) {
    if (!data?.gateway_token) return;
    const tok = document.getElementById("token");
    if (tok && !tok.value) tok.value = data.gateway_token;
    try {
      sessionStorage.setItem("vit_gateway_token", data.gateway_token);
    } catch (_) {
      /* ignore */
    }
  }

  async function saveSecrets(msgEl) {
    const res = await fetch("/api/setup/secrets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectSecrets()),
    });
    const data = await res.json();
    if (msgEl) {
      msgEl.textContent = data.ok ? `Opgeslagen in ${data.path}` : "Opslaan mislukt";
    }
    return data;
  }

  async function openGuide(target) {
    await fetch("/api/setup/open-guide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    });
  }

  async function loadStatus() {
    const res = await fetch("/api/setup/status");
    const data = await res.json();
    applyToken(data);
    const box = overlay.querySelector("#wiz-status");
    if (box) {
      const opsN = Object.values(data.ops_configured || {}).filter(Boolean).length;
      box.textContent = [
        `Versie ${data.version}`,
        data.secret_exists ? "Secrets OK" : "Secrets worden aangemaakt",
        data.lmstudio_up ? "✓ LM Studio" : "○ LM Studio nog uit",
        data.ollama_up ? "✓ Ollama" : "○ Ollama optioneel",
        data.ops_env_exists
          ? `Ops.env · ${opsN} service(s) geconfigureerd`
          : "Ops.env template wordt aangemaakt",
        `Keys: ${(data.keys_present || []).filter((k) => k !== "VIT_GATEWAY_TOKEN").join(", ") || "nog geen cloud keys"}`,
      ].join("\n");
    }
    if (data.setup_complete && !force) {
      overlay.classList.add("hidden");
    } else {
      overlay.classList.remove("hidden");
      showStep(0);
    }
    return data;
  }

  async function refreshVitWizard() {
    const box = overlay.querySelector("#wiz-vit-apps");
    const msg = overlay.querySelector("#wiz-vit-msg");
    if (!box) return;
    try {
      const res = await fetch("/api/setup/probe");
      const d = await res.json();
      const lines = (d.vit_apps || []).map(
        (a) => `${a.installed ? "✓" : "○"} ${a.name}${a.web && !a.installed ? " (web)" : ""}`
      );
      box.textContent =
        lines.join("\n") ||
        `Suite: ${d.vit_apps_installed || 0}/${d.vit_apps_count || 0} geïnstalleerd`;
      if (msg) {
        msg.textContent =
          (d.vit_apps_installed || 0) > 0
            ? "Open de apps hierboven en log in — hub koppelt via vit_app_open / handoff."
            : "Nog geen VIT-apps gevonden in ~/Applications — Kluis web werkt wél.";
      }
    } catch (e) {
      box.textContent = String(e);
    }
  }

  async function refreshProbe() {
    const box = overlay.querySelector("#wiz-final");
    if (!box) return;
    try {
      const res = await fetch("/api/setup/probe");
      const d = await res.json();
      applyToken(d);
      box.textContent = [
        `Hub v${d.version}`,
        d.lmstudio_up ? "✓ Lokaal LM Studio" : "○ LM Studio — start later mag",
        d.ollama_up ? "✓ Ollama" : "○ Ollama",
        d.openrouter_key ? "✓ OpenRouter (gratis + meer)" : "○ OpenRouter key",
        d.gemini_key ? "✓ Gemini / Nano Banana" : "○ Gemini key (beelden)",
        d.deepseek_key ? "✓ DeepSeek direct" : "○ DeepSeek (via OpenRouter kan ook)",
        d.bridge_up ? "✓ Claude/ChatGPT bridge :8317" : "○ Bridge — log in via stap 5",
        d.omniroute_up ? "✓ OmniRoute :20128" : "○ OmniRoute optioneel",
        d.xai_key ? "✓ Grok" : "○ Grok optioneel",
        `VIT-apps: ${d.vit_apps_installed || 0}/${d.vit_apps_count || 0} geïnstalleerd`,
        `Cursor base URL: ${d.cursor_base_url}`,
        d.gateway_token ? `Token (voor Cursor): ${d.gateway_token}` : "",
      ]
        .filter(Boolean)
        .join("\n");
    } catch (e) {
      box.textContent = String(e);
    }
  }

  async function runImport() {
    const msg = overlay.querySelector("#wiz-import-msg");
    const btn = overlay.querySelector("#wiz-import");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Bezig…";
    }
    if (msg) msg.textContent = "Import + sync…";
    try {
      await saveSecrets(null);
      const res = await fetch("/api/setup/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secrets: collectSecrets(), open_a11y: false }),
      });
      const data = await res.json();
      const k = data.knowledge || {};
      const mig = data.migration || {};
      const skillsBlock = mig.skills || data.import?.skills || {};
      const sk = skillsBlock.found ?? k.skills ?? 0;
      const mirrored = mig.profile?.sources?.mirrored_files ?? 0;
      const mcpN = (mig.profile?.mcp_servers || []).length;
      if (msg) {
        msg.textContent =
          `${k.conversations || 0} chats · ${k.memories || 0} mem · ${sk} skills · ` +
          `${mirrored} files gespiegeld · ${mcpN} MCP` +
          (skillsBlock.agents_promoted
            ? ` · ${skillsBlock.agents_promoted.written || 0} agents`
            : "");
      }
      return data;
    } catch (e) {
      if (msg) msg.textContent = String(e);
      throw e;
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Migreer ALLES nu";
      }
    }
  }

  overlay.querySelector("#wiz-next")?.addEventListener("click", async () => {
    // Auto-opslaan keys bij elke stap → alles in 1x goed
    try {
      await saveSecrets(null);
    } catch (_) {
      /* ignore */
    }
    showStep(step + 1);
  });
  overlay.querySelector("#wiz-back")?.addEventListener("click", () => showStep(step - 1));
  overlay.querySelector("#wiz-skip")?.addEventListener("click", () => {
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
  });
  overlay.querySelector("#wiz-start")?.addEventListener("click", () => showStep(1));

  overlay.querySelectorAll("[data-guide]").forEach((btn) => {
    btn.addEventListener("click", () => openGuide(btn.getAttribute("data-guide")));
  });

  overlay.querySelector("#wiz-save-local")?.addEventListener("click", () =>
    saveSecrets(overlay.querySelector("#wiz-local-msg"))
  );
  overlay.querySelector("#wiz-save-cloud")?.addEventListener("click", () =>
    saveSecrets(overlay.querySelector("#wiz-cloud-msg"))
  );
  overlay.querySelector("#wiz-save-gemini")?.addEventListener("click", () =>
    saveSecrets(overlay.querySelector("#wiz-gemini-msg"))
  );
  overlay.querySelector("#wiz-save-omni")?.addEventListener("click", () =>
    saveSecrets(overlay.querySelector("#wiz-omni-msg"))
  );
  overlay.querySelector("#wiz-vit-refresh")?.addEventListener("click", () => refreshVitWizard());

  overlay.querySelector("#wiz-save-bridge")?.addEventListener("click", async () => {
    const msg = overlay.querySelector("#wiz-bridge-msg");
    await saveSecrets(msg);
    const slots = [
      {
        url: overlay.querySelector("#wiz-bridge-url-1")?.value || "http://127.0.0.1:8317/v1",
        key: overlay.querySelector("#wiz-bridge")?.value || "",
        label: "Bridge #1",
      },
      {
        url: overlay.querySelector("#wiz-bridge-url-2")?.value || "",
        key: overlay.querySelector("#wiz-bridge-key-2")?.value || "",
        label: "Bridge #2",
      },
      {
        url: overlay.querySelector("#wiz-bridge-url-3")?.value || "",
        key: overlay.querySelector("#wiz-bridge-key-3")?.value || "",
        label: "Bridge #3",
      },
    ];
    let n = 0;
    for (const s of slots) {
      if (!s.url.trim()) continue;
      try {
        const res = await fetch("/api/accounts/bridge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            label: s.label,
            base_url: s.url.trim(),
            api_key: s.key,
            tags: ["claude", "chatgpt"],
            enabled: true,
          }),
        });
        if (res.ok) n += 1;
      } catch (_) {
        /* ignore */
      }
    }
    if (msg) msg.textContent = `${n} bridge-abo(s) in pool. Bij uitputting → volgende automatisch.`;
  });

  overlay.querySelector("#wiz-copy-url")?.addEventListener("click", async () => {
    const url = overlay.querySelector("#wiz-cursor-url")?.textContent || "";
    try {
      await navigator.clipboard.writeText(url);
      overlay.querySelector("#wiz-cursor-msg").textContent = "Gekopieerd.";
    } catch {
      overlay.querySelector("#wiz-cursor-msg").textContent = url;
    }
  });

  overlay.querySelector("#wiz-export-continue")?.addEventListener("click", async () => {
    const res = await fetch("/api/workspace/export-continue", { method: "POST" });
    const data = await res.json();
    overlay.querySelector("#wiz-cursor-msg").textContent = data.ok
      ? `Continue-config: ${data.path}`
      : "Export mislukt";
  });

  overlay.querySelector("#wiz-a11y")?.addEventListener("click", () => {
    fetch("/api/setup/open-accessibility", { method: "POST" });
  });

  overlay.querySelector("#wiz-import")?.addEventListener("click", () => runImport());
  overlay.querySelector("#wiz-probe")?.addEventListener("click", () => refreshProbe());

  overlay.querySelector("#wiz-finish")?.addEventListener("click", async () => {
    await saveSecrets(null);
    await fetch("/api/setup/complete", { method: "POST" });
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
    location.reload();
  });

  loadStatus().catch(() => {
    overlay.classList.remove("hidden");
    showStep(0);
  });
})();
