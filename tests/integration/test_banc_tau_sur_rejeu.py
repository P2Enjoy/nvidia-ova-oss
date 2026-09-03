"""Le banc c joué par la boucle complète sous gardes, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U29c2 — adaptateur + branchement au dispatch CLI `banc`
@verifies docs/SPEC_BANCS.md §S18.5 (intégration : épisode court joué en rejeu
          par la boucle complète sous gardes, relevé `banc.json` écrit et
          exact), §S17.1–§S17.2 (réussite binaire, champs du relevé), §S16.4
          (fin sur `clore()`), §S16.3 (utilisateur `scripte` en rejeu), §S1.4
          (déterminisme : épisode identique à seed égal)
@verifies docs/SPEC_HARNAIS.md §H15.9 et docs/SPEC_BANCS.md §S18.3 (Σ tenu sous
          le schéma `service`, relevé nommant le schéma), §H15.8 (un pas = un
          tour, paramètre requis unique reçu verbatim — le message à
          l'utilisateur porte espaces et ponctuation), §H16 (gardes actives)

Même principe à deux passes que `test_banc_ctf_sur_rejeu.py` : la première passe
capture les corps réellement émis par la boucle (transport scripté), la seconde
les sert par le vrai rejoueur HTTP — le client, l'authentification et
l'appariement sont ceux du produit. L'utilisateur simulé `scripte` répond
réellement dans les deux passes (§S16.3).
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.bancs.tau.adaptateur import UTILISATEUR_SCRIPTE, jouer_episode_tau
from avo.bancs.tau.scenario import generer_episode_tau
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur
from tests.e2e.scenarios_banc import (
    HYPOTHESE_TAU,
    actions_parfaites_tau,
    gabarit_reponse,
    reponse_pas,
)

CLE = "sk-cle-de-rejeu-du-banc"
SEED = 8
HORIZON = 8


class TestBancTauSurRejeu(unittest.TestCase):
    """§S18.5 : boucle complète sous gardes, en HTTP, relevé exact."""

    def setUp(self) -> None:
        cassette_reelle = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
        if not cassette_reelle.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = gabarit_reponse()
        base, self.scenario, _ = generer_episode_tau(SEED)
        base.fermer()
        self.actions = actions_parfaites_tau(self.scenario)
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

    def _jouer(self, config: Config, run_id: str, client: LLMClient | None = None) -> Any:
        espace = Workspace.ouvrir(config, run_id, racine=self.racine / run_id)
        releve = jouer_episode_tau(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            utilisateur=UTILISATEUR_SCRIPTE,
            client_llm=client,
        )
        return releve, espace

    def _capturer_corps(self) -> list[dict[str, Any]]:
        """Première passe : la boucle réelle émet, le transport scripté répond."""
        corps_emis: list[dict[str, Any]] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            corps_emis.append(json.loads(corps))
            reponse = reponse_pas(self.gabarit, self.actions[len(corps_emis) - 1], HYPOTHESE_TAU)
            return ReponseHTTP(200, json.dumps(reponse).encode())

        config = self._config("http://capture.invalide")
        releve, _ = self._jouer(
            config, "tau-capture", LLMClient(config, transport=transport, dormir=lambda _: None)
        )
        self.assertTrue(releve.reussi, "la capture doit déjà réussir l'épisode")
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
                        body=reponse_pas(self.gabarit, self.actions[rang], HYPOTHESE_TAU),
                    ),
                    recorded_at="2026-09-03T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "cassettes" / "banc_tau.jsonl"
        chemin.parent.mkdir(parents=True)
        cassette.ecrire(chemin)
        self.serveur = creer_serveur(chemin.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def test_episode_conforme_en_http_releve_exact(self) -> None:
        base = self._servir(self._capturer_corps())
        config = self._config(base)
        releve, espace = self._jouer(config, "tau-rejeu")

        # Réussite binaire et compteurs (§S17.1, §S17.2).
        self.assertTrue(releve.reussi)
        self.assertEqual(releve.actions, 5)
        self.assertEqual(releve.repliques, 2)
        self.assertEqual(releve.transactions, 1)
        self.assertEqual(releve.violations, 0)
        self.assertEqual(releve.arret, "clos par l'agent")

        # Relevé écrit et exact (§S17.2).
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["seed"], SEED)
        self.assertEqual(ecrit["domaine"], "detail")
        self.assertEqual(ecrit["intention"], self.scenario.famille)
        self.assertTrue(ecrit["eligible"])
        self.assertTrue(ecrit["reussi"])
        self.assertEqual(ecrit["arret"], "clos par l'agent")
        self.assertEqual(ecrit["banc"], "tau")
        self.assertEqual(ecrit["schema_etat"], "service")
        self.assertEqual(ecrit["utilisateur"], "scripte")
        self.assertGreater(ecrit["tokens_consommes"], 0)
        self.assertIsNotNone(ecrit["taille_prompt_moyenne"])
        self.assertIsNotNone(ecrit["duree_secondes"])

        # Un pas = un tour (§H15.8) : un appel LLM par action, phase `state`.
        appels = [ligne for ligne in espace.lire_metriques() if ligne["type"] == "llm"]
        self.assertEqual(len(appels), 5)
        self.assertTrue(all(appel["phase"] == "state" for appel in appels))

        # Σ persisté sous le schéma du domaine (§H15.5, §H15.9, §S18.3).
        etat = json.loads(espace.etat_json.read_text(encoding="utf-8"))
        self.assertEqual(etat["hypotheses"], [HYPOTHESE_TAU])
        self.assertIn("client_identifie", etat)
        self.assertIn("reste_a_faire", etat)
        self.assertNotIn("position", etat)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
