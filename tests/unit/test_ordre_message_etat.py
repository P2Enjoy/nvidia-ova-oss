"""Preuves de l'ordre du message composé d'un pas du mode `state` (§H15.11).

@verifies docs/BACKLOG.md U31 — ordre du message composé : notes, observation,
          Σ, protocole ; messages exceptionnels en tête
@verifies docs/SPEC_HARNAIS.md §H15.11 (le moins volatil d'abord, Σ en queue ;
          invariant : préfixe identique jusqu'à Σ entre deux pas dont notes et
          observation sont identiques ; le protocole reste adjacent à la
          réponse ; l'erreur nommée d'un pas refusé garde la tête, §H16.0.6)
@verifies docs/SPEC_HARNAIS.md §H15.8 (un pas = un tour, message utilisateur
          composé de Σ, des notes, de l'observation, des actions et du protocole)

Le transport du client est injecté (aucun réseau, aucune cassette) : chaque test
scripte les réponses du modèle et lit le message utilisateur réellement émis.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.memory.notes import Notes
from avo.tools.registre import Outil, RegistreOutils

CLE = "cle-de-test"


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": CLE,
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


class _EnvironnementImmobile:
    """Environnement dont l'observation ne change pas : le cas « observation
    inchangée » (~25 % des pas mesurés en campagne, §H15.11)."""

    def __init__(self) -> None:
        self.jouees: list[str] = []
        self._derniere: Any = None

    def observation(self) -> str:
        return "grille-fixe"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> Any:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self, action: str, **parametres: Any) -> Any:
        self.jouees.append(action)
        return None


class _TransportScripte:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)
        self.corps_emis: list[dict[str, Any]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        self.corps_emis.append(json.loads(corps))
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())

    def invite(self, rang: int) -> str:
        return str(self.corps_emis[rang]["messages"][-1]["content"])


def _pas(patch: dict[str, Any], action: str = "avance") -> dict[str, Any]:
    bloc = json.dumps({"state_patch": patch, "action": action})
    return {
        "message": {"role": "assistant", "content": f"réflexion\n```json\n{bloc}\n```"},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


class TestOrdreMessageEtat(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")
        self.environnement = _EnvironnementImmobile()

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _registre(self) -> RegistreOutils:
        def avance() -> str:
            self.environnement.jouer("avance")
            return "action jouée"

        return RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement",
                    parametres={"type": "object", "properties": {}},
                    fonction=avance,
                    etiquettes=frozenset({"action"}),
                )
            ]
        )

    def _boucle(self, reponses: list[dict[str, Any]]) -> tuple[BoucleAgent, _TransportScripte]:
        config = _config()
        transport = _TransportScripte(reponses)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        return (
            BoucleAgent(config, client, self._registre(), self.environnement, self.notes),
            transport,
        )

    def test_l_ordre_est_notes_observation_sigma_protocole(self) -> None:
        boucle, transport = self._boucle([_pas({"hypotheses": ["h1"]})])
        boucle.jouer_tour(1)
        invite = transport.invite(0)
        positions = [
            invite.index("Observation :\ngrille-fixe"),
            invite.index("Actions disponibles :"),
            invite.index("État courant (Σ) :"),
            invite.index(prompts.PROTOCOLE_ETAT_FORMAT),
        ]
        self.assertEqual(positions, sorted(positions), "notes → observation → Σ → protocole")
        # Le protocole reste adjacent à la réponse : rien ne le suit (§H16.0.7).
        self.assertTrue(invite.endswith(prompts.protocole_etat(boucle._schema_effectif)))

    def test_le_prefixe_jusqu_a_sigma_est_identique_entre_deux_pas(self) -> None:
        # Deux pas à notes et observation identiques : Σ change (patch appliqué),
        # le préfixe jusqu'à Σ est identique octet à octet (§H15.11).
        boucle, transport = self._boucle(
            [_pas({"hypotheses": ["h1"]}), _pas({"hypotheses": ["h1", "h2"]})]
        )
        boucle.jouer_tour(1)
        boucle.jouer_tour(2)
        premier, second = transport.invite(0), transport.invite(1)
        self.assertNotEqual(premier, second, "Σ a changé entre les deux pas")
        marque = "État courant (Σ) :"
        self.assertEqual(premier.split(marque)[0], second.split(marque)[0])
        # Le second pas lit le Σ issu du premier patch ; le premier lisait Σ₀.
        self.assertIn('"h1"', second.split(marque)[1])
        self.assertNotIn('"h1"', premier)

    def test_l_erreur_nommee_garde_la_tete_du_message(self) -> None:
        # §H16.0.6 : la primauté de l'erreur est inchangée par §H15.11 ; la
        # relance porte le même préfixe après elle (même Σ, même observation).
        invalide = {
            "message": {"role": "assistant", "content": "pas de bloc json ici"},
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 5,
            "total_duration": 1_000_000,
        }
        boucle, transport = self._boucle([invalide, _pas({"hypotheses": ["h1"]})])
        boucle.jouer_tour(1)
        premier, relance = transport.invite(0), transport.invite(1)
        self.assertTrue(relance.startswith("Ta réponse précédente était invalide"))
        self.assertTrue(relance.endswith(premier), "le contenu recomposé suit l'erreur, inchangé")


if __name__ == "__main__":
    unittest.main()
