"""Le résumé de coupure de bout en bout, contre le rejeu HTTP réel (§H17).

@verifies docs/BACKLOG.md U34 — Résumé de coupure des réponses tronquées
@verifies docs/SPEC_HARNAIS.md §H17.1 (déclenchement sur `length` sans bloc
          exploitable en mode `state`), §H17.2 (appel de résumé séparé, servi par
          le même endpoint), §H17.3 (le résumé figure dans le corps de l'appel
          suivant), §H17.5 (métrique `coupure` écrite dans le workspace)

Même principe à deux passes que `test_boucle_etat.py` : les réponses du modèle
sont scriptées (contenu ET `done_reason`, la coupure étant l'objet du test), leur
forme est celle réellement enregistrée chez le serveur, et l'échange passe par le
vrai rejoueur HTTP — l'appariement des requêtes prouvant au passage que le corps
rejoué de la nouvelle tentative porte bien le résumé (§H4.7 : une requête inconnue
rend une erreur explicite, jamais une réponse inventée).
"""

from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils
from llm_replay.cassette import (
    AUTH_VALIDE,
    Cassette,
    Exchange,
    RequestRecord,
    ResponseRecord,
    premiere_conversation,
)
from llm_replay.server import creer_serveur

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-du-resume-de-coupure"

#: Scénario : tentative tronquée sans bloc, résumé, nouvelle tentative valide.
_BLOC_VALIDE = json.dumps({"state_patch": {"hypotheses": ["h1"]}, "action": "avance"})
_REPONSES: list[tuple[str, str]] = [
    ("Je raisonne longuement et la génération s'arrête au mil", "length"),
    ("Approche : explorer. Acquis : rien d'établi. Reste : agir.", "stop"),
    (f"Je fais court.\n```json\n{_BLOC_VALIDE}\n```", "stop"),
]


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _EnvironnementFactice:
    def __init__(self) -> None:
        self.jouees: list[str] = []
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"grille-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees.append("avance")
        self._derniere = _Issue(f"grille-{len(self.jouees)}", Evenement.PREDICTION_CONFIRMEE)
        return "action jouée"


def _registre(environnement: _EnvironnementFactice) -> RegistreOutils:
    return RegistreOutils(
        [
            Outil(
                nom="avance",
                description="Joue une action d'environnement",
                parametres={"type": "object", "properties": {}},
                fonction=environnement.jouer,
                etiquettes=frozenset({"action"}),
            )
        ]
    )


class TestCoupureSurRejeu(unittest.TestCase):
    """La coupure est absorbée en HTTP réel : résumé injecté, pas rejoué, métrique."""

    def setUp(self) -> None:
        if not CASSETTE_REELLE.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = premiere_conversation(Cassette.lire(CASSETTE_REELLE))
        self.serveur: ThreadingHTTPServer | None = None

    def tearDown(self) -> None:
        if self.serveur is not None:
            self.serveur.shutdown()
            self.serveur.server_close()
            self.fil.join(timeout=5)
        self._dossier.cleanup()

    def _servir(self, cassette: Path) -> str:
        self.serveur = creer_serveur(cassette.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def _config(self, hote: str) -> Config:
        return charger(
            Mode.REJEU,
            env={
                "OLLAMA_HOST": hote,
                "OLLAMA_API_KEY": CLE,
                "AVO_CONTEXT_MODE": "state",
                "AVO_GARDES": "false",
            },
            racine=Path("/inexistant"),
        )

    def _reponse_scriptee(self, index: int) -> dict[str, Any]:
        contenu, done_reason = _REPONSES[index % len(_REPONSES)]
        reponse = copy.deepcopy(self.gabarit)
        reponse["message"]["content"] = contenu
        reponse["message"].pop("tool_calls", None)
        reponse["done_reason"] = done_reason
        return reponse

    def _boucle(self, config: Config, workspace: Workspace | None) -> BoucleAgent:
        environnement = _EnvironnementFactice()
        return BoucleAgent(
            config,
            LLMClient(config, dormir=lambda _: None),
            _registre(environnement),
            environnement,
            Notes(self.racine / "notes"),
            workspace=workspace,
        )

    def test_la_coupure_est_absorbee_et_le_resume_rejoue_en_http(self) -> None:
        # Passe 1 : capturer les corps réellement émis par la boucle.
        corps_emis: list[dict[str, Any]] = []

        def transport_capture(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            corps_emis.append(json.loads(corps))
            return ReponseHTTP(
                200, json.dumps(self._reponse_scriptee(len(corps_emis) - 1)).encode()
            )

        config_capture = charger(
            Mode.REJEU,
            env={
                "OLLAMA_HOST": "http://capture.invalide",
                "OLLAMA_API_KEY": CLE,
                "AVO_CONTEXT_MODE": "state",
                "AVO_GARDES": "false",
            },
            racine=Path("/inexistant"),
        )
        environnement_capture = _EnvironnementFactice()
        BoucleAgent(
            config_capture,
            LLMClient(config_capture, transport=transport_capture, dormir=lambda _: None),
            _registre(environnement_capture),
            environnement_capture,
            Notes(self.racine / "notes_capture"),
        ).jouer_tour(1)
        self.assertEqual(len(corps_emis), 3, "tentative, résumé, nouvelle tentative")
        # Le corps de la nouvelle tentative porte le résumé (§H17.3).
        message_retente = corps_emis[2]["messages"][1]["content"]
        self.assertIn("Approche : explorer.", message_retente)
        self.assertIn("approche plus courte", message_retente)

        # Passe 2 : cassette générée depuis les corps capturés, servie en HTTP réel.
        cassette = Cassette()
        for index, corps in enumerate(corps_emis):
            cassette.ajouter(
                Exchange(
                    request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                    response=ResponseRecord(
                        status=200,
                        headers={"content-type": "application/json"},
                        body=self._reponse_scriptee(index),
                    ),
                    recorded_at="2026-09-13T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "scenario_coupure.jsonl"
        cassette.ecrire(chemin)
        config = self._config(self._servir(chemin))
        workspace = Workspace.ouvrir(config, "run-coupure-rejeu", racine=self.racine)
        boucle = self._boucle(config, workspace)

        tour = boucle.jouer_tour(1)

        self.assertEqual(tour.action, "avance", "le pas rejoué après la coupure aboutit")
        self.assertEqual(tour.retries_patch, 1, "la coupure a coûté une tentative, pas le tour")
        self.assertEqual(boucle.bilan.resumes_coupure, 1)
        coupures = [
            dict(ligne) for ligne in workspace.lire_metriques() if ligne.get("type") == "coupure"
        ]
        self.assertEqual(len(coupures), 1)
        self.assertTrue(coupures[0]["resume"])
        self.assertEqual(coupures[0]["mode"], "state")
        phases = [
            ligne.get("phase") for ligne in workspace.lire_metriques() if ligne.get("type") == "llm"
        ]
        self.assertIn("resume_coupure", phases, "l'appel de résumé est mesuré (§H17.5)")

    def test_prompts_version_du_bilan(self) -> None:
        """Le bilan nomme la version des prompts sous laquelle la coupure est mesurée."""
        self.assertEqual(prompts.VERSION, "1.11")


if __name__ == "__main__":
    unittest.main()
