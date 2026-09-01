"""Le Dépôt logiciel joué par la boucle complète sous gardes, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U29a4 — branchement du Dépôt logiciel à l'adaptateur
          et à la CLI
@verifies docs/SPEC_BANCS.md §S6.4 (intégration : partie jouée en rejeu par la
          boucle complète sous gardes sur un épisode court, relevé `banc.json`
          écrit et exact), §S4.4 (résolution B.1 au relevé), §S5.1–§S5.3 (score
          continu et relevé), §S1.4 (déterminisme : épisode identique à seed égal)
@verifies docs/SPEC_HARNAIS.md §H15.8 (un pas = un tour, message système du
          contexte monté), §H16 (gardes actives : lignes PREDICTION/VERDICT,
          champ `hypotheses` peuplé)

Même principe à deux passes que `test_banc_sur_rejeu.py` : la première passe
capture les corps réellement émis par la boucle (transport scripté), la seconde
les sert par le vrai rejoueur HTTP — le client, l'authentification et
l'appariement sont ceux du produit. Le contenu scripté vient de la politique
parfaite du dépôt (§S4.5) ; l'enveloppe de réponse est celle réellement
enregistrée sur le vrai endpoint.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.bancs.skillexec.adaptateur import jouer_episode
from avo.bancs.skillexec.depot import generer_episode_depot
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur
from tests.e2e.scenarios_banc import (
    HYPOTHESE_DEPOT,
    actions_parfaites_depot,
    gabarit_reponse,
    reponse_pas,
)

CLE = "sk-cle-de-rejeu-du-banc-depot"

#: Épisode court couvrant les quatre types d'événements et DEUX demandes jugées
#: (relevé du générateur, seed 6) : deux `fix_ci` et deux `merge` sont dus.
SEED = 6
HORIZON = 8


class TestBancDepotSurRejeu(unittest.TestCase):
    """§S6.4 : boucle complète sous gardes, en HTTP, relevé et résolution exacts."""

    def setUp(self) -> None:
        cassette_reelle = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
        if not cassette_reelle.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = gabarit_reponse()
        self.actions = actions_parfaites_depot(generer_episode_depot(SEED, HORIZON))
        self.serveur: ThreadingHTTPServer | None = None

    def tearDown(self) -> None:
        if self.serveur is not None:
            self.serveur.shutdown()
            self.serveur.server_close()
            self.fil.join(timeout=5)
        self._dossier.cleanup()

    def _config(self, base: str) -> Config:
        return charger(
            Mode.REJEU,
            env={
                "OLLAMA_HOST": base,
                "OLLAMA_API_KEY": CLE,
                "AVO_CONTEXT_MODE": "state",
                "AVO_GARDES": "true",
            },
            racine=Path("/inexistant"),
        )

    def _capturer_corps(self) -> list[dict[str, Any]]:
        """Première passe : la boucle réelle émet, le transport scripté répond."""
        corps_emis: list[dict[str, Any]] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            corps_emis.append(json.loads(corps))
            reponse = reponse_pas(self.gabarit, self.actions[len(corps_emis) - 1], HYPOTHESE_DEPOT)
            return ReponseHTTP(200, json.dumps(reponse).encode())

        config = self._config("http://capture.invalide")
        espace = Workspace.ouvrir(config, "banc-depot-capture", racine=self.racine / "capture")
        releve = jouer_episode(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
            environnement="depot",
        )
        self.assertEqual(releve.score, 1.0, "la capture doit déjà jouer parfaitement")
        return corps_emis

    def _servir(self, corps_emis: list[dict[str, Any]]) -> str:
        cassette = Cassette()
        for rang, corps in enumerate(corps_emis):
            cassette.ajouter(
                Exchange(
                    request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                    response=ResponseRecord(
                        status=200,
                        headers={"content-type": "application/json"},
                        body=reponse_pas(self.gabarit, self.actions[rang], HYPOTHESE_DEPOT),
                    ),
                    recorded_at="2026-09-01T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "cassettes" / "banc_depot.jsonl"
        chemin.parent.mkdir(parents=True)
        cassette.ecrire(chemin)
        self.serveur = creer_serveur(chemin.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def test_episode_parfait_en_http_releve_et_resolution_exacts(self) -> None:
        base = self._servir(self._capturer_corps())
        config = self._config(base)
        espace = Workspace.ouvrir(config, "banc-depot-rejeu", racine=self.racine / "rejeu")
        releve = jouer_episode(config, espace, seed=SEED, horizon=HORIZON, environnement="depot")

        # Score et compteurs en forme fermée (§S5.1, §S5.2).
        self.assertEqual(releve.score, 1.0)
        self.assertEqual(releve.correctes, HORIZON)
        self.assertEqual(releve.incorrectes, 0)
        self.assertEqual(releve.invalides, 0)

        # Relevé écrit et exact, résolution B.1 comprise (§S5.3, §S4.4).
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["score"], 1.0)
        self.assertEqual(ecrit["seed"], SEED)
        self.assertEqual(ecrit["horizon"], HORIZON)
        self.assertEqual(ecrit["environnement"], "depot")
        self.assertEqual(ecrit["evenements_consommes"], HORIZON)
        self.assertEqual(ecrit["arret"], "épisode épuisé : tous les événements sont consommés")
        self.assertEqual(ecrit["resolution"], 1.0)
        self.assertEqual(ecrit["demandes_resolues"], 2)
        self.assertEqual(ecrit["demandes_jugees"], 2)
        self.assertGreater(ecrit["tokens_consommes"], 0)
        self.assertIsNotNone(ecrit["taille_prompt_moyenne"])
        self.assertIsNotNone(ecrit["duree_secondes"])

        # Un pas = un tour (§H15.8) : un appel LLM par événement, phase `state`.
        appels = [ligne for ligne in espace.lire_metriques() if ligne["type"] == "llm"]
        self.assertEqual(len(appels), HORIZON)
        self.assertTrue(all(appel["phase"] == "state" for appel in appels))

        # Σ persisté après chaque pas validé (§H15.5) : les gardes y ont exigé
        # une hypothèse (§H16.1).
        etat = json.loads(espace.etat_json.read_text(encoding="utf-8"))
        self.assertEqual(etat["hypotheses"], [HYPOTHESE_DEPOT])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
