/**
 * mixer.js
 * --------
 * Gère le mixer audio : Web Audio API, pistes, EQ, mute/volume,
 * lecture synchronisée et barre de seek.
 *
 * Expose window.Mixer utilisé par app.js et sessions.js.
 */

window.Mixer = (() => {

  // ─── Web Audio ─────────────────────────────────────────────────────────────
  const audioCtx   = new (window.AudioContext || window.webkitAudioContext)();
  const masterGain = audioCtx.createGain();
  masterGain.connect(audioCtx.destination);

  // ─── Construction du mixer ─────────────────────────────────────────────────

  /**
   * Construit les cartes de pistes et initialise le graph audio.
   * Appelé après une séparation réussie ou au chargement d'une session.
   *
   * @param {string[]} stemNames - Liste des noms de stems à afficher.
   */
  async function build(stemNames) {
    const grid = document.getElementById("tracks-grid");
    grid.innerHTML = "";
    App.state.stems      = [];
    App.state.isPlaying  = false;
    App.state.startOffset = 0;
    App.state.duration   = 0;

    for (const name of stemNames) {
      const meta     = App.STEM_META[name] || { icon: "🎵", color: "#ffffff" };
      const gainNode = audioCtx.createGain();
      const eq       = _createEQChain(gainNode);

      const stem = { name, meta, gainNode, eq, buffer: null, source: null, muted: false, volume: 1 };
      App.state.stems.push(stem);

      // Chargement audio en arrière-plan (n'attend pas)
      _loadAudio(stem);

      // Rendu de la carte HTML
      const card = _buildCard(name, meta);
      grid.appendChild(card);
      _attachCardListeners(card, stem, name);
    }

    document.getElementById("mixer-section").style.display = "block";
    document.getElementById("master-bar").style.display    = "flex";

    // Remplace les boutons "tout muter / tout activer" pour éviter
    // l'accumulation de listeners sur les rechargements de session
    _rebindGlobalButtons();
  }

  /** Crée la chaîne EQ : gainNode → bass → mid → treble → masterGain */
  function _createEQChain(gainNode) {
    const eq = {
      bass:   _createFilter("lowshelf",  200),
      mid:    _createFilter("peaking",  1000),
      treble: _createFilter("highshelf", 4000),
    };
    gainNode.connect(eq.bass);
    eq.bass.connect(eq.mid);
    eq.mid.connect(eq.treble);
    eq.treble.connect(masterGain);
    return eq;
  }

  function _createFilter(type, freq) {
    const f = audioCtx.createBiquadFilter();
    f.type            = type;
    f.frequency.value = freq;
    f.gain.value      = 0;
    return f;
  }

  /** Télécharge et décode le WAV d'un stem, met à jour la durée globale. */
  function _loadAudio(stem) {
    fetch(`/audio/${App.state.jobId}/${stem.name}`)
      .then(r => r.arrayBuffer())
      .then(ab => audioCtx.decodeAudioData(ab))
      .then(buf => {
        stem.buffer = buf;
        App.state.duration = Math.max(App.state.duration, buf.duration);
        _updateTimeDisplay();
        document.getElementById("card-" + stem.name)?.classList.add("ready");
      })
      .catch(err => console.warn(`Impossible de charger ${stem.name}:`, err));
  }

  /** Génère le HTML d'une carte de piste. */
  function _buildCard(name, meta) {
    const isDrums = name === "drums";
    const card    = document.createElement("div");
    card.className = "track-card";
    card.id        = "card-" + name;
    card.style.setProperty("--stem-color", meta.color);
    card.innerHTML = `
      <div class="track-header">
        <div>
          <div class="track-icon">${meta.icon}</div>
          <div class="track-name">${name}</div>
        </div>
        <button class="mute-btn" id="mute-${name}" title="Mute/Unmute">M</button>
      </div>

      <div class="volume-wrap">
        <div class="volume-label">
          <span>VOLUME</span>
          <span class="volume-val" id="vol-val-${name}">100%</span>
        </div>
        <input type="range" id="vol-${name}" min="0" max="1" step="0.01" value="1" />
      </div>

      <div class="eq-wrap">
        <div class="volume-label"><span>EQ</span></div>
        ${["bass","mid","treble"].map(band => `
        <div class="eq-row">
          <span class="eq-lbl">${band.toUpperCase()}</span>
          <input type="range" id="eq-${band}-${name}" min="-12" max="12" step="0.5" value="0" />
          <span class="eq-val" id="eq-${band}-val-${name}">0dB</span>
        </div>`).join("")}
      </div>

      <a class="download-btn" href="/audio/${App.state.jobId}/${name}" download="${name}.wav">
        ↓ Télécharger ${name}.wav
      </a>

      ${isDrums
        ? `<div class="no-sheet-label">Partition non disponible (drums)</div>`
        : `<div class="sheet-actions" id="sheet-actions-${name}">
             <button class="sheet-btn" id="sheet-btn-${name}">🎼 Générer</button>
             <button class="sheet-view-btn" id="sheet-view-btn-${name}" style="display:none" title="Visualiser la partition">👁</button>
           </div>`
      }
    `;
    return card;
  }

  /** Attache tous les listeners d'une carte (mute, volume, EQ, partition). */
  function _attachCardListeners(card, stem, name) {
    // Mute
    card.querySelector(`#mute-${name}`).addEventListener("click", () => toggleMute(name));

    // Volume
    card.querySelector(`#vol-${name}`).addEventListener("input", e => {
      const v = parseFloat(e.target.value);
      stem.volume = v;
      if (!stem.muted) stem.gainNode.gain.value = v;
      document.getElementById(`vol-val-${name}`).textContent = Math.round(v * 100) + "%";
    });

    // EQ
    ["bass","mid","treble"].forEach(band => {
      card.querySelector(`#eq-${band}-${name}`).addEventListener("input", e => {
        const db = parseFloat(e.target.value);
        stem.eq[band].gain.value = db;
        document.getElementById(`eq-${band}-val-${name}`).textContent =
          (db >= 0 ? "+" : "") + db + "dB";
      });
    });

    // Partition (sauf drums)
    if (name !== "drums") {
      card.querySelector(`#sheet-btn-${name}`)
        .addEventListener("click", () => Sheets.generate(App.state.jobId, name));
      card.querySelector(`#sheet-view-btn-${name}`)
        .addEventListener("click", () => Sheets.openViewer(App.state.jobId, name));

      // Affiche le bouton œil si la partition existe déjà (session rechargée)
      fetch(`/api/sheet/file/${App.state.jobId}/${name}`, { method: "HEAD" }).then(r => {
        if (r.ok) {
          document.getElementById(`sheet-view-btn-${name}`).style.display = "flex";
          document.getElementById(`sheet-btn-${name}`).textContent = "🎼 Regénérer";
        }
      });
    }
  }

  /** Rebranche les boutons globaux "tout muter / tout activer" sans doublon. */
  function _rebindGlobalButtons() {
    ["btn-mute-all","btn-solo-all"].forEach(id => {
      const old = document.getElementById(id);
      const neo = old.cloneNode(true);
      old.replaceWith(neo);
    });
    document.getElementById("btn-mute-all").addEventListener("click", () =>
      App.state.stems.forEach(s => { if (!s.muted) toggleMute(s.name); })
    );
    document.getElementById("btn-solo-all").addEventListener("click", () =>
      App.state.stems.forEach(s => { if (s.muted) toggleMute(s.name); })
    );
  }

  // ─── Mute ──────────────────────────────────────────────────────────────────

  function toggleMute(name) {
    const stem = App.state.stems.find(s => s.name === name);
    if (!stem) return;
    stem.muted = !stem.muted;
    stem.gainNode.gain.value = stem.muted ? 0 : stem.volume;
    document.getElementById("card-"  + name).classList.toggle("muted",    stem.muted);
    document.getElementById("mute-"  + name).classList.toggle("is-muted", stem.muted);
  }

  // ─── Playback ──────────────────────────────────────────────────────────────

  function togglePlay() {
    if (audioCtx.state === "suspended") audioCtx.resume();
    App.state.isPlaying ? _pauseAll() : _playAll();
  }

  function _playAll() {
    const offset = App.state.startOffset;
    App.state.startTime = audioCtx.currentTime;

    App.state.stems.forEach(stem => {
      if (!stem.buffer) return;
      try { stem.source?.stop(); } catch (_) {}

      const src = audioCtx.createBufferSource();
      src.buffer = stem.buffer;
      src.connect(stem.gainNode);
      src.start(0, offset);
      src.onended = () => {
        if (App.state.isPlaying) {
          App.state.isPlaying  = false;
          App.state.startOffset = 0;
          document.getElementById("master-play").textContent = "▶";
          _updateSeek();
        }
      };
      stem.source = src;
    });

    App.state.isPlaying = true;
    document.getElementById("master-play").textContent = "⏸";
    requestAnimationFrame(_seekLoop);
  }

  function _pauseAll() {
    App.state.startOffset = Math.min(
      audioCtx.currentTime - App.state.startTime + App.state.startOffset,
      App.state.duration
    );
    App.state.stems.forEach(stem => {
      try { stem.source?.stop(); } catch (_) {}
      stem.source = null;
    });
    App.state.isPlaying = false;
    document.getElementById("master-play").textContent = "▶";
  }

  function stopAll() {
    App.state.stems.forEach(stem => {
      try { stem.source?.stop(); } catch (_) {}
      stem.source = null;
    });
    App.state.isPlaying  = false;
    App.state.startOffset = 0;
  }

  // ─── Seek ──────────────────────────────────────────────────────────────────

  document.getElementById("seek-slider").addEventListener("input", e => {
    const pct = parseFloat(e.target.value) / 100;
    App.state.startOffset = pct * App.state.duration;
    if (App.state.isPlaying) { _pauseAll(); _playAll(); }
    _updateTimeDisplay();
  });

  function _seekLoop() {
    if (!App.state.isPlaying) return;
    _updateSeek();
    requestAnimationFrame(_seekLoop);
  }

  function _updateSeek() {
    const elapsed = App.state.isPlaying
      ? audioCtx.currentTime - App.state.startTime + App.state.startOffset
      : App.state.startOffset;
    const pct = App.state.duration ? (elapsed / App.state.duration) * 100 : 0;
    document.getElementById("seek-slider").value              = Math.min(pct, 100);
    document.getElementById("time-current").textContent       = _fmt(elapsed);
  }

  function _updateTimeDisplay() {
    document.getElementById("time-total").textContent = _fmt(App.state.duration);
  }

  function _fmt(s) {
    if (!s || isNaN(s)) return "0:00";
    return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  }

  // ─── Listeners globaux ─────────────────────────────────────────────────────

  document.getElementById("master-play").addEventListener("click", togglePlay);

  document.getElementById("master-vol").addEventListener("input", e => {
    masterGain.gain.value = parseFloat(e.target.value);
  });

  // ─── API publique ──────────────────────────────────────────────────────────
  return { build, stopAll, toggleMute };

})();