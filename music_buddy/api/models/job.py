"""
models/job.py
-------------
Dataclasses représentant les jobs de traitement audio et de génération de partitions.
Utilisées comme source de vérité pour le stockage en mémoire dans les services.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Job:
    """
    Représente un job de séparation audio (Demucs).

    Cycle de vie du statut :
        pending → downloading (YouTube seulement) → processing → done
                                                              └→ error
    """

    job_id: str
    model: str
    filename: str  # Nom du fichier MP3 ou titre YouTube
    status: str = "pending"
    progress: int = 0
    stems: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "model": self.model,
            "filename": self.filename,
            "status": self.status,
            "progress": self.progress,
            "stems": self.stems,
            "error": self.error,
        }


@dataclass
class SheetJob:
    """
    Représente un job de génération de partition (Basic Pitch → MIDI → MusicXML).

    Cycle de vie du statut :
        pending → transcribing → cleaning → rendering → done
                                                     └→ error
    """

    sheet_job_id: str
    job_id: str  # Job parent (séparation audio)
    stem: str  # Nom du stem (vocals, bass, etc.)
    status: str = "pending"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sheet_job_id": self.sheet_job_id,
            "job_id": self.job_id,
            "stem": self.stem,
            "status": self.status,
            "error": self.error,
        }
