# 🎵 Music Buddy

[![Python versions](https://img.shields.io/badge/python-3.11-blue)](https://docs.python.org/3/whatsnew/)
[![Code style: Black](https://img.shields.io/badge/code%20style-Black-000000.svg)](https://github.com/psf/black)
[![security: bandit](https://img.shields.io/badge/security-bandit-purple.svg)](https://github.com/PyCQA/bandit)
[![CI](https://github.com/SebanDan/music-buddy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SebanDan/music-buddy/actions/workflows/ci.yml)
[![Release](https://github.com/SebanDan/music-buddy/actions/workflows/tag-release.yml/badge.svg?branch=main)](https://github.com/SebanDan/music-buddy/actions/workflows/tag-release.yml)
[![Publish Docker image](https://img.shields.io/github/actions/workflow/status/SebanDan/music-buddy/deploy-docker.yml?label=Docker%20Release)](https://github.com/SebanDan/music-buddy/actions/workflows/deploy-docker.yml)

Python webapp for separating audio tracks with [Demucs](https://github.com/facebookresearch/demucs).

---

## Installation

### Option A — Local launch with uv

```bash
# 1. Clone the project
git clone https://github.com/SebanDan/music-buddy.git
cd music-buddy

# 2. Start the server
uv run python music_buddy/app.py
```

Then open http://localhost:5000 in your browser.

---

### Option B — Docker

#### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- At least **10 GB of free disk space** (torch + Demucs models are large)

#### Build

```bash
docker build -t music-buddy .
```

#### Run

```bash
docker run -p 5000:8000 music-buddy
```

Then open http://localhost:5000 in your browser.

#### With session persistence

By default, separated audio files and sessions are lost when the container stops. To keep them:

```bash
docker run -p 5000:8000 music-buddy
```

---

## Usage

1. **Sessions** — your previous separations appear at the top, click to reload them in the mixer
2. **New separation** — click "+ New separation" then:
   - Paste a **YouTube URL** or drag a **MP3 file**
   - Choose a **model**:
     - `htdemucs` — 4 tracks: vocals, drums, bass, other (fast)
     - `htdemucs_6s` — 6 tracks: + guitar and piano
     - `mdx_extra` — 4 tracks, better quality, slower
   - Click **Separate tracks** and wait (1–5 minutes)
3. **Mixer**:
   - **M** button to mute/unmute a track
   - **VOLUME** slider to adjust the level
   - **EQ** sliders (Bass / Mid / Treble) to shape the sound
   - **▶** button at the bottom for synchronized playback
   - Download each track as WAV
   - Generate a **MusicXML score** for melodic tracks

---

## Project structure

```
music_buddy/
├── app.py                        ← Flask entry point
├── api/
│   ├── routes/               ← Flask blueprints (audio, sessions, sheets)
│   ├── services/             ← business logic (demucs, youtube, sheet_music)
│   └── models/               ← Job, SheetJob dataclasses
└── front/
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/               ← app.js, mixer.js, sessions.js, sheets.js
│   └── templates/
│       └── index.html
└── database/                     ← created automatically
    ├── uploads/                  ← temporary MP3s (deleted after processing)
    ├── separated/                ← separated WAV + MIDI + MusicXML
    └── sessions/
        └── sessions.json
```
