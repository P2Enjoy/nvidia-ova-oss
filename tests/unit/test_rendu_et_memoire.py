"""Preuves du rendu et de la mémoire de frames : sorties exactes, rien ne se perd.

@verifies docs/BACKLOG.md U18 — Rendu texte, inspection, mémoire de frames
@verifies docs/SPEC_ARCAGI3.md §A4.1 (rendu canonique, ligne d'état), §A4.2
          (coordonnées (row, col)), §A4.3 (mémoire sans perte, inspect, read_pixels,
          diff), §A4.4 (outils purs, sorties attendues exactes)
"""

from __future__ import annotations

import unittest

from arc_replay.jeu_cible import CIBLE, JeuCible, cellules_cible
from avo.arc.memoire import (
    DIFF_CELLULES_MAX,
    VUES_MAX,
    FrameInconnue,
    MemoireFrames,
    RegionInvalide,
    outil_diff,
    outil_inspect,
    outil_read_pixels,
    rendre_region,
    valider_region,
)
from avo.arc.rendu import (
    COTE,
    GrilleInvalide,
    ligne_etat,
    parser_grille,
    rendre_grille,
    rendre_observation,
    valider_grille,
)


def _grille(valeur: int = 0) -> list[list[int]]:
    return [[valeur] * COTE for _ in range(COTE)]


def _grille_de_jeu(niveau: int = 1) -> list[list[int]]:
    jeu = JeuCible()
    jeu.niveau = niveau
    jeu.reset()
    return jeu._grille()


class TestRenduCanonique(unittest.TestCase):
    """§A4.1 : la grille exacte, rien d'autre."""

    def test_le_rendu_a_soixante_quatre_lignes_de_soixante_quatre_valeurs(self) -> None:
        lignes = rendre_grille(_grille()).splitlines()
        self.assertEqual(len(lignes), COTE)
        self.assertTrue(all(len(ligne.split()) == COTE for ligne in lignes))

    def test_les_valeurs_sont_separees_par_un_espace(self) -> None:
        grille = _grille()
        grille[0][0], grille[0][1] = 3, 12
        self.assertTrue(rendre_grille(grille).startswith("3 12 0 0"))

    def test_le_rendu_ne_porte_aucune_interpretation(self) -> None:
        """§A5.1 : nommer un objet reviendrait à souffler la réponse à l'agent."""
        rendu = rendre_grille(_grille_de_jeu())
        for interdit in ("cible", "curseur", "bordure", "target", "cursor"):
            self.assertNotIn(interdit, rendu.lower())

    def test_une_grille_mal_formee_est_refusee(self) -> None:
        with self.assertRaises(GrilleInvalide):
            valider_grille([[0] * COTE] * (COTE - 1))
        with self.assertRaises(GrilleInvalide) as capture:
            valider_grille([[0] * 3] + [[0] * COTE] * (COTE - 1))
        self.assertIn("ligne 0", str(capture.exception))


class TestAllerRetour(unittest.TestCase):
    """La propriété exigée : rendu ∘ parsing = identité."""

    def test_le_rendu_puis_l_analyse_restituent_la_grille(self) -> None:
        for niveau in (1, 2, 3):
            with self.subTest(niveau=niveau):
                grille = _grille_de_jeu(niveau)
                self.assertEqual(parser_grille(rendre_grille(grille)), grille)

    def test_l_aller_retour_tient_sur_toutes_les_couleurs(self) -> None:
        grille = _grille()
        for index in range(16):
            grille[index][index] = index
        self.assertEqual(parser_grille(rendre_grille(grille)), grille)


class TestLigneEtat(unittest.TestCase):
    def test_la_ligne_porte_les_quatre_informations(self) -> None:
        ligne = ligne_etat(2, 1, 17, ["ACTION1", "ACTION6", "RESET"])
        self.assertEqual(ligne, "niveau=2 score=1 actions_niveau=17 actions=ACTION1,ACTION6,RESET")

    def test_l_absence_d_action_est_dite(self) -> None:
        self.assertIn("actions=(aucune)", ligne_etat(1, 0, 0, []))

    def test_l_observation_est_l_etat_puis_la_grille(self) -> None:
        observation = rendre_observation(_grille(), 1, 0, 0, ["RESET"])
        lignes = observation.splitlines()
        self.assertTrue(lignes[0].startswith("niveau=1"))
        self.assertEqual(len(lignes), COTE + 1)


