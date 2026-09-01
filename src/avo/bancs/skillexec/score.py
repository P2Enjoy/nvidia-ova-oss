"""Relevé et score continu du banc a.

@spec docs/BACKLOG.md U29a1 — environnement Entrepôt du banc a
@spec docs/SPEC_BANCS.md §S5.1 (score = actions correctes / événements
      actionnables), §S5.2 (première action, conforme ou non), §S5.3 (relevé
      par épisode, écrit en JSON par l'adaptateur — U29a2)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Releve:
    """Compteurs d'un épisode ; les champs de coût sont remplis par l'adaptateur.

    `incorrectes` compte les actions VALIDES mais autres que l'obligation ;
    `invalides` les actions refusées par les règles de transition (§S3.2). Les
    deux valent 0 au score (§S5.2).
    """

    seed: int
    horizon: int
    bruit: int
    correctes: int = 0
    incorrectes: int = 0
    invalides: int = 0
    #: Renseignés par l'adaptateur (§S5.3, U29a2) ; None tant qu'aucun run LLM.
    tokens_consommes: int | None = None
    taille_prompt_moyenne: float | None = None
    duree_secondes: float | None = None
    champs_libres: dict[str, Any] = field(default_factory=dict)

    @property
    def evenements_consommes(self) -> int:
        return self.correctes + self.incorrectes + self.invalides

    @property
    def score(self) -> float:
        """Score continu de §S5.1, dans [0, 1] ; 0.0 pour un horizon nul."""
        if self.horizon == 0:
            return 0.0
        return self.correctes / self.horizon

    def compter(self, valide: bool, correcte: bool) -> None:
        """Enregistre la première action d'un événement (§S5.2)."""
        if correcte:
            self.correctes += 1
        elif valide:
            self.incorrectes += 1
        else:
            self.invalides += 1

    def en_dict(self) -> dict[str, Any]:
        """Forme sérialisable du relevé (`banc.json`, §S5.3)."""
        return {
            "seed": self.seed,
            "horizon": self.horizon,
            "bruit": self.bruit,
            "score": self.score,
            "correctes": self.correctes,
            "incorrectes": self.incorrectes,
            "invalides": self.invalides,
            "evenements_consommes": self.evenements_consommes,
            "tokens_consommes": self.tokens_consommes,
            "taille_prompt_moyenne": self.taille_prompt_moyenne,
            "duree_secondes": self.duree_secondes,
            **self.champs_libres,
        }
