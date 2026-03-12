/**
 * app.js — module principal
 * Gère : état global, zones UI, source tabs, modèles, split, polling, toasts.
 */

// ─── État global ──────────────────────────────────────────────────────────────
window.App = {
  state: {
    file:            null,
    currentFileName: null,
    model:           "htdemucs",
    jobId:           null,
    isPlaying:       false,
    startOffset:     0,
    startTime:       0,
    duration:        0,
    stems:           [],
  },
  STEM_META: {
    vocals: { icon: "🎤", color: "var(--col-vocals)" },
    drums:  { icon: "🥁", color: "var(--col-drums)"  },
    bass:   { icon: "🎸", color: "var(--col-bass)"   },
    other:  { icon: "🎹", color: "var(--col-other)"  },
    guitar: { icon: "🎸", color: "var(--col-guitar)" },
    piano:  { icon: "🎹", color: "var(--col-piano)"  },
  },
};

// ─── Zones UI ─────────────────────────────────────────────────────────────────

/** Affiche la zone de séparation (cachée par défaut). */
function showSplitZone() {
  document.getElementById("zone-split").style.display = "block";
  document.getElementById("zone-split").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/** Cache la zone de séparation. */
function hideSplitZone() {
  document.getElementById("zone-split").style.display = "none";
}

/** Affiche la zone mixer avec un titre optionnel. */
function showMixerZone(title) {
  const zone = document.getElementById("zone-mixer");
  zone.style.display = "block";
  if (title) document.getElementById("mixer-title").textContent = title;
}

document.getElementById("btn-show-split").addEventListener("click", showSplitZone);
document.getElementById("btn-hide-split").addEventListener("click", hideSplitZone);

// ─── Source tabs ──────────────────────────────────────────────────────────────

let activeSource = "youtube"; // YouTube par défaut

document.querySelectorAll(".source-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    activeSource = tab.dataset.tab;
    document.querySelectorAll(".source-tab").forEach(t =>
      t.classList.toggle("active", t === tab)
    );
    document.querySelectorAll(".source-panel").forEach(p =>
      p.classList.toggle("active", p.id === "panel-" + activeSource)
    );
    updateSplitBtn();
  });
});

document.getElementById("yt-url").addEventListener("input", updateSplitBtn);

function updateSplitBtn() {
  const btn = document.getElementById("split-btn");
  btn.disabled = activeSource === "mp3"
    ? !App.state.file
    : !document.getElementById("yt-url").value.trim();
}

// ─── Modèles ──────────────────────────────────────────────────────────────────

async function loadModels() {
  const res  = await fetch("/api/models");
  const data = await res.json();
  const grid = document.getElementById("model-grid");

  Object.entries(data).forEach(([key, model]) => {
    const card = document.createElement("label");
    card.className = "model-card" + (key === App.state.model ? " active" : "");
    card.innerHTML = `
      <input type="radio" name="model" value="${key}" ${key === App.state.model ? "checked" : ""} />
      <div class="model-name">${model.label}</div>
      <div class="model-stems">
        ${model.stems.map(s => {
          const color = (App.STEM_META[s] || {}).color || "#fff";
          return `<span class="stem-pill" style="border-color:${color};color:${color}">${s}</span>`;
        }).join("")}
      </div>
    `;
    card.querySelector("input").addEventListener("change", () => {
      document.querySelectorAll(".model-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      App.state.model = key;
    });
    grid.appendChild(card);
  });
}

// ─── Drag & Drop / fichier ────────────────────────────────────────────────────

const dropZone  = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const fileLabel = document.getElementById("file-name");

dropZone.addEventListener("dragover",  e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", ()  => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", e => { if (e.target.files[0]) setFile(e.target.files[0]); });

function setFile(f) {
  if (!f.name.toLowerCase().endsWith(".mp3")) { showToast("Seuls les MP3 sont acceptés !"); return; }
  App.state.file = f;
  App.state.currentFileName = f.name;
  fileLabel.textContent   = "📂 " + f.name;
  fileLabel.style.display = "block";
  updateSplitBtn();
}

// ─── Lancement séparation ─────────────────────────────────────────────────────

document.getElementById("split-btn").addEventListener("click", startSplit);

async function startSplit() {
  document.getElementById("split-btn").disabled = true;

  // Réinitialise les pistes si besoin
  Mixer.stopAll();
  App.state.stems = [];
  App.state.duration = 0;
  App.state.startOffset = 0;
  document.getElementById("zone-mixer").style.display = "none";
  document.getElementById("master-bar").style.display = "none";
  document.getElementById("tracks-grid").innerHTML    = "";

  activeSource === "youtube" ? await _startYoutube() : await _startUpload();
}

async function _startUpload() {
  if (!App.state.file) return;
  const form = new FormData();
  form.append("file",  App.state.file);
  form.append("model", App.state.model);
  showProgress(5, "Upload en cours…");
  try {
    const data = await fetch("/api/upload", { method: "POST", body: form }).then(r => r.json());
    if (data.error) throw new Error(data.error);
    App.state.jobId = data.job_id;
    _pollStatus();
  } catch (e) {
    showToast(e.message);
    document.getElementById("split-btn").disabled = false;
    hideProgress();
  }
}

async function _startYoutube() {
  const url = document.getElementById("yt-url").value.trim();
  if (!url) return;
  showProgress(5, "Envoi…");
  try {
    const data = await fetch("/api/youtube", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, model: App.state.model }),
    }).then(r => r.json());
    if (data.error) throw new Error(data.error);
    App.state.jobId = data.job_id;
    App.state.currentFileName = url;
    _pollStatus();
  } catch (e) {
    showToast(e.message);
    document.getElementById("split-btn").disabled = false;
    hideProgress();
  }
}

