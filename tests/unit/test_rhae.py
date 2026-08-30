"""Preuves du RHAE : vecteurs exacts, refus, et attribution des actions aux niveaux.

@verifies docs/BACKLOG.md U20 — RHAE
@verifies docs/SPEC_ARCAGI3.md §A6.1 (définition Tycho §3.1), §A6.1 bis (la somme
          porte sur tous les niveaux du jeu), §A6.3 (vecteurs), §A6.4 (contrat),
          §A1.2 (RESET initial gratuit, suivants comptés), §A2.2 (historique typé)

Les valeurs attendues sont calculées à la main dans les commentaires : un test qui
recopierait la formule ne prouverait rien d'autre que sa propre cohérence.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from avo.arc.rhae import (
    EFFICACITE_MAX,
    NiveauJoue,
    RhaeInvalide,
    efficacite_niveau,
    niveaux_joues,
    rhae_global,
    rhae_jeu,
)

#: Baselines du jeu de rejeu (§A3.2), en forme fermée.
CIBLE = (39, 19, 18)


@dataclass
class _Entree:
    """Le peu qu'une entrée d'historique doit porter pour le calcul (§A6.4)."""

    commande: str
    niveau: int
    score: int


class TestEfficaciteDUnNiveau(unittest.TestCase):
    """§A6.3 : les vecteurs travaillés à la main."""

    def test_un_niveau_non_complete_vaut_zero_meme_joue_vite(self) -> None:
        """Aller vite sans finir ne rapporte rien : c'est la complétion qui ouvre le score."""
        niveau = NiveauJoue(niveau=1, baseline=10, actions=5, complete=False)
        self.assertEqual(efficacite_niveau(niveau), 0.0)

    def test_egaler_l_humain_vaut_exactement_cent(self) -> None:
        # 100·(39/39)² = 100
        niveau = NiveauJoue(niveau=1, baseline=39, actions=39, complete=True)
        self.assertEqual(efficacite_niveau(niveau), 100.0)

    def test_faire_mieux_que_l_humain_est_plafonne_a_115(self) -> None:
        # 100·(10/5)² = 400, plafonné à 115
        niveau = NiveauJoue(niveau=1, baseline=10, actions=5, complete=True)
        self.assertEqual(efficacite_niveau(niveau), EFFICACITE_MAX)

    def test_faire_deux_fois_pire_que_l_humain_vaut_vingt_cinq(self) -> None:
        # 100·(10/20)² = 25 — le carré punit l'inefficacité plus que linéairement
        niveau = NiveauJoue(niveau=1, baseline=10, actions=20, complete=True)
        self.assertEqual(efficacite_niveau(niveau), 25.0)

    def test_zero_action_avec_complétion_vaut_zero(self) -> None:
        """Cas nommé par la définition, inatteignable par le protocole."""
        niveau = NiveauJoue(niveau=1, baseline=10, actions=0, complete=True)
        self.assertEqual(efficacite_niveau(niveau), 0.0)


class TestRefusDeNiveau(unittest.TestCase):
    """§A6.4 : une donnée impossible lève, elle ne devient pas un score de 0."""

    def test_une_baseline_nulle_est_refusee(self) -> None:
        with self.assertRaises(RhaeInvalide) as capture:
            NiveauJoue(niveau=1, baseline=0, actions=5, complete=True)
        self.assertIn("baseline", str(capture.exception))

    def test_une_baseline_negative_est_refusee(self) -> None:
        with self.assertRaises(RhaeInvalide):
            NiveauJoue(niveau=1, baseline=-3, actions=5, complete=True)

    def test_un_niveau_zero_est_refuse(self) -> None:
        with self.assertRaises(RhaeInvalide):
            NiveauJoue(niveau=0, baseline=10, actions=5, complete=True)

    def test_des_actions_negatives_sont_refusees(self) -> None:
        with self.assertRaises(RhaeInvalide):
            NiveauJoue(niveau=1, baseline=10, actions=-1, complete=False)


