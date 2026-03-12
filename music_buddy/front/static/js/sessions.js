/**
 * sessions.js
 * -----------
 * Gère les sessions sauvegardées : liste, sauvegarde, suppression, rechargement.
 *
 * Expose window.Sessions utilisé par app.js.
 */

window.Sessions = (() => {

  // ─── Chargement de la liste ────────────────────────────────────────────────

  /** Charge et affiche la liste des sessions depuis l'API. */
  async function load() {
    try {
      const res  = await fetch("/api/sessions");
      const list = await res.json();
      _render(list);
    } catch {
      document.getElementById("sessions-list").innerHTML =
        '<p class="no-sessions">Impossible de charger les sessions.</p>';
    }
  }

  /** Génère le HTML de la liste de sessions. */
  function _render(sessions) {
    const container = document.getElementById("sessions-list");

    if (!sessions.length) {
      container.innerHTML =
        '<p class="no-sessions">Aucune session — séparez une musique pour commencer.</p>';
      return;
    }

    container.innerHTML = "";
    // Plus récente en premier
    [...sessions].reverse().forEach(sess => {
      const card = document.createElement("div");
      card.className = "session-card";
      card.innerHTML = `
        <div class="session-icon">🎛️</div>
        <div class="session-info">
          <div class="session-name">${sess.name}</div>
          <div class="session-meta">${sess.model} · ${sess.saved_at}</div>
          <div class="session-stems">
            ${sess.stems.map(s => {
              const color = (App.STEM_META[s] || {}).color || "#fff";
              return `<span class="stem-pill" style="border-color:${color};color:${color}">${s}</span>`;
            }).join("")}
          </div>
        </div>
        <button class="session-del-btn" title="Supprimer" data-id="${sess.session_id}">✕</button>
      `;

      // Clic sur la carte → charger la session dans le mixer
      card.addEventListener("click", e => {
        if (e.target.classList.contains("session-del-btn")) return;
        _loadIntoMixer(sess);
      });

      // Bouton supprimer
      card.querySelector(".session-del-btn").addEventListener("click", async e => {
        e.stopPropagation();
        if (!confirm(`Supprimer la session "${sess.name}" ?\n(Les fichiers WAV seront conservés)`)) return;
        await fetch(`/api/sessions/delete/${sess.session_id}`, { method: "DELETE" });
        load(); // Rafraîchit la liste
      });

      container.appendChild(card);
    });
  }

  /** Charge une session sauvegardée directement dans le mixer. */
  async function _loadIntoMixer(sess) {
    Mixer.stopAll();
    App.state.stems       = [];
    App.state.duration    = 0;
    App.state.startOffset = 0;
    App.state.jobId       = sess.job_id;

    document.getElementById("progress-section").style.display = "none";
    document.getElementById("mixer-section").style.display    = "none";
    document.getElementById("master-bar").style.display       = "none";
    document.getElementById("tracks-grid").innerHTML           = "";

    showToast(`Chargement de "${sess.name}"…`, false);
    await Mixer.build(sess.stems);
    showToast(`✓ Session "${sess.name}" chargée !`, true);
  }

  // ─── Sauvegarde ───────────────────────────────────────────────────────────

  /** Ouvre la modale de sauvegarde. */
  function openSaveModal() {
    if (!App.state.jobId) return;
    const input = document.getElementById("session-name-input");
    // Pré-remplir avec le nom du fichier sans extension
    input.value = App.state.currentFileName
      ? App.state.currentFileName.replace(/\.mp3$/i, "")
      : "";
    document.getElementById("save-modal").classList.add("open");
    input.focus();
  }

  /** Sauvegarde la session courante via l'API. */
  async function save() {
    const name = document.getElementById("session-name-input").value.trim() || "Sans titre";
    document.getElementById("save-modal").classList.remove("open");

    try {
      const res  = await fetch("/api/sessions/save", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: App.state.jobId,
          name,
          model: App.state.model,
          stems: App.state.stems.map(s => s.name),
        }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      showToast("✓ Session sauvegardée !", true);
      load(); // Rafraîchit la liste
    } catch (e) {
      showToast("Erreur : " + e.message);
    }
  }

  // ─── Listeners modales ────────────────────────────────────────────────────

  document.getElementById("save-session-btn").addEventListener("click", openSaveModal);

  document.getElementById("modal-confirm").addEventListener("click", save);

  document.getElementById("modal-cancel").addEventListener("click", () => {
    document.getElementById("save-modal").classList.remove("open");
  });

  // Fermer en cliquant en dehors
  document.getElementById("save-modal").addEventListener("click", e => {
    if (e.target === document.getElementById("save-modal"))
      document.getElementById("save-modal").classList.remove("open");
  });

  // Valider avec Entrée
  document.getElementById("session-name-input").addEventListener("keydown", e => {
    if (e.key === "Enter") save();
  });

  // ─── API publique ─────────────────────────────────────────────────────────
  return { load };

})();