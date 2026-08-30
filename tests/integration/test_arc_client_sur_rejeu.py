"""Le client ARC face au contrat local, en HTTP réel.

@verifies docs/BACKLOG.md U17 — Client API ARC
@verifies docs/SPEC_ARCAGI3.md §A2.1 (méthodes), §A2.2 (historique typé et persisté),
          §A2.3 (garde anti-publication), §A1.2 (protocole), §A1.4 (format de fil)
@verifies docs/SPEC_HARNAIS.md §H6.1 (les frames vivent dans le workspace du run)

Le client parle au serveur de U16 par le réseau : c'est la première fois que les deux
côtés du contrat de fil se rencontrent. S'ils divergeaient, ces tests rougiraient.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.jeu_cible import JeuCible, baseline_humaine
from arc_replay.serveur import creer_serveur
from avo.arc.client import ArcClient, ArcProtocoleError, EtatArc, PublicationInterdite, TypeFrame
from avo.config import Config, Mode, charger
from avo.memory.workspace import Workspace


class _PileArc:
    def demarrer(self, **kwargs: Any) -> str:
        self.serveur: ThreadingHTTPServer = creer_serveur(port=0, **kwargs)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def arreter(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(timeout=5)


class TestClientSurRejeu(unittest.TestCase, _PileArc):
    def setUp(self) -> None:
        self.base = self.demarrer(niveaux=3)
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self.arreter()
        self._dossier.cleanup()

    def _config(self) -> Config:
        return charger(
            Mode.REJEU,
            env={"ARC_BASE_URL": self.base, "ARC_API_KEY": "cle-de-test"},
            racine=Path("/inexistant"),
        )

    def _client(self) -> ArcClient:
        return ArcClient(self._config())

    def test_le_listing_rend_les_baselines_du_jeu(self) -> None:
        jeux = self._client().games()
        self.assertEqual(len(jeux), 1)
        self.assertEqual(jeux[0]["baseline_actions"], [baseline_humaine(n) for n in (1, 2, 3)])

    def test_le_cycle_de_scorecard_fonctionne(self) -> None:
        client = self._client()
        carte = client.open_scorecard(["integration"])
        self.assertFalse(client.scorecard(carte)["closed"])
        self.assertTrue(client.close_scorecard(carte)["closed"])

    def test_une_partie_complete_par_le_client(self) -> None:
        """Les deux côtés du contrat de fil se rencontrent réellement."""
        client = self._client()
        carte = client.open_scorecard([])
        debut = client.reset(game_id="cible-synthetique", card_id=carte)
        self.assertIs(debut.frames[-1].type, TypeFrame.INIT_RESET)
        guid = debut.guid

        temoin = JeuCible(niveaux=3)
        temoin.reset()
        actions = 0
        for niveau in (1, 2, 3):
            for action, ligne, colonne in temoin.chemin_optimal():
                numero = int(action.removeprefix("ACTION"))
                coordonnees = (
                    (ligne, colonne) if ligne is not None and colonne is not None else None
                )
                resultat = client.action(numero, guid=guid, coordonnees=coordonnees, card_id=carte)
                temoin.jouer(action, ligne, colonne)
                actions += 1
            self.assertEqual(resultat.score, niveau)

        self.assertIs(resultat.etat, EtatArc.GAGNEE)
        self.assertIs(resultat.frames[-1].type, TypeFrame.TERMINAL_GAGNE)
        self.assertEqual(actions, sum(baseline_humaine(n) for n in (1, 2, 3)))
        self.assertTrue(client.close_scorecard(carte)["closed"])

    def test_les_frames_transitoires_sont_bien_etiquetees(self) -> None:
        client = self._client()
        debut = client.reset()
        resultat = client.action(2, guid=debut.guid)
        self.assertEqual(len(resultat.frames), 2)
        self.assertIs(resultat.frames[0].type, TypeFrame.TRANSITOIRE)
        self.assertIs(resultat.frames[1].type, TypeFrame.DECISION)

    def test_le_game_over_est_typé_et_ferme_les_actions(self) -> None:
        client = self._client()
        debut = client.reset()
        for _ in range(3):
            resultat = client.action(6, guid=debut.guid, coordonnees=(32, 32))
        self.assertIs(resultat.etat, EtatArc.PERDUE)
        self.assertIs(resultat.frames[-1].type, TypeFrame.TERMINAL_PERDU)
        self.assertEqual(resultat.actions_disponibles, ("RESET",))

    def test_le_reset_relance_apres_la_perte(self) -> None:
        client = self._client()
        debut = client.reset()
        for _ in range(3):
            client.action(6, guid=debut.guid, coordonnees=(32, 32))
        reprise = client.reset(guid=debut.guid)
        self.assertIs(reprise.etat, EtatArc.EN_COURS)
        self.assertIs(reprise.frames[-1].type, TypeFrame.INIT_RESET)

    def test_l_historique_est_persiste_par_niveau_dans_le_run(self) -> None:
        """§A2.2 et §H6.1 : les frames vivent dans le workspace du run."""
        client = self._client()
        espace = Workspace.ouvrir(client.config, "run-arc", racine=self.racine)
        debut = client.reset()
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        for action, ligne, colonne in temoin.chemin_optimal():
            numero = int(action.removeprefix("ACTION"))
            client.action(
                numero,
                guid=debut.guid,
                coordonnees=(ligne, colonne) if ligne is not None and colonne is not None else None,
            )
            temoin.jouer(action, ligne, colonne)

        client.historique.ecrire(espace.chemin / "frames")
        fichiers = sorted((espace.chemin / "frames").glob("*.jsonl"))
        self.assertTrue(fichiers)
        entrees = [
            json.loads(ligne) for ligne in fichiers[0].read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(entrees[0]["commande"], "RESET")
        self.assertIsNone(entrees[0]["frame_de_decision"])
        self.assertIsNotNone(entrees[1]["frame_de_decision"])
        self.assertIn("frames/niveau_01.jsonl", espace.arborescence())

    def test_une_commande_invalide_est_rendue_avec_son_motif(self) -> None:
        client = self._client()
        debut = client.reset()
        with self.assertRaises(ArcProtocoleError) as capture:
            client.action(6, guid=debut.guid)
        self.assertIn("coordonnées", str(capture.exception))

    def test_la_garde_refuse_l_api_officielle_en_mode_rejeu(self) -> None:
        """§A2.3 : par construction, ces tests ne peuvent pas publier."""
        with self.assertRaises(PublicationInterdite):
            ArcClient(
                charger(
                    Mode.REJEU,
                    env={"ARC_BASE_URL": "https://three.arcprize.org"},
                    racine=Path("/inexistant"),
                )
            )


class TestClientSurEpisode(unittest.TestCase, _PileArc):
    """§A3.3 : un épisode dévié rend une erreur explicite, jamais une réponse inventée."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        chemin = Path(self._dossier.name) / "episode.jsonl"
        chemin.write_text(
            "\n".join(
                json.dumps(entree)
                for entree in (
                    {
                        "command": "RESET",
                        "response": {
                            "guid": "g1",
                            "game_id": "reel",
                            "frames": [[[0]]],
                            "state": "NOT_FINISHED",
                            "score": 0,
                            "level": 1,
                            "actions_level": 0,
                            "available_actions": ["ACTION1", "RESET"],
                        },
                    },
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.base = self.demarrer(episode=chemin)

    def tearDown(self) -> None:
        self.arreter()
        self._dossier.cleanup()

    def _client(self) -> ArcClient:
        return ArcClient(
            charger(Mode.REJEU, env={"ARC_BASE_URL": self.base}, racine=Path("/inexistant")),
            dormir=lambda _: None,
        )

    def test_l_episode_enregistre_se_rejoue(self) -> None:
        resultat = self._client().reset()
        self.assertEqual(resultat.guid, "g1")
        self.assertEqual(resultat.game_id, "reel")

    def test_une_deviation_remonte_comme_erreur_et_non_comme_reponse(self) -> None:
        client = self._client()
        client.reset()
        with self.assertRaises(Exception) as capture:
            client.action(4, guid="g1")
        self.assertNotIsInstance(capture.exception, AssertionError)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
