"""Branchement du Dépôt logiciel : contrat de boucle, outils, épisode joué, CLI.

@verifies docs/BACKLOG.md U29a4 — branchement du Dépôt logiciel à l'adaptateur
          et à la CLI
@verifies docs/SPEC_BANCS.md §S6.1 (contrat `Environnement`, outils étiquetés
          `action` avec `prediction`), §S6.2 (contexte de tâche : protocole
          §S4.2/§S4.5 donné, jamais l'état de vérité ni la suite d'événements),
          §S4.2 (`merge` reçoit son numéro en texte : « 3 » et « #3 » se
          lisent, un numéro imprenable est une action invalide nommée qui
          consomme l'événement), §S4.4 (résolution B.1 portée au relevé),
          §S5.2 (première action comparée à l'obligation), §S5.3 (relevé
          `banc.json`), §S6.3 (CLI : dispatch du dépôt, refus nommés)
@verifies docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement`), §H15.8 (message
          système du contexte monté, résolution du champ `action` en texte)

Aucun réseau, aucune cassette : le client est scripté par transport injecté, la
forme des corps restant celle du client réel (§H14.1).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from avo.bancs import BancInconnu, executer_banc
from avo.bancs.skillexec.adaptateur import (
    CONTEXTE_TACHE_DEPOT,
    EnvironnementBancDepot,
    jouer_episode,
)
from avo.bancs.skillexec.depot import EnvironnementDepot, generer_episode_depot
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.etats import Evenement
from avo.memory.workspace import Workspace
from tests.e2e.scenarios_banc import HYPOTHESE_DEPOT, actions_parfaites_depot, contenu_pas

#: Épisode des preuves : les quatre types d'événements et une demande jugée
#: (affectation, revue, echec_ci, ci_verte — relevé du générateur, seed 12).
SEED = 12
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
    """§S6.1, §H8.2 : le wrapper du dépôt parle le contrat de la boucle."""

    def setUp(self) -> None:
        self.moteur = EnvironnementDepot(generer_episode_depot(SEED, HORIZON))
        self.environnement = EnvironnementBancDepot(self.moteur)

    def test_observation_initiale_sans_issue(self) -> None:
        self.assertNotIn("Issue de ta dernière action", self.environnement.observation())

    def test_observation_porte_l_issue_de_la_derniere_action(self) -> None:
        """§S2.3 : l'agent voit les issues de ses actions — l'adaptateur compose."""
        outil = next(o for o in self.environnement.outils() if o.nom == "commit")
        texte = outil.fonction(branche="branche_0", fichier="fichier_0", prediction="p")
        self.assertIn("fichier_0", texte)
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
            self.environnement.actions_disponibles(),
            ("commit", "create_pr", "merge", "fix_ci", "wait"),
        )


class TestOutils(unittest.TestCase):
    """§S6.1, §H16.2 : cinq outils d'action, paramètre `prediction` selon le mode."""

    def test_cinq_outils_etiquetes_action(self) -> None:
        environnement = EnvironnementBancDepot(EnvironnementDepot(generer_episode_depot(1, 2)))
        outils = environnement.outils()
        self.assertEqual(
            [o.nom for o in outils], ["commit", "create_pr", "merge", "fix_ci", "wait"]
        )
        for outil in outils:
            with self.subTest(outil=outil.nom):
                self.assertIn("action", outil.etiquettes)

    def test_prediction_requise_en_mode_transcript(self) -> None:
        environnement = EnvironnementBancDepot(
            EnvironnementDepot(generer_episode_depot(1, 2)),
            avec_prediction=True,
            prediction_requise=True,
        )
        outil = next(o for o in environnement.outils() if o.nom == "merge")
        self.assertIn("prediction", outil.parametres["required"])

    def test_prediction_optionnelle_en_mode_state(self) -> None:
        environnement = EnvironnementBancDepot(
            EnvironnementDepot(generer_episode_depot(1, 2)),
            avec_prediction=True,
            prediction_requise=False,
        )
        outil = next(o for o in environnement.outils() if o.nom == "commit")
        self.assertIn("prediction", outil.parametres["properties"])
        self.assertNotIn("prediction", outil.parametres.get("required", []))

    def test_sans_gardes_pas_de_prediction(self) -> None:
        environnement = EnvironnementBancDepot(
            EnvironnementDepot(generer_episode_depot(1, 2)), avec_prediction=False
        )
        outil = next(o for o in environnement.outils() if o.nom == "wait")
        self.assertNotIn("prediction", outil.parametres["properties"])


class TestNumeroDePrEnTexte(unittest.TestCase):
    """§S4.2 : le numéro de `merge` arrive en texte et l'erreur reste nommée."""

    def setUp(self) -> None:
        self.moteur = EnvironnementDepot(generer_episode_depot(SEED, HORIZON))

    def test_numero_imprenable_invalide_et_consomme(self) -> None:
        issue = self.moteur.merge("trois")
        self.assertFalse(issue.valide)
        self.assertIn("numéro de PR invalide", issue.observation)
        self.assertEqual(self.moteur.releve.evenements_consommes, 1)

    def test_numero_prefixe_diese_se_lit(self) -> None:
        """« #1 » se lit comme 1 : l'erreur parle de la PR, pas du format."""
        issue = self.moteur.merge("#1")
        self.assertFalse(issue.valide)
        self.assertIn("PR #1 n'est pas ouverte", issue.observation)


