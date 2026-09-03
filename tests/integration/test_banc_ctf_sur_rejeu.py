"""Le banc b joué par la boucle complète sous gardes, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U29b2 — adaptateur + branchement au dispatch CLI `banc`
@verifies docs/SPEC_BANCS.md §S12.5 (intégration : épisode court joué en rejeu
          par la boucle complète sous gardes, relevé `banc.json` écrit et
          exact), §S11.1–§S11.2 (pass@1 binaire et champs du relevé), §S9.3
          (fin sur capture), §S10.3 (exécuteur `processus` en preuve), §S1.4
          (déterminisme : défi identique à seed égal)
@verifies docs/SPEC_HARNAIS.md §H15.9 et docs/SPEC_BANCS.md §S12.3 (Σ tenu sous
          le schéma `ctf`, relevé nommant le schéma), §H15.8 (un pas = un tour,
          paramètre requis unique reçu verbatim — la commande porte espaces et
          options), §H16 (gardes actives)

Même principe à deux passes que `test_banc_sur_rejeu.py` : la première passe
capture les corps réellement émis par la boucle (transport scripté), la seconde
les sert par le vrai rejoueur HTTP — le client, l'authentification et
l'appariement sont ceux du produit. Les commandes du recouvrement canonique
s'exécutent RÉELLEMENT (exécuteur `processus`, §S10.3) dans les deux passes.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.bancs.ctf.adaptateur import EXECUTEUR_PROCESSUS, jouer_episode_ctf
from avo.bancs.ctf.defis import generer_defi
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur
from tests.e2e.scenarios_banc import (
    HYPOTHESE_CTF,
    actions_parfaites_ctf,
    gabarit_reponse,
    reponse_pas,
)

CLE = "sk-cle-de-rejeu-du-banc"
SEED = 5
HORIZON = 4


class TestBancCtfSurRejeu(unittest.TestCase):
    """§S12.5 : boucle complète sous gardes, en HTTP, relevé exact."""

    def setUp(self) -> None:
        cassette_reelle = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
        if not cassette_reelle.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = gabarit_reponse()
        self.actions = actions_parfaites_ctf(generer_defi(SEED, "fouille"))
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
        releve = jouer_episode_ctf(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            famille="fouille",
            executeur=EXECUTEUR_PROCESSUS,
            client_llm=client,
        )
        return releve, espace

    def _capturer_corps(self) -> list[dict[str, Any]]:
        """Première passe : la boucle réelle émet, le transport scripté répond."""
        corps_emis: list[dict[str, Any]] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            corps_emis.append(json.loads(corps))
            reponse = reponse_pas(self.gabarit, self.actions[len(corps_emis) - 1], HYPOTHESE_CTF)
            return ReponseHTTP(200, json.dumps(reponse).encode())

        config = self._config("http://capture.invalide")
        releve, _ = self._jouer(
            config, "ctf-capture", LLMClient(config, transport=transport, dormir=lambda _: None)
        )
        self.assertTrue(releve.reussi, "la capture doit déjà résoudre le défi")
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
                        body=reponse_pas(self.gabarit, self.actions[rang], HYPOTHESE_CTF),
                    ),
                    recorded_at="2026-09-03T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "cassettes" / "banc_ctf.jsonl"
        chemin.parent.mkdir(parents=True)
        cassette.ecrire(chemin)
        self.serveur = creer_serveur(chemin.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def test_capture_en_http_releve_exact(self) -> None:
        base = self._servir(self._capturer_corps())
        config = self._config(base)
        releve, espace = self._jouer(config, "ctf-rejeu")

        # Pass@1 binaire et compteurs (§S11.1, §S11.2).
        self.assertTrue(releve.reussi)
        self.assertEqual(releve.actions, 2)
        self.assertEqual(releve.commandes, 1)
        self.assertEqual(releve.refus_forme, 0)
        self.assertEqual(releve.soumissions, 1)
        self.assertEqual(releve.soumissions_incorrectes, 0)
        self.assertEqual(releve.arret, "drapeau capturé")

        # Relevé écrit et exact (§S11.2).
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["seed"], SEED)
        self.assertEqual(ecrit["famille"], "fouille")
        self.assertEqual(ecrit["horizon"], HORIZON)
        self.assertTrue(ecrit["reussi"])
        self.assertEqual(ecrit["arret"], "drapeau capturé")
        self.assertEqual(ecrit["banc"], "ctf")
        self.assertEqual(ecrit["schema_etat"], "ctf")
        self.assertEqual(ecrit["executeur"], EXECUTEUR_PROCESSUS)
        self.assertGreater(ecrit["tokens_consommes"], 0)
        self.assertIsNotNone(ecrit["taille_prompt_moyenne"])
        self.assertIsNotNone(ecrit["duree_secondes"])

        # Un pas = un tour (§H15.8) : un appel LLM par action, phase `state`.
        appels = [ligne for ligne in espace.lire_metriques() if ligne["type"] == "llm"]
        self.assertEqual(len(appels), 2)
        self.assertTrue(all(appel["phase"] == "state" for appel in appels))

        # Σ persisté sous le schéma du domaine (§H15.5, §H15.9, §S12.3).
        etat = json.loads(espace.etat_json.read_text(encoding="utf-8"))
        self.assertEqual(etat["hypotheses"], [HYPOTHESE_CTF])
        self.assertIn("repertoire_travail", etat)
        self.assertIn("resume_commandes", etat)
        self.assertNotIn("position", etat)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
