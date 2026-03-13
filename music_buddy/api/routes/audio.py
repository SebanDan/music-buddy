"""
routes/audio.py
---------------
Routes HTTP liées au traitement audio :
    POST /api/upload        — Upload MP3 → séparation Demucs
    POST /api/youtube       — URL YouTube → téléchargement → séparation Demucs
    GET  /api/status/<id>   — Statut d'un job de séparation
    GET  /audio/<id>/<stem> — Téléchargement d'un stem WAV
    GET  /api/models        — Liste des modèles Demucs disponibles
"""

import threading
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory

import music_buddy.api.services.music_splitter as splitter_service
import music_buddy.api.services.youtube_manager as youtube_service
from music_buddy.api.models.job import SplitterJob

audio_bp = Blueprint("audio", __name__)

# Stockage en mémoire des jobs de séparation { job_id: SplitterJob }
# Note : réinitialisé au redémarrage du serveur.
# Pour de la persistence, remplacer par une vraie DB.
jobs: dict[str, SplitterJob] = {}

# Stems pour lesquels la partition n'a pas de sens (pas de hauteur tonale)
STEMS_NO_SHEET = {"drums"}


@audio_bp.route("/api/models")
def get_models():
    """Retourne la liste des modèles Demucs disponibles avec leurs stems."""
    return jsonify(current_app.config["MODELS"])


@audio_bp.route("/api/upload", methods=["POST"])
def upload():
    """
    Reçoit un fichier MP3, le sauvegarde, et lance la séparation Demucs
    en arrière-plan dans un thread dédié.

    Form data :
        file  — fichier MP3
        model — identifiant du modèle Demucs (défaut: htdemucs)

    Returns:
        { job_id } — identifiant à utiliser pour poller /api/status/<job_id>
    """
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file = request.files["file"]
    model = request.form.get("model", "htdemucs")

    if not file.filename:
        return jsonify({"error": "Nom de fichier vide"}), 400
    if not file.filename.lower().endswith(".mp3"):
        return jsonify({"error": "Seuls les fichiers MP3 sont acceptés"}), 400
    if model not in current_app.config["MODELS"]:
        return jsonify({"error": f"Modèle inconnu : {model}"}), 400

    job_id = str(uuid.uuid4())
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    input_path = upload_dir / f"{job_id}.mp3"
    file.save(input_path)

    job = SplitterJob(job_id=job_id, model=model, filename=file.filename)
    jobs[job_id] = job

    threading.Thread(
        target=splitter_service.run,
        args=(job, input_path, Path(current_app.config["OUTPUT_FOLDER"])),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id})


@audio_bp.route("/api/youtube", methods=["POST"])
def youtube():
    """
    Reçoit une URL YouTube, télécharge le son en MP3 via yt-dlp,
    puis lance la séparation Demucs — même pipeline que /api/upload.

    Body JSON :
        url   — URL de la vidéo YouTube
        model — identifiant du modèle Demucs (défaut: htdemucs)

    Returns:
        { job_id } — identifiant à poller
    """
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    model = data.get("model", "htdemucs")

    if not url:
        return jsonify({"error": "URL manquante"}), 400
    if not ("youtube.com" in url or "youtu.be" in url):
        return jsonify({"error": "Seules les URLs YouTube sont acceptées"}), 400
    if model not in current_app.config["MODELS"]:
        return jsonify({"error": f"Modèle inconnu : {model}"}), 400

    job_id = str(uuid.uuid4())
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    input_path = upload_dir / f"{job_id}.mp3"

    job = SplitterJob(job_id=job_id, model=model, filename=url)
    jobs[job_id] = job

    threading.Thread(
        target=youtube_service.download_and_split,
        args=(job, url, input_path, Path(current_app.config["OUTPUT_FOLDER"])),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id})


@audio_bp.route("/api/status/<job_id>")
def status(job_id):
    """
    Retourne l'état courant d'un job de séparation.

    Returns:
        Dictionnaire Job sérialisé (status, progress, stems, error, ...)
    """
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job introuvable"}), 404
    return jsonify(job.to_dict())


@audio_bp.route("/audio/<job_id>/<stem>")
def serve_audio(job_id, stem):
    """
    Sert un fichier WAV pour un stem donné.
    Utilisé par le frontend pour charger l'audio dans le mixer.
    """
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    audio_dir = output_folder / job_id
    filename = f"{stem}.wav"

    if not (audio_dir / filename).exists():
        return jsonify({"error": "Fichier audio introuvable"}), 404

    return send_from_directory(audio_dir, filename)
