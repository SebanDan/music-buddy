"""
models/job.py
-------------
Dataclasses représentant les jobs de traitement audio et de génération de partitions.
Utilisées comme source de vérité pour le stockage en mémoire dans les services.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import uuid4


@dataclass
class Job:

    uuid: str = field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    progress: int = 0
    error: Optional[str] = None

    @classmethod
    def progress_hook(self, info):
        if info["status"] == "downloading":
            downloaded = info.get("downloaded_bytes", 0)
            total = info.get("total_bytes") or info.get("total_bytes_estimate")

            if total:
                percent = downloaded / total * 100
                self.progress = 10 + percent * 0.8  # téléchargement = 10→90%

        elif info["status"] == "finished":
            self.progress = 90


@dataclass
class SplitterJob(Job):
    """
    Représente un job de séparation audio (Demucs).

    Cycle de vie du statut :
        pending → downloading (YouTube seulement) → processing → done
                                                              └→ error
    """

    job_id: str = field(default_factory=lambda: str(uuid4()))
    model: str = ""
    filename: str = ""
    stems: List[str] = field(default_factory=list)

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
class SheetJob(Job):
    """
    Représente un job de génération de partition (Basic Pitch → MIDI → MusicXML).

    Cycle de vie du statut :
        pending → transcribing → cleaning → rendering → done
                                                     └→ error
    """

    sheet_job_id: str = field(default_factory=lambda: str(uuid4()))
    job_id: str = field(default_factory=lambda: str(uuid4()))
    stem: str = ""

    def to_dict(self) -> dict:
        return {
            "sheet_job_id": self.sheet_job_id,
            "job_id": self.job_id,
            "stem": self.stem,
            "status": self.status,
            "error": self.error,
        }
