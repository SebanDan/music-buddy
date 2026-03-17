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
from pathlib import Path

from yt_dlp import YoutubeDL

import music_buddy.api.services.music_splitter as splitter_service
from music_buddy.api.models.job import SplitterJob

logger = logging.getLogger(__name__)


def get_title(url: str) -> str | None:
    """
    Récupère le titre d'une vidéo YouTube sans télécharger l'audio.
    Retourne None en cas d'échec (non bloquant).

    Args:
        url: URL de la vidéo YouTube.
    """
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["title"]
    return None


def download_and_split(
    job: SplitterJob, url: str, input_path: Path, output_folder: Path
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
        title = get_title(url)
        if title:
            job.filename = title
            logger.info("[%s] Titre YouTube : %s", job.job_id, title)

        job.progress = 20

        # Étape 2 : téléchargement audio → MP3
        logger.info("[%s] Téléchargement YouTube : %s", job.job_id, url)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(input_path.with_suffix(".%(ext)s")),
            "noplaylist": True,
            "progress_hooks": [job.progress_hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ],
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        job.progress = 100
        logger.info(f"[{job.job_id}] Téléchargement terminé : {input_path}")

    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        logger.error(f"[{job.job_id}] Erreur téléchargement YouTube : {exc}")
        return

    # Pipeline identique à un upload MP3 classique
    splitter_service.run(job, input_path, output_folder)
