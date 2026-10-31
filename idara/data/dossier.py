"""مجلد بيانات المؤسسة: كل ما يخص التثبيت في مجلد واحد قابل للنقل."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

NOM_BASE = "data.db"
SOUS_DOSSIERS = ("modeles", "archives", "pieces", "sauvegardes")


@dataclass(frozen=True)
class DossierDonnees:
    racine: Path

    @property
    def base(self) -> Path:
        return self.racine / NOM_BASE

    @property
    def modeles(self) -> Path:
        return self.racine / "modeles"

    @property
    def archives(self) -> Path:
        return self.racine / "archives"

    @property
    def pieces(self) -> Path:
        return self.racine / "pieces"

    @property
    def sauvegardes(self) -> Path:
        return self.racine / "sauvegardes"

    def preparer(self) -> "DossierDonnees":
        """ينشئ المجلد وفروعه إن لم تكن موجودة."""
        self.racine.mkdir(parents=True, exist_ok=True)
        for nom in SOUS_DOSSIERS:
            (self.racine / nom).mkdir(exist_ok=True)
        return self
