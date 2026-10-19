(function () {
  const overlay = document.getElementById("wizard");
  if (!overlay) return;

  const params = new URLSearchParams(location.search);
  const force = params.get("wizard") === "1";
  let step = 0;
  const steps = [...overlay.querySelectorAll("[data-step]")];

  function showStep(i) {
    step = Math.max(0, Math.min(steps.length - 1, i));
    steps.forEach((el, idx) => el.classList.toggle("active", idx === step));
    overlay.querySelector("#wiz-progress").textContent = `${step + 1} / ${steps.length}`;
  }

  function collectSecrets() {
    return {
      OPENROUTER_API_KEY: overlay.querySelector("#wiz-openrouter")?.value || "",
      XAI_API_KEY: overlay.querySelector("#wiz-xai")?.value || "",
      BRIDGE_API_KEY: overlay.querySelector("#wiz-bridge")?.value || "",
      VIT_LOCAL_LIGHT_MODEL: overlay.querySelector("#wiz-light")?.value || "",
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

  async function loadStatus() {
    const res = await fetch("/api/setup/status");
    const data = await res.json();
    applyToken(data);
    const box = overlay.querySelector("#wiz-status");
    if (box) {
      box.textContent = [
        `Versie ${data.version}`,
        data.secret_exists ? "Secrets-bestand OK" : "Secrets worden aangemaakt",
        data.lmstudio_up ? "LM Studio bereikbaar" : "LM Studio nog niet (optioneel)",
        data.ollama_up ? "Ollama bereikbaar" : "Ollama nog niet (optioneel)",
        `Keys: ${(data.keys_present || []).join(", ") || "nog geen cloud keys"}`,
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

  async function runBootstrap({ openA11y = false, finish = false } = {}) {
    const msg = overlay.querySelector("#wiz-go-msg") || overlay.querySelector("#wiz-import-msg");
    const btn = overlay.querySelector("#wiz-go-all") || overlay.querySelector("#wiz-import");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Bezig…";
    }
    if (msg) msg.textContent = "Import + sync + klaarzetten…";
    try {
      const res = await fetch("/api/setup/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secrets: collectSecrets(),
          open_a11y: openA11y,
        }),
      });
      const data = await res.json();
      const k = data.knowledge || {};
      if (msg) {
        msg.textContent =
          data.ok === false
            ? "Setup mislukt"
            : `${k.conversations || 0} chats · ${k.memories || 0} memories · ${k.projects || 0} projects`;
      }
      await loadStatus();
      if (finish && data.ok !== false) {
        overlay.classList.add("hidden");
        history.replaceState({}, "", "/");
        location.reload();
      }
      return data;
    } catch (e) {
      if (msg) msg.textContent = String(e);
      throw e;
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = btn.id === "wiz-go-all" ? "Alles nu regelen" : "Importeer alles nu";
      }
    }
  }

  overlay.querySelector("#wiz-next")?.addEventListener("click", () => showStep(step + 1));
  overlay.querySelector("#wiz-back")?.addEventListener("click", () => showStep(step - 1));
  overlay.querySelector("#wiz-skip")?.addEventListener("click", () => {
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
  });

  overlay.querySelector("#wiz-go-all")?.addEventListener("click", () =>
    runBootstrap({ openA11y: true, finish: true })
  );

  overlay.querySelector("#wiz-save-keys")?.addEventListener("click", async () => {
    const body = collectSecrets();
    const res = await fetch("/api/setup/secrets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    overlay.querySelector("#wiz-keys-msg").textContent = data.ok
      ? `Opgeslagen in ${data.path}`
      : "Opslaan mislukt";
  });

  overlay.querySelector("#wiz-a11y")?.addEventListener("click", () => {
    fetch("/api/setup/open-accessibility", { method: "POST" });
  });

  overlay.querySelector("#wiz-import")?.addEventListener("click", () =>
    runBootstrap({ openA11y: false, finish: false })
  );

  overlay.querySelector("#wiz-finish")?.addEventListener("click", async () => {
    await fetch("/api/setup/complete", { method: "POST" });
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
    location.reload();
  });

  loadStatus().catch(() => overlay.classList.remove("hidden"));
})();
