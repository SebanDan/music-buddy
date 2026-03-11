# 🎵 Music Buddy

Webapp Python pour séparer les pistes audio avec [Demucs](https://github.com/facebookresearch/demucs).

## Installation

```bash
# 1. Cloner / copier les fichiers dans un dossier
cd demucs-studio

# 2. Installer les dépendances
pip install flask demucs

# 3. Lancer le serveur
python app.py
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

```
demucs-studio/
├── app.py              ← serveur Flask (backend)
├── requirements.txt    ← dépendances Python
├── templates/
│   └── index.html      ← interface (HTML + CSS + JS, tout en un)
├── uploads/            ← créé automatiquement, MP3 temporaires
└── separated/          ← créé automatiquement, WAV de sortie
```

## Notes

- La séparation prend 1–5 minutes selon le modèle et votre CPU/GPU.
- Si vous avez un GPU NVIDIA, Demucs l'utilisera automatiquement.
- Les fichiers WAV générés sont en 44.1kHz stéréo.