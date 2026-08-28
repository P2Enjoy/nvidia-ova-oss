"""Preuves de la comptabilité des tokens : estimation, calibration, totaux.

@verifies docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@verifies docs/SPEC_HARNAIS.md §H5.2 (estimation corrigée par le compte réel)
"""

from __future__ import annotations

import unittest

from avo.context.tokens import CARACTERES_PAR_TOKEN, TokenLedger, estimer_messages, estimer_tokens


class TestEstimation(unittest.TestCase):
    def test_texte_vide_ne_coute_rien(self) -> None:
        self.assertEqual(estimer_tokens(""), 0)

    def test_un_texte_non_vide_coute_au_moins_un_token(self) -> None:
        self.assertEqual(estimer_tokens("a"), 1)

    def test_estimation_proportionnelle_a_la_longueur(self) -> None:
        self.assertEqual(estimer_tokens("x" * 340, caracteres_par_token=3.4), 100)

    def test_les_messages_comptent_roles_et_contenus(self) -> None:
        messages = [{"role": "user", "content": "x" * 340}]
        self.assertGreater(estimer_messages(messages, 3.4), 100)


class TestCalibration(unittest.TestCase):
    """§H5.2 : l'estimation sert aux seuils, le réel fait foi et recalibre."""

    def test_sans_echange_le_facteur_vaut_un(self) -> None:
        self.assertEqual(TokenLedger().facteur_correction, 1.0)

    def test_une_sous_estimation_resserre_le_rapport(self) -> None:
        registre = TokenLedger()
        depart = registre.caracteres_par_token
        registre.enregistrer(estime=100, prompt_eval_count=200)
        self.assertLess(registre.caracteres_par_token, depart)
        self.assertEqual(registre.facteur_correction, 2.0)

    def test_une_sur_estimation_relache_le_rapport(self) -> None:
        registre = TokenLedger()
        depart = registre.caracteres_par_token
        registre.enregistrer(estime=200, prompt_eval_count=100)
        self.assertGreater(registre.caracteres_par_token, depart)

    def test_apres_calibration_l_estimation_se_rapproche_du_reel(self) -> None:
        registre = TokenLedger()
        texte = "x" * 1000
        estime = registre.estimer(texte)
        reel = estime * 2
        registre.enregistrer(estime=estime, prompt_eval_count=reel)
        self.assertEqual(registre.estimer(texte), reel)

    def test_un_serveur_sans_compteur_ne_deregle_pas_l_estimation(self) -> None:
        registre = TokenLedger()
        depart = registre.caracteres_par_token
        registre.enregistrer(estime=100, prompt_eval_count=0)
        self.assertEqual(registre.caracteres_par_token, depart)
        self.assertEqual(registre.appels, 1)


class TestTotaux(unittest.TestCase):
    def test_les_totaux_cumulent_entree_et_sortie(self) -> None:
        registre = TokenLedger()
        registre.enregistrer(estime=100, prompt_eval_count=120, eval_count=30)
        registre.enregistrer(estime=200, prompt_eval_count=240, eval_count=60)
        self.assertEqual(registre.appels, 2)
        self.assertEqual(registre.reel_cumule, 360)
        self.assertEqual(registre.sortie_cumulee, 90)
        self.assertEqual(registre.total_tokens, 450)

    def test_le_resume_ne_porte_que_des_compteurs(self) -> None:
        registre = TokenLedger()
        registre.enregistrer(estime=100, prompt_eval_count=120, eval_count=30)
        resume = registre.resume()
        self.assertEqual(resume["total_tokens"], 150)
        self.assertEqual(resume["appels"], 1)
        self.assertAlmostEqual(float(resume["facteur_correction"]), 1.2)
        self.assertNotIn("contenu", resume)

    def test_le_rapport_par_defaut_est_celui_mesure(self) -> None:
        self.assertEqual(TokenLedger().caracteres_par_token, CARACTERES_PAR_TOKEN)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
