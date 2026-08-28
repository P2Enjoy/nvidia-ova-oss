"""Espace de travail d'un run : artefacts auto-porteurs et auditables.

@spec docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@spec docs/SPEC_HARNAIS.md §H6.1 (arborescence du run), §H11.2 (métriques),
      §H11.3 (transcripts), §H4.6 (aucun secret persisté)

Un run doit pouvoir être audité sans le dépôt : le manifeste porte la configuration
résolue (sans secret) et la version du code, les transcripts portent les échanges
exacts, les métriques portent les compteurs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import avo
from avo.config import Config

#: Sous-répertoires créés à l'ouverture d'un run (§H6.1).
SOUS_DOSSIERS = ("transcripts", "notes", "frames", "lineage")


class Workspace:
    """`runs/<run_id>/` — la totalité des artefacts d'une exécution (§H6.1)."""

    def __init__(self, racine: Path, run_id: str) -> None:
        self.run_id = run_id
        self.chemin = racine / run_id
        self._segment = 0

    @classmethod
    def ouvrir(
        cls,
        config: Config,
        run_id: str,
        racine: Path | None = None,
        horodatage: datetime | None = None,
    ) -> Workspace:
        """Crée l'arborescence et écrit le manifeste."""
        espace = cls(racine if racine is not None else config.runs_dir, run_id)
        espace.chemin.mkdir(parents=True, exist_ok=True)
        for sous in SOUS_DOSSIERS:
            (espace.chemin / sous).mkdir(exist_ok=True)
        espace.ecrire_manifeste(config, horodatage)
        return espace

    # ------------------------------------------------------------------ chemins
    @property
    def manifeste(self) -> Path:
        return self.chemin / "manifest.json"

    @property
    def metriques(self) -> Path:
        return self.chemin / "metrics.jsonl"

    @property
    def rapport(self) -> Path:
        return self.chemin / "report.md"

    @property
    def notes(self) -> Path:
        return self.chemin / "notes"

    @property
    def transcripts(self) -> Path:
        return self.chemin / "transcripts"

    def chemin_segment(self, numero: int) -> Path:
        return self.transcripts / f"segment_{numero:03d}.jsonl"

    # ---------------------------------------------------------------- écritures
    def ecrire_manifeste(self, config: Config, horodatage: datetime | None = None) -> None:
        """Manifeste du run : configuration SANS secret, version, horodatage."""
        instant = horodatage or datetime.now(UTC)
        contenu = {
            "run_id": self.run_id,
            "version_harnais": avo.__version__,
            "ouvert_le": instant.isoformat(timespec="seconds"),
            "config": config.resume(),
        }
        self.manifeste.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def metrique(
        self, type_evenement: str, *, horodatage: datetime | None = None, **champs: Any
    ) -> None:
        """Ajoute une ligne à `metrics.jsonl` (§H11.2).

        `horodatage` est réservé aux mots-clés : sans cela, un champ de métrique
        passé en `**champs` pourrait le remplir par accident.
        """
        instant = horodatage or datetime.now(UTC)
        ligne = {
            "horodatage": instant.isoformat(timespec="milliseconds"),
            "type": type_evenement,
            **champs,
        }
        with self.metriques.open("a", encoding="utf-8") as flux:
            flux.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")

    def nouveau_segment(self) -> int:
        """Ouvre un segment de transcript et rend son numéro (§H11.3)."""
        self._segment += 1
        self.chemin_segment(self._segment).touch()
        return self._segment

    def ajouter_au_transcript(self, numero: int, entree: Mapping[str, Any]) -> None:
        """Ajoute une entrée au transcript d'un segment. Append-only (§H5.1)."""
        with self.chemin_segment(numero).open("a", encoding="utf-8") as flux:
            flux.write(json.dumps(entree, ensure_ascii=False, default=str) + "\n")

    def lire_metriques(self) -> list[dict[str, Any]]:
        """Relit les métriques écrites. Utilisé par le rapport et les preuves."""
        if not self.metriques.exists():
            return []
        return [
            json.loads(ligne)
            for ligne in self.metriques.read_text(encoding="utf-8").splitlines()
            if ligne.strip()
        ]

    def ecrire_rapport(self, titre: str, sections: Iterable[tuple[str, str]]) -> None:
        """Écrit `report.md` : le compte rendu lisible du run (§H6.1)."""
        morceaux = [f"# {titre}", "", f"Run : `{self.run_id}`", ""]
        for nom, corps in sections:
            morceaux.extend([f"## {nom}", "", corps.rstrip(), ""])
        self.rapport.write_text("\n".join(morceaux), encoding="utf-8")

    def arborescence(self) -> list[str]:
        """Chemins relatifs présents, triés. Sert aux preuves de conformité H6.1."""
        return sorted(
            str(chemin.relative_to(self.chemin))
            for chemin in self.chemin.rglob("*")
            if chemin.is_file() or chemin.is_dir()
        )
