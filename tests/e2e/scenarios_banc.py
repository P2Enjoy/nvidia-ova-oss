"""Décor partagé des preuves du banc a : politique parfaite et pas scriptés.

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc` ; U29a4 —
          branchement du Dépôt logiciel (politique parfaite §S4.5)
@verifies docs/SPEC_BANCS.md §S3.5 et §S4.5 (obligations : les politiques
          parfaites les rejouent exactement), §S6.4 (preuves du banc : rejeu
          déterministe, score exact)
@verifies docs/SPEC_HARNAIS.md §H15.8 (forme textuelle du champ `action`),
          §H16.2 et §H16.3 (lignes PREDICTION/VERDICT des pas scriptés)

La politique parfaite suit l'état NOMINAL du générateur (§S3.4) : rangement sur la
plus petite étagère vide, obligations honorées à chaque pas — l'état réel reste
alors identique au nominal, et le score vaut exactement 1. Les réponses scriptées
empruntent l'enveloppe réellement enregistrée sur le vrai endpoint (§H4.7) : aucune
forme n'est inventée.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from avo.bancs.skillexec.depot import (
    AFFECTATION,
    ECHEC_CI,
    REVUE,
    EpisodeDepot,
    nom_branche,
    nom_fichier,
)
from avo.bancs.skillexec.generation import (
    COMMANDE,
    NB_ETAGERES,
    RECEPTION,
    Episode,
    nom_etagere,
)
from tests.e2e.scenarios import ENV_EPINGLE, JETON, gabarit_reponse

__all__ = [
    "ENV_EPINGLE_BANC",
    "HYPOTHESE_DEPOT",
    "JETON",
    "actions_parfaites",
    "actions_parfaites_depot",
    "contenu_pas",
    "gabarit_reponse",
    "reponse_pas",
]

#: Hypothèse des pas scriptés du Dépôt logiciel (§H16.1) — le décor de l'Entrepôt
#: garde la sienne par défaut, la cassette existante restant appariable.
HYPOTHESE_DEPOT = "je tiens l'état exact du dépôt"

#: Environnement épinglé du banc (§A8.5, même principe que `scenarios.ENV_EPINGLE`) :
#: le mode `state` est celui du produit par défaut, épinglé ici pour que la cassette
#: reste appariable quel que soit le `.env` local.
ENV_EPINGLE_BANC: dict[str, str] = {
    **ENV_EPINGLE,
    "AVO_CONTEXT_MODE": "state",
    "AVO_GARDES": "true",
    "AVO_GARDE_RETRIES": "2",
    "AVO_NUM_PREDICT": "4096",
}


def actions_parfaites(episode: Episode) -> list[str]:
    """Le jeu parfait sur un épisode, en textes d'action du mode `state` (§H15.8).

    L'ombre suivie ici applique les mêmes résolutions que l'état nominal du
    générateur (§S3.4) : la divergence est donc nulle et chaque action est
    l'obligation de son événement (§S3.5).
    """
    etageres: dict[str, str] = {}
    actions: list[str] = []
    for evenement in episode.evenements:
        if evenement.type == RECEPTION:
            libre = _plus_petite_vide(etageres)
            etageres[libre] = evenement.article
            actions.append(f"store {evenement.article}, {libre}")
        elif evenement.type == COMMANDE:
            source = next(nom for nom, article in etageres.items() if article == evenement.article)
            del etageres[source]
            actions.append(f"ship {evenement.article}, {source}")
        elif evenement.etagere in etageres:
            # La destination se choisit AVANT de libérer la source (§S3.2 : elle
            # doit être vide au moment du geste), comme le nominal (§S3.4).
            article = etageres[evenement.etagere]
            destination = _plus_petite_vide(etageres)
            del etageres[evenement.etagere]
            etageres[destination] = article
            actions.append(f"move {article}, {evenement.etagere}, {destination}")
        else:
            actions.append("wait")
    return actions


def _plus_petite_vide(etageres: dict[str, str]) -> str:
    for indice in range(NB_ETAGERES):
        nom = nom_etagere(indice)
        if nom not in etageres:
            return nom
    raise AssertionError("aucune étagère vide — épisode impossible sur 500 étagères")


def actions_parfaites_depot(episode: EpisodeDepot) -> list[str]:
    """Le jeu parfait sur un épisode du Dépôt logiciel (§S4.5), textes §H15.8.

    Sous jeu parfait, l'état réel reste identique au nominal : les numéros de PR
    des événements sont exactement ceux que la politique a ouverts, chaque
    obligation est jouable, et `wait` n'est jamais dû.
    """
    actions: list[str] = []
    for evenement in episode.evenements:
        if evenement.type == AFFECTATION:
            actions.append(
                f"commit {nom_branche(evenement.demande)}, {nom_fichier(evenement.demande)}"
            )
        elif evenement.type == REVUE:
            actions.append(f"create_pr {nom_branche(evenement.demande)}")
        elif evenement.type == ECHEC_CI:
            actions.append(f"fix_ci {nom_branche(evenement.demande)}")
        else:
            actions.append(f"merge {evenement.pr}")
    return actions


def contenu_pas(action: str, hypothese: str = "je tiens l'état exact de l'entrepôt") -> str:
    """Le texte d'un pas scripté conforme aux gardes (§H16.2, §H16.3, §H15.1).

    La ligne VERDICT est inutile au premier pas (aucune prédiction antérieure)
    mais inoffensive : le contenu identique à chaque pas garde la génération de
    cassette déterministe (§A8.5).
    """
    charge = {
        "state_patch": {"hypotheses": [hypothese]},
        "action": action,
    }
    return (
        "je joue l'obligation de l'événement courant\n"
        "PREDICTION: je m'attends au succès de l'action annoncée\n"
        "VERDICT: confirmee\n"
        "```json\n" + json.dumps(charge, ensure_ascii=False) + "\n```"
    )


def reponse_pas(
    gabarit: dict[str, Any],
    action: str,
    hypothese: str = "je tiens l'état exact de l'entrepôt",
) -> dict[str, Any]:
    """Un corps de réponse du vrai serveur, au contenu scripté (§H4.7)."""
    reponse = copy.deepcopy(gabarit)
    reponse["message"]["content"] = contenu_pas(action, hypothese)
    reponse["message"].pop("tool_calls", None)
    return reponse
