# 🎵 Music Buddy

[![Python versions](https://img.shields.io/badge/python-3.11-blue)](https://docs.python.org/3/whatsnew/) [![Code style: Black](https://img.shields.io/badge/code%20style-Black-000000.svg)](https://github.com/psf/black) [![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

[![ci](https://github.com/SebanDan/music-buddy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SebanDan/music-buddy/actions/workflows/ci.yml)[![Release](https://github.com/SebanDan/music-buddy/actions/workflows/tag-release.yml/badge.svg?branch=main)](https://github.com/SebanDan/music-buddy/actions/workflows/tag-release.yml)[![Publish Docker image](https://github.com/SebanDan/music-buddy/actions/workflows/deploy-docker.yml/badge.svg)](https://github.com/SebanDan/music-buddy/actions/workflows/deploy-docker.yml)

Webapp Python pour séparer les pistes audio avec [Demucs](https://github.com/facebookresearch/demucs).

## Installation

```bash
uv sync
uv run python app.py
```

Puis ouvrir http://localhost:5000 dans votre navigateur.

## Utilisation

1. **Glissez un MP3** dans la zone de dépôt
2. **Choisissez un modèle** selon les instruments souhaités :
   - `htdemucs` — 4 pistes : voix, batterie, basse, autre (rapide)
   - `htdemucs_6s` — 6 pistes : + guitare et piano
   - `mdx_extra` — 4 pistes, meilleure qualité, plus lent
3. Cliquez sur **Séparer les pistes** et attendez (quelques minutes)
4. Dans le **mixer** :
   - Bouton **M** pour muter/unmuter une piste
   - Slider **VOLUME** pour ajuster le niveau
   - Sliders **EQ** (Bass / Mid / Treble) pour colorer le son
   - Bouton **play** en bas pour lancer la lecture synchronisée
   - Téléchargez chaque piste en WAV

## Structure des fichiers

## Notes

- La séparation prend 1–5 minutes selon le modèle et votre CPU/GPU.
- Si vous avez un GPU NVIDIA, Demucs l'utilisera automatiquement.
- Les fichiers WAV générés sont en 44.1kHz stéréo.
