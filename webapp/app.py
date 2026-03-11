"""
Demucs Web App — Backend Flask
Sépare les pistes audio d'un fichier MP3 avec Demucs.
"""

import json
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

# ─── Configuration ────────────────────────────────────────────────────────────
UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("separated")
CONFIG_FOLDER = Path("config")
SESSIONS_FILE = Path("sessions/sessions.json")  # index de toutes les sessions
# UPLOAD_FOLDER.mkdir(exist_ok=True)
# OUTPUT_FOLDER.mkdir(exist_ok=True)
TEMPLATES_FOLDER = Path("templates")

# Modèles Demucs disponibles et leurs stems
MODELS = json.load((CONFIG_FOLDER / "models.json").open("rb"))
# Stockage des jobs en mémoire { job_id: { status, progress, stems, error } }
jobs = {}

# ─── Routes principales ───────────────────────────────────────────────────────

app = Flask(__name__, template_folder=TEMPLATES_FOLDER)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/models")
def get_models():
    """Retourne la liste des modèles disponibles."""
    return jsonify(MODELS)


@app.route("/api/upload", methods=["POST"])
def upload():
    """
    Reçoit un fichier MP3, lance Demucs en arrière-plan,
    retourne un job_id pour suivre l'avancement.
    """
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file = request.files["file"]
    model = request.form.get("model", "htdemucs")

    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide"}), 400

    if not file.filename.lower().endswith(".mp3"):
        return jsonify({"error": "Seuls les fichiers MP3 sont acceptés"}), 400

    if model not in MODELS:
        return jsonify({"error": "Modèle inconnu"}), 400

    # Sauvegarde du fichier uploadé
    job_id = str(uuid.uuid4())
    input_path = UPLOAD_FOLDER / f"{job_id}.mp3"
    file.save(input_path)

    # Initialisation du job
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "model": model,
        "filename": file.filename,
        "stems": [],
        "error": None,
    }

    # Lancement du traitement en arrière-plan
    thread = threading.Thread(
        target=run_demucs,
        args=(job_id, input_path, model),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    """Retourne l'état d'avancement d'un job."""
    if job_id not in jobs:
        return jsonify({"error": "Job introuvable"}), 404
    return jsonify(jobs[job_id])


@app.route("/audio/<job_id>/<stem>")
def serve_audio(job_id, stem):
    """Sert un fichier WAV d'une piste séparée."""
    audio_dir = OUTPUT_FOLDER / job_id
    filename = f"{stem}.wav"
    if not (audio_dir / filename).exists():
        return jsonify({"error": "Fichier introuvable"}), 404
    return send_from_directory(audio_dir, filename)


@app.route("/api/youtube", methods=["POST"])
def youtube():
    """
    Reçoit une URL YouTube, télécharge le son en MP3 via yt-dlp,
    puis lance Demucs — même pipeline que /api/upload.
    Body JSON : { url, model }
    """
    data = request.get_json()
    url = (data.get("url") or "").strip()
    model = data.get("model", "htdemucs")

    if not url:
        return jsonify({"error": "URL manquante"}), 400
    if not ("youtube.com" in url or "youtu.be" in url):
        return jsonify({"error": "Seules les URLs YouTube sont acceptées"}), 400
    if model not in MODELS:
        return jsonify({"error": "Modèle inconnu"}), 400

    job_id = str(uuid.uuid4())
    input_path = UPLOAD_FOLDER / f"{job_id}.mp3"

    jobs[job_id] = {
        "status": "downloading",
        "progress": 0,
        "model": model,
        "filename": url,  # sera remplacé par le titre réel après le dl
        "stems": [],
        "error": None,
    }

    thread = threading.Thread(
        target=run_ytdlp_then_demucs,
        args=(job_id, url, input_path, model),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


# ─── Téléchargement YouTube ───────────────────────────────────────────────────


def run_ytdlp_then_demucs(job_id: str, url: str, input_path: Path, model: str):
    """
    1. Récupère le titre de la vidéo (rapide, sans téléchargement).
    2. Télécharge l'audio en MP3 avec yt-dlp.
    3. Lance run_demucs sur le fichier téléchargé.
    """
    try:
        jobs[job_id]["status"] = "downloading"
        jobs[job_id]["progress"] = 5

        # ── Étape 1 : récupérer le titre sans télécharger ──────────
        title_result = subprocess.run(
            ["yt-dlp", "--print", "title", "--no-download", "--no-playlist", url],
            capture_output=True,
            text=True,
        )
        if title_result.returncode == 0 and title_result.stdout.strip():
            jobs[job_id]["filename"] = title_result.stdout.strip().splitlines()[0]

        jobs[job_id]["progress"] = 10

        # ── Étape 2 : téléchargement audio ─────────────────────────
        # On laisse yt-dlp choisir le nom de sortie dans UPLOAD_FOLDER
        # puis on renomme en job_id.mp3 pour garder notre convention.
        dl_result = subprocess.run(
            [
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
                "--output",
                str(UPLOAD_FOLDER / f"{job_id}.%(ext)s"),
                "--no-playlist",
                url,
            ],
            capture_output=True,
            text=True,
        )

        if dl_result.returncode != 0:
            err = (
                dl_result.stderr.strip().splitlines()[-1]
                if dl_result.stderr.strip()
                else "Erreur yt-dlp inconnue"
            )
            raise RuntimeError(err)

        # yt-dlp écrit d'abord dans un format source puis convertit en .mp3
        # Le fichier final devrait être job_id.mp3
        if not input_path.exists():
            raise RuntimeError("Fichier MP3 introuvable après téléchargement.")

        jobs[job_id]["progress"] = 20

    except Exception as exc:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(exc)
        return

    # Pipeline Demucs identique à un upload classique
    run_demucs(job_id, input_path, model)


# ─── Génération de partitions ─────────────────────────────────────────────────

# Stockage des jobs de partition en mémoire
# { sheet_job_id: { status, job_id, stem, error } }
sheet_jobs = {}

# Stems pour lesquels la transcription n'a pas de sens (pas de hauteurs tonales)
STEMS_NO_SHEET = {"drums"}


@app.route("/api/sheet/generate", methods=["POST"])
def generate_sheet():
    """
    Lance la transcription MIDI + génération MusicXML pour un stem donné.
    Body JSON : { job_id, stem }
    Retourne un sheet_job_id à poller via /api/sheet/status/<id>
    """
    data = request.get_json()
    job_id = data.get("job_id")
    stem = data.get("stem")

    if not job_id or not stem:
        return jsonify({"error": "job_id et stem requis"}), 400

    if stem in STEMS_NO_SHEET:
        return jsonify({"error": f"Transcription non disponible pour '{stem}'"}), 400

    wav_path = OUTPUT_FOLDER / job_id / f"{stem}.wav"
    if not wav_path.exists():
        return jsonify({"error": "Fichier WAV introuvable"}), 404

    sheet_job_id = str(uuid.uuid4())
    sheet_jobs[sheet_job_id] = {
        "status": "pending",
        "job_id": job_id,
        "stem": stem,
        "error": None,
    }

    thread = threading.Thread(
        target=run_sheet_generation,
        args=(sheet_job_id, job_id, stem, wav_path),
        daemon=True,
    )
    thread.start()

    return jsonify({"sheet_job_id": sheet_job_id})


@app.route("/api/sheet/status/<sheet_job_id>")
def sheet_status(sheet_job_id):
    """Retourne l'etat d'un job de generation de partition."""
    if sheet_job_id not in sheet_jobs:
        return jsonify({"error": "Job introuvable"}), 404
    return jsonify(sheet_jobs[sheet_job_id])


@app.route("/api/sheet/file/<job_id>/<stem>")
def serve_sheet(job_id, stem):
    """Sert le fichier MusicXML genere."""
    xml_path = OUTPUT_FOLDER / job_id / f"{stem}.musicxml"
    if not xml_path.exists():
        return jsonify({"error": "Partition introuvable"}), 404
    return send_from_directory(
        OUTPUT_FOLDER / job_id,
        f"{stem}.musicxml",
        mimetype="application/vnd.recordare.musicxml+xml",
    )


def run_sheet_generation(sheet_job_id: str, job_id: str, stem: str, wav_path: Path):
    """
    Pipeline complet : WAV -> MIDI (Basic Pitch) -> nettoyage -> MusicXML (music21).
    Tout est sauvegarde dans OUTPUT_FOLDER / job_id /.
    """
    out_dir = OUTPUT_FOLDER / job_id

    try:
        sheet_jobs[sheet_job_id]["status"] = "transcribing"

        # 1. Basic Pitch : audio -> MIDI
        from basic_pitch.inference import predict

        _, midi_data, _ = predict(str(wav_path))

        midi_path = out_dir / f"{stem}.mid"
        midi_data.write(str(midi_path))

        sheet_jobs[sheet_job_id]["status"] = "cleaning"

        # 2. Nettoyage : supprime les notes trop courtes (< 50ms)
        import pretty_midi

        midi = pretty_midi.PrettyMIDI(str(midi_path))
        for instrument in midi.instruments:
            instrument.notes = [
                note for note in instrument.notes if (note.end - note.start) > 0.05
            ]
        midi.write(str(midi_path))

        sheet_jobs[sheet_job_id]["status"] = "rendering"

        # 3. music21 : MIDI -> MusicXML
        from music21 import converter

        score = converter.parse(str(midi_path))
        xml_path = out_dir / f"{stem}.musicxml"
        score.write("musicxml", str(xml_path))

        sheet_jobs[sheet_job_id]["status"] = "done"

    except Exception as exc:
        sheet_jobs[sheet_job_id]["status"] = "error"
        sheet_jobs[sheet_job_id]["error"] = str(exc)


# ─── Traitement Demucs ────────────────────────────────────────────────────────


def run_demucs(job_id: str, input_path: Path, model: str):
    """
    Lance Demucs en sous-processus et met à jour le job au fil de l'avancement.
    Les fichiers WAV sont ensuite déplacés dans OUTPUT_FOLDER / job_id.
    """
    jobs[job_id]["status"] = "processing"
    jobs[job_id]["progress"] = 5

    try:
        # Dossier de sortie temporaire pour ce job
        out_dir = OUTPUT_FOLDER / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # Commande Demucs
        cmd = [
            "python3",
            "-m",
            "demucs",
            "--name",
            model,
            "--out",
            str(OUTPUT_FOLDER),
            str(input_path),
        ]

        jobs[job_id]["progress"] = 10

        # Exécution (peut prendre plusieurs minutes)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr or "Erreur Demucs inconnue")

        jobs[job_id]["progress"] = 80

        # Demucs place les fichiers dans : OUTPUT_FOLDER / model / filename_sans_ext / stem.wav
        # On les déplace dans OUTPUT_FOLDER / job_id / stem.wav pour simplifier les URLs
        source_name = input_path.stem  # = job_id
        demucs_out = OUTPUT_FOLDER / model / source_name

        stems_found = []
        if demucs_out.exists():
            for wav_file in sorted(demucs_out.glob("*.wav")):
                stem_name = wav_file.stem
                destination = out_dir / f"{stem_name}.wav"
                wav_file.rename(destination)
                stems_found.append(stem_name)

        if not stems_found:
            raise RuntimeError(
                "Aucune piste générée — vérifiez que Demucs est installé."
            )

        # Nettoyage du dossier temporaire Demucs
        try:
            demucs_out.rmdir()
            (OUTPUT_FOLDER / model).rmdir()
        except OSError:
            pass  # Pas grave si non vide

        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["stems"] = stems_found

    except Exception as exc:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(exc)

    finally:
        # Suppression du MP3 uploadé
        try:
            input_path.unlink()
        except OSError:
            pass


# ─── Sessions ─────────────────────────────────────────────────────────────────


def load_sessions() -> dict:
    """Lit l'index des sessions depuis le fichier JSON."""
    if not SESSIONS_FILE.exists():
        return {}
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except Exception:
        return {}


def save_sessions(sessions: dict):
    """Écrit l'index des sessions sur le disque."""
    SESSIONS_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False), encoding="UTF-8"
    )


