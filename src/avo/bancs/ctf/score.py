"""Relevé pass@1 du banc b.

@spec docs/BACKLOG.md U29b1 — relevé pass@1 du banc b
@spec docs/SPEC_BANCS.md §S11.1 (score binaire : capture ou non, pas de score
      partiel), §S11.2 (champs du relevé ; relevé écrit même sur incident,
      jamais de succès simulé), §S11.3 (agrégation pass@1 par série de seeds)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReleveCtf:
    """Compteurs d'un épisode CTF ; les champs de coût viennent de l'adaptateur.

    `commandes` compte toutes les actions `bash`, refus de forme compris
    (§S11.2) ; `actions` compte commandes et soumissions confondues (§S8.3).
    """

    seed: int
    famille: str
    horizon: int
    reussi: bool = False
    actions: int = 0
    commandes: int = 0
    refus_forme: int = 0
    soumissions: int = 0
    soumissions_incorrectes: int = 0
    arret: str | None = None
    #: Renseignés par l'adaptateur (§S5.3, U29b2) ; None tant qu'aucun run LLM.
    tokens_consommes: int | None = None
    taille_prompt_moyenne: float | None = None
    duree_secondes: float | None = None
    champs_libres: dict[str, Any] = field(default_factory=dict)

    def en_dict(self) -> dict[str, Any]:
        """Forme sérialisable du relevé (`banc.json`, §S11.2)."""
        return {
            "seed": self.seed,
            "famille": self.famille,
            "horizon": self.horizon,
            "reussi": self.reussi,
            "actions": self.actions,
            "commandes": self.commandes,
            "refus_forme": self.refus_forme,
            "soumissions": self.soumissions,
            "soumissions_incorrectes": self.soumissions_incorrectes,
            "arret": self.arret,
            "tokens_consommes": self.tokens_consommes,
            "taille_prompt_moyenne": self.taille_prompt_moyenne,
            "duree_secondes": self.duree_secondes,
            **self.champs_libres,
        }
