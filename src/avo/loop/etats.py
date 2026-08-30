"""Machine d'états de la boucle agent : Planning → Implementation → Evaluation → Bug-Fixing.

@spec docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@spec docs/SPEC_HARNAIS.md §H8.1 (états et transitions pilotées par les événements)

La machine est du **code** : les transitions sont déterministes et pilotées par des
événements observables. Le contenu des phases, lui, est du prompt (`prompts.py`).
Cette séparation est délibérée : une transition qui dépendrait de l'interprétation
d'un texte libre serait irreproductible, et un run ne pourrait plus être rejoué.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Phase(StrEnum):
    """Les quatre états de la boucle (§H8.1)."""

    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    EVALUATION = "evaluation"
    BUG_FIXING = "bug_fixing"


class Evenement(StrEnum):
    """Ce qui fait avancer la machine. Tous observables, aucun interprété."""

    #: L'agent a annoncé son action et sa prédiction.
    ACTION_CHOISIE = "action_choisie"
    #: Une action d'environnement a été jouée et une observation est revenue.
    ACTION_JOUEE = "action_jouee"
    #: L'observation est conforme à la prédiction annoncée.
    PREDICTION_CONFIRMEE = "prediction_confirmee"
    #: L'agent a déclaré sa prédiction contredite.
    CONTRADICTION = "contradiction"
    #: Le niveau vient d'être complété.
    NIVEAU_COMPLETE = "niveau_complete"
    #: La tentative est perdue.
    GAME_OVER = "game_over"
    #: Les hypothèses ont été révisées.
    REVISION_FAITE = "revision_faite"


class TransitionInterdite(RuntimeError):
    """Événement impossible dans l'état courant : la machine refuse de deviner."""


#: Table des transitions (§H8.1). Exhaustive et close : tout couple absent est une
#: erreur explicite, jamais un état de repli silencieux.
TRANSITIONS: Final[dict[tuple[Phase, Evenement], Phase]] = {
    (Phase.PLANNING, Evenement.ACTION_CHOISIE): Phase.IMPLEMENTATION,
    (Phase.IMPLEMENTATION, Evenement.ACTION_JOUEE): Phase.EVALUATION,
    # Après évaluation : on repart planifier, sauf incident.
    (Phase.EVALUATION, Evenement.PREDICTION_CONFIRMEE): Phase.PLANNING,
    (Phase.EVALUATION, Evenement.NIVEAU_COMPLETE): Phase.PLANNING,
    (Phase.EVALUATION, Evenement.CONTRADICTION): Phase.BUG_FIXING,
    (Phase.EVALUATION, Evenement.GAME_OVER): Phase.BUG_FIXING,
    # Le bug-fixing ne joue pas : il révise, puis rend la main à la planification.
    (Phase.BUG_FIXING, Evenement.REVISION_FAITE): Phase.PLANNING,
}

#: Événements terminaux d'un tour : ils closent l'évaluation d'une manière ou d'une
#: autre. Sert aux bilans et aux métriques.
EVENEMENTS_DE_TOUR: Final = (
    Evenement.PREDICTION_CONFIRMEE,
    Evenement.CONTRADICTION,
    Evenement.NIVEAU_COMPLETE,
    Evenement.GAME_OVER,
)


def suivant(phase: Phase, evenement: Evenement) -> Phase:
    """Rend la phase suivante, ou lève en nommant le couple refusé.

    Lever plutôt que rester sur place : une transition impossible signale un défaut
    de la boucle, et l'absorber produirait un run qui tourne sans avancer.
    """
    try:
        return TRANSITIONS[(phase, evenement)]
    except KeyError as erreur:
        permis = sorted(evt.value for (etat, evt) in TRANSITIONS if etat is phase)
        raise TransitionInterdite(
            f"événement « {evenement.value} » impossible depuis la phase "
            f"« {phase.value} » ; événements admis : {', '.join(permis) or 'aucun'} "
            "(docs/SPEC_HARNAIS.md §H8.1)."
        ) from erreur


def evenements_admis(phase: Phase) -> tuple[Evenement, ...]:
    """Événements que la machine accepte dans cet état."""
    return tuple(evt for (etat, evt) in TRANSITIONS if etat is phase)
