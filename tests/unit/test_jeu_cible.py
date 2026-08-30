"""Preuves du moteur `cible` : déplacements, bordure, clics, protocole, baselines.

@verifies docs/BACKLOG.md U16 — Serveur de rejeu arc-replay et jeu cible
@verifies docs/SPEC_ARCAGI3.md §A3.2 (spécification fermée), §A1.1 (grilles, frames
          transitoires), §A1.2 (protocole de score : RESET, complétion, game over)
"""

from __future__ import annotations

import unittest

from arc_replay.jeu_cible import (
    BORDURE,
    CIBLE,
    CLICS_RATES_MAX,
    COTE,
    CURSEUR,
    CURSEUR_TRANSITOIRE,
    DEPART,
    EtatPartie,
    JeuCible,
    baseline_humaine,
    cellules_cible,
    coin_cible,
)


def _partie(niveaux: int = 3) -> JeuCible:
    jeu = JeuCible(niveaux=niveaux)
    jeu.reset()
    return jeu


def _jouer_optimal(jeu: JeuCible) -> int:
    """Joue le niveau courant parfaitement et rend le nombre d'actions dépensées."""
    actions = 0
    for action, ligne, colonne in jeu.chemin_optimal():
        jeu.jouer(action, ligne, colonne)
        actions += 1
    return actions


class TestGrille(unittest.TestCase):
    def test_la_grille_est_carree_et_bordee(self) -> None:
        grille = _partie()._grille()
        self.assertEqual(len(grille), COTE)
        self.assertTrue(all(len(ligne) == COTE for ligne in grille))
        self.assertEqual(grille[0][0], BORDURE)
        self.assertEqual(grille[COTE - 1][COTE - 1], BORDURE)

    def test_la_cible_occupe_quatre_cellules(self) -> None:
        jeu = _partie()
        grille = jeu._grille()
        cellules = [
            (ligne, colonne)
            for ligne in range(COTE)
            for colonne in range(COTE)
            if grille[ligne][colonne] == CIBLE
        ]
        self.assertEqual(len(cellules), 4)
        self.assertEqual(set(cellules), cellules_cible(jeu.niveau))

    def test_le_curseur_part_au_centre(self) -> None:
        jeu = _partie()
        ligne, colonne = DEPART
        self.assertEqual(jeu._grille()[ligne][colonne], CURSEUR)

    def test_la_cible_bouge_a_chaque_niveau(self) -> None:
        coins = {coin_cible(niveau) for niveau in range(1, 4)}
        self.assertEqual(len(coins), 3)
        for ligne, colonne in coins:
            self.assertTrue(2 <= ligne <= 61 and 2 <= colonne <= 61)


class TestDeplacements(unittest.TestCase):
    def test_les_quatre_directions_deplacent_le_curseur(self) -> None:
        for action, attendu in (
            ("ACTION1", (31, 32)),
            ("ACTION2", (33, 32)),
            ("ACTION3", (32, 31)),
            ("ACTION4", (32, 33)),
        ):
            with self.subTest(action=action):
                jeu = _partie()
                jeu.jouer(action)
                self.assertEqual(jeu.curseur, attendu)

    def test_la_bordure_bloque_mais_l_action_compte(self) -> None:
        """Une action bloquée reste une action dépensée (§A1.2)."""
        jeu = _partie()
        jeu.curseur = (1, 1)
        jeu.jouer("ACTION1")
        self.assertEqual(jeu.curseur, (1, 1))
        self.assertEqual(jeu.actions_niveau, 1)

    def test_deux_frames_dont_une_transitoire(self) -> None:
        """§A3.2 : une frame transitoire précède chaque frame de décision."""
        jeu = _partie()
        resultat = jeu.jouer("ACTION2")
        self.assertEqual(len(resultat.frames), 2)
        ligne, colonne = jeu.curseur
        self.assertEqual(resultat.frames[0][ligne][colonne], CURSEUR_TRANSITOIRE)
        self.assertEqual(resultat.frames[1][ligne][colonne], CURSEUR)


