"""Rendu et mémoire alimentés par les frames que le serveur envoie réellement.

@verifies docs/BACKLOG.md U18 — Rendu texte, inspection, mémoire de frames
@verifies docs/SPEC_ARCAGI3.md §A4.1 (rendu canonique), §A4.3 (mémoire sans perte,
          inspect, read_pixels, diff), §A2.2 (typage des frames)

Les grilles ne sont pas fabriquées ici : elles traversent le réseau depuis
`arc-replay`, passent par le client typé de U17, puis alimentent la mémoire.
"""

from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from arc_replay.jeu_cible import CIBLE, CURSEUR, JeuCible, cellules_cible
from arc_replay.serveur import creer_serveur
from avo.arc.client import ArcClient
from avo.arc.memoire import MemoireFrames
from avo.arc.rendu import COTE, parser_grille, rendre_grille, rendre_observation
from avo.config import Mode, charger


class TestRenduSurFramesReelles(unittest.TestCase):
    serveur: ThreadingHTTPServer

    def setUp(self) -> None:
        self.serveur = creer_serveur(port=0, niveaux=3)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        config = charger(
            Mode.REJEU,
            env={"ARC_BASE_URL": f"http://{hote!s}:{port}"},
            racine=Path("/inexistant"),
        )
        self.client = ArcClient(config)
        self.memoire = MemoireFrames()

    def tearDown(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(timeout=5)

    def _memoriser(self, resultat: object) -> int:
        frames = [(frame.type.value, frame.grille) for frame in resultat.frames]  # type: ignore[attr-defined]
        return self.memoire.enregistrer_tour(frames)

    def test_une_frame_reelle_se_rend_et_se_relit_a_l_identique(self) -> None:
        debut = self.client.reset()
        grille = debut.frames[-1].grille
        rendu = rendre_grille(grille)
        self.assertEqual(len(rendu.splitlines()), COTE)
        self.assertEqual(parser_grille(rendu), grille)

    def test_l_observation_porte_l_etat_puis_la_grille_du_serveur(self) -> None:
        debut = self.client.reset()
        observation = rendre_observation(
            debut.frames[-1].grille,
            debut.niveau,
            debut.score,
            debut.actions_niveau,
            debut.actions_disponibles,
        )
        premiere = observation.splitlines()[0]
        self.assertIn("niveau=1", premiere)
        self.assertIn("ACTION6", premiere)
        self.assertEqual(len(observation.splitlines()), COTE + 1)

    def test_la_memoire_conserve_les_frames_transitoires_du_serveur(self) -> None:
        debut = self.client.reset()
        self._memoriser(debut)
        resultat = self.client.action(2, guid=debut.guid)
        self._memoriser(resultat)
        self.assertEqual(self.memoire.resume()["frames"], 3)
        self.assertEqual(self.memoire.frame(2, 0).type, "transient")
        self.assertEqual(self.memoire.frame(2, 1).type, "decision")

    def test_le_diff_voit_le_deplacement_du_curseur(self) -> None:
        """Deux cellules changent : celle qu'on quitte, celle où l'on arrive."""
        debut = self.client.reset()
        self._memoriser(debut)
        self._memoriser(self.client.action(2, guid=debut.guid))
        rendu = self.memoire.diff(1, 2)
        self.assertIn("2 cellules modifiées", rendu)
        self.assertIn(f"(32,32):{CURSEUR}→0", rendu)
        self.assertIn(f"(33,32):0→{CURSEUR}", rendu)

    def test_read_pixels_retrouve_la_cible_dans_la_frame_reelle(self) -> None:
        debut = self.client.reset()
        self._memoriser(debut)
        ligne, colonne = min(cellules_cible(1))
        valeurs = self.memoire.read_pixels((ligne, colonne, ligne + 1, colonne + 1))
        self.assertEqual(valeurs.count(f"={CIBLE}"), 4)

    def test_inspect_retrouve_une_frame_de_plusieurs_tours_en_arriere(self) -> None:
        """§A4.3 : rien ne se perd, même après plusieurs tours."""
        debut = self.client.reset()
        self._memoriser(debut)
        for _ in range(5):
            self._memoriser(self.client.action(4, guid=debut.guid))
        rendu = self.memoire.inspect(tour=1, region=(31, 31, 33, 33))
        self.assertIn("tour 1, frame 0 (reset_init)", rendu)
        self.assertIn(str(CURSEUR), rendu)

    def test_le_rendu_d_une_partie_gagnee_reste_exact(self) -> None:
        debut = self.client.reset()
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        for _ in range(3):
            for action, ligne, colonne in temoin.chemin_optimal():
                numero = int(action.removeprefix("ACTION"))
                coordonnees = (
                    (ligne, colonne) if ligne is not None and colonne is not None else None
                )
                resultat = self.client.action(numero, guid=debut.guid, coordonnees=coordonnees)
                temoin.jouer(action, ligne, colonne)
        grille = resultat.frames[-1].grille
        self.assertEqual(parser_grille(rendre_grille(grille)), grille)
        self.assertEqual(resultat.actions_disponibles, ("RESET",))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
