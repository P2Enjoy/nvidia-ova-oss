"""Le contrat ARC-AGI-3 local, éprouvé en HTTP réel.

@verifies docs/BACKLOG.md U16 — Serveur de rejeu arc-replay et jeu cible ; U22 — fil mesuré
@verifies docs/SPEC_ARCAGI3.md §A3.1 (contrat HTTP), §A3.3 (épisodes, déviation),
          §A1.2 (protocole de score), §A1.3 (surfaces), §A1.4 (format de fil mesuré),
          §A6.2 (baselines exposées)

Une partie est gagnée **à la main, par requêtes**, action par action : c'est la
preuve que le contrat tient debout avant que le client U17 ne s'y branche.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.jeu_cible import JeuCible, baseline_humaine
from arc_replay.serveur import creer_serveur


class _Client:
    """Client HTTP minimal : le test parle le contrat sans passer par le harnais."""

    def __init__(self, base: str) -> None:
        self.base = base

    def appeler(self, methode: str, chemin: str, corps: Any = None) -> tuple[int, Any]:
        donnees = json.dumps(corps).encode() if corps is not None else None
        requete = urllib.request.Request(self.base + chemin, data=donnees, method=methode)  # noqa: S310
        if donnees is not None:
            requete.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(requete, timeout=30) as reponse:  # noqa: S310
                return int(reponse.status), json.loads(reponse.read())
        except urllib.error.HTTPError as erreur:
            return int(erreur.code), json.loads(erreur.read())


class _ServeurLance:
    def demarrer(self, **kwargs: Any) -> _Client:
        self.serveur: ThreadingHTTPServer = creer_serveur(port=0, **kwargs)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return _Client(f"http://{hote!s}:{port}")

    def arreter(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(timeout=5)


class TestContratHTTP(unittest.TestCase, _ServeurLance):
    def setUp(self) -> None:
        self.client = self.demarrer(niveaux=3)

    def tearDown(self) -> None:
        self.arreter()

    def _demarrer_partie(self) -> tuple[str, str, dict[str, Any]]:
        """RESET conforme au fil mesuré : `game_id` ET `card_id` requis (§A1.4)."""
        _, ouverture = self.client.appeler("POST", "/api/scorecard/open", {"tags": []})
        carte = ouverture["card_id"]
        _, debut = self.client.appeler(
            "POST", "/api/cmd/RESET", {"game_id": "cible-synthetique", "card_id": carte}
        )
        return carte, debut["guid"], debut

    def test_le_point_de_sante_repond(self) -> None:
        statut, corps = self.client.appeler("GET", "/_health")
        self.assertEqual(statut, 200)
        self.assertEqual(corps["status"], "ok")

    def test_le_listing_expose_les_baselines_par_niveau(self) -> None:
        """§A6.2 : ce sont elles qui font foi pour le RHAE."""
        statut, corps = self.client.appeler("GET", "/api/games")
        self.assertEqual(statut, 200)
        self.assertEqual(len(corps), 1)
        self.assertEqual(corps[0]["baseline_actions"], [baseline_humaine(n) for n in (1, 2, 3)])
        self.assertIn("keyboard_click", corps[0]["tags"])

    def test_un_scorecard_s_ouvre_se_lit_et_se_ferme(self) -> None:
        _, ouverture = self.client.appeler("POST", "/api/scorecard/open", {"tags": ["test"]})
        carte = ouverture["card_id"]
        statut, lecture = self.client.appeler("GET", f"/api/scorecard/{carte}")
        self.assertEqual(statut, 200)
        self.assertFalse(lecture["closed"])
        _, fermeture = self.client.appeler("POST", "/api/scorecard/close", {"card_id": carte})
        self.assertTrue(fermeture["closed"])

    def test_un_scorecard_inconnu_est_refuse(self) -> None:
        statut, _ = self.client.appeler("GET", "/api/scorecard/inexistant")
        self.assertEqual(statut, 404)

    def test_le_reset_cree_la_partie_et_rend_une_frame(self) -> None:
        _, ouverture = self.client.appeler("POST", "/api/scorecard/open", {"tags": []})
        statut, corps = self.client.appeler(
            "POST",
            "/api/cmd/RESET",
            {"game_id": "cible-synthetique", "card_id": ouverture["card_id"]},
        )
        self.assertEqual(statut, 200)
        self.assertEqual(corps["state"], "NOT_FINISHED")
        self.assertEqual(corps["levels_completed"], 0)
        self.assertEqual(corps["win_levels"], 3)
        self.assertTrue(corps["full_reset"])
        self.assertEqual(corps["action_input"]["id"], 0)
        self.assertEqual(len(corps["frame"]), 1)
        self.assertEqual(len(corps["frame"][0]), 64)
        self.assertIn(6, corps["available_actions"])
        self.assertNotIn(0, corps["available_actions"], "RESET jamais déclaré (§A1.4)")

    def test_un_jeu_inconnu_du_backend_est_refuse_nomme(self) -> None:
        """§A1.4 mesuré : le refus nomme le jeu, comme l'API officielle."""
        _, ouverture = self.client.appeler("POST", "/api/scorecard/open", {"tags": []})
        statut, corps = self.client.appeler(
            "POST", "/api/cmd/RESET", {"game_id": "cible", "card_id": ouverture["card_id"]}
        )
        self.assertEqual(statut, 400)
        self.assertIn("cible not found", corps["error"])

    def test_un_reset_sans_card_id_est_refuse(self) -> None:
        statut, corps = self.client.appeler(
            "POST", "/api/cmd/RESET", {"game_id": "cible-synthetique"}
        )
        self.assertEqual(statut, 400)
        self.assertIn("card_id", corps["error"])

    def test_une_action_rend_deux_frames_dont_la_transitoire(self) -> None:
        _, guid, _ = self._demarrer_partie()
        _, corps = self.client.appeler(
            "POST", "/api/cmd/ACTION2", {"game_id": "cible-synthetique", "guid": guid}
        )
        self.assertEqual(len(corps["frame"]), 2)
        self.assertNotIn("actions_level", corps, "aucun compteur par frame (§A1.4)")

    def test_une_partie_est_gagnee_a_la_main_action_par_action(self) -> None:
        """La preuve centrale : le contrat permet une vraie partie de bout en bout."""
        carte, guid, _ = self._demarrer_partie()

        temoin = JeuCible(niveaux=3)
        temoin.reset()
        actions = 0
        for niveau in (1, 2, 3):
            for action, ligne, colonne in temoin.chemin_optimal():
                charge: dict[str, Any] = {"game_id": "cible-synthetique", "guid": guid}
                if ligne is not None:
                    # Fil mesuré (§A4.2) : x = colonne, y = ligne.
                    charge |= {"x": colonne, "y": ligne}
                statut, corps = self.client.appeler("POST", f"/api/cmd/{action}", charge)
                self.assertEqual(statut, 200)
                temoin.jouer(action, ligne, colonne)
                actions += 1
            self.assertEqual(corps["levels_completed"], niveau, f"niveau {niveau} complété")

        self.assertEqual(corps["state"], "WIN")
        self.assertEqual(actions, sum(baseline_humaine(n) for n in (1, 2, 3)))
        self.assertEqual(corps["available_actions"], [], "RESET jamais déclaré (§A1.4)")

        _, fermeture = self.client.appeler("POST", "/api/scorecard/close", {"card_id": carte})
        environnements = {env["id"]: env for env in fermeture["environments"]}
        self.assertEqual(environnements["cible-synthetique"]["levels_completed"], 3)

    def test_trois_clics_rates_perdent_la_partie(self) -> None:
        _, guid, _ = self._demarrer_partie()
        for _ in range(3):
            statut, corps = self.client.appeler(
                "POST",
                "/api/cmd/ACTION6",
                {"game_id": "cible-synthetique", "guid": guid, "x": 32, "y": 32},
            )
            self.assertEqual(statut, 200)
        self.assertEqual(corps["state"], "GAME_OVER")
        self.assertEqual(corps["available_actions"], [])

    def test_le_reset_relance_apres_une_perte(self) -> None:
        carte, guid, _ = self._demarrer_partie()
        for _ in range(3):
            self.client.appeler(
                "POST",
                "/api/cmd/ACTION6",
                {"game_id": "cible-synthetique", "guid": guid, "x": 32, "y": 32},
            )
        _, reprise = self.client.appeler(
            "POST",
            "/api/cmd/RESET",
            {"game_id": "cible-synthetique", "card_id": carte, "guid": guid},
        )
        self.assertEqual(reprise["state"], "NOT_FINISHED")
        self.assertFalse(reprise["full_reset"], "relance de la partie existante")

    def test_une_action_sur_une_partie_inconnue_est_refusee(self) -> None:
        statut, corps = self.client.appeler(
            "POST", "/api/cmd/ACTION1", {"game_id": "cible-synthetique", "guid": "inexistant"}
        )
        self.assertEqual(statut, 404)
        self.assertIn("inconnue", corps["error"])

    def test_action6_sans_x_y_est_refuse_comme_le_fil_mesure(self) -> None:
        """§A1.4 mesuré : row/col n'existe pas sur le fil, seuls x et y passent."""
        _, guid, _ = self._demarrer_partie()
        statut, corps = self.client.appeler(
            "POST",
            "/api/cmd/ACTION6",
            {"game_id": "cible-synthetique", "guid": guid, "row": 32, "col": 32},
        )
        self.assertEqual(statut, 400)
        self.assertIn("x et y", corps["error"])