class TestContexteTache(unittest.TestCase):
    """§S6.2, §S1.3 : le protocole est donné, jamais l'état ni les événements."""

    def test_nomme_les_cinq_actions_et_le_bruit(self) -> None:
        for attendu in ("commit", "create_pr", "merge", "fix_ci", "wait", "TELEMETRIE DE FOND"):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, CONTEXTE_TACHE_DEPOT)

    def test_ne_revele_aucun_episode(self) -> None:
        """Aucun identifiant concret de demande : l'état de vérité reste caché."""
        for interdit in ("demande_0", "branche_0", "fichier_0", "PR #1 "):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, CONTEXTE_TACHE_DEPOT)


class TestEpisodeJoue(unittest.TestCase):
    """§S6.3, §S5.3, §S4.4 : boucle complète sous gardes, relevé et résolution."""

    def _jouer(self, contenus: list[str], tours_max: int | None = None) -> tuple[Any, Workspace]:
        config = _config()
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        espace = Workspace.ouvrir(config, "banc-depot-unitaire", racine=Path(dossier.name))
        releve = jouer_episode(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            tours_max=tours_max,
            client_llm=_client(config, iter(contenus)),
            environnement="depot",
        )
        return releve, espace

    def test_jeu_parfait_score_1_resolution_1_et_releve_exact(self) -> None:
        actions = actions_parfaites_depot(generer_episode_depot(SEED, HORIZON))
        releve, espace = self._jouer(
            [contenu_pas(action, HYPOTHESE_DEPOT) for action in actions]
        )
        self.assertEqual(releve.score, 1.0)
        self.assertEqual(releve.correctes, HORIZON)
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["score"], 1.0)
        self.assertEqual(ecrit["banc"], "skillexec")
        self.assertEqual(ecrit["environnement"], "depot")
        self.assertEqual(ecrit["seed"], SEED)
        # Résolution B.1 (§S4.4) : la demande jugée est correctement résolue.
        self.assertEqual(ecrit["resolution"], 1.0)
        self.assertEqual(ecrit["demandes_resolues"], 1)
        self.assertEqual(ecrit["demandes_jugees"], 1)

    def test_le_message_systeme_est_le_contexte_de_tache_du_depot(self) -> None:
        """§H15.8 : l'adaptateur fournit le contexte du dépôt à K (§H16.1)."""
        config = _config()
        vus: list[str] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            charge = json.loads(corps)
            vus.append(charge["messages"][0]["content"])
            reponse = {
                "model": config.modele,
                "created_at": "x",
                "message": {"role": "assistant", "content": contenu_pas("wait", HYPOTHESE_DEPOT)},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
                "total_duration": 1,
            }
            return ReponseHTTP(200, json.dumps(reponse).encode())

        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        espace = Workspace.ouvrir(config, "banc-depot-systeme", racine=Path(dossier.name))
        jouer_episode(
            config,
            espace,
            seed=1,
            horizon=1,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
            environnement="depot",
        )
        self.assertTrue(vus)
        self.assertEqual(vus[0], CONTEXTE_TACHE_DEPOT)

    def test_action_incorrecte_paye_au_score_et_a_la_resolution(self) -> None:
        """§S5.2, §S4.4 : `wait` face au `ci_verte` dû vaut 0 — et la demande
        jugée, jamais fusionnée, n'est pas résolue."""
        actions = actions_parfaites_depot(generer_episode_depot(SEED, HORIZON))
        # Le dernier événement de cet épisode est le `ci_verte` de la demande 0 :
        # l'obligation est `merge 1`, `wait` est valide mais jamais correct ici.
        self.assertTrue(actions[-1].startswith("merge"))
        actions[-1] = "wait"
        releve, espace = self._jouer(
            [contenu_pas(action, HYPOTHESE_DEPOT) for action in actions]
        )
        self.assertEqual(releve.correctes, HORIZON - 1)
        self.assertEqual(releve.incorrectes, 1)
        ecrit = json.loads((espace.chemin / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(ecrit["resolution"], 0.0)
        self.assertEqual(ecrit["demandes_resolues"], 0)
        self.assertEqual(ecrit["demandes_jugees"], 1)


class TestDispatch(unittest.TestCase):
    """§S6.3 : le dépôt est dispatché, les refus restent nommés."""

    def test_environnement_inconnu_nomme_les_deux(self) -> None:
        with self.assertRaises(BancInconnu) as contexte:
            executer_banc("skillexec", "inconnu", seed=1, horizon=1)
        self.assertIn("entrepot", str(contexte.exception))
        self.assertIn("depot", str(contexte.exception))

    def test_jouer_episode_refuse_un_environnement_inconnu(self) -> None:
        config = _config()
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        espace = Workspace.ouvrir(config, "banc-refus", racine=Path(dossier.name))
        with self.assertRaises(ValueError):
            jouer_episode(config, espace, seed=1, horizon=1, environnement="inconnu")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