class TestClics(unittest.TestCase):
    def test_un_clic_sur_la_cible_avec_le_curseur_complete_le_niveau(self) -> None:
        jeu = _partie()
        actions = _jouer_optimal(jeu)
        self.assertEqual(jeu.score, 1)
        self.assertEqual(jeu.niveau, 2)
        self.assertEqual(actions, baseline_humaine(1))

    def test_un_clic_ailleurs_que_sur_le_curseur_ne_compte_pas_comme_reussi(self) -> None:
        """Les coordonnées doivent être celles du curseur (§A3.2)."""
        jeu = _partie()
        cible = next(iter(cellules_cible(1)))
        jeu.jouer("ACTION6", cible[0], cible[1])
        self.assertEqual(jeu.score, 0)
        self.assertEqual(jeu.clics_rates, 1)

    def test_trois_clics_rates_perdent_la_tentative(self) -> None:
        jeu = _partie()
        for _ in range(CLICS_RATES_MAX):
            jeu.jouer("ACTION6", *jeu.curseur)
        self.assertIs(jeu.etat, EtatPartie.PERDUE)
        self.assertEqual(jeu.actions_disponibles_test(), ["RESET"])

    def test_apres_la_perte_seul_reset_est_disponible(self) -> None:
        jeu = _partie()
        for _ in range(CLICS_RATES_MAX):
            jeu.jouer("ACTION6", *jeu.curseur)
        with self.assertRaises(ValueError):
            jeu.jouer("ACTION1")

    def test_le_clic_exige_des_coordonnees(self) -> None:
        with self.assertRaises(ValueError):
            _partie().jouer("ACTION6")

    def test_une_action_inconnue_est_refusee(self) -> None:
        with self.assertRaises(ValueError):
            _partie().jouer("ACTION9")


class TestProtocole(unittest.TestCase):
    """§A1.2 : le RESET initial est gratuit, les suivants coûtent une action."""

    def test_le_reset_initial_ne_coute_rien(self) -> None:
        jeu = JeuCible()
        jeu.reset()
        self.assertEqual(jeu.actions_totales, 0)
        self.assertIs(jeu.etat, EtatPartie.EN_COURS)

    def test_un_reset_en_cours_de_partie_coute_une_action(self) -> None:
        jeu = _partie()
        jeu.jouer("ACTION2")
        jeu.reset()
        self.assertEqual(jeu.actions_totales, 2)

    def test_le_reset_replace_le_curseur_et_efface_les_ratés(self) -> None:
        jeu = _partie()
        jeu.jouer("ACTION2")
        jeu.jouer("ACTION6", *jeu.curseur)
        jeu.reset()
        self.assertEqual(jeu.curseur, DEPART)
        self.assertEqual(jeu.clics_rates, 0)

    def test_completer_tous_les_niveaux_gagne_la_partie(self) -> None:
        jeu = _partie(niveaux=3)
        total = 0
        for _ in range(3):
            total += _jouer_optimal(jeu)
        self.assertIs(jeu.etat, EtatPartie.GAGNEE)
        self.assertEqual(jeu.score, 3)
        self.assertEqual(total, sum(baseline_humaine(n) for n in (1, 2, 3)))

    def test_le_compteur_du_niveau_repart_a_zero(self) -> None:
        jeu = _partie()
        _jouer_optimal(jeu)
        self.assertEqual(jeu.actions_niveau, 0)
        self.assertEqual(jeu.actions_par_niveau[1], baseline_humaine(1))


class TestBaselines(unittest.TestCase):
    """§A3.2 : la baseline est en forme fermée, donc le RHAE attendu est connu."""

    def test_la_baseline_est_la_distance_plus_le_clic(self) -> None:
        for niveau in (1, 2, 3):
            with self.subTest(niveau=niveau):
                ligne, colonne = DEPART
                distance = min(
                    abs(ligne - cl) + abs(colonne - cc) for cl, cc in cellules_cible(niveau)
                )
                self.assertEqual(baseline_humaine(niveau), distance + 1)

    def test_une_partie_parfaite_depense_exactement_la_baseline(self) -> None:
        """C'est ce qui rendra le RHAE attendu vérifiable exactement (§A6.3)."""
        jeu = _partie()
        for niveau in (1, 2, 3):
            with self.subTest(niveau=niveau):
                self.assertEqual(_jouer_optimal(jeu), baseline_humaine(niveau))

    def test_les_baselines_sont_exposees_pour_le_listing(self) -> None:
        self.assertEqual(JeuCible(niveaux=3).baselines(), [baseline_humaine(n) for n in (1, 2, 3)])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
