# 🎵 Music Buddy

[![Python versions](https://img.shields.io/badge/python-3.11-blue)](https://docs.python.org/3/whatsnew/) [![Code style: Black](https://img.shields.io/badge/code%20style-Black-000000.svg)](https://github.com/psf/black) [![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit) [![ci](https://github.com/SebanDan/music-buddy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SebanDan/music-buddy/actions/workflows/ci.yml)[![Release](https://github.com/SebanDan/music-buddy/actions/workflows/tag-release.yml/badge.svg?branch=main)](https://github.com/SebanDan/music-buddy/actions/workflows/tag-release.yml)[![Publish Docker image](https://github.com/SebanDan/music-buddy/actions/workflows/deploy-docker.yml/badge.svg)](https://github.com/SebanDan/music-buddy/actions/workflows/deploy-docker.yml)

Webapp Python pour séparer les pistes audio avec [Demucs](https://github.com/facebookresearch/demucs).

---

## Installation

### Option A — Lancement local avec uv

```bash
# 1. Cloner le projet
git clone https://github.com/SebanDan/music-buddy.git
cd music-to-partoch

# 2. Lancer le serveur
uv run python music_buddy/app.py
```

Puis ouvrir http://localhost:5000 dans votre navigateur.

---

### Option B — Docker

#### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé
- Au moins **10 Go d'espace disque libre** (torch + modèles Demucs sont volumineux)

#### Build

```bash
docker build -t music-buddy .
```

#### Lancement

```bash
docker run -p 5000:8000 music-buddy
```

Puis ouvrir http://localhost:5000 dans votre navigateur.

#### Avec persistance des sessions

Par défaut, les fichiers audio séparés et les sessions sont perdus à l'arrêt du container. Pour les conserver :

```bash
docker run -p 5000:8000 music-buddy
```

---

## Utilisation

1. **Sessions** — vos séparations précédentes s'affichent en haut, cliquez pour les recharger dans le mixer
2. **Nouvelle séparation** — cliquez sur "+ Nouvelle séparation" puis :
   - Collez une **URL YouTube** ou glissez un **fichier MP3**
   - Choisissez un **modèle** :
     - `htdemucs` — 4 pistes : voix, batterie, basse, autre (rapide)
     - `htdemucs_6s` — 6 pistes : + guitare et piano
     - `mdx_extra` — 4 pistes, meilleure qualité, plus lent
   - Cliquez sur **Séparer les pistes** et attendez (1–5 minutes)
3. **Mixer** :
   - Bouton **M** pour muter/unmuter une piste
   - Slider **VOLUME** pour ajuster le niveau
   - Sliders **EQ** (Bass / Mid / Treble) pour colorer le son
   - Bouton **▶** en bas pour la lecture synchronisée
   - Téléchargez chaque piste en WAV
   - Générez une **partition MusicXML** pour les pistes mélodiques

---

## Structure du projet

```
music_buddy/
├── app.py                        ← point d'entrée Flask
├── api/
│   ├── routes/               ← blueprints Flask (audio, sessions, sheets)
│   ├── services/             ← logique métier (demucs, youtube, sheet_music)
│   └── models/               ← dataclasses Job, SheetJob
└── front/
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/               ← app.js, mixer.js, sessions.js, sheets.js
│   └── templates/
│       └── index.html
└── database/                     ← créé automatiquement
    ├── uploads/                  ← MP3 temporaires (supprimés après traitement)
    ├── separated/                ← WAV séparés + MIDI + MusicXML
    └── sessions/
        └── sessions.json
```