@app.route("/api/sessions")
def list_sessions():
    """Retourne la liste de toutes les sessions sauvegardées."""
    sessions = load_sessions()
    # Vérifie que les fichiers existent encore sur le disque
    valid = {}
    for sid, info in sessions.items():
        folder = OUTPUT_FOLDER / info["job_id"]
        if folder.exists():
            valid[sid] = info
    # Mise à jour si certaines sessions ont été supprimées manuellement
    if len(valid) != len(sessions):
        save_sessions(valid)
    return jsonify(list(valid.values()))


@app.route("/api/sessions/save", methods=["POST"])
def save_session():
    """
    Sauvegarde la session courante avec un nom donné par l'utilisateur.
    Body JSON : { job_id, name, model, stems }
    """
    data = request.get_json()
    job_id = data.get("job_id")
    name = data.get("name", "Sans titre").strip() or "Sans titre"
    model = data.get("model", "")
    stems = data.get("stems", [])

    if not job_id:
        return jsonify({"error": "job_id manquant"}), 400

    folder = OUTPUT_FOLDER / job_id
    if not folder.exists():
        return jsonify({"error": "Dossier audio introuvable"}), 404

    session_id = str(uuid.uuid4())
    sessions = load_sessions()
    sessions[session_id] = {
        "session_id": session_id,
        "job_id": job_id,
        "name": name,
        "model": model,
        "stems": stems,
        "saved_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    save_sessions(sessions)
    return jsonify({"session_id": session_id, "message": "Session sauvegardée !"})


@app.route("/api/sessions/delete/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """
    Supprime une session de l'index.
    Passe delete_files=true pour supprimer aussi les WAV sur le disque.
    """
    sessions = load_sessions()
    if session_id not in sessions:
        return jsonify({"error": "Session introuvable"}), 404

    info = sessions.pop(session_id)
    save_sessions(sessions)

    # Suppression optionnelle des fichiers audio
    if request.args.get("delete_files") == "true":
        folder = OUTPUT_FOLDER / info["job_id"]
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)

    return jsonify({"message": "Session supprimée"})


# ─── Lancement ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🎵 Demucs Web App")
    print("   → http://localhost:5000")
    app.run(debug=True, port=5000)
