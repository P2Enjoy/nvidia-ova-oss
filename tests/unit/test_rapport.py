"""Preuves du rapport de campagne : ce qu'il dit, et ce qu'il refuse de taire.

@verifies docs/BACKLOG.md U23 — Runner de campagne et rapport
@verifies docs/SPEC_ARCAGI3.md §A7.3 (contenu du rapport), §A7.4 (fonction pure),
          §A6.1 (le détail par niveau rend le RHAE vérifiable à la main)
"""

from __future__ import annotations

import unittest
from typing import Any

from avo.arc.campagne import Plafonds, ResultatCampagne, ResultatJeu
from avo.arc.rapport import (
    REFERENCES,
    comparaison,
    couts,
    evenements,
    formater,
    limites,
    sections,
    table_par_jeu,
    table_par_niveau,
)
from avo.arc.rhae import NiveauJoue, rhae_jeu


def _jeu(game_id: str, complets: int = 3, actions: int = 76) -> ResultatJeu:
    niveaux = tuple(
        NiveauJoue(
            niveau=index + 1,
            baseline=base,
            actions=base if index < complets else 0,
            complete=index < complets,
        )
        for index, base in enumerate((39, 19, 18))
    )
    return ResultatJeu(
        game_id=game_id,
        guid="g",
        niveaux=niveaux,
        rhae=rhae_jeu(niveaux),
        tours=actions,
        arret="tours_epuises",
        actions=actions,
        niveaux_completes=complets,
        game_overs=0,
        tokens_prompt=1_000,
        tokens_generes=300,
        secondes=8.0,
        continuations=2,
        depassements=1,
        interventions=3,
        versions_committees=complets,
    )


def _campagne(mode: str = "replay", **surcharges: object) -> ResultatCampagne:
    jeux = surcharges.pop("jeux", (_jeu("cible"),))
    return ResultatCampagne(
        run_id="run-1",
        mode=mode,
        card_id=surcharges.pop("card_id", "carte-1"),  # type: ignore[arg-type]
        plafonds=Plafonds(actions_niveau=200, actions_jeu=800, tours_max=800),
        jeux=jeux,  # type: ignore[arg-type]
        score_global=100.0,
    )


class TestMiseEnForme(unittest.TestCase):
    def test_deux_decimales(self) -> None:
        self.assertEqual(formater(100.0), "100.00")
        self.assertEqual(formater(100.0 / 6), "16.67")


class TestTables(unittest.TestCase):
    def test_la_table_par_jeu_porte_les_quatre_colonnes_exigees(self) -> None:
        rendu = table_par_jeu([_jeu("cible")])
        for attendu in ("Niveaux complétés", "Actions", "Baseline", "RHAE"):
            with self.subTest(colonne=attendu):
                self.assertIn(attendu, rendu)
        self.assertIn("| 3 / 3 |", rendu)
        self.assertIn("| 76 |", rendu, "la baseline cumulée du jeu cible")

    def test_sans_jeu_la_table_le_dit_au_lieu_d_etre_vide(self) -> None:
        self.assertIn("Aucun jeu", table_par_jeu([]))

    def test_le_detail_par_niveau_donne_les_entrees_de_la_formule(self) -> None:
        rendu = table_par_niveau([_jeu("cible")])
        self.assertIn("Baseline hₗ", rendu)
        self.assertIn("Actions aₗ", rendu)
        self.assertIn("Poids wₗ", rendu)
        self.assertEqual(rendu.count("| `cible` |"), 3, "une ligne par niveau du jeu")


class TestCoutsEtEvenements(unittest.TestCase):
    def test_les_couts_comptent_les_appels_depuis_les_metriques(self) -> None:
        metriques: list[dict[str, Any]] = [
            {"type": "llm"},
            {"type": "llm", "tronquee": True},
            {"type": "action"},
        ]
        rendu = couts([_jeu("cible")], metriques)
        self.assertIn("appels au modèle : **2**", rendu)
        self.assertIn("1 tronqué", rendu)
        self.assertIn("tokens de prompt : **1000**", rendu)
        self.assertIn("actions dépensées : **76**", rendu)

    def test_sans_troncature_la_mention_n_apparait_pas(self) -> None:
        self.assertNotIn("tronqué", couts([_jeu("cible")], [{"type": "llm"}]))

    def test_les_evenements_exiges_sont_tous_presents(self) -> None:
        rendu = evenements([_jeu("cible")])
        for attendu in ("continuations", "413", "superviseur", "lignée", "game over"):
            with self.subTest(evenement=attendu):
                self.assertIn(attendu, rendu)
        self.assertIn("continuations en contexte frais : **2**", rendu)
        self.assertIn("interventions du superviseur : **3**", rendu)


class TestComparaisonEtLimites(unittest.TestCase):
    def test_les_trois_references_publiees_figurent(self) -> None:
        rendu = comparaison(_campagne())
        for nom, _, _ in REFERENCES:
            with self.subTest(reference=nom):
                self.assertIn(nom, rendu)
        self.assertIn("cette campagne", rendu)

    def test_en_rejeu_le_rapport_dit_que_le_score_n_est_pas_comparable(self) -> None:
        """Un rapport muet là-dessus se lirait comme un score ARC-AGI-3."""
        rendu = limites(_campagne(mode="replay"))
        self.assertIn("mode rejeu", rendu)
        self.assertIn("pas comparable", rendu)

    def test_en_live_cette_reserve_disparait(self) -> None:
        self.assertNotIn("pas comparable", limites(_campagne(mode="live")))

    def test_sans_scorecard_le_rapport_dit_que_rien_n_est_publie(self) -> None:
        self.assertIn("rien n'a été publié", limites(_campagne(card_id=None)))

    def test_un_jeu_non_termine_est_nomme(self) -> None:
        rendu = limites(_campagne(jeux=(_jeu("cible", complets=1, actions=39),)))
        self.assertIn("Jeux non terminés", rendu)
        self.assertIn("`cible`", rendu)

    def test_un_arret_sur_borne_est_nomme(self) -> None:
        jeu = _jeu("cible")
        borne = ResultatJeu(**{**jeu.__dict__, "arret": "budget de tokens du jeu épuisé (500)"})
        self.assertIn("budget de tokens", limites(_campagne(jeux=(borne,))))


class TestSections(unittest.TestCase):
    def test_toutes_les_sections_exigees_par_A7_3_sont_produites(self) -> None:
        titres = [titre for titre, _ in sections(_campagne(), [])]
        self.assertEqual(
            titres,
            [
                "Résultat",
                "Par jeu",
                "Détail par niveau",
                "Coûts",
                "Événements",
                "Comparaison aux références publiées",
                "Limites et écarts",
            ],
        )

    def test_l_entete_porte_le_score_global_et_les_plafonds(self) -> None:
        corps = dict(sections(_campagne(), []))["Résultat"]
        self.assertIn("score global", corps)
        self.assertIn("100.00", corps)
        self.assertIn("200 actions/niveau", corps)
        self.assertIn("tokens/jeu aucun", corps, "un plafond absent est dit absent")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