function _pollStatus() {
  const iv = setInterval(async () => {
    try {
      const data = await fetch(`/api/status/${App.state.jobId}`).then(r => r.json());

      if (data.status === "downloading") {
        showProgress(data.progress || 10, "⬇ Téléchargement YouTube…");
      } else if (data.status === "processing" || data.status === "pending") {
        showProgress(data.progress, "Séparation en cours… (peut prendre quelques minutes)");
        if (data.filename && App.state.currentFileName?.startsWith("http"))
          App.state.currentFileName = data.filename;
      } else if (data.status === "done") {
        clearInterval(iv);
        if (data.filename) App.state.currentFileName = data.filename;
        showProgress(100, "Terminé !");
        setTimeout(() => {
          hideProgress();
          hideSplitZone();
          showMixerZone(App.state.currentFileName || "Pistes");
          Mixer.build(data.stems);
          document.getElementById("split-btn").disabled = false;
          updateSplitBtn();
        }, 600);
      } else if (data.status === "error") {
        clearInterval(iv);
        hideProgress();
        showToast("Erreur : " + data.error);
        document.getElementById("split-btn").disabled = false;
        updateSplitBtn();
      }
    } catch { clearInterval(iv); showToast("Erreur réseau"); }
  }, 1500);
}

// ─── Progression ──────────────────────────────────────────────────────────────

function showProgress(pct, label) {
  document.getElementById("progress-section").style.display = "block";
  document.getElementById("progress-fill").style.width      = pct + "%";
  document.getElementById("progress-label").textContent     = label;
}
function hideProgress() {
  document.getElementById("progress-section").style.display = "none";
}

// ─── Réinitialisation ─────────────────────────────────────────────────────────

document.getElementById("new-music-btn").addEventListener("click", () => {
  Mixer.stopAll();
  Object.assign(App.state, {
    file: null, currentFileName: null, jobId: null,
    stems: [], duration: 0, startOffset: 0, isPlaying: false,
  });
  document.getElementById("zone-mixer").style.display   = "none";
  document.getElementById("zone-split").style.display   = "none";
  document.getElementById("master-bar").style.display   = "none";
  document.getElementById("progress-section").style.display = "none";
  document.getElementById("tracks-grid").innerHTML      = "";
  document.getElementById("file-name").style.display    = "none";
  document.getElementById("file-input").value           = "";
  document.getElementById("yt-url").value               = "";
  document.getElementById("split-btn").disabled         = true;
  document.getElementById("seek-slider").value          = 0;
  document.getElementById("time-current").textContent   = "0:00";
  document.getElementById("time-total").textContent     = "0:00";
  document.getElementById("master-play").textContent    = "▶";
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ─── Toast ────────────────────────────────────────────────────────────────────

function showToast(msg, success = false) {
  const t = document.getElementById("toast");
  t.textContent   = msg;
  t.className     = success ? "success" : "";
  t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 3500);
}
window.showToast = showToast;

// ─── Init ─────────────────────────────────────────────────────────────────────

loadModels();
Sessions.load();