class TestRhaeDUnJeu(unittest.TestCase):
    """§A6.1 : minimum de l'efficacité pondérée et du plafond par complétion."""

    def test_une_partie_parfaite_vaut_cent(self) -> None:
        niveaux = [
            NiveauJoue(niveau=index + 1, baseline=base, actions=base, complete=True)
            for index, base in enumerate(CIBLE)
        ]
        resultat = rhae_jeu(niveaux)
        self.assertEqual(resultat.valeur, 100.0)
        self.assertEqual(resultat.plafond_completion, 100.0)
        self.assertFalse(resultat.plafonne)

    def test_les_niveaux_tardifs_pesent_plus(self) -> None:
        """Σwe/Σw = (1·100 + 2·25 + 3·115)/6 = 495/6 = 82,5 — la moyenne simple ferait 80."""
        niveaux = [
            NiveauJoue(niveau=1, baseline=10, actions=10, complete=True),
            NiveauJoue(niveau=2, baseline=10, actions=20, complete=True),
            NiveauJoue(niveau=3, baseline=10, actions=5, complete=True),
        ]
        resultat = rhae_jeu(niveaux)
        self.assertEqual(resultat.efficacite_ponderee, 82.5)
        self.assertNotEqual(resultat.efficacite_ponderee, 80.0, "pondération non appliquée")
        self.assertEqual(resultat.valeur, 82.5)

    def test_la_completion_plafonne_un_jeu_partiellement_termine(self) -> None:
        """e₁ = min(115, 100·(39/20)²) = 115 → 115/6 = 19,17 ; plafond = 100·1/6 = 16,67."""
        niveaux = [
            NiveauJoue(niveau=1, baseline=39, actions=20, complete=True),
            NiveauJoue(niveau=2, baseline=19, actions=0, complete=False),
            NiveauJoue(niveau=3, baseline=18, actions=0, complete=False),
        ]
        resultat = rhae_jeu(niveaux)
        self.assertAlmostEqual(resultat.efficacite_ponderee, 115.0 / 6, places=10)
        self.assertAlmostEqual(resultat.plafond_completion, 100.0 / 6, places=10)
        self.assertAlmostEqual(resultat.valeur, 100.0 / 6, places=10)
        self.assertTrue(resultat.plafonne)

    def test_les_niveaux_jamais_atteints_pesent_au_denominateur(self) -> None:
        """§A6.1 bis : sans eux, terminer le premier niveau sur trois vaudrait 100."""
        niveaux = [
            NiveauJoue(niveau=1, baseline=39, actions=39, complete=True),
            NiveauJoue(niveau=2, baseline=19, actions=0, complete=False),
            NiveauJoue(niveau=3, baseline=18, actions=0, complete=False),
        ]
        self.assertAlmostEqual(rhae_jeu(niveaux).valeur, 100.0 / 6, places=10)
        self.assertEqual(rhae_jeu(niveaux[:1]).valeur, 100.0, "sur le seul niveau atteint")

    def test_un_jeu_sans_aucune_completion_vaut_zero(self) -> None:
        niveaux = [NiveauJoue(niveau=1, baseline=39, actions=200, complete=False)]
        resultat = rhae_jeu(niveaux)
        self.assertEqual(resultat.valeur, 0.0)
        self.assertEqual(resultat.plafond_completion, 0.0)

    def test_le_resume_est_journalisable(self) -> None:
        niveaux = [
            NiveauJoue(niveau=1, baseline=39, actions=39, complete=True),
            NiveauJoue(niveau=2, baseline=19, actions=5, complete=False),
        ]
        resume = rhae_jeu(niveaux).resume()
        self.assertEqual(resume["niveaux"], 2)
        self.assertEqual(resume["niveaux_completes"], 1)
        self.assertEqual(resume["actions"], 44)

    def test_une_suite_a_trou_est_refusee(self) -> None:
        niveaux = [
            NiveauJoue(niveau=1, baseline=39, actions=39, complete=True),
            NiveauJoue(niveau=3, baseline=18, actions=18, complete=True),
        ]
        with self.assertRaises(RhaeInvalide) as capture:
            rhae_jeu(niveaux)
        self.assertIn("[1, 2]", str(capture.exception))

    def test_un_doublon_est_refuse(self) -> None:
        niveaux = [NiveauJoue(niveau=1, baseline=39, actions=39, complete=True)] * 2
        with self.assertRaises(RhaeInvalide):
            rhae_jeu(niveaux)

    def test_un_jeu_sans_niveau_est_refuse(self) -> None:
        with self.assertRaises(RhaeInvalide):
            rhae_jeu([])


class TestRhaeGlobal(unittest.TestCase):
    def test_moyenne_arithmetique_sur_le_perimetre(self) -> None:
        self.assertEqual(rhae_global([100.0, 50.0]), 75.0)

    def test_un_perimetre_vide_est_refuse(self) -> None:
        """Une moyenne sur rien n'est pas 0 : elle n'existe pas."""
        with self.assertRaises(RhaeInvalide):
            rhae_global([])


