"""
routes/sessions.py
------------------
Routes HTTP pour la gestion des sessions sauvegardées :
    GET    /api/sessions                    — Liste toutes les sessions
    POST   /api/sessions/save               — Sauvegarde la session courante
    DELETE /api/sessions/delete/<id>        — Supprime une session

Une session est une snapshot d'un job terminé : elle retient le job_id,
le nom donné par l'utilisateur, le modèle utilisé et la liste des stems.
Les données sont persistées dans un fichier sessions.json sur le disque.
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

sessions_bp = Blueprint("sessions", __name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _sessions_file() -> Path:
    return Path(current_app.config["SESSIONS_FILE"])


def _output_folder() -> Path:
    return Path(current_app.config["OUTPUT_FOLDER"])


def _load() -> dict:
    """Lit le fichier sessions.json. Retourne un dict vide si absent ou corrompu."""
    f = _sessions_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(sessions: dict) -> None:
    """Écrit le dict sessions dans sessions.json."""
    _sessions_file().write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ─── Routes ───────────────────────────────────────────────────────────────────


@sessions_bp.route("/api/sessions")
def list_sessions():
    """
    Retourne toutes les sessions sauvegardées dont les fichiers audio existent encore.
    Nettoie automatiquement les sessions dont le dossier audio a été supprimé manuellement.
    """
    sessions = _load()
    output = _output_folder()

    # Filtrage des sessions dont les WAV ont disparu du disque
    valid = {sid: s for sid, s in sessions.items() if (output / s["job_id"]).exists()}
    orphans = len(sessions) - len(valid)

    if orphans:
        _save(valid)
        current_app.logger.info(
            f"Sessions nettoyées : {orphans} session(s) orpheline(s) supprimées"
        )

    return jsonify(list(valid.values()))


@sessions_bp.route("/api/sessions/save", methods=["POST"])
def save_session():
    """
    Sauvegarde la session courante.

    Body JSON :
        job_id — identifiant du job de séparation
        name   — nom donné par l'utilisateur (défaut: "Sans titre")
        model  — modèle Demucs utilisé
        stems  — liste des stems disponibles

    Returns:
        { session_id, message }
    """
    data = request.get_json() or {}
    job_id = data.get("job_id", "").strip()
    name = (data.get("name") or "Sans titre").strip()
    model = data.get("model", "")
    stems = data.get("stems", [])

    if not job_id:
        return jsonify({"error": "job_id manquant"}), 400

    if not (_output_folder() / job_id).exists():
        return jsonify({"error": "Dossier audio introuvable pour ce job_id"}), 404

    session_id = str(uuid.uuid4())
    sessions = _load()
    sessions[session_id] = {
        "session_id": session_id,
        "job_id": job_id,
        "name": name,
        "model": model,
        "stems": stems,
        "saved_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    _save(sessions)

    current_app.logger.info(f"Session sauvegardée : '{name}' (job: {job_id})")
    return jsonify({"session_id": session_id, "message": "Session sauvegardée !"})


@sessions_bp.route("/api/sessions/delete/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """
    Supprime une session de l'index.

    Query params :
        delete_files=true — supprime aussi les fichiers WAV et partitions sur le disque

    Returns:
        { message }
    """
    sessions = _load()

    if session_id not in sessions:
        return jsonify({"error": "Session introuvable"}), 404

    info = sessions.pop(session_id)
    _save(sessions)

    # Suppression optionnelle des fichiers audio sur le disque
    if request.args.get("delete_files") == "true":
        folder = _output_folder() / info["job_id"]
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            current_app.logger.info(f"Fichiers supprimés pour job {info['job_id']}")

    current_app.logger.info(f"Session supprimée : '{info['name']}' ({session_id})")
    return jsonify({"message": "Session supprimée"})
