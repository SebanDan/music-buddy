"""
services/demucs.py
------------------
Service de séparation audio via Demucs.

Responsabilités :
- Lancer Demucs en sous-processus
- Déplacer les fichiers WAV générés dans le dossier du job
- Mettre à jour le Job en mémoire tout au long du traitement
- Nettoyer les fichiers temporaires (MP3 uploadé, dossiers Demucs intermédiaires)
"""

import logging
import re
import subprocess
from pathlib import Path

from api.models.job import SplitterJob

logger = logging.getLogger(__name__)


def run(job: SplitterJob, input_path: Path, output_folder: Path) -> None:
    """
    Sépare les pistes audio d'un fichier MP3 avec Demucs.

    Le pipeline est le suivant :
        1. Demucs écrit dans output_folder/<model>/<job_id>/
        2. On déplace chaque stem.wav vers output_folder/<job_id>/stem.wav
        3. On supprime les dossiers temporaires créés par Demucs
        4. On supprime le fichier MP3 source

    Args:
        job:           Instance Job à mettre à jour (status, progress, stems).
        input_path:    Chemin vers le fichier MP3 à traiter.
        output_folder: Dossier racine de sortie (ex: Path("separated")).
    """
    job.status = "processing"
    job.progress = 0
    out_dir = output_folder / job.job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("[%s] Démarrage Demucs (modèle: %s)", job.job_id, job.model)
        process = subprocess.Popen(
            [
                "python3",
                "-m",
                "demucs",
                "--name",
                job.model,
                "--out",
                str(output_folder),
                str(input_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout or []:
            match = re.search(r"(\d+)%", line)
            if match:
                job.progress = int(match.group(1))

        returncode = process.wait(timeout=3600)

        if returncode != 0:
            raise RuntimeError(process.stderr)

        # Demucs place les WAV dans : output_folder/<model>/<job_id>/stem.wav
        # On les déplace dans output_folder/<job_id>/stem.wav
        demucs_out = output_folder / job.model / input_path.stem  # stem = job_id

        stems_found = []
        if demucs_out.exists():
            for wav_file in sorted(demucs_out.glob("*.wav")):
                destination = out_dir / wav_file.name
                wav_file.rename(destination)
                stems_found.append(wav_file.stem)
                logger.info(f"[{job.job_id}] Stem récupéré : {wav_file.stem}")

        if not stems_found:
            raise RuntimeError(
                "Aucune piste générée — vérifiez que Demucs est installé."
            )

        # Nettoyage des dossiers temporaires créés par Demucs
        _cleanup_demucs_dirs(demucs_out, output_folder, job.model)

        job.status = "done"
        job.progress = 100
        job.stems = stems_found
        logger.info(f"[{job.job_id}] Séparation terminée : {stems_found}")

    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        logger.error(f"[{job.job_id}] Erreur Demucs : {exc}")

    finally:
        # Toujours supprimer le MP3 source après traitement
        _delete_input_file(input_path, job.job_id)


def _cleanup_demucs_dirs(demucs_out: Path, output_folder: Path, model: str) -> None:
    """Supprime les dossiers intermédiaires laissés par Demucs."""
    try:
        demucs_out.rmdir()
        (output_folder / model).rmdir()
    except OSError:
        # Non-fatal : le dossier n'est peut-être pas vide si d'autres jobs tournent
        pass


def _delete_input_file(input_path: Path, job_id: str) -> None:
    """Supprime le fichier MP3 uploadé ou téléchargé."""
    try:
        input_path.unlink(missing_ok=True)
        logger.debug(f"[{job_id}] Fichier source supprimé : {input_path}")
    except OSError as e:
        logger.warning(f"[{job_id}] Impossible de supprimer {input_path} : {e}")
