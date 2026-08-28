"""Preuves de la machine d'états : transitions déterministes et closes.

@verifies docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@verifies docs/SPEC_HARNAIS.md §H8.1 (états et transitions pilotées par les événements)
@verifies docs/SPEC_ARCAGI3.md §A5.1 (aucune règle de jeu dans les prompts)
"""

from __future__ import annotations

import unittest

from avo.loop import prompts
from avo.loop.etats import (
    EVENEMENTS_DE_TOUR,
    TRANSITIONS,
    Evenement,
    Phase,
    TransitionInterdite,
    evenements_admis,
    suivant,
)


class TestTransitions(unittest.TestCase):
    """§H8.1 : le cycle nominal et ses embranchements."""

    def test_le_cycle_nominal_boucle_sur_planning(self) -> None:
        phase = Phase.PLANNING
        phase = suivant(phase, Evenement.ACTION_CHOISIE)
        self.assertIs(phase, Phase.IMPLEMENTATION)
        phase = suivant(phase, Evenement.ACTION_JOUEE)
        self.assertIs(phase, Phase.EVALUATION)
        phase = suivant(phase, Evenement.PREDICTION_CONFIRMEE)
        self.assertIs(phase, Phase.PLANNING)

    def test_une_contradiction_derive_vers_le_bug_fixing(self) -> None:
        self.assertIs(suivant(Phase.EVALUATION, Evenement.CONTRADICTION), Phase.BUG_FIXING)

    def test_un_game_over_derive_aussi_vers_le_bug_fixing(self) -> None:
        """Une tentative perdue se révise, elle ne se rejoue pas à l'identique."""
        self.assertIs(suivant(Phase.EVALUATION, Evenement.GAME_OVER), Phase.BUG_FIXING)

    def test_un_niveau_complete_repart_en_planification(self) -> None:
        self.assertIs(suivant(Phase.EVALUATION, Evenement.NIVEAU_COMPLETE), Phase.PLANNING)

    def test_le_bug_fixing_rend_la_main_a_la_planification(self) -> None:
        self.assertIs(suivant(Phase.BUG_FIXING, Evenement.REVISION_FAITE), Phase.PLANNING)

    def test_le_bug_fixing_ne_joue_jamais_directement(self) -> None:
        """Il révise ; agir repasse par la planification, donc par une prédiction."""
        for evenement in Evenement:
            cible = TRANSITIONS.get((Phase.BUG_FIXING, evenement))
            if cible is not None:
                self.assertIsNot(cible, Phase.IMPLEMENTATION)


class TestTransitionsInterdites(unittest.TestCase):
    """La table est close : tout couple absent lève, aucun repli silencieux."""

    def test_un_evenement_impossible_leve_en_nommant_les_admis(self) -> None:
        with self.assertRaises(TransitionInterdite) as capture:
            suivant(Phase.PLANNING, Evenement.GAME_OVER)
        message = str(capture.exception)
        self.assertIn("game_over", message)
        self.assertIn("planning", message)
        self.assertIn("action_choisie", message)

    def test_aucune_phase_n_accepte_tous_les_evenements(self) -> None:
        for phase in Phase:
            with self.subTest(phase=phase):
                self.assertLess(len(evenements_admis(phase)), len(Evenement))

    def test_chaque_phase_a_au_moins_une_sortie(self) -> None:
        """Aucun état ne doit être un cul-de-sac."""
        for phase in Phase:
            with self.subTest(phase=phase):
                self.assertGreater(len(evenements_admis(phase)), 0)

    def test_toutes_les_phases_sont_atteignables(self) -> None:
        atteintes = {cible for cible in TRANSITIONS.values()}
        atteintes.add(Phase.PLANNING)  # état initial
        self.assertEqual(atteintes, set(Phase))

    def test_les_evenements_de_tour_closent_tous_l_evaluation(self) -> None:
        for evenement in EVENEMENTS_DE_TOUR:
            with self.subTest(evenement=evenement):
                self.assertIn((Phase.EVALUATION, evenement), TRANSITIONS)


class TestPromptsSansRegleDeJeu(unittest.TestCase):
    """§A5.1 : un indice glissé ici invaliderait toute l'évaluation."""

    TEXTES = (
        prompts.SYSTEME,
        prompts.PLANNING,
        prompts.IMPLEMENTATION,
        prompts.EVALUATION,
        prompts.BUG_FIXING,
        prompts.BORNE_PROCHE,
    )

    #: Termes qui trahiraient une connaissance du jeu ou de son but.
    INTERDITS = (
        "cible",
        "curseur",
        "clique sur",
        "gagner",
        "victoire",
        "ennemi",
        "obstacle",
        "porte",
        "clé",
        "score maximal",
        "64x64",
        "64 × 64",
    )

    def test_aucun_prompt_ne_decrit_de_regle_ni_de_but(self) -> None:
        for texte in self.TEXTES:
            for interdit in self.INTERDITS:
                with self.subTest(interdit=interdit):
                    self.assertNotIn(interdit, texte.lower())

    def test_les_prompts_restent_courts(self) -> None:
        """Ils sont réémis à chaque tour : le préremplissage domine le coût."""
        for texte in self.TEXTES:
            with self.subTest(debut=texte[:24]):
                self.assertLess(len(texte), 700)

    def test_le_contrat_demande_prediction_puis_bilan(self) -> None:
        self.assertIn("énonce ce que tu attends", prompts.SYSTEME.lower())
        self.assertIn("prédiction", prompts.PLANNING.lower())
        self.assertIn("changements visibles", prompts.EVALUATION.lower())

    def test_une_seule_action_est_exigee(self) -> None:
        self.assertIn("une seule", prompts.IMPLEMENTATION.lower())

    def test_les_prompts_sont_versionnes(self) -> None:
        """Un rapport doit pouvoir dire sous quelle formulation il a été obtenu."""
        self.assertRegex(prompts.VERSION, r"^\d+\.\d+$")

    def test_chaque_phase_a_son_prompt(self) -> None:
        for phase in Phase:
            with self.subTest(phase=phase):
                self.assertTrue(prompts.prompt_de_phase(phase.value))

    def test_une_phase_inconnue_leve(self) -> None:
        with self.assertRaises(KeyError):
            prompts.prompt_de_phase("inexistante")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
