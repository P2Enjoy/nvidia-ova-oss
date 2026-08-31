"""Le RHAE calculé sur des parties RÉELLEMENT jouées contre le rejeu ARC, en HTTP.

@verifies docs/BACKLOG.md U20 — RHAE
@verifies docs/SPEC_ARCAGI3.md §A6.3 (reproduction d'un RHAE=100.00 de bout en bout
          sur `cible`), §A6.2 (baselines servies par `/api/games`), §A6.4 (pont entre
          l'historique typé et les entrées de la formule), §A1.2 (RESET initial
          gratuit, RESET en cours de partie compté)

Les vecteurs unitaires prouvent la formule ; ce fichier prouve que ce qu'on lui donne
à manger vient bien d'une partie, sans qu'aucun compteur ne soit fabriqué. Les
baselines ne sont pas écrites en dur : elles sont demandées au serveur, comme en
campagne.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.jeu_cible import JeuCible
from arc_replay.serveur import creer_serveur
from avo.arc.client import ArcClient, EtatArc
from avo.arc.interface import InterfaceArc
from avo.arc.rhae import niveaux_joues, rhae_global, rhae_jeu
from avo.config import Config, Mode, charger

#: Clic qui manque la cible à coup sûr : le curseur y démarre, la cible est ailleurs.
CLIC_MANQUE = (32, 32)


class TestRhaeSurPartieReelle(unittest.TestCase):
    def setUp(self) -> None:
        self.serveur: ThreadingHTTPServer = creer_serveur(port=0, niveaux=3)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        self.base = f"http://{hote!s}:{port}"
        self._dossier = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(timeout=5)
        self._dossier.cleanup()

    def _config(self) -> Config:
        return charger(
            Mode.REJEU,
            env={"ARC_BASE_URL": self.base, "ARC_API_KEY": "cle-de-test"},
            racine=Path("/inexistant"),
        )

    def _interface(self) -> InterfaceArc:
        client = ArcClient(self._config())
        interface = InterfaceArc(
            client, game_id="cible-synthetique", card_id=client.open_scorecard([])
        )
        interface.demarrer()
        return interface

    @staticmethod
    def _jouer_niveau_optimal(interface: InterfaceArc, temoin: JeuCible) -> None:
        """Rejoue le chemin parfait du niveau courant, sur les deux côtés."""
        for commande, ligne, colonne in temoin.chemin_optimal():
            coordonnees = (ligne, colonne) if ligne is not None and colonne is not None else None
            interface.jouer(commande, coordonnees)
            temoin.jouer(commande, ligne, colonne)

    def _baselines(self) -> tuple[int, ...]:
        """Comme en campagne : la source de vérité est `/api/games` (§A6.2)."""
        jeux: list[dict[str, Any]] = ArcClient(self._config()).games()
        self.assertEqual(len(jeux), 1)
        return tuple(int(valeur) for valeur in jeux[0]["baseline_actions"])

    # -- preuves ---------------------------------------------------------------
    def test_une_partie_parfaite_rend_exactement_cent(self) -> None:
        """§A6.3 : la valeur que les sources citent pour AVO, reproduite de bout en bout."""
        baselines = self._baselines()
        self.assertEqual(baselines, (39, 19, 18))

        interface = self._interface()
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        for _ in range(3):
            self._jouer_niveau_optimal(interface, temoin)
        assert interface.dernier is not None
        self.assertIs(interface.dernier.etat, EtatArc.GAGNEE)

        niveaux = niveaux_joues(interface.client.historique.entrees, baselines)
        self.assertEqual([niveau.actions for niveau in niveaux], list(baselines))
        self.assertTrue(all(niveau.complete for niveau in niveaux))

        resultat = rhae_jeu(niveaux)
        self.assertEqual(resultat.valeur, 100.0)
        self.assertEqual(resultat.plafond_completion, 100.0)
        self.assertFalse(resultat.plafonne)
        self.assertEqual(rhae_global([resultat.valeur]), 100.0)

    def test_le_total_des_actions_correspond_au_comptage_de_l_interface(self) -> None:
        """Deux comptages indépendants du même run doivent coïncider (§A5.3, §A6.4)."""
        baselines = self._baselines()
        interface = self._interface()
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        for _ in range(3):
            self._jouer_niveau_optimal(interface, temoin)

        niveaux = niveaux_joues(interface.client.historique.entrees, baselines)
        self.assertEqual(sum(niveau.actions for niveau in niveaux), interface.comptage.actions_jeu)

    def test_le_reset_initial_est_gratuit_et_celui_du_milieu_est_compte(self) -> None:
        """§A1.2 mesuré sur une vraie partie : perdue, relancée, puis gagnée au niveau 1.

        3 clics manqués + 1 RESET + 39 actions du chemin parfait = 43 actions pour le
        niveau 1. Si le RESET de création avait été compté, on en lirait 44.
        """
        baselines = self._baselines()
        interface = self._interface()
        for _ in range(3):
            interface.jouer("ACTION6", CLIC_MANQUE)
        assert interface.dernier is not None
        self.assertIs(interface.dernier.etat, EtatArc.PERDUE)

        interface.jouer("RESET")
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        self._jouer_niveau_optimal(interface, temoin)

        niveaux = niveaux_joues(interface.client.historique.entrees, baselines)
        self.assertEqual([niveau.actions for niveau in niveaux], [43, 0, 0])
        self.assertEqual([niveau.complete for niveau in niveaux], [True, False, False])

        # e₁ = 100·(39/43)² ≈ 82,2607 ; Σwe/Σw = e₁/6 ≈ 13,7101 ; plafond = 100/6 ≈ 16,6667.
        resultat = rhae_jeu(niveaux)
        self.assertAlmostEqual(resultat.valeur, 100 * (39 * 39) / (43 * 43) / 6, places=10)
        self.assertTrue(13.70 < resultat.valeur < 13.72, resultat.valeur)
        self.assertFalse(resultat.plafonne, "l'efficacité reste sous le plafond ici")

    def test_une_partie_arretee_au_premier_niveau_est_plafonnee_par_la_completion(self) -> None:
        """§A6.1 bis : les deux niveaux jamais atteints pèsent au dénominateur."""
        baselines = self._baselines()
        interface = self._interface()
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        self._jouer_niveau_optimal(interface, temoin)

        niveaux = niveaux_joues(interface.client.historique.entrees, baselines)
        self.assertEqual([niveau.actions for niveau in niveaux], [39, 0, 0])
        resultat = rhae_jeu(niveaux)
        # Un niveau parfait sur trois : e₁ = 100, Σw = 6, donc 100/6 ≈ 16,67 — et non 100.
        self.assertAlmostEqual(resultat.valeur, 100.0 / 6, places=10)
        self.assertAlmostEqual(resultat.plafond_completion, 100.0 / 6, places=10)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
