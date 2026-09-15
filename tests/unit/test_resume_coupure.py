"""Résumé de coupure des réponses tronquées (§H17).

@verifies docs/BACKLOG.md U34 — Résumé de coupure des réponses tronquées
@verifies docs/SPEC_HARNAIS.md §H17.1 (déclenchement sur `length` sans action
          exploitable, dans les deux modes ; non-déclenchement sinon),
          §H17.2 (appel séparé en contexte propre, entrée et sortie bornées,
          dégradation sur erreur du client), §H17.3 (injection en append : canal
          d'erreur du pas suivant en mode `state`, observation du transcript en
          mode `transcript`), §H17.4 (interrupteur `AVO_COUPURE_RESUME`),
          §H17.5 (métriques `coupure` et `llm` phase `resume_coupure`, bilan
          `resumes_coupure`)

Aucun réseau : client au transport scripté (forme des corps §H4.3), environnement
factice minimal.
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
from avo.context.etat import LISTE_CHAINES, ChampEtat, SchemaEtat
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import ENTREE_RESUME_MAX, NUM_PREDICT_RESUME, BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-resume-coupure",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            # U37 : mécanismes H18 hors du périmètre de ces tests — épinglés
            # inactifs pour garder les séquences d'appels scriptées exactes.
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _EnvironnementFactice:
    """Environnement minimal : une action, jamais terminal."""

    def __init__(self) -> None:
        self.jouees: list[str] = []
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"observation-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees.append("avance")
        self._derniere = _Issue(f"observation-{len(self.jouees)}", Evenement.PREDICTION_CONFIRMEE)
        return "action jouée"


class _TransportScripte:
    """Sert des réponses (dictionnaires ou statuts d'erreur) dans l'ordre."""

    def __init__(self, reponses: list[Any]) -> None:
        self.reponses = list(reponses)
        self.corps: list[dict[str, Any]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        self.corps.append(json.loads(corps))
        reponse = self.reponses.pop(0)
        if isinstance(reponse, int):
            return ReponseHTTP(reponse, b'{"error": "panne scriptee"}')
        return ReponseHTTP(200, json.dumps(reponse).encode())


def _reponse(
    contenu: str,
    done_reason: str = "stop",
    reasoning: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": contenu}
    if reasoning:
        message["thinking"] = reasoning
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "message": message,
        "done_reason": done_reason,
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


def _pas_valide(action: str = "avance") -> dict[str, Any]:
    bloc = json.dumps({"state_patch": {"hypotheses": ["h"]}, "action": action})
    return _reponse(f"```json\n{bloc}\n```")


_SCHEMA = SchemaEtat(
    "test-coupure-v1",
    (ChampEtat("hypotheses", LISTE_CHAINES, "ce que tu tiens pour vrai"),),
)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(
        self, reponses: list[Any], **env: str
    ) -> tuple[BoucleAgent, _EnvironnementFactice, Workspace, _TransportScripte]:
        config = _config(**env)
        environnement = _EnvironnementFactice()
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
        workspace = Workspace.ouvrir(config, "run-coupure", racine=self.racine)
        transport = _TransportScripte(reponses)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
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
        return boucle, environnement, workspace, transport

    def _metriques(self, workspace: Workspace, type_evenement: str) -> list[dict[str, Any]]:
        return [
            dict(ligne)
            for ligne in workspace.lire_metriques()
            if ligne.get("type") == type_evenement
        ]


class TestDeclenchementModeEtat(_Base):
    """§H17.1 : en mode `state`, une réponse tronquée qui échoue au décodage."""

    def test_tronquee_sans_bloc_resume_puis_retente_avec_le_resume(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("raisonnement coupé net", done_reason="length"),
                _reponse("Approche : X. Acquis : Y. Reste : Z."),
                _pas_valide(),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance", "le pas rejoué aboutit")
        self.assertEqual(boucle.bilan.resumes_coupure, 1)
        # L'appel de résumé est en contexte propre et borné (§H17.2).
        corps_resume = transport.corps[1]
        self.assertEqual(corps_resume["messages"][0]["content"], prompts.SYSTEME_RESUME_COUPURE)
        self.assertEqual(len(corps_resume["messages"]), 2)
        self.assertNotIn("tools", corps_resume)
        self.assertEqual(corps_resume["options"]["num_predict"], NUM_PREDICT_RESUME)
        # Le pas suivant lit l'erreur nommée PUIS le résumé (§H17.3, §H16.0.6).
        message_retente = transport.corps[2]["messages"][1]["content"]
        self.assertIn("Ta réponse précédente était invalide", message_retente)
        self.assertIn("Approche : X. Acquis : Y. Reste : Z.", message_retente)
        self.assertIn("approche plus courte", message_retente)
        # Comptabilité (§H17.5).
        coupures = self._metriques(workspace, "coupure")
        self.assertEqual(len(coupures), 1)
        self.assertEqual(coupures[0]["mode"], "state")
        self.assertTrue(coupures[0]["resume"])
        self.assertGreater(coupures[0]["caracteres_resume"], 0)
        lignes_llm = self._metriques(workspace, "llm")
        self.assertIn("resume_coupure", [ligne.get("phase") for ligne in lignes_llm])

    def test_invalide_mais_non_tronquee_ne_resume_pas(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("pas de bloc json ici", done_reason="stop"),
                _pas_valide(),
            ]
        )
        boucle.jouer_tour(1)
        self.assertEqual(len(transport.corps), 2, "aucun appel de résumé émis")
        self.assertEqual(boucle.bilan.resumes_coupure, 0)
        self.assertEqual(self._metriques(workspace, "coupure"), [])

    def test_tronquee_avec_bloc_exploitable_ne_resume_pas(self) -> None:
        tronquee_mais_complete = _pas_valide()
        tronquee_mais_complete["done_reason"] = "length"
        boucle, _env, workspace, transport = self._boucle([tronquee_mais_complete])
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance", "l'action tronquée mais décodable est jouée")
        self.assertEqual(len(transport.corps), 1, "aucun appel de résumé émis")
        self.assertEqual(boucle.bilan.resumes_coupure, 0)

    def test_interrupteur_a_false_ne_resume_pas(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("raisonnement coupé net", done_reason="length"),
                _pas_valide(),
            ],
            AVO_COUPURE_RESUME="false",
        )
        boucle.jouer_tour(1)
        self.assertEqual(len(transport.corps), 2, "aucun appel de résumé émis (§H17.4)")
        self.assertEqual(boucle.bilan.resumes_coupure, 0)
        self.assertEqual(self._metriques(workspace, "coupure"), [])


class TestAppelDeResume(_Base):
    """§H17.2 : bornes de l'appel et dégradation sur erreur du client."""

    def test_l_entree_est_bornee_tete_et_queue(self) -> None:
        tete = "DEBUT-" + "a" * ENTREE_RESUME_MAX
        queue = "z" * 100 + "-FIN"
        boucle, _env, _workspace, transport = self._boucle(
            [
                _reponse(tete + queue, done_reason="length"),
                _reponse("résumé court"),
                _pas_valide(),
            ]
        )
        boucle.jouer_tour(1)
        entree = transport.corps[1]["messages"][1]["content"]
        self.assertLessEqual(len(entree), ENTREE_RESUME_MAX + len(prompts.MARQUEUR_COUPE_RESUME))
        self.assertIn(prompts.MARQUEUR_COUPE_RESUME, entree)
        self.assertTrue(entree.startswith("DEBUT-"), "la tête est conservée")
        self.assertTrue(entree.endswith("-FIN"), "la queue est conservée")

    def test_une_panne_serveur_degrade_sans_bloquer_le_pas(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("raisonnement coupé net", done_reason="length"),
                # L'appel de résumé meurt en 500, retries du client compris (§H4.5).
                500,
                500,
                500,
                500,
                500,
                500,
                _pas_valide(),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance", "le pas rejoué aboutit malgré la dégradation")
        self.assertEqual(boucle.bilan.resumes_coupure, 0)
        coupures = self._metriques(workspace, "coupure")
        self.assertEqual(len(coupures), 1)
        self.assertFalse(coupures[0]["resume"])
        self.assertEqual(coupures[0]["erreur"], "ServerError")
        message_retente = transport.corps[-1]["messages"][1]["content"]
        self.assertNotIn("approche plus courte", message_retente)

    def test_un_resume_vide_degrade_avec_son_motif(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("raisonnement coupé net", done_reason="length"),
                _reponse("   "),
                _pas_valide(),
            ]
        )
        boucle.jouer_tour(1)
        self.assertEqual(boucle.bilan.resumes_coupure, 0)
        coupures = self._metriques(workspace, "coupure")
        self.assertEqual(len(coupures), 1)
        self.assertFalse(coupures[0]["resume"])
        self.assertEqual(coupures[0]["erreur"], "resume_vide")


class TestDeclenchementModeTranscript(_Base):
    """§H17.1 : en mode `transcript`, Implementation tronquée sans appel d'action."""

    def test_implementation_tronquee_sans_action_injecte_le_resume(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("je planifie"),
                _reponse("je voulais agir mais", done_reason="length"),
                _reponse("Approche : X. Acquis : Y. Reste : Z."),
            ],
            AVO_CONTEXT_MODE="transcript",
        )
        tour = boucle.jouer_tour(1)
        self.assertIsNone(tour.action, "le tour n'a pas agi")
        self.assertEqual(boucle.bilan.resumes_coupure, 1)
        messages = boucle.contexte.transcript.pour_api()
        dernier = messages[-1]["content"]
        self.assertIn("Approche : X. Acquis : Y. Reste : Z.", dernier)
        self.assertIn("approche plus courte", dernier)
        coupures = self._metriques(workspace, "coupure")
        self.assertEqual(len(coupures), 1)
        self.assertEqual(coupures[0]["mode"], "transcript")

    def test_implementation_tronquee_avec_action_ne_resume_pas(self) -> None:
        boucle, _env, _workspace, transport = self._boucle(
            [
                _reponse("je planifie"),
                _reponse(
                    "j'agis",
                    done_reason="length",
                    tool_calls=[{"function": {"name": "avance", "arguments": {}}}],
                ),
                _reponse("j'évalue : conforme"),
            ],
            AVO_CONTEXT_MODE="transcript",
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance", "l'action tronquée mais présente est jouée")
        self.assertEqual(boucle.bilan.resumes_coupure, 0)
        self.assertEqual(len(transport.corps), 3, "aucun appel de résumé émis")

    def test_implementation_sans_action_ni_troncature_ne_resume_pas(self) -> None:
        boucle, _env, workspace, transport = self._boucle(
            [
                _reponse("je planifie"),
                _reponse("je ne fais rien", done_reason="stop"),
            ],
            AVO_CONTEXT_MODE="transcript",
        )
        tour = boucle.jouer_tour(1)
        self.assertIsNone(tour.action)
        self.assertEqual(len(transport.corps), 2, "aucun appel de résumé émis")
        self.assertEqual(self._metriques(workspace, "coupure"), [])


class TestBilan(_Base):
    """§H17.5 : le bilan expose le compteur, à zéro par défaut."""

    def test_le_resume_du_bilan_porte_le_compteur(self) -> None:
        boucle, _env, _workspace, _transport = self._boucle([_pas_valide()])
        boucle.jouer_tour(1)
        self.assertEqual(boucle.bilan.resume()["resumes_coupure"], 0)


if __name__ == "__main__":
    unittest.main()
