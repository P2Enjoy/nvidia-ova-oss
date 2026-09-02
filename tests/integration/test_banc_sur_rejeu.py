"""Le banc a joué par la boucle complète sous gardes, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc` ; U29a4 —
          dérive d'état jouée par la boucle complète
@verifies docs/SPEC_BANCS.md §S6.4 (intégration : partie jouée en rejeu par la
          boucle complète sous gardes sur un épisode court, relevé `banc.json`
          écrit et exact), §S5.1–§S5.3 (score continu et relevé), §S1.4
          (déterminisme : épisode identique à seed égal), §S3.8 et §S5.5
          (épisode sous dérive : alerte lue, récupération immédiate au relevé)
@verifies docs/SPEC_HARNAIS.md §H15.9 et docs/SPEC_BANCS.md §S6.5 (Σ tenu sous le
          schéma du domaine, relevé nommant le schéma)
@verifies docs/SPEC_HARNAIS.md §H15.8 (un pas = un tour, message système du
          contexte monté), §H16 (gardes actives : lignes PREDICTION/VERDICT,
          champ `hypotheses` peuplé)

Même principe à deux passes que `test_boucle_etat.py` : la première passe capture
les corps réellement émis par la boucle (transport scripté), la seconde les sert
par le vrai rejoueur HTTP — le client, l'authentification et l'appariement sont
ceux du produit. Le contenu scripté vient de la politique parfaite du banc ;
l'enveloppe de réponse est celle réellement enregistrée sur le vrai endpoint.
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
from avo.bancs.skillexec.generation import generer_episode
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP, ServerError
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur
from tests.e2e.scenarios_banc import actions_parfaites, gabarit_reponse, reponse_pas

CLE = "sk-cle-de-rejeu-du-banc"
SEED = 11
HORIZON = 4


class TestBancSurRejeu(unittest.TestCase):
    """§S6.4 : boucle complète sous gardes, en HTTP, relevé exact."""

    def setUp(self) -> None:
        cassette_reelle = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
        if not cassette_reelle.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = gabarit_reponse()
        self.actions = actions_parfaites(generer_episode(SEED, HORIZON))
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
            reponse = reponse_pas(self.gabarit, self.actions[len(corps_emis) - 1])
            return ReponseHTTP(200, json.dumps(reponse).encode())

        config = self._config("http://capture.invalide")
        espace = Workspace.ouvrir(config, "banc-capture", racine=self.racine / "capture")
        releve = jouer_episode(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
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
                        body=reponse_pas(self.gabarit, self.actions[rang]),
                    ),
                    recorded_at="2026-09-01T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "cassettes" / "banc_entrepot.jsonl"
        chemin.parent.mkdir(parents=True)
        cassette.ecrire(chemin)
        self.serveur = creer_serveur(chemin.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def test_episode_parfait_en_http_releve_exact(self) -> None:
        base = self._servir(self._capturer_corps())
        config = self._config(base)
        espace = Workspace.ouvrir(config, "banc-rejeu", racine=self.racine / "rejeu")
        releve = jouer_episode(config, espace, seed=SEED, horizon=HORIZON)

        # Score et compteurs en forme fermée (§S5.1, §S5.2).
        self.assertEqual(releve.score, 1.0)
        self.assertEqual(releve.correctes, HORIZON)
        self.assertEqual(releve.incorrectes, 0)
        self.assertEqual(releve.invalides, 0)

        # Relevé écrit et exact (§S5.3).
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["score"], 1.0)
        self.assertEqual(ecrit["seed"], SEED)
        self.assertEqual(ecrit["horizon"], HORIZON)
        self.assertEqual(ecrit["evenements_consommes"], HORIZON)
        self.assertEqual(ecrit["arret"], "épisode épuisé : tous les événements sont consommés")
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
        self.assertEqual(etat["hypotheses"], ["je tiens l'état exact de l'entrepôt"])
        # Σ tenu sous le schéma du domaine (§H15.9, §S6.5) : les contenants de
        # l'Entrepôt existent, à leur défaut tant que la politique ne les remplit pas.
        self.assertEqual(etat["inventaire"], {})
        self.assertEqual(etat["en_attente"], [])
        self.assertNotIn("position", etat)
        self.assertEqual(ecrit["schema_etat"], "banc-entrepot-v1")

    def test_episode_sous_derive_recupere_en_zero_pas(self) -> None:
        """§S3.8, §S5.5 : la boucle complète joue l'épisode à dérive en HTTP ;
        la politique parfaite lit l'alerte, le score reste 1 et la récupération
        est immédiate — le relevé porte les champs de §S5.5."""
        self.actions = actions_parfaites(generer_episode(SEED, HORIZON, derive=True))
        corps_emis: list[dict[str, Any]] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            corps_emis.append(json.loads(corps))
            reponse = reponse_pas(self.gabarit, self.actions[len(corps_emis) - 1])
            return ReponseHTTP(200, json.dumps(reponse).encode())

        config = self._config("http://capture.invalide")
        espace = Workspace.ouvrir(config, "derive-capture", racine=self.racine / "derive-capture")
        jouer_episode(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            derive=True,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
        )
        base = self._servir(corps_emis)
        config = self._config(base)
        espace = Workspace.ouvrir(config, "derive-rejeu", racine=self.racine / "derive-rejeu")
        releve = jouer_episode(config, espace, seed=SEED, horizon=HORIZON, derive=True)

        self.assertEqual(releve.score, 1.0)
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["pas_de_recuperation"], 0)
        self.assertTrue(ecrit["recupere"])
        self.assertGreaterEqual(ecrit["derive_evenement"], HORIZON // 2)

    def test_requete_hors_cassette_rend_une_erreur_explicite(self) -> None:
        """§H4.7 : un écart d'appariement est un rouge lisible, jamais une réponse
        inventée — le rejoueur refuse (erreur serveur), il ne fabrique rien."""
        base = self._servir(self._capturer_corps())
        config = self._config(base)
        client = LLMClient(config, dormir=lambda _: None)
        messages = [{"role": "user", "content": "requête étrangère à la cassette"}]
        with self.assertRaises(ServerError):
            client.chat(messages, tools=None)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
