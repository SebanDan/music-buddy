"""
routes/sheets.py
----------------
Routes HTTP pour la génération et la visualisation de partitions :
    POST /api/sheet/generate          — Lance la génération (async)
    GET  /api/sheet/status/<id>       — Statut du job de génération
    GET  /api/sheet/file/<id>/<stem>  — Sert le fichier MusicXML généré

La génération est asynchrone (thread dédié) car Basic Pitch peut prendre
1 à 3 minutes selon la durée du stem.
"""

import threading
import uuid
from pathlib import Path

import api.services.music_sheet as sheet_service
from api.models.job import SheetJob
from flask import Blueprint, current_app, jsonify, request, send_from_directory

sheets_bp = Blueprint("sheets", __name__)

# Stockage en mémoire des jobs de partition { sheet_job_id: SheetJob }
sheet_jobs: dict[str, SheetJob] = {}

# Stems pour lesquels la transcription en notes n'a pas de sens
STEMS_NO_SHEET = {"drums"}


@sheets_bp.route("/api/sheet/generate", methods=["POST"])
def generate():
    """
    Lance la génération d'une partition pour un stem donné.
    La génération se fait en arrière-plan (Basic Pitch peut être long).

    Body JSON :
        job_id — identifiant du job de séparation parent
        stem   — nom du stem à transcrire (ex: "vocals", "bass")

    Returns:
        { sheet_job_id } — à poller via /api/sheet/status/<id>
    """
    data = request.get_json() or {}
    job_id = data.get("job_id", "").strip()
    stem = data.get("stem", "").strip()

    if not job_id or not stem:
        return jsonify({"error": "job_id et stem sont requis"}), 400

    if stem in STEMS_NO_SHEET:
        return (
            jsonify(
                {
                    "error": f"Transcription non disponible pour '{stem}' (pas de hauteurs tonales)"
                }
            ),
            400,
        )

    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    wav_path = output_folder / job_id / f"{stem}.wav"

    if not wav_path.exists():
        return jsonify({"error": f"Fichier WAV introuvable : {stem}.wav"}), 404

    sheet_job_id = str(uuid.uuid4())
    sheet_job = SheetJob(sheet_job_id=sheet_job_id, job_id=job_id, stem=stem)
    sheet_jobs[sheet_job_id] = sheet_job

    threading.Thread(
        target=sheet_service.run,
        args=(sheet_job, wav_path, output_folder / job_id),
        daemon=True,
    ).start()

    current_app.logger.info(f"Génération partition lancée : {stem} (job: {job_id})")
    return jsonify({"sheet_job_id": sheet_job_id})


@sheets_bp.route("/api/sheet/status/<sheet_job_id>")
def status(sheet_job_id):
    """
    Retourne l'état courant d'un job de génération de partition.

    Returns:
        Dictionnaire SheetJob sérialisé (status, stem, error, ...)
    """
    sheet_job = sheet_jobs.get(sheet_job_id)
    if not sheet_job:
        return jsonify({"error": "Job de partition introuvable"}), 404
    return jsonify(sheet_job.to_dict())


@sheets_bp.route("/api/sheet/file/<job_id>/<stem>")
def serve_file(job_id, stem):
    """
    Sert le fichier MusicXML généré pour un stem donné.
    Utilisé par le frontend pour afficher la partition via Verovio.
    """
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    xml_path = output_folder / job_id / f"{stem}.musicxml"

    if not xml_path.exists():
        return jsonify({"error": "Partition introuvable — générez-la d'abord"}), 404

    return send_from_directory(
        output_folder / job_id,
        f"{stem}.musicxml",
        mimetype="application/vnd.recordare.musicxml+xml",
    )
