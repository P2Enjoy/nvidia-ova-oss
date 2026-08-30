"""Décor partagé des E2E : scénarios scriptés, environnement épinglé, politique.

@spec docs/BACKLOG.md U21
@spec docs/SPEC_ARCAGI3.md §A8.5 (contrat d'implémentation des E2E), §A8.3
@spec docs/SPEC_ARCAGI3.md §A3.2 (chemin optimal du jeu `cible`, outil de test)
@spec docs/SPEC_HARNAIS.md §H4.7 (enveloppe de réponse prise dans la cassette réelle)

Ce module est importé par le générateur de cassettes ET par les tests : les deux
doivent partager à l'octet près l'environnement épinglé et la politique scriptée,
sans quoi l'appariement par empreinte du rejoueur échouerait (§A8.5).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arc_replay.jeu_cible import CLIC, DEPART, EtatPartie, JeuCible
from avo.loop import prompts
from llm_replay.cassette import Cassette

#: Jeu servi par arc-replay (§A3.2).
JEU = "cible-synthetique"

#: Jeton de rejeu : n'est pas un secret, la nature d'authentification seule compte.
JETON = "sk-jeton-de-rejeu-e2e"

#: Cassette réelle du contrat : source de l'enveloppe de réponse (§H4.7).
CASSETTE_CONTRAT = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")

#: Dossier des cassettes servies par la pile compose.
DOSSIER_CASSETTES = Path("tests/fixtures/llm/cassettes")

#: Environnement épinglé (§A8.5) : tous les champs qui entrent dans les corps de
#: requête ou gouvernent le déroulé, fixés pour neutraliser tout `.env` local.
ENV_EPINGLE: dict[str, str] = {
    "OLLAMA_CONTEXT_LENGTH": "229376",
    "AVO_MODEL": "qwen3.6:35b",
    "AVO_THINK": "false",
    "AVO_TEMPERATURE": "0.7",
    "AVO_CONTEXT_SOFT_RATIO": "0.85",
    "AVO_TOOL_STEPS_MAX": "40",
    "AVO_SUP_STALL_ACTIONS": "60",
    "AVO_SUP_COOLDOWN": "30",
}

#: Plafonds communs aux deux scénarios : au-dessus des 80 actions du plus long.
PLAFONDS_CLI = ("--tours-max", "120", "--actions-max-niveau", "100", "--actions-max-jeu", "200")

#: Clic hors cible à coup sûr : le curseur y démarre, aucune cible n'y est (§A3.2).
CLIC_MANQUE = {"row": DEPART[0], "col": DEPART[1]}

Outil = tuple[str, dict[str, Any]]


def _outil(action: str, ligne: int | None, colonne: int | None) -> Outil:
    """Traduit une action du moteur en appel d'outil de l'interface (§A5)."""
    if action == CLIC:
        return ("action6", {"row": ligne, "col": colonne})
    return (action.lower(), {})


def _chemin_parfait(moteur: JeuCible) -> list[Outil]:
    """Rejoue `chemin_optimal()` niveau après niveau jusqu'à la victoire."""
    suite: list[Outil] = []
    for _ in range(moteur.niveaux):
        for action, ligne, colonne in moteur.chemin_optimal():
            suite.append(_outil(action, ligne, colonne))
            moteur.jouer(action, ligne, colonne)
    if moteur.etat is not EtatPartie.GAGNEE:
        raise AssertionError("le chemin parfait devait gagner la partie")
    return suite


def actions_victoire() -> list[Outil]:
    """Partie parfaite : exactement la somme des baselines (§A8.5)."""
    moteur = JeuCible()
    moteur.reset()
    return _chemin_parfait(moteur)


def actions_echec_puis_victoire() -> list[Outil]:
    """Trois clics manqués → GAME_OVER, RESET compté, puis partie parfaite."""
    moteur = JeuCible()
    moteur.reset()
    suite: list[Outil] = []
    for _ in range(3):
        suite.append(("action6", dict(CLIC_MANQUE)))
        moteur.jouer(CLIC, CLIC_MANQUE["row"], CLIC_MANQUE["col"])
    if moteur.etat is not EtatPartie.PERDUE:
        raise AssertionError("trois clics manqués devaient perdre la tentative")
    suite.append(("reset", {}))
    moteur.reset()
    return suite + _chemin_parfait(moteur)


@dataclass(frozen=True)
class Scenario:
    """Un scénario E2E : sa cassette, son discriminant, sa suite d'actions."""

    nom: str
    cassette: str
    #: Discriminant de scénario (§A8.5) : rend les corps des deux scénarios
    #: disjoints dans le dossier de cassettes fusionné.
    num_predict: str
    actions: tuple[Outil, ...]
    actions_attendues: int
    niveaux_attendus: tuple[int, ...]

    def environnement(self, hote_llm: str, base_arc: str) -> dict[str, str]:
        """Variables communes générateur/tests, endpoints inclus."""
        return {
            **ENV_EPINGLE,
            "AVO_NUM_PREDICT": self.num_predict,
            "OLLAMA_HOST": hote_llm,
            "OLLAMA_API_KEY": JETON,
            "ARC_BASE_URL": base_arc,
        }


VICTOIRE = Scenario(
    nom="victoire",
    cassette="e2e_victoire.jsonl",
    num_predict="4096",
    actions=tuple(actions_victoire()),
    actions_attendues=76,
    niveaux_attendus=(39, 19, 18),
)

ECHEC = Scenario(
    nom="echec",
    cassette="e2e_echec.jsonl",
    num_predict="4097",
    actions=tuple(actions_echec_puis_victoire()),
    actions_attendues=80,
    niveaux_attendus=(43, 19, 18),
)

SCENARIOS = (VICTOIRE, ECHEC)


def gabarit_reponse() -> dict[str, Any]:
    """Enveloppe de réponse réelle : première conversation 200 de la cassette du
    contrat. Aucune forme n'est inventée (§H4.7)."""
    for echange in Cassette.lire(CASSETTE_CONTRAT):
        corps = echange.response.body
        if echange.response.status == 200 and isinstance(corps, dict) and "message" in corps:
            return copy.deepcopy(corps)
    raise AssertionError(
        "aucune réponse de conversation dans la cassette du contrat — lancer « make record-llm »"
    )


def repondre(
    gabarit: dict[str, Any], charge: dict[str, Any], rang: int, scenario: Scenario
) -> tuple[dict[str, Any], bool]:
    """Politique scriptée : une action du scénario par prompt d'Implementation,
    un constat textuel partout ailleurs. Rend (réponse, le rang avance)."""
    reponse = copy.deepcopy(gabarit)
    if prompts.IMPLEMENTATION in charge["messages"][-1]["content"]:
        nom, arguments = scenario.actions[min(rang, len(scenario.actions) - 1)]
        reponse["message"]["content"] = "je joue la commande prévue par le scénario"
        reponse["message"]["tool_calls"] = [{"function": {"name": nom, "arguments": arguments}}]
        return reponse, True
    reponse["message"]["content"] = "j'observe la grille et je consigne ce que je vois"
    reponse["message"].pop("tool_calls", None)
    return reponse, False
