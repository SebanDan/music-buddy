/**
 * sheets.js
 * ---------
 * Gère la génération et la visualisation des partitions musicales.
 *
 * Flow en 2 étapes :
 *   1. generate()    — lance Basic Pitch en arrière-plan, met à jour le bouton
 *   2. openViewer()  — ouvre la modale avec rendu SVG via Verovio
 *
 * Expose window.Sheets utilisé par mixer.js.
 */

window.Sheets = (() => {

  // ─── Verovio ───────────────────────────────────────────────────────────────

  let verovioReady = false;
  let vrvToolkit   = null;

  // Initialise le toolkit Verovio dès que le WASM est prêt
  window.addEventListener("load", () => {
    if (typeof verovio === "undefined") return;
    const init = () => {
      vrvToolkit   = new verovio.toolkit();
      verovioReady = true;
    };
    if (verovio.module.calledRun) {
      init();
    } else {
      verovio.module.onRuntimeInitialized = init;
    }
  });

  // ─── Labels de statut affichés dans le bouton ──────────────────────────────

  const STATUS_LABELS = {
    pending:      "⏳ En attente…",
    transcribing: "🎵 Transcription MIDI…",
    cleaning:     "🧹 Nettoyage…",
    rendering:    "🎼 Génération MusicXML…",
    done:         "✓ Terminé",
    error:        "✗ Erreur",
  };

  // ─── Étape 1 : génération ──────────────────────────────────────────────────

  /**
   * Lance la génération d'une partition pour un stem.
   * Si la partition existe déjà, affiche juste un toast et révèle le bouton œil.
   *
   * @param {string} jobId - Identifiant du job de séparation.
   * @param {string} stem  - Nom du stem (vocals, bass, etc.).
   */
  async function generate(jobId, stem) {
    const btn     = document.getElementById(`sheet-btn-${stem}`);
    const viewBtn = document.getElementById(`sheet-view-btn-${stem}`);

    // Vérifie si la partition a déjà été générée
    const exists = await fetch(`/api/sheet/file/${jobId}/${stem}`, { method: "HEAD" });
    if (exists.ok) {
      btn.textContent       = "🎼 Regénérer";
      viewBtn.style.display = "flex";
      showToast("Partition déjà disponible — cliquez sur 👁 pour la voir.", true);
      return;
    }

    _setButtonLoading(btn, viewBtn, true);

    try {
      const res  = await fetch("/api/sheet/generate", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ job_id: jobId, stem }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      // Polling silencieux : les étapes s'affichent dans le label du bouton
      await _pollGeneration(data.sheet_job_id, stem, viewBtn);

    } catch (e) {
      showToast("Erreur partition : " + e.message);
      _setButtonLoading(btn, viewBtn, false);
    }
  }

  /** Polling du statut de génération — met à jour le label du bouton. */
  async function _pollGeneration(sheetJobId, stem, viewBtn) {
    const btn = document.getElementById(`sheet-btn-${stem}`);

    return new Promise(resolve => {
      const iv = setInterval(async () => {
        try {
          const res  = await fetch(`/api/sheet/status/${sheetJobId}`);
          const data = await res.json();

          if (!["done","error"].includes(data.status)) {
            btn.textContent = STATUS_LABELS[data.status] || "⏳…";
          }

          if (data.status === "done") {
            clearInterval(iv);
            btn.disabled      = false;
            btn.classList.remove("loading");
            btn.textContent   = "🎼 Regénérer";
            viewBtn.style.display = "flex";
            showToast(`✓ Partition "${stem}" prête — cliquez sur 👁 pour la voir.`, true);
            resolve();

          } else if (data.status === "error") {
            clearInterval(iv);
            _setButtonLoading(btn, viewBtn, false, true);
            showToast("Erreur génération : " + (data.error || "inconnue"));
            resolve();
          }
        } catch {
          clearInterval(iv);
          _setButtonLoading(btn, viewBtn, false, true);
          resolve();
        }
      }, 2000);
    });
  }

  function _setButtonLoading(btn, viewBtn, loading, error = false) {
    btn.disabled = loading;
    btn.classList.toggle("loading", loading);
    if (!loading) {
      btn.textContent       = error ? "🎼 Générer" : "🎼 Regénérer";
      viewBtn.style.display = error ? "none" : "flex";
    } else {
      btn.textContent = "⏳…";
    }
  }

  // ─── Étape 2 : visualisation ───────────────────────────────────────────────

  /**
   * Ouvre la modale de partition et rend le MusicXML via Verovio.
   *
   * @param {string} jobId - Identifiant du job de séparation.
   * @param {string} stem  - Nom du stem à afficher.
   */
  async function openViewer(jobId, stem) {
    const modal     = document.getElementById("sheet-modal");
    const container = document.getElementById("sheet-svg-container");
    const statusEl  = document.getElementById("sheet-status-msg");
    const dlLink    = document.getElementById("sheet-dl-link");

    // Initialise la modale
    document.getElementById("sheet-modal-stem-label").textContent = stem.toUpperCase();
    dlLink.style.display    = "none";
    container.innerHTML     = "";
    statusEl.textContent    = "⏳ Chargement…";
    statusEl.style.display  = "block";
    modal.classList.add("open");

    try {
      const res = await fetch(`/api/sheet/file/${jobId}/${stem}`);
      if (!res.ok) throw new Error("Fichier partition introuvable");
      const xml = await res.text();

      statusEl.style.display = "none";
      dlLink.href     = `/api/sheet/file/${jobId}/${stem}`;
      dlLink.download = `${stem}.musicxml`;
      dlLink.style.display = "inline-block";
      _renderVerovio(xml, container);

    } catch (e) {
      statusEl.textContent = "✗ " + e.message;
    }
  }

  /**
   * Rend un MusicXML en SVG via Verovio et l'injecte dans le container.
   * Affiche un fallback si Verovio n'est pas encore chargé.
   */
  function _renderVerovio(xmlText, container) {
    container.innerHTML = "";

    if (!verovioReady || !vrvToolkit) {
      container.innerHTML = `
        <div class="verovio-fallback">
          Verovio non chargé — téléchargez le MusicXML et ouvrez-le dans MuseScore.
        </div>`;
      return;
    }

    try {
      vrvToolkit.setOptions({
        pageWidth:        1400,
        pageHeight:       2400,
        scale:            45,
        adjustPageHeight: true,
        breaks:           "auto",
      });
      vrvToolkit.loadData(xmlText);

      const pageCount = vrvToolkit.getPageCount();
      for (let i = 1; i <= pageCount; i++) {
        const div = document.createElement("div");
        div.className = "sheet-page";
        div.innerHTML = vrvToolkit.renderToSVG(i);
        container.appendChild(div);
      }
    } catch (e) {
      container.innerHTML = `<div class="verovio-error">Erreur Verovio : ${e.message}</div>`;
    }
  }

  // ─── Listeners modale ─────────────────────────────────────────────────────

  document.getElementById("sheet-modal-close").addEventListener("click", () => {
    document.getElementById("sheet-modal").classList.remove("open");
  });

  document.getElementById("sheet-modal").addEventListener("click", e => {
    if (e.target === document.getElementById("sheet-modal"))
      document.getElementById("sheet-modal").classList.remove("open");
  });

  // ─── API publique ─────────────────────────────────────────────────────────
  return { generate, openViewer };

})();