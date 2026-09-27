"""Rendu texte des observations : la grille exacte, rien d'autre.

@spec docs/BACKLOG.md U18 — Rendu texte, inspection, mémoire de frames
@spec docs/SPEC_ARCAGI3.md §A4.1 (rendu canonique, ligne d'état APRÈS la grille),
      §A4.2 (coordonnées (row, col) 0-basées), §A4.4 (rendu pur, sorties exactes)
@spec docs/BACKLOG.md U31 — ligne d'état après la grille (§H15.11 : le compteur
      d'actions, volatil, ne doit pas précéder les ~8 200 tokens de grille)
@spec docs/SPEC_ARCAGI3.md §A5.1 (direct-interaction : aucune interprétation ajoutée)

Configuration AVO, reprise du billet NVIDIA : **texte seul**, chaque observation
étant la grille 64×64 exacte. Aucune image, aucun résumé, aucune mise en évidence.
Enrichir le rendu — nommer un objet, signaler une différence — reviendrait à
souffler à l'agent une interprétation qu'il doit inférer, et fausserait l'évaluation
sans que rien ne l'indique dans les scores.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

Grille = list[list[int]]

#: Côté de la grille (§A1.1).
COTE: Final = 64


class GrilleInvalide(ValueError):
    """Grille dont la forme n'est pas celle du contrat (§A1.1)."""


def valider_grille(grille: Sequence[Sequence[int]]) -> None:
    """Vérifie la forme. Lève plutôt que de rendre une observation tronquée."""
    if len(grille) != COTE:
        raise GrilleInvalide(f"{COTE} lignes attendues, {len(grille)} reçues")
    for index, ligne in enumerate(grille):
        if len(ligne) != COTE:
            raise GrilleInvalide(f"ligne {index} : {COTE} colonnes attendues, {len(ligne)} reçues")


def rendre_grille(grille: Sequence[Sequence[int]]) -> str:
    """Rendu canonique : 64 lignes de 64 valeurs décimales séparées par des espaces."""
    valider_grille(grille)
    return "\n".join(" ".join(str(valeur) for valeur in ligne) for ligne in grille)


def parser_grille(texte: str) -> Grille:
    """Inverse exact de `rendre_grille`. Sert à prouver que rien ne se perd."""
    lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
    grille = [[int(valeur) for valeur in ligne.split()] for ligne in lignes]
    valider_grille(grille)
    return grille


def ligne_etat(
    niveau: int, score: int, actions_niveau: int, actions_disponibles: Sequence[str]
) -> str:
    """Ligne d'état, rendue APRÈS la grille (§A4.1, §H15.11)."""
    actions = ",".join(actions_disponibles) or "(aucune)"
    return f"niveau={niveau} score={score} actions_niveau={actions_niveau} actions={actions}"


def rendre_observation(
    grille: Sequence[Sequence[int]],
    niveau: int,
    score: int,
    actions_niveau: int,
    actions_disponibles: Sequence[str],
) -> str:
    """Observation complète : grille exacte puis ligne d'état (§A4.1).

    La ligne d'état SUIT la grille (§H15.11, mesuré le 2026-09-27) : son compteur
    `actions_niveau` change à chaque action valide ; placé avant la grille, il
    invalidait le cache de préfixe de la grille entière à chaque pas.
    """
    etat = ligne_etat(niveau, score, actions_niveau, actions_disponibles)
    return f"{rendre_grille(grille)}\n{etat}"
