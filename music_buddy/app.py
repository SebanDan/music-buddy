"""
app.py
------
Point d'entrée de Demucs Studio.

Initialise l'application Flask, enregistre les blueprints et crée
les dossiers nécessaires au démarrage.

Lancement :
    python app.py
    # ou avec uv :
    uv run python app.py
"""

import logging
from pathlib import Path

from api.routes import audio_bp, sessions_bp, sheets_bp
from flask import Flask, render_template

# ─── Configuration ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

DATABASE_FOLDER = BASE_DIR / "database"
# Dossiers de données (relatifs au répertoire de lancement)
UPLOAD_FOLDER = (
    DATABASE_FOLDER / "uploads"
)  # MP3 temporaires (supprimés après traitement)
OUTPUT_FOLDER = DATABASE_FOLDER / "separated"  # WAV séparés + MIDI + MusicXML
SESSIONS_FILE = DATABASE_FOLDER / "sessions" / "sessions.json"
FRONT_FOLDER = BASE_DIR / "front"
CONFIG_FOLDER = BASE_DIR / "config"

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


# ─── Factory ──────────────────────────────────────────────────────────────────


def create_app() -> Flask:
    """
    Crée et configure l'application Flask.
    Séparé en factory function pour faciliter les tests unitaires.
    """
    app = Flask(
        __name__, static_folder="front/static", template_folder="front/templates"
    )

    # Injection de la configuration dans app.config
    # Les blueprints y accèdent via current_app.config
    app.config.update(
        UPLOAD_FOLDER=str(UPLOAD_FOLDER),
        OUTPUT_FOLDER=str(OUTPUT_FOLDER),
        SESSIONS_FILE=str(SESSIONS_FILE),
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,  # 200 MB max upload
    )

    # Création des dossiers au démarrage
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    OUTPUT_FOLDER.mkdir(exist_ok=True)

    # Enregistrement des blueprints
    app.register_blueprint(audio_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(sheets_bp)

    # Route principale
    @app.route("/")
    def index():
        return render_template("index.html")

    app.logger.info("Music Buddy démarré")
    return app


# ─── Lancement ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    webapp = create_app()
    print("\n🎵 Music Buddy")
    print("   → http://localhost:5000\n")
    webapp.run(debug=True, port=5000)
