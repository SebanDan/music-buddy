/**
 * sessions.js — gestion des sessions sauvegardées
 * Rail 2 lignes + recherche live + chargement dans mixer.
 */

window.Sessions = (() => {

  let _allSessions = [];

  // ─── Chargement ────────────────────────────────────────────────────────────

  async function load() {
    try {
      const res    = await fetch("/api/sessions");
      _allSessions = await res.json();
      _render(_allSessions);
    } catch {
      document.getElementById("sessions-list").innerHTML =
        '<p class="no-sessions">Impossible de charger les sessions.</p>';
    }
  }

  // Filtrage live par nom
  document.getElementById("sessions-search").addEventListener("input", e => {
    const q = e.target.value.trim().toLowerCase();
    _render(q ? _allSessions.filter(s => s.name.toLowerCase().includes(q)) : _allSessions);
  });

  // ─── Rendu du rail ─────────────────────────────────────────────────────────

  function _render(sessions) {
    const container = document.getElementById("sessions-list");

    if (!sessions.length) {
      container.innerHTML = '<p class="no-sessions">Aucune session — lancez une séparation pour commencer.</p>';
      return;
    }

    container.innerHTML = "";
    [...sessions].reverse().forEach(sess => {
      const chip = document.createElement("div");
      chip.className = "session-card";

      const dots = sess.stems.map(s => {
        const color = (App.STEM_META[s] || {}).color || "#fff";
        return `<span class="stem-dot" style="background:${color}" title="${s}"></span>`;
      }).join("");

      chip.innerHTML = `
        <div class="session-name">${sess.name}</div>
        <div class="session-meta">${sess.model} · ${sess.saved_at}</div>
        <div class="session-stems">${dots}</div>
        <button class="session-del-btn" title="Supprimer">✕</button>
      `;

      chip.addEventListener("click", e => {
        if (e.target.classList.contains("session-del-btn")) return;
        _loadIntoMixer(sess);
      });

      chip.querySelector(".session-del-btn").addEventListener("click", async e => {
        e.stopPropagation();
        if (!confirm(`Supprimer "${sess.name}" ?`)) return;
        await fetch(`/api/sessions/delete/${sess.session_id}`, { method: "DELETE" });
        load();
      });

      container.appendChild(chip);
    });
  }

  // ─── Chargement dans le mixer ──────────────────────────────────────────────

  /** Charge une session sauvegardée dans la zone mixer. */
  async function _loadIntoMixer(sess) {
    Mixer.stopAll();
    App.state.stems         = [];
    App.state.duration      = 0;
    App.state.startOffset   = 0;
    App.state.jobId         = sess.job_id;
    App.state.currentFileName = sess.name;

    // Cache la zone split si ouverte, réinitialise le mixer
    document.getElementById("zone-split").style.display  = "none";
    document.getElementById("zone-mixer").style.display  = "none";
    document.getElementById("master-bar").style.display  = "none";
    document.getElementById("tracks-grid").innerHTML     = "";
    document.getElementById("progress-section").style.display = "none";

    showToast(`Chargement de "${sess.name}"…`);
    document.getElementById("mixer-title").textContent = sess.name;
    document.getElementById("zone-mixer").style.display = "block";
    await Mixer.build(sess.stems);
    showToast(`✓ "${sess.name}" chargée !`, true);
  }

  // ─── Sauvegarde ────────────────────────────────────────────────────────────

  function openSaveModal() {
    if (!App.state.jobId) return;
    const input = document.getElementById("session-name-input");
    input.value = App.state.currentFileName
      ? App.state.currentFileName.replace(/\.mp3$/i, "")
      : "";
    document.getElementById("save-modal").classList.add("open");
    input.focus();
  }

  async function save() {
    const name = document.getElementById("session-name-input").value.trim() || "Sans titre";
    document.getElementById("save-modal").classList.remove("open");
    try {
      const data = await fetch("/api/sessions/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: App.state.jobId, name,
          model:  App.state.model,
          stems:  App.state.stems.map(s => s.name),
        }),
      }).then(r => r.json());
      if (data.error) throw new Error(data.error);
      showToast("✓ Session sauvegardée !", true);
      load();
    } catch (e) {
      showToast("Erreur : " + e.message);
    }
  }

  // ─── Listeners modales ─────────────────────────────────────────────────────

  document.getElementById("save-session-btn").addEventListener("click", openSaveModal);
  document.getElementById("modal-confirm").addEventListener("click", save);
  document.getElementById("modal-cancel").addEventListener("click", () => {
    document.getElementById("save-modal").classList.remove("open");
  });
  document.getElementById("save-modal").addEventListener("click", e => {
    if (e.target === document.getElementById("save-modal"))
      document.getElementById("save-modal").classList.remove("open");
  });
  document.getElementById("session-name-input").addEventListener("keydown", e => {
    if (e.key === "Enter") save();
  });

  return { load };

})();