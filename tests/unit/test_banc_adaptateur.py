"""Adaptateur du banc a : contrat de boucle, outils, épisode joué, CLI.

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc`
@verifies docs/SPEC_BANCS.md §S6.1 (contrat `Environnement`, outils étiquetés
          `action` avec `prediction`, descriptions qui énoncent commande et
          syntaxe), §S6.2 (contexte de tâche : protocole donné, jamais l'état de
          vérité ni la suite d'événements), §S2.3 (l'agent voit les observations
          et les issues de ses actions), §S5.3 (relevé `banc.json`),
          §S6.3 (CLI `banc` : refus nommé d'un banc ou environnement inconnu)
@verifies docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement`), §H15.8 (le message
          système du mode `state` est celui du contexte monté), §H16.1 (garde
          documentaire du mode `state` : action retenue tant que `hypotheses`
          est vide)

Aucun réseau, aucune cassette : le client est scripté par transport injecté, la
forme des corps restant celle du client réel (§H14.1).
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from avo import cli
from avo.bancs import BancInconnu, executer_banc
from avo.bancs.skillexec.adaptateur import (
    CONTEXTE_TACHE,
    EnvironnementBancEntrepot,
    jouer_episode,
)
from avo.bancs.skillexec.entrepot import EnvironnementEntrepot
from avo.bancs.skillexec.generation import generer_episode
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.etats import Evenement
from avo.memory.workspace import Workspace
from tests.e2e.scenarios_banc import actions_parfaites, contenu_pas

SEED = 7
HORIZON = 5


def _config(env: dict[str, str] | None = None) -> Config:
    return charger(
        Mode.REJEU,
        env={"OLLAMA_CONTEXT_LENGTH": "229376", "AVO_CONTEXT_MODE": "state", **(env or {})},
        racine=Path("/inexistant"),
    )


def _client(config: Config, contenus: Iterator[str]) -> LLMClient:
    """Un client réel au transport scripté : l'enveloppe reste celle de l'API."""

    def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        reponse = {
            "model": config.modele,
            "created_at": "2026-09-01T00:00:00Z",
            "message": {"role": "assistant", "content": next(contenus)},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 100,
            "eval_count": 50,
            "total_duration": 1_000_000,
        }
        return ReponseHTTP(200, json.dumps(reponse).encode())

    return LLMClient(config, transport=transport, dormir=lambda _: None)


class TestContratEnvironnement(unittest.TestCase):
    """§S6.1, §H8.2 : le wrapper parle le contrat de la boucle."""

    def setUp(self) -> None:
        self.moteur = EnvironnementEntrepot(generer_episode(SEED, HORIZON))
        self.environnement = EnvironnementBancEntrepot(self.moteur)

    def test_observation_initiale_sans_issue(self) -> None:
        self.assertNotIn("Issue de ta dernière action", self.environnement.observation())

    def test_observation_porte_l_issue_de_la_derniere_action(self) -> None:
        """§S2.3 : l'agent voit les issues de ses actions — l'adaptateur compose."""
        outil = next(o for o in self.environnement.outils() if o.nom == "store")
        texte = outil.fonction(article="article_0", etagere="etagere_3", prediction="p")
        self.assertIn("article_0", texte)
        observation = self.environnement.observation()
        self.assertIn("Issue de ta dernière action", observation)
        self.assertIn(texte, observation)

    def test_issue_et_evenement(self) -> None:
        outil = next(o for o in self.environnement.outils() if o.nom == "wait")
        outil.fonction(prediction="p")
        issue = self.environnement.derniere_issue()
        assert issue is not None
        self.assertIs(issue.evenement, Evenement.PREDICTION_CONFIRMEE)

    def test_etat_terminal_suit_le_moteur(self) -> None:
        self.assertIsNone(self.environnement.etat_terminal())
        outil = next(o for o in self.environnement.outils() if o.nom == "wait")
        for _ in range(HORIZON):
            outil.fonction(prediction="p")
        self.assertIsNotNone(self.environnement.etat_terminal())

    def test_actions_disponibles(self) -> None:
        self.assertEqual(
            self.environnement.actions_disponibles(), ("store", "ship", "move", "wait")
        )


class TestOutils(unittest.TestCase):
    """§S6.1, §H16.2 : quatre outils d'action, paramètre `prediction` selon le mode."""

    def test_quatre_outils_etiquetes_action(self) -> None:
        environnement = EnvironnementBancEntrepot(EnvironnementEntrepot(generer_episode(1, 2)))
        outils = environnement.outils()
        self.assertEqual([o.nom for o in outils], ["store", "ship", "move", "wait"])
        for outil in outils:
            with self.subTest(outil=outil.nom):
                self.assertIn("action", outil.etiquettes)

    def test_prediction_requise_en_mode_transcript(self) -> None:
        environnement = EnvironnementBancEntrepot(
            EnvironnementEntrepot(generer_episode(1, 2)),
            avec_prediction=True,
            prediction_requise=True,
        )
        outil = next(o for o in environnement.outils() if o.nom == "store")
        self.assertIn("prediction", outil.parametres["required"])

    def test_prediction_optionnelle_en_mode_state(self) -> None:
        """§H15.8 : la prédiction voyage en ligne de texte, la boucle l'injecte."""
        environnement = EnvironnementBancEntrepot(
            EnvironnementEntrepot(generer_episode(1, 2)),
            avec_prediction=True,
            prediction_requise=False,
        )
        outil = next(o for o in environnement.outils() if o.nom == "store")
        self.assertIn("prediction", outil.parametres["properties"])
        self.assertNotIn("prediction", outil.parametres.get("required", []))

    def test_sans_gardes_pas_de_prediction(self) -> None:
        environnement = EnvironnementBancEntrepot(
            EnvironnementEntrepot(generer_episode(1, 2)), avec_prediction=False
        )
        outil = next(o for o in environnement.outils() if o.nom == "wait")
        self.assertNotIn("prediction", outil.parametres["properties"])