class TestModeEpisode(unittest.TestCase, _ServeurLance):
    """§A3.3 : un épisode enregistré se rejoue, toute déviation est dite."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        chemin = Path(self._dossier.name) / "episode.jsonl"
        chemin.write_text(
            "\n".join(
                json.dumps(entree)
                for entree in (
                    {"command": "RESET", "response": {"guid": "g1", "state": "NOT_FINISHED"}},
                    {"command": "ACTION2", "response": {"guid": "g1", "state": "NOT_FINISHED"}},
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.client = self.demarrer(episode=chemin)

    def tearDown(self) -> None:
        self.arreter()
        self._dossier.cleanup()

    def test_l_episode_est_rejoue_dans_l_ordre(self) -> None:
        statut, premier = self.client.appeler("POST", "/api/cmd/RESET", {})
        self.assertEqual(statut, 200)
        self.assertEqual(premier["guid"], "g1")
        statut, second = self.client.appeler("POST", "/api/cmd/ACTION2", {"guid": "g1"})
        self.assertEqual(statut, 200)

    def test_une_deviation_rend_une_erreur_explicite(self) -> None:
        self.client.appeler("POST", "/api/cmd/RESET", {})
        statut, corps = self.client.appeler("POST", "/api/cmd/ACTION4", {"guid": "g1"})
        self.assertEqual(statut, 409)
        self.assertIn("déviation de l'épisode", corps["error"])
        self.assertIn("ACTION2", corps["error"])

    def test_un_episode_epuise_le_dit(self) -> None:
        self.client.appeler("POST", "/api/cmd/RESET", {})
        self.client.appeler("POST", "/api/cmd/ACTION2", {"guid": "g1"})
        statut, corps = self.client.appeler("POST", "/api/cmd/ACTION2", {"guid": "g1"})
        self.assertEqual(statut, 409)
        self.assertIn("épuisé", corps["error"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
