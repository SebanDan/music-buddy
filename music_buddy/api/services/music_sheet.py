"""
services/sheet_music.py
-----------------------
Service de génération de partitions musicales.

Pipeline complet pour un stem audio :
    WAV → MIDI (Basic Pitch) → nettoyage (pretty_midi) → MusicXML (music21)

Les imports de basic_pitch, pretty_midi et music21 sont faits à l'intérieur
des fonctions pour éviter de bloquer le démarrage de Flask si ces librairies
ne sont pas installées.
"""

import logging
from pathlib import Path

import pretty_midi
from api.models.job import SheetJob
from basic_pitch.inference import predict
from music21 import converter

logger = logging.getLogger(__name__)

# Durée minimale d'une note pour qu'elle soit conservée (en secondes).
# En dessous de ce seuil, la note est considérée comme un artefact de transcription.
MIN_NOTE_DURATION = 0.05


def run(sheet_job: SheetJob, wav_path: Path, out_dir: Path) -> None:
    """
    Génère une partition MusicXML à partir d'un fichier WAV.

    Étapes :
        1. transcribing — Basic Pitch transcrit l'audio en MIDI
        2. cleaning     — pretty_midi supprime les notes trop courtes
        3. rendering    — music21 convertit le MIDI en MusicXML

    Les fichiers intermédiaires (.mid) et finaux (.musicxml) sont écrits
    dans out_dir, qui correspond à output_folder/<job_id>/.

    Args:
        sheet_job: Instance SheetJob à mettre à jour.
        wav_path:  Chemin vers le fichier WAV source.
        out_dir:   Dossier de sortie (doit exister).
    """
    stem = sheet_job.stem

    try:
        # ── Étape 1 : transcription audio → MIDI ──────────────────
        sheet_job.status = "transcribing"
        logger.info(
            f"[{sheet_job.sheet_job_id}] Transcription Basic Pitch : {wav_path.name}"
        )
        midi_path = _transcribe_to_midi(wav_path, out_dir, stem)

        # ── Étape 2 : nettoyage des artefacts ─────────────────────
        sheet_job.status = "cleaning"
        logger.info(f"[{sheet_job.sheet_job_id}] Nettoyage MIDI")
        _clean_midi(midi_path)

        # ── Étape 3 : export MusicXML ──────────────────────────────
        sheet_job.status = "rendering"
        logger.info(f"[{sheet_job.sheet_job_id}] Export MusicXML")
        _midi_to_musicxml(midi_path, out_dir, stem)

        sheet_job.status = "done"
        logger.info(f"[{sheet_job.sheet_job_id}] Partition générée pour '{stem}'")

    except Exception as exc:
        sheet_job.status = "error"
        sheet_job.error = str(exc)
        logger.error(f"[{sheet_job.sheet_job_id}] Erreur génération partition : {exc}")


def _transcribe_to_midi(wav_path: Path, out_dir: Path, stem: str) -> Path:
    """
    Utilise Basic Pitch pour transcrire un audio WAV en fichier MIDI.

    Returns:
        Chemin vers le fichier .mid généré.
    """

    _, midi_data, _ = predict(str(wav_path))
    midi_path = out_dir / f"{stem}.mid"
    midi_data.write(str(midi_path))
    return midi_path


def _clean_midi(midi_path: Path) -> None:
    """
    Supprime les notes trop courtes d'un fichier MIDI (artefacts de transcription).
    Réécrit le fichier sur place.

    Une note dont la durée est inférieure à MIN_NOTE_DURATION secondes
    est généralement un artefact et non une note musicale intentionnelle.
    """

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    total_before = sum(len(inst.notes) for inst in midi.instruments)

    for instrument in midi.instruments:
        instrument.notes = [
            note
            for note in instrument.notes
            if (note.end - note.start) >= MIN_NOTE_DURATION
        ]

    total_after = sum(len(inst.notes) for inst in midi.instruments)
    logger.debug(f"Nettoyage MIDI : {total_before} → {total_after} notes")

    midi.write(str(midi_path))


def _midi_to_musicxml(midi_path: Path, out_dir: Path, stem: str) -> Path:
    """
    Convertit un fichier MIDI en MusicXML via music21.

    Returns:
        Chemin vers le fichier .musicxml généré.
    """

    score = converter.parse(str(midi_path))
    xml_path = out_dir / f"{stem}.musicxml"
    score.write("musicxml", str(xml_path))
    return xml_path