class TestRegions(unittest.TestCase):
    """§A4.3 : les marges d'index rattachent ce qu'on voit aux coordonnées."""

    def test_une_decoupe_porte_les_index_en_marge(self) -> None:
        grille = _grille()
        grille[3][4] = 7
        rendu = rendre_region(grille, (2, 3, 4, 5))
        lignes = rendu.splitlines()
        self.assertEqual(lignes[0].split(), ["3", "4", "5"], "index de colonnes")
        self.assertEqual([ligne.split()[0] for ligne in lignes[1:]], ["2", "3", "4"])
        self.assertIn("7", lignes[2])

    def test_une_region_hors_grille_est_refusee(self) -> None:
        with self.assertRaises(RegionInvalide) as capture:
            valider_region((0, 0, COTE, 0))
        self.assertIn("hors de la grille", str(capture.exception))

    def test_une_region_mal_ordonnee_est_refusee(self) -> None:
        with self.assertRaises(RegionInvalide) as capture:
            valider_region((5, 5, 2, 9))
        self.assertIn("mal ordonnée", str(capture.exception))

    def test_une_region_d_une_seule_cellule_est_valide(self) -> None:
        self.assertEqual(valider_region((3, 3, 3, 3)), (3, 3, 3, 3))


class TestMemoireSansPerte(unittest.TestCase):
    """§A4.3 : toute frame reçue est conservée, décision comme transitoire."""

    def _memoire(self) -> MemoireFrames:
        memoire = MemoireFrames()
        memoire.enregistrer_tour([("reset_init", _grille_de_jeu(1))])
        memoire.enregistrer_tour([("transient", _grille(1)), ("decision", _grille_de_jeu(2))])
        return memoire

    def test_les_frames_transitoires_sont_conservees_elles_aussi(self) -> None:
        memoire = self._memoire()
        self.assertEqual(len(memoire.frames), 3)
        self.assertEqual(memoire.resume()["frames"], 3)

    def test_seules_les_frames_agissables_comptent_comme_decision(self) -> None:
        memoire = self._memoire()
        types = {frame.type for frame in memoire.frames_de_decision()}
        self.assertEqual(types, {"reset_init", "decision"})
        self.assertEqual(len(memoire.frames_de_decision()), 2)

    def test_la_derniere_frame_d_un_tour_est_rendue_par_defaut(self) -> None:
        memoire = self._memoire()
        self.assertEqual(memoire.frame(2).type, "decision")
        self.assertEqual(memoire.frame(2, 0).type, "transient")

    def test_sans_tour_la_frame_la_plus_recente_est_rendue(self) -> None:
        self.assertEqual(self._memoire().frame().tour, 2)

    def test_un_tour_inconnu_liste_les_tours_disponibles(self) -> None:
        with self.assertRaises(FrameInconnue) as capture:
            self._memoire().frame(9)
        self.assertIn("[1, 2]", str(capture.exception))

    def test_un_index_inconnu_liste_les_index_disponibles(self) -> None:
        with self.assertRaises(FrameInconnue) as capture:
            self._memoire().frame(2, 5)
        self.assertIn("[0, 1]", str(capture.exception))

    def test_une_memoire_vide_le_dit(self) -> None:
        with self.assertRaises(FrameInconnue):
            MemoireFrames().frame()

    def test_la_memoire_copie_les_grilles(self) -> None:
        """Une grille modifiée après coup ne doit pas altérer le souvenir."""
        grille = _grille()
        memoire = MemoireFrames()
        memoire.enregistrer_tour([("decision", grille)])
        grille[0][0] = 9
        self.assertEqual(memoire.frame().grille[0][0], 0)


