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

  async function loadStatus() {
    const res = await fetch("/api/setup/status");
    const data = await res.json();
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

  overlay.querySelector("#wiz-next")?.addEventListener("click", () => showStep(step + 1));
  overlay.querySelector("#wiz-back")?.addEventListener("click", () => showStep(step - 1));
  overlay.querySelector("#wiz-skip")?.addEventListener("click", () => {
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
  });

  overlay.querySelector("#wiz-save-keys")?.addEventListener("click", async () => {
    const body = {
      OPENROUTER_API_KEY: overlay.querySelector("#wiz-openrouter")?.value || "",
      XAI_API_KEY: overlay.querySelector("#wiz-xai")?.value || "",
      BRIDGE_API_KEY: overlay.querySelector("#wiz-bridge")?.value || "",
      VIT_LOCAL_LIGHT_MODEL: overlay.querySelector("#wiz-light")?.value || "",
    };
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

  overlay.querySelector("#wiz-import")?.addEventListener("click", async () => {
    const btn = overlay.querySelector("#wiz-import");
    btn.disabled = true;
    btn.textContent = "Bezig…";
    try {
      const res = await fetch("/api/import/all", { method: "POST" });
      const data = await res.json();
      const k = data.knowledge || {};
      overlay.querySelector("#wiz-import-msg").textContent =
        `${k.conversations || 0} chats · ${k.memories || 0} memories · ${k.projects || 0} projects`;
      await fetch("/api/sync/start?interval_sec=300", { method: "POST" });
    } catch (e) {
      overlay.querySelector("#wiz-import-msg").textContent = String(e);
    } finally {
      btn.disabled = false;
      btn.textContent = "Importeer alles nu";
    }
  });

  overlay.querySelector("#wiz-finish")?.addEventListener("click", async () => {
    await fetch("/api/setup/complete", { method: "POST" });
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
    location.reload();
  });

  loadStatus().catch(() => overlay.classList.remove("hidden"));
})();
