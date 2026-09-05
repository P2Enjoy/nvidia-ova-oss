"""Métrique `observation_inchangee` : la mesure du non-progrès, sans effet (§H11.2).

@verifies docs/BACKLOG.md U31 — amélioration générique sur mesures (journal
          2026-09-05, suites 43–46 : le non-progrès est le candidat désigné par
          la campagne U25 tranche 1, immesurable post-hoc — cette métrique est
          la mesure préalable exigée par la règle U31)
@verifies docs/SPEC_HARNAIS.md §H11.2 (métrique émise après chaque action VALIDE
          dont l'observation rendue est strictement identique à celle d'avant
          l'action ; action refusée exclue ; aucun effet sur le comportement)

Aucun réseau : client au transport scripté, environnement factice dont
l'observation change — ou non — après une action.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.context.contexte import Contexte
from avo.context.etat import LISTE_CHAINES, POSITION, ChampEtat, SchemaEtat
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-observation",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement
    refusee: bool = False


class _EnvironnementImmobile:
    """Environnement factice : l'observation ne change jamais, sauf demande."""

    def __init__(self, observation_change: bool, refuse: bool = False) -> None:
        self.observation_change = observation_change
        self.refuse = refuse
        self.jouees = 0
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        if self.observation_change:
            return f"observation-{self.jouees}"
        return "observation-fixe"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees += 1
        self._derniere = _Issue(
            "action refusée." if self.refuse else "action jouée.",
            Evenement.PREDICTION_CONFIRMEE,
            refusee=self.refuse,
        )
        return self._derniere.observation


class _TransportScripte:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())


def _pas(action: str = "avance") -> dict[str, Any]:
    bloc = json.dumps({"state_patch": {"hypotheses": ["h"]}, "action": action})
    return {
        "message": {"role": "assistant", "content": f"```json\n{bloc}\n```"},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


_SCHEMA = SchemaEtat(
    "test-observation-v1",
    (
        ChampEtat("hypotheses", LISTE_CHAINES, "ce que tu tiens pour vrai"),
        ChampEtat("position", POSITION, "où tu en es"),
    ),
)


class TestObservationInchangee(unittest.TestCase):
    """§H11.2 : la métrique s'émet quand — et seulement quand — rien n'a changé."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.addCleanup(self._dossier.cleanup)

    def _jouer_un_tour(self, environnement: _EnvironnementImmobile) -> list[dict[str, Any]]:
        config = _config()
        registre = RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement.",
                    parametres={"type": "object", "properties": {}},
                    fonction=environnement.jouer,
                    etiquettes=frozenset({"action"}),
                )
            ]
        )
        workspace = Workspace.ouvrir(config, "run-test-observation", racine=self.racine)
        client = LLMClient(config, transport=_TransportScripte([_pas()]), dormir=lambda _: None)
        contexte = Contexte(config=config, systeme=prompts.SYSTEME, schema_etat=_SCHEMA)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            environnement,
            Notes(self.racine / "notes"),
            contexte=contexte,
            workspace=workspace,
        )
        boucle.jouer_tour(1)
        chemin = workspace.chemin / "metrics.jsonl"
        lignes = [json.loads(ligne) for ligne in chemin.read_text().splitlines()]
        return [ligne for ligne in lignes if ligne.get("type") == "observation_inchangee"]

    def test_observation_identique_emet_la_metrique(self) -> None:
        metriques = self._jouer_un_tour(_EnvironnementImmobile(observation_change=False))
        self.assertEqual(len(metriques), 1)
        self.assertEqual(metriques[0]["action"], "avance")
        self.assertEqual(metriques[0]["tour"], 1)

    def test_observation_changee_n_emet_rien(self) -> None:
        metriques = self._jouer_un_tour(_EnvironnementImmobile(observation_change=True))
        self.assertEqual(metriques, [])

    def test_action_refusee_n_emet_rien(self) -> None:
        """Une action refusée laisse l'observation inchangée par nature : son
        refus porte déjà sa métrique, la compter ici doublerait la mesure."""
        metriques = self._jouer_un_tour(
            _EnvironnementImmobile(observation_change=False, refuse=True)
        )
        self.assertEqual(metriques, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
