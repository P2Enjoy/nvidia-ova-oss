"""Métrique `prefixe_pas` : préfixe commun et partie de divergence du message de pas (§H11.2).

@verifies docs/BACKLOG.md U31 — métrique `prefixe_pas`, lecture hors ligne du froid
          de préremplissage que `prefill_ms` ne rend pas sous coupure du pont
@verifies docs/SPEC_HARNAIS.md §H11.2 (`prefixe_pas` : `caracteres`, `prefixe_commun`,
          `divergence` ∈ {tete, notes, observation, etat, protocole, aucune, premier} ;
          une métrique par message composé, relances comprises ; aucun contenu
          journalisé), §H15.11 (ordre notes → observation → Σ → protocole ; la
          divergence d'un pas à observation inchangée tombe dans Σ ; l'erreur nommée
          d'un pas refusé porte la divergence en tête)

Aucun réseau : transport scripté, workspace en répertoire temporaire pour lire
`metrics.jsonl`. Les fonctions pures sont éprouvées directement (nominal, limites).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.boucle import BoucleAgent
from avo.loop.prefixe import (
    AUCUNE,
    PREMIER,
    TETE,
    longueur_prefixe_commun,
    mesurer_prefixe,
    partie_de,
)
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils

REPERES = {"notes": 10, "observation": 40, "etat": 100, "protocole": 130}


class TestFonctionsPures(unittest.TestCase):
    def test_longueur_du_prefixe_commun(self) -> None:
        self.assertEqual(longueur_prefixe_commun("abcdef", "abcxyz"), 3)
        self.assertEqual(longueur_prefixe_commun("abc", "abc"), 3)
        self.assertEqual(longueur_prefixe_commun("abc", "abcdef"), 3)
        self.assertEqual(longueur_prefixe_commun("", "abc"), 0)
        self.assertEqual(longueur_prefixe_commun("xbc", "abc"), 0)

    def test_partie_de_chaque_offset(self) -> None:
        self.assertEqual(partie_de(0, REPERES), TETE)
        self.assertEqual(partie_de(9, REPERES), TETE)
        self.assertEqual(partie_de(10, REPERES), "notes")
        self.assertEqual(partie_de(39, REPERES), "notes")
        self.assertEqual(partie_de(40, REPERES), "observation")
        self.assertEqual(partie_de(100, REPERES), "etat")
        self.assertEqual(partie_de(129, REPERES), "etat")
        self.assertEqual(partie_de(130, REPERES), "protocole")
        self.assertEqual(partie_de(10_000, REPERES), "protocole")

    def test_mesure_premier_message(self) -> None:
        self.assertEqual(
            mesurer_prefixe(None, "x" * 200, REPERES),
            {"caracteres": 200, "prefixe_commun": 0, "divergence": PREMIER},
        )

    def test_mesure_message_identique(self) -> None:
        m = "x" * 200
        self.assertEqual(
            mesurer_prefixe(m, m, REPERES),
            {"caracteres": 200, "prefixe_commun": 200, "divergence": AUCUNE},
        )

    def test_mesure_divergence_dans_une_partie(self) -> None:
        precedent = "x" * 200
        courant = "x" * 105 + "y" + "x" * 94
        self.assertEqual(
            mesurer_prefixe(precedent, courant, REPERES),
            {"caracteres": 200, "prefixe_commun": 105, "divergence": "etat"},
        )

    def test_un_prefixe_strict_diverge_a_sa_fin(self) -> None:
        # Le courant prolonge le précédent : la divergence est à la longueur du
        # précédent, jamais « aucune » — le cache s'arrête là.
        precedent = "x" * 50
        courant = "x" * 60
        self.assertEqual(
            mesurer_prefixe(precedent, courant, REPERES),
            {"caracteres": 60, "prefixe_commun": 50, "divergence": "observation"},
        )


# ------------------------------------------------------------- dans la boucle


def _config() -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "cle-de-test",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
        },
        racine=Path("/inexistant"),
    )


class _EnvironnementImmobile:
    def __init__(self) -> None:
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


def _reponse(contenu: str) -> dict[str, Any]:
    return {
        "message": {"role": "assistant", "content": contenu},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


def _pas(patch: dict[str, Any]) -> dict[str, Any]:
    bloc = json.dumps({"state_patch": patch, "action": "avance"})
    return _reponse(f"réflexion\n```json\n{bloc}\n```")


class TestMetriquePrefixePas(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        racine = Path(self._dossier.name)
        self.notes = Notes(racine / "notes")
        self.workspace = Workspace.ouvrir(_config(), "run-test", racine=racine / "runs")
        self.environnement = _EnvironnementImmobile()

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _registre(self) -> RegistreOutils:
        return RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement",
                    parametres={"type": "object", "properties": {}},
                    fonction=lambda: "action jouée",
                    etiquettes=frozenset({"action"}),
                )
            ]
        )

    def _boucle(self, reponses: list[dict[str, Any]]) -> tuple[BoucleAgent, _TransportScripte]:
        config = _config()
        transport = _TransportScripte(reponses)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        boucle = BoucleAgent(
            config,
            client,
            self._registre(),
            self.environnement,
            self.notes,
            workspace=self.workspace,
            jeu="jeu-test",
        )
        return boucle, transport

    def _prefixes(self) -> list[dict[str, Any]]:
        return [m for m in self.workspace.lire_metriques() if m["type"] == "prefixe_pas"]

    def test_une_metrique_par_message_compose(self) -> None:
        boucle, transport = self._boucle(
            [_pas({"hypotheses": ["h1"]}), _pas({"hypotheses": ["h1", "h2"]})]
        )
        boucle.jouer_tour(1)
        boucle.jouer_tour(2)
        prefixes = self._prefixes()
        self.assertEqual(len(prefixes), 2)
        premier, second = prefixes
        self.assertEqual(premier["divergence"], PREMIER)
        self.assertEqual(premier["prefixe_commun"], 0)
        self.assertEqual(premier["caracteres"], len(transport.invite(0)))
        # Notes et observation inchangées : la divergence tombe dans Σ, et le
        # préfixe commun couvre exactement le message jusqu'au bloc Σ (§H15.11).
        self.assertEqual(second["divergence"], "etat")
        self.assertEqual(second["caracteres"], len(transport.invite(1)))
        marque = "État courant (Σ) :"
        self.assertGreaterEqual(second["prefixe_commun"], transport.invite(1).index(marque))
        self.assertLess(second["prefixe_commun"], second["caracteres"])
        self.assertEqual(premier["jeu"], "jeu-test")
        # Aucun contenu dans la métrique : des longueurs et un nom de partie.
        self.assertEqual(
            set(premier) - {"horodatage", "type", "jeu"},
            {"caracteres", "prefixe_commun", "divergence"},
        )

    def test_la_relance_d_un_pas_refuse_diverge_en_tete(self) -> None:
        boucle, transport = self._boucle(
            [_reponse("pas de bloc json ici"), _pas({"hypotheses": ["h1"]})]
        )
        boucle.jouer_tour(1)
        prefixes = self._prefixes()
        self.assertEqual(len(prefixes), 2, "une métrique par message, relance comprise")
        self.assertEqual(prefixes[1]["divergence"], TETE)
        # Le préfixe commun s'arrête dans la tête, avant les notes (§H15.11 : la
        # relance repaie l'erreur nommée, puis retrouve le contenu recomposé).
        self.assertLess(prefixes[1]["prefixe_commun"], transport.invite(1).index("Tes notes"))
        self.assertTrue(transport.invite(1).startswith("Ta réponse précédente était invalide"))


if __name__ == "__main__":
    unittest.main()