class TestContexteTache(unittest.TestCase):
    """§S6.2, §S1.3 : le protocole est donné, jamais l'état ni les événements."""

    def test_nomme_les_quatre_actions_et_le_bruit(self) -> None:
        for attendu in ("store", "ship", "move", "wait", "TELEMETRIE DE FOND"):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, CONTEXTE_TACHE)

    def test_ne_revele_aucun_episode(self) -> None:
        """Aucun identifiant concret d'article : l'état de vérité reste caché."""
        for interdit in ("article_0", "article_1", "etagere_3"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, CONTEXTE_TACHE)


class TestEpisodeJoue(unittest.TestCase):
    """§S6.3, §S5.3 : la boucle complète sous gardes, relevé écrit et exact."""

    def _jouer(self, contenus: list[str], tours_max: int | None = None) -> tuple[Any, Workspace]:
        config = _config()
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        espace = Workspace.ouvrir(config, "banc-unitaire", racine=Path(dossier.name))
        releve = jouer_episode(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            tours_max=tours_max,
            client_llm=_client(config, iter(contenus)),
        )
        return releve, espace

    def test_jeu_parfait_score_1_et_releve_exact(self) -> None:
        actions = actions_parfaites(generer_episode(SEED, HORIZON))
        releve, espace = self._jouer([contenu_pas(action) for action in actions])
        self.assertEqual(releve.score, 1.0)
        self.assertEqual(releve.correctes, HORIZON)
        self.assertEqual(
            releve.champs_libres["arret"],
            "épisode épuisé : tous les événements sont consommés",
        )
        self.assertEqual(releve.tokens_consommes, 150 * HORIZON)
        self.assertIsNotNone(releve.taille_prompt_moyenne)
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["score"], 1.0)
        self.assertEqual(ecrit["banc"], "skillexec")
        self.assertEqual(ecrit["environnement"], "entrepot")
        self.assertEqual(ecrit["mode_contexte"], "state")
        self.assertEqual(ecrit["seed"], SEED)

    def test_le_message_systeme_est_le_contexte_de_tache(self) -> None:
        """§H15.8 amendé : l'adaptateur fournit son contexte de tâche à K."""
        config = _config()
        vus: list[str] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            charge = json.loads(corps)
            vus.append(charge["messages"][0]["content"])
            reponse = {
                "model": config.modele,
                "created_at": "x",
                "message": {"role": "assistant", "content": contenu_pas("wait")},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
                "total_duration": 1,
            }
            return ReponseHTTP(200, json.dumps(reponse).encode())

        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        espace = Workspace.ouvrir(config, "banc-systeme", racine=Path(dossier.name))
        jouer_episode(
            config,
            espace,
            seed=1,
            horizon=1,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
        )
        self.assertTrue(vus)
        self.assertEqual(vus[0], CONTEXTE_TACHE)

    def test_action_retenue_par_la_garde_sans_consommer_l_evenement(self) -> None:
        """§H16.1/§H16.2 : un pas sans artefact retient l'action, gratuite."""
        actions = actions_parfaites(generer_episode(SEED, HORIZON))
        sans_prediction = (
            "je réponds sans les lignes exigées\n"
            '```json\n{"state_patch": {}, "action": "' + actions[0] + '"}\n```'
        )
        releve, _espace = self._jouer(
            [sans_prediction, *[contenu_pas(action) for action in actions]],
            tours_max=HORIZON + 1,
        )
        self.assertEqual(releve.score, 1.0)
        self.assertEqual(releve.champs_libres["tours"], HORIZON + 1)
        self.assertGreater(releve.champs_libres["redemandes_gardes"], 0)

    def test_action_incorrecte_paye_au_score(self) -> None:
        """§S5.2 : valide-mais-autre vaut 0 — l'épisode, lui, avance.

        L'action fautive est le DERNIER événement : plus tôt, l'état réel aurait
        divergé du nominal et les actions parfaites suivantes auraient cascadé —
        c'est précisément l'écart que §S3.4 fait payer au score.
        """
        actions = actions_parfaites(generer_episode(SEED, HORIZON))
        # L'obligation du dernier événement (maintenance sur étagère occupée) est
        # un move : wait est valide, jamais correct (§S3.5).
        actions[-1] = "wait"
        releve, _espace = self._jouer([contenu_pas(action) for action in actions])
        self.assertEqual(releve.correctes, HORIZON - 1)
        self.assertEqual(releve.incorrectes, 1)
        self.assertAlmostEqual(releve.score, (HORIZON - 1) / HORIZON)


class TestDispatch(unittest.TestCase):
    """§S6.3 : refus nommés — jamais un échec obscur ni un succès simulé."""

    def test_banc_inconnu(self) -> None:
        with self.assertRaises(BancInconnu) as contexte:
            executer_banc("inconnu", "entrepot", seed=1, horizon=1)
        self.assertIn("skillexec", str(contexte.exception))

    def test_environnement_inconnu(self) -> None:
        with self.assertRaises(BancInconnu) as contexte:
            executer_banc("skillexec", "inconnu", seed=1, horizon=1)
        self.assertIn("entrepot", str(contexte.exception))

    def test_cli_refuse_en_nommant(self) -> None:
        erreurs = io.StringIO()
        with contextlib.redirect_stderr(erreurs):
            code = cli.main(
                ["banc", "inconnu", "--env", "entrepot", "--seed", "1", "--horizon", "2"]
            )
        self.assertEqual(code, 2)
        self.assertIn("banc refusé", erreurs.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
