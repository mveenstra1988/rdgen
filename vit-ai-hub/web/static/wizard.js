(function () {
  const overlay = document.getElementById("wizard");
  if (!overlay) return;

  const params = new URLSearchParams(location.search);
  const force = params.get("wizard") === "1";
  let step = 0;
  let autoPromise = null;
  const steps = [...overlay.querySelectorAll("[data-step]")];
  const titles = ["Welkom", "Inloggen", "Klaar"];

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
    if (titles[step] === "Inloggen") refreshBridgeStatus();
    if (titles[step] === "Klaar") refreshProbe();
  }

  function collectSecrets() {
    return {
      GEMINI_API_KEY: overlay.querySelector("#wiz-gemini")?.value || "",
    };
  }

  function applyToken(data) {
    const tok = data?.gateway_token;
    if (!tok) return;
    const el = document.getElementById("token");
    if (el && !el.value) el.value = tok;
    try {
      sessionStorage.setItem("vit_gateway_token", tok);
    } catch (_) {
      /* ignore */
    }
  }

  function setMsg(text) {
    const msg = overlay.querySelector("#wiz-bridge-msg");
    if (msg) msg.textContent = text;
  }

  async function saveGemini(msgEl) {
    const key = overlay.querySelector("#wiz-gemini")?.value || "";
    if (!key.trim()) {
      if (msgEl) msgEl.textContent = "Nog geen Gemini-key — log in en plak de key.";
      return null;
    }
    const res = await fetch("/api/setup/secrets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ GEMINI_API_KEY: key.trim() }),
    });
    const data = await res.json();
    if (msgEl) {
      msgEl.textContent = data.ok ? "Gemini-key opgeslagen." : "Opslaan mislukt";
    }
    return data;
  }

  async function openGuide(target) {
    const res = await fetch("/api/setup/open-guide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    });
    return res.json();
  }

  function setAutoLog(lines) {
    const box = overlay.querySelector("#wiz-auto-log");
    if (!box) return;
    box.classList.remove("hidden");
    box.textContent = Array.isArray(lines) ? lines.filter(Boolean).join("\n") : String(lines);
  }

  async function runInstallAuto(opts = {}) {
    const body = {
      secrets: collectSecrets(),
      mark_complete: Boolean(opts.mark_complete),
      open_a11y: false,
    };
    setAutoLog(["Installatie op achtergrond…", "· Bridge + token + migratie + Cursor"]);
    const res = await fetch("/api/setup/install-auto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    applyToken(data);
    const s = data.steps || {};
    setAutoLog([
      data.ok ? "✓ Installatie klaar — jij hoeft alleen in te loggen" : "○ Deels klaar — logins hieronder",
      s.gateway_token?.ok ? "✓ Hub-token" : "○ Hub-token",
      s.bridge?.ok || s.bridge?.status?.configured ? "✓ Bridge" : "○ Bridge (op Mac)",
      s.migrate?.ok ? "✓ Kennis/skills/MCP gemigreerd" : "○ Migratie",
      s.continue?.ok ? "✓ Continue→hub" : "○ Continue",
      s.cursor?.ok ? "✓ Cursor-wire" : "○ Cursor-wire",
      data.cursor_base_url ? `Cursor URL: ${data.cursor_base_url}` : "",
    ]);
    return data;
  }

  /** Start install op achtergrond — blokkeert login-knoppen NIET. */
  function kickAutoInstall() {
    if (!autoPromise) {
      autoPromise = runInstallAuto().catch((e) => {
        setAutoLog(String(e));
        return null;
      });
    }
    return autoPromise;
  }

  async function loadStatus() {
    const res = await fetch("/api/setup/status");
    const data = await res.json();
    applyToken(data);
    const box = overlay.querySelector("#wiz-status");
    if (box) {
      box.textContent = [
        `Versie ${data.version}`,
        "Jij: Claude · ChatGPT · Cursor · Gemini",
        "Hub: bridge, token, migratie, defaults — automatisch",
        data.lmstudio_up ? "✓ LM Studio al online" : "○ LM Studio later mag",
      ].join("\n");
    }
    if (data.setup_complete && !force) {
      overlay.classList.add("hidden");
    } else {
      overlay.classList.remove("hidden");
      showStep(0);
      kickAutoInstall();
    }
    return data;
  }

  async function refreshBridgeStatus() {
    const box = overlay.querySelector("#wiz-bridge-status");
    const msg = overlay.querySelector("#wiz-bridge-msg");
    try {
      // Geen await op install-auto — anders lijkt de UI dood
      const res = await fetch("/api/setup/probe");
      const d = await res.json();
      applyToken(d);
      if (box) {
        box.textContent = [
          d.bridge_key || d.bridge?.api_key_configured
            ? "✓ Bridge-key (auto)"
            : "○ Bridge-key volgt…",
          d.bridge_up ? "✓ Bridge draait" : "○ Bridge — login start install",
          d.claude_logged_in ? "✓ Claude ingelogd" : "○ Claude — knop hieronder",
          d.chatgpt_logged_in ? "✓ ChatGPT ingelogd" : "○ ChatGPT — knop hieronder",
          d.gemini_key ? "✓ Gemini-key" : "○ Gemini — login + key plakken",
          d.bridge?.installed ? "✓ Bridge-binary" : "○ Bridge-binary (download bij login)",
        ].join("\n");
      }
      if (msg && !msg.dataset.busy) {
        const left = [
          !d.claude_logged_in && "Claude",
          !d.chatgpt_logged_in && "ChatGPT",
          !d.gemini_key && "Gemini",
        ].filter(Boolean);
        msg.textContent = left.length
          ? `Nog inloggen: ${left.join(", ")}. Klik een oranje knop — browser opent.`
          : "Alle logins OK — ga door naar Klaar.";
      }
    } catch (e) {
      if (box) box.textContent = String(e);
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
        d.claude_logged_in ? "✓ Claude" : "○ Claude (optioneel later)",
        d.chatgpt_logged_in ? "✓ ChatGPT" : "○ ChatGPT (optioneel later)",
        d.gemini_key ? "✓ Gemini / Nano Banana" : "○ Gemini (beelden later)",
        d.bridge_up ? "✓ Bridge" : "○ Bridge",
        d.bridge_key ? "✓ Bridge-key auto" : "○ Bridge-key",
        d.lmstudio_up ? "✓ LM Studio" : "○ LM Studio later",
        `Cursor: ${d.cursor_base_url || "http://127.0.0.1:8787/v1"}`,
        d.gateway_token ? `Token: ${d.gateway_token}` : "",
      ]
        .filter(Boolean)
        .join("\n");
    } catch (e) {
      box.textContent = String(e);
    }
  }

  async function doBridgeLogin(provider, btn) {
    const msg = overlay.querySelector("#wiz-bridge-msg");
    if (msg) msg.dataset.busy = "1";
    const label = btn?.textContent || "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Bezig…";
    }
    setMsg(
      provider === "claude"
        ? "Bridge klaarzetten + Claude-login… browser opent zo."
        : "Bridge klaarzetten + ChatGPT-login… browser opent zo."
    );
    try {
      const res = await fetch("/api/bridge/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMsg(`Fout ${res.status}: ${data.detail || data.error || "login mislukt"}`);
        window.open(
          provider === "claude" ? "https://claude.ai/login" : "https://chatgpt.com/",
          "_blank"
        );
      } else if (data.ok) {
        setMsg(data.hint || "Browser open — log in, daarna ↻ Status.");
      } else {
        setMsg(data.error || data.hint || "Login starten mislukt — zie logs.");
        // Zichtbare fallback zodat er altijd iets opent
        window.open(
          provider === "claude" ? "https://claude.ai/login" : "https://chatgpt.com/",
          "_blank"
        );
      }
      await refreshBridgeStatus();
    } catch (e) {
      setMsg("Netwerkfout: " + String(e));
    } finally {
      if (msg) delete msg.dataset.busy;
      if (btn) {
        btn.disabled = false;
        btn.textContent = label;
      }
    }
  }

  overlay.querySelector("#wiz-next")?.addEventListener("click", async () => {
    try {
      await saveGemini(null);
    } catch (_) {
      /* ignore */
    }
    kickAutoInstall();
    showStep(step + 1);
  });
  overlay.querySelector("#wiz-back")?.addEventListener("click", () => showStep(step - 1));
  overlay.querySelector("#wiz-skip")?.addEventListener("click", () => {
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
  });

  overlay.querySelector("#wiz-start")?.addEventListener("click", () => {
    kickAutoInstall();
    showStep(1);
  });

  overlay.querySelector("#wiz-bridge-login-claude")?.addEventListener("click", (ev) =>
    doBridgeLogin("claude", ev.currentTarget)
  );
  overlay.querySelector("#wiz-bridge-login-gpt")?.addEventListener("click", (ev) =>
    doBridgeLogin("chatgpt", ev.currentTarget)
  );
  overlay.querySelector("#wiz-bridge-refresh")?.addEventListener("click", () => refreshBridgeStatus());

  overlay.querySelector("#wiz-login-cursor")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Bezig…";
    setMsg("Cursor openen…");
    try {
      const data = await openGuide("cursor_settings");
      setMsg(
        data.ok
          ? "Cursor geopend. Hub-URL/token: ~/.config/vit/cursor-hub.json"
          : data.error || data.hint || "Cursor openen mislukt — is Cursor geïnstalleerd?"
      );
    } catch (e) {
      setMsg(String(e));
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  });

  overlay.querySelector("#wiz-login-gemini")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Bezig…";
    setMsg("Google AI Studio openen…");
    try {
      const data = await openGuide("gemini");
      setMsg(
        data.ok
          ? "Browser open — log in bij Google, maak een API key en plak die hieronder."
          : data.error || "Kon Gemini-pagina niet openen."
      );
      // Fallback: open zelf in dit venster als mac open faalde
      if (!data.ok) {
        window.open("https://aistudio.google.com/apikey", "_blank");
      }
    } catch (e) {
      setMsg(String(e));
      window.open("https://aistudio.google.com/apikey", "_blank");
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  });

  overlay.querySelector("#wiz-gemini")?.addEventListener("change", () =>
    saveGemini(overlay.querySelector("#wiz-bridge-msg"))
  );
  overlay.querySelector("#wiz-gemini")?.addEventListener("blur", () =>
    saveGemini(overlay.querySelector("#wiz-bridge-msg"))
  );

  overlay.querySelector("#wiz-probe")?.addEventListener("click", () => refreshProbe());

  overlay.querySelector("#wiz-finish")?.addEventListener("click", async () => {
    const btn = overlay.querySelector("#wiz-finish");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Afronden…";
    }
    try {
      await saveGemini(null);
      await runInstallAuto({ mark_complete: true });
      await fetch("/api/setup/complete", { method: "POST" });
    } catch (_) {
      /* ignore */
    }
    overlay.classList.add("hidden");
    history.replaceState({}, "", "/");
    location.reload();
  });

  loadStatus().catch(() => {
    overlay.classList.remove("hidden");
    showStep(0);
  });
})();
