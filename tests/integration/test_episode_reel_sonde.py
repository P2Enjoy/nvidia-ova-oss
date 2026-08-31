"""L'épisode RÉEL capturé par la sonde U22 se rejoue vert par le client.

@verifies docs/BACKLOG.md U22 — Sonde de contrat API officielle
@verifies docs/SPEC_ARCAGI3.md §A1.4 (format de fil mesuré), §A3.3 (épisode réel
          servi par arc-replay, déviation sur corps), §A4.2 (conversion x/y émise
          par le client sur le fil)

C'est la preuve de bout en bout de la sonde : les corps que le client émet
aujourd'hui doivent être ceux que l'API officielle a acceptés le 2026-08-31, et
les réponses réelles doivent se parser sans perte. Si le client déviait du fil
mesuré — une clé renommée, une coordonnée mal convertie — `arc-replay` répondrait
une déviation explicite et ce test rougirait.
"""

from __future__ import annotations

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.serveur import creer_serveur
from avo.arc.client import ArcClient, EtatArc, TypeFrame
from avo.config import Mode, charger

#: L'épisode réel de la sonde, committé expurgé (§A3.3).
EPISODE = Path(__file__).parent.parent / "fixtures" / "arc" / "episodes" / "sonde_u22.jsonl"


class TestEpisodeReelDeLaSonde(unittest.TestCase):
    serveur: ThreadingHTTPServer

    def setUp(self) -> None:
        self.assertTrue(EPISODE.exists(), f"fixture absente : {EPISODE}")
        self.enregistre = [
            json.loads(ligne)
            for ligne in EPISODE.read_text(encoding="utf-8").splitlines()
            if ligne.strip()
        ]
        self.serveur = creer_serveur(port=0, episode=EPISODE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        config = charger(
            Mode.REJEU,
            env={"ARC_BASE_URL": f"http://{hote!s}:{port}"},
            racine=Path("/inexistant"),
        )
        self.client = ArcClient(config, dormir=lambda _: None)

    def tearDown(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(timeout=5)

    def _rejouer(self) -> list[Any]:
        """Rejoue chaque commande enregistrée par la voie normale du client."""
        resultats: list[Any] = []
        guid = ""
        for entree in self.enregistre:
            requete = entree["request"]
            if entree["command"] == "RESET":
                resultat = self.client.reset(game_id=requete["game_id"], card_id="carte-locale")
                guid = resultat.guid
            else:
                numero = int(entree["command"].removeprefix("ACTION"))
                coordonnees = None
                if "x" in requete:
                    # (row, col) internes : le client refera la conversion x/y.
                    coordonnees = (int(requete["y"]), int(requete["x"]))
                resultat = self.client.action(
                    numero, game_id=requete["game_id"], guid=guid, coordonnees=coordonnees
                )
            resultats.append(resultat)
        return resultats

    def test_l_episode_reel_se_rejoue_vert_de_bout_en_bout(self) -> None:
        resultats = self._rejouer()
        self.assertEqual(len(resultats), len(self.enregistre))
        for resultat, entree in zip(resultats, self.enregistre, strict=True):
            with self.subTest(commande=entree["command"]):
                self.assertEqual(resultat.guid, entree["response"]["guid"])
                self.assertEqual(resultat.game_id, entree["response"]["game_id"])
                self.assertEqual(resultat.score, entree["response"]["levels_completed"])
                self.assertEqual(len(resultat.frames), len(entree["response"]["frame"]))

    def test_les_reponses_reelles_se_parsent_sans_perte(self) -> None:
        debut = self._rejouer()[0]
        self.assertIs(debut.etat, EtatArc.EN_COURS)
        self.assertIs(debut.frames[-1].type, TypeFrame.INIT_RESET)
        self.assertEqual(debut.niveau, 1)
        self.assertEqual(debut.niveaux_requis, self.enregistre[0]["response"]["win_levels"])
        self.assertEqual(
            debut.actions_disponibles,
            tuple(
                f"ACTION{n}" if n else "RESET"
                for n in self.enregistre[0]["response"]["available_actions"]
            ),
        )
        for frame in debut.frames:
            self.assertEqual(len(frame.grille), 64)
            self.assertEqual(len(frame.grille[0]), 64)

    def test_la_derniere_frame_d_une_action_reste_une_decision(self) -> None:
        """Les frames multiples d'ACTION6 : transitoires d'abord, décision en dernier."""
        dernier = self._rejouer()[-1]
        self.assertGreaterEqual(len(dernier.frames), 1)
        self.assertIs(dernier.frames[-1].type, TypeFrame.DECISION)
        for frame in dernier.frames[:-1]:
            self.assertIs(frame.type, TypeFrame.TRANSITOIRE)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
