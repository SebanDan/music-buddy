"""
services/youtube.py
-------------------
Service de téléchargement audio depuis YouTube via yt-dlp.

Responsabilités :
- Récupérer le titre de la vidéo (sans télécharger)
- Télécharger l'audio en MP3 haute qualité
- Mettre à jour le Job en mémoire
- Passer la main au service Demucs une fois le MP3 prêt
"""

import logging
import subprocess
from pathlib import Path

import api.services.music_splitter as splitter_service
from api.models.job import Job

logger = logging.getLogger(__name__)


def fetch_title(url: str) -> str | None:
    """
    Récupère le titre d'une vidéo YouTube sans télécharger l'audio.
    Retourne None en cas d'échec (non bloquant).

    Args:
        url: URL de la vidéo YouTube.
    """
    result = subprocess.run(
        ["yt-dlp", "--print", "title", "--no-download", "--no-playlist", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().splitlines()[0]
    return None


def download_and_split(
    job: Job, url: str, input_path: Path, output_folder: Path
) -> None:
    """
    Télécharge l'audio d'une vidéo YouTube en MP3, puis lance la séparation Demucs.

    Le téléchargement se fait en deux étapes séparées :
        1. Récupération du titre (rapide, sans téléchargement)
        2. Téléchargement audio + conversion en MP3

    Args:
        job:           Instance Job à mettre à jour.
        url:           URL YouTube à télécharger.
        input_path:    Chemin de destination du MP3 (ex: uploads/<job_id>.mp3).
        output_folder: Dossier racine de sortie pour Demucs.
    """
    job.status = "downloading"
    job.progress = 5

    try:
        # Étape 1 : titre (non bloquant, améliore juste l'UX)
        title = fetch_title(url)
        if title:
            job.filename = title
            logger.info(f"[{job.job_id}] Titre YouTube : {title}")

        job.progress = 10

        # Étape 2 : téléchargement audio → MP3
        # --output avec %(ext)s laisse yt-dlp gérer le format intermédiaire
        # avant la conversion finale en .mp3
        logger.info(f"[{job.job_id}] Téléchargement YouTube : {url}")
        result = subprocess.run(
            [
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",  # Meilleure qualité disponible
                "--output",
                str(input_path.with_suffix(".%(ext)s")),
                "--no-playlist",  # Ne pas télécharger toute une playlist
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            last_line = (
                result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
            )
            raise RuntimeError(last_line or "Erreur yt-dlp inconnue")

        if not input_path.exists():
            raise RuntimeError("Fichier MP3 introuvable après téléchargement.")

        job.progress = 20
        logger.info(f"[{job.job_id}] Téléchargement terminé : {input_path}")

    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        logger.error(f"[{job.job_id}] Erreur téléchargement YouTube : {exc}")
        return

    # Pipeline identique à un upload MP3 classique
    splitter_service.run(job, input_path, output_folder)