class TestInspection(unittest.TestCase):
    def setUp(self) -> None:
        self.memoire = MemoireFrames()
        self.memoire.enregistrer_tour([("decision", _grille_de_jeu(1))])

    def test_inspect_sans_region_rend_la_grille_entiere(self) -> None:
        rendu = self.memoire.inspect()
        self.assertIn("tour 1, frame 0 (decision)", rendu)
        self.assertEqual(len(rendu.splitlines()), COTE + 1)

    def test_inspect_avec_region_rend_une_decoupe_indexee(self) -> None:
        ligne, colonne = min(cellules_cible(1))
        rendu = self.memoire.inspect(region=(ligne, colonne, ligne + 1, colonne + 1))
        self.assertIn(str(CIBLE), rendu)
        self.assertIn(str(ligne), rendu)

    def test_plusieurs_vues_sont_admises(self) -> None:
        rendu = self.memoire.inspect(vues=[(0, 0, 1, 1), (10, 10, 11, 11)])
        self.assertEqual(rendu.count("région"), 2)

    def test_trop_de_vues_est_refuse(self) -> None:
        with self.assertRaises(RegionInvalide) as capture:
            self.memoire.inspect(vues=[(0, 0, 1, 1)] * (VUES_MAX + 1))
        self.assertIn(str(VUES_MAX), str(capture.exception))

    def test_read_pixels_rend_les_valeurs_exactes(self) -> None:
        ligne, colonne = min(cellules_cible(1))
        rendu = self.memoire.read_pixels((ligne, colonne, ligne, colonne))
        self.assertEqual(rendu, f"({ligne},{colonne})={CIBLE}")

    def test_les_outils_sont_purs(self) -> None:
        """§A4.4 : inspecter ne change rien à la mémoire."""
        avant = len(self.memoire.frames)
        self.memoire.inspect()
        self.memoire.read_pixels((0, 0, 2, 2))
        self.assertEqual(len(self.memoire.frames), avant)


class TestDiff(unittest.TestCase):
    def test_deux_frames_identiques_ne_donnent_aucun_changement(self) -> None:
        memoire = MemoireFrames()
        memoire.enregistrer_tour([("decision", _grille())])
        memoire.enregistrer_tour([("decision", _grille())])
        self.assertIn("aucune cellule modifiée", memoire.diff(1, 2))

    def test_les_cellules_modifiees_sont_listees_avec_leur_transition(self) -> None:
        memoire = MemoireFrames()
        memoire.enregistrer_tour([("decision", _grille())])
        apres = _grille()
        apres[5][7] = 3
        memoire.enregistrer_tour([("decision", apres)])
        rendu = memoire.diff(1, 2)
        self.assertIn("1 cellules modifiées", rendu)
        self.assertIn("(5,7):0→3", rendu)

    def test_la_liste_est_bornee_et_le_reste_est_compte(self) -> None:
        """§A4.3 : une énumération de milliers de cellules noierait l'information."""
        memoire = MemoireFrames()
        memoire.enregistrer_tour([("decision", _grille(0))])
        memoire.enregistrer_tour([("decision", _grille(1))])
        rendu = memoire.diff(1, 2)
        self.assertIn(f"{COTE * COTE} cellules modifiées", rendu)
        # Chaque cellule listée s'écrit « (ligne,colonne):ancien→nouveau » : compter
        # « ): » compte les cellules, là où compter les flèches inclurait celle de
        # l'en-tête « tours 1 → 2 ».
        self.assertEqual(rendu.count("):"), DIFF_CELLULES_MAX)
        self.assertIn(f"et {COTE * COTE - DIFF_CELLULES_MAX} autres", rendu)


class TestSurfaceOutil(unittest.TestCase):
    """§H7.4 : une erreur d'outil est rendue au modèle, jamais levée."""

    def setUp(self) -> None:
        self.memoire = MemoireFrames()
        self.memoire.enregistrer_tour([("decision", _grille())])

    def test_inspect_sur_un_tour_inconnu_rend_un_texte_d_erreur(self) -> None:
        self.assertTrue(outil_inspect(self.memoire, turn=42).startswith("error:"))

    def test_read_pixels_sur_une_region_invalide_rend_un_texte_d_erreur(self) -> None:
        resultat = outil_read_pixels(self.memoire, region=[0, 0, 999, 0])
        self.assertTrue(resultat.startswith("error:"))
        self.assertIn("hors de la grille", resultat)

    def test_une_region_mal_formee_est_signalee(self) -> None:
        self.assertIn("ligne0", outil_read_pixels(self.memoire, region=[1, 2]))

    def test_diff_sur_un_tour_inconnu_rend_un_texte_d_erreur(self) -> None:
        self.assertTrue(outil_diff(self.memoire, 1, 42).startswith("error:"))

    def test_les_outils_annoncent_qu_ils_sont_gratuits(self) -> None:
        """§A1.2 : l'inspection ne coûte aucune action, l'agent doit le savoir."""
        from avo.arc.memoire import SCHEMA_DIFF, SCHEMA_INSPECT, SCHEMA_READ_PIXELS

        for schema in (SCHEMA_INSPECT, SCHEMA_READ_PIXELS, SCHEMA_DIFF):
            with self.subTest(outil=schema["function"]["name"]):
                self.assertIn("gratuit", schema["function"]["description"].lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