class TestAttributionDesActions(unittest.TestCase):
    """§A6.4 : le pont entre l'historique typé et les entrées de la formule."""

    def test_le_reset_de_creation_est_gratuit(self) -> None:
        entrees = [_Entree(commande="RESET", niveau=1, score=0)]
        niveaux = niveaux_joues(entrees, CIBLE)
        self.assertEqual([niveau.actions for niveau in niveaux], [0, 0, 0])

    def test_chaque_commande_suivante_coute_une_action(self) -> None:
        entrees = [
            _Entree(commande="RESET", niveau=1, score=0),
            _Entree(commande="ACTION2", niveau=1, score=0),
            _Entree(commande="ACTION2", niveau=1, score=0),
        ]
        self.assertEqual(niveaux_joues(entrees, CIBLE)[0].actions, 2)

    def test_un_reset_en_cours_de_partie_coute_une_action(self) -> None:
        entrees = [
            _Entree(commande="RESET", niveau=1, score=0),
            _Entree(commande="RESET", niveau=1, score=0),
        ]
        self.assertEqual(niveaux_joues(entrees, CIBLE)[0].actions, 1)

    def test_l_action_qui_complete_reste_imputee_au_niveau_qu_elle_termine(self) -> None:
        """L'API la renvoie avec le niveau SUIVANT ; l'y imputer fausserait deux niveaux."""
        entrees = [
            _Entree(commande="RESET", niveau=1, score=0),
            _Entree(commande="ACTION2", niveau=1, score=0),
            _Entree(commande="ACTION6", niveau=2, score=1),
            _Entree(commande="ACTION2", niveau=2, score=1),
        ]
        niveaux = niveaux_joues(entrees, CIBLE)
        self.assertEqual([niveau.actions for niveau in niveaux], [2, 1, 0])
        self.assertEqual([niveau.complete for niveau in niveaux], [True, False, False])

    def test_la_completion_vient_du_score_du_serveur(self) -> None:
        entrees = [
            _Entree(commande="RESET", niveau=1, score=0),
            _Entree(commande="ACTION6", niveau=2, score=1),
            _Entree(commande="ACTION6", niveau=3, score=2),
        ]
        niveaux = niveaux_joues(entrees, CIBLE)
        self.assertEqual([niveau.complete for niveau in niveaux], [True, True, False])

    def test_les_niveaux_non_atteints_figurent_avec_leur_baseline(self) -> None:
        entrees = [_Entree(commande="RESET", niveau=1, score=0)]
        niveaux = niveaux_joues(entrees, CIBLE)
        self.assertEqual([niveau.baseline for niveau in niveaux], list(CIBLE))
        self.assertEqual(len(niveaux), 3)

    def test_un_numero_final_au_dela_du_dernier_niveau_est_tolere(self) -> None:
        """Après la victoire finale, l'API peut avancer son compteur ; nul n'y joue."""
        entrees = [
            _Entree(commande="RESET", niveau=3, score=2),
            _Entree(commande="ACTION6", niveau=4, score=3),
        ]
        niveaux = niveaux_joues(entrees, CIBLE)
        self.assertEqual([niveau.actions for niveau in niveaux], [0, 0, 1])
        self.assertTrue(all(niveau.complete for niveau in niveaux))

    def test_une_action_jouee_depuis_un_niveau_hors_bornes_est_refusee(self) -> None:
        entrees = [
            _Entree(commande="RESET", niveau=1, score=0),
            _Entree(commande="ACTION2", niveau=5, score=0),
            _Entree(commande="ACTION2", niveau=5, score=0),
        ]
        with self.assertRaises(RhaeInvalide) as capture:
            niveaux_joues(entrees, CIBLE)
        self.assertIn("niveau 5", str(capture.exception))

    def test_un_historique_vide_est_refuse(self) -> None:
        with self.assertRaises(RhaeInvalide):
            niveaux_joues([], CIBLE)

    def test_un_historique_qui_ne_commence_pas_par_reset_est_refuse(self) -> None:
        entrees = [_Entree(commande="ACTION2", niveau=1, score=0)]
        with self.assertRaises(RhaeInvalide) as capture:
            niveaux_joues(entrees, CIBLE)
        self.assertIn("RESET", str(capture.exception))

    def test_un_jeu_sans_baseline_est_refuse(self) -> None:
        entrees = [_Entree(commande="RESET", niveau=1, score=0)]
        with self.assertRaises(RhaeInvalide):
            niveaux_joues(entrees, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
