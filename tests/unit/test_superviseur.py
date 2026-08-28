"""Preuves du superviseur : détecteurs positifs ET négatifs, cooldown, séparation.

@verifies docs/BACKLOG.md U15 — Superviseur
@verifies docs/SPEC_HARNAIS.md §H10.1 (il n'agit jamais), §H10.2 (déclencheurs
          mesurables), §H10.3 (intervention, cooldown, journalisation), §H5.1 (append-only)
"""

from __future__ import annotations

import unittest
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.context.transcript import Transcript
from avo.llm.client import ChatResult, LLMClient
from avo.supervisor import (
    BALISE,
    BUG_FIXING_CONSECUTIFS_MAX,
    FENETRE_CYCLE,
    REPETITIONS_CYCLE,
    Superviseur,
    Trajectoire,
    cycle_improductif,
    empreinte_frame,
    rafale_bug_fixing,
    stagnation,
)


def _config(**env: str) -> Config:
    return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))


class _ClientScripte(LLMClient):
    """Client qui rend une directive fixe et compte ses appels."""

    def __init__(self, directive: str = "essaie plutôt le bord gauche") -> None:
        self.directive = directive
        self.appels: list[list[dict[str, object]]] = []

    def chat(self, messages, tools=None, **surcharges):  # type: ignore[no-untyped-def]
        self.appels.append(list(messages))
        return ChatResult(content=self.directive)


def _trajectoire(actions: list[tuple[str, str]], **suites: bool) -> Trajectoire:
    trajectoire = Trajectoire()
    for action, observation in actions:
        trajectoire.enregistrer(action, observation, **suites)
    return trajectoire


class TestStagnation(unittest.TestCase):
    """§H10.2 : trop d'actions sans complétion ni entrée de lignée."""

    def test_sous_le_seuil_rien_ne_se_declenche(self) -> None:
        trajectoire = _trajectoire([("a", f"f{n}") for n in range(5)])
        self.assertIsNone(stagnation(trajectoire, seuil=10))

    def test_au_seuil_le_motif_est_rendu(self) -> None:
        trajectoire = _trajectoire([("a", f"f{n}") for n in range(10)])
        motif = stagnation(trajectoire, seuil=10)
        self.assertIsNotNone(motif)
        self.assertIn("stagnation", str(motif))
        self.assertIn("10", str(motif))

    def test_une_completion_de_niveau_remet_le_compteur_a_zero(self) -> None:
        trajectoire = Trajectoire()
        for n in range(9):
            trajectoire.enregistrer("a", f"f{n}")
        trajectoire.enregistrer("a", "f-gagnant", niveau_complete=True)
        self.assertEqual(trajectoire.actions_depuis_progres, 0)
        self.assertIsNone(stagnation(trajectoire, seuil=10))

    def test_une_entree_de_lignee_compte_aussi_comme_progres(self) -> None:
        """§H10.2 : « sans complétion de niveau ET sans nouvelle entrée de lignée »."""
        trajectoire = _trajectoire([("a", f"f{n}") for n in range(10)])
        self.assertIsNotNone(stagnation(trajectoire, seuil=10))
        trajectoire.signaler_version_committee()
        self.assertIsNone(stagnation(trajectoire, seuil=10))


class TestCycleImproductif(unittest.TestCase):
    """§H10.2 : répéter sans que la frame change."""

    def test_repeter_sans_changement_declenche(self) -> None:
        trajectoire = _trajectoire([("avance", "identique")] * FENETRE_CYCLE)
        motif = cycle_improductif(trajectoire)
        self.assertIsNotNone(motif)
        self.assertIn("cycle improductif", str(motif))
        self.assertIn("avance", str(motif))

    def test_repeter_avec_effets_differents_ne_declenche_pas(self) -> None:
        """Répéter une action qui produit des effets différents est légitime."""
        trajectoire = _trajectoire([("avance", f"frame{n}") for n in range(FENETRE_CYCLE)])
        self.assertIsNone(cycle_improductif(trajectoire))

    def test_actions_variees_sur_frame_figee_ne_declenchent_pas(self) -> None:
        """C'est la répétition d'UNE action qui compte, pas l'immobilité seule."""
        trajectoire = _trajectoire([(f"action{n}", "identique") for n in range(FENETRE_CYCLE)])
        self.assertIsNone(cycle_improductif(trajectoire))

    def test_une_fenetre_incomplete_ne_declenche_pas(self) -> None:
        trajectoire = _trajectoire([("avance", "identique")] * (FENETRE_CYCLE - 1))
        self.assertIsNone(cycle_improductif(trajectoire))

    def test_juste_sous_le_nombre_de_repetitions_ne_declenche_pas(self) -> None:
        pas = [("avance", "identique")] * (REPETITIONS_CYCLE - 1)
        pas += [(f"autre{n}", f"bouge{n}") for n in range(FENETRE_CYCLE - len(pas))]
        self.assertIsNone(cycle_improductif(_trajectoire(pas)))

    def test_seule_la_fenetre_recente_compte(self) -> None:
        trajectoire = _trajectoire([("avance", "identique")] * FENETRE_CYCLE)
        self.assertIsNotNone(cycle_improductif(trajectoire))
        for n in range(FENETRE_CYCLE):
            trajectoire.enregistrer(f"neuve{n}", f"frame{n}")
        self.assertIsNone(cycle_improductif(trajectoire))


class TestRafaleBugFixing(unittest.TestCase):
    def test_sous_le_maximum_rien_ne_se_declenche(self) -> None:
        trajectoire = Trajectoire()
        for _ in range(BUG_FIXING_CONSECUTIFS_MAX):
            trajectoire.enregistrer("a", "f", bug_fixing=True)
        self.assertIsNone(rafale_bug_fixing(trajectoire))

    def test_au_dela_du_maximum_le_motif_est_rendu(self) -> None:
        trajectoire = Trajectoire()
        for _ in range(BUG_FIXING_CONSECUTIFS_MAX + 1):
            trajectoire.enregistrer("a", "f", bug_fixing=True)
        self.assertIn("rafale", str(rafale_bug_fixing(trajectoire)))

    def test_un_tour_sans_correction_remet_le_compteur_a_zero(self) -> None:
        trajectoire = Trajectoire()
        for _ in range(BUG_FIXING_CONSECUTIFS_MAX + 1):
            trajectoire.enregistrer("a", "f", bug_fixing=True)
        trajectoire.enregistrer("a", "f", bug_fixing=False)
        self.assertEqual(trajectoire.bug_fixing_consecutifs, 0)
        self.assertIsNone(rafale_bug_fixing(trajectoire))


class TestCooldownEtIntervention(unittest.TestCase):
    """§H10.3 : au plus une intervention par cooldown, et elle n'agit jamais."""

    def setUp(self) -> None:
        self.client = _ClientScripte()
        self.superviseur = Superviseur(
            _config(AVO_SUP_STALL_ACTIONS="5", AVO_SUP_COOLDOWN="10"), self.client
        )

    def _stagner(self, actions: int) -> None:
        for n in range(actions):
            self.superviseur.trajectoire.enregistrer("avance", f"frame{n}")

    def test_aucune_intervention_sans_motif(self) -> None:
        self._stagner(2)
        self.assertIsNone(self.superviseur.doit_intervenir())

    def test_le_motif_declenche_une_intervention(self) -> None:
        self._stagner(5)
        self.assertIsNotNone(self.superviseur.doit_intervenir())

    def test_le_cooldown_empeche_une_seconde_intervention_immediate(self) -> None:
        self._stagner(5)
        transcript = Transcript.ouvrir("sys")
        transcript, _ = self.superviseur.intervenir(transcript, "motif", "notes", "observation")
        self._stagner(3)
        self.assertTrue(self.superviseur.en_cooldown())
        self.assertIsNone(self.superviseur.doit_intervenir())

    def test_apres_le_cooldown_une_nouvelle_intervention_est_possible(self) -> None:
        self._stagner(5)
        transcript = Transcript.ouvrir("sys")
        self.superviseur.intervenir(transcript, "motif", "notes", "observation")
        self._stagner(10)
        self.assertFalse(self.superviseur.en_cooldown())
        self.assertIsNotNone(self.superviseur.doit_intervenir())

    def test_l_injection_est_balisee_et_append_only(self) -> None:
        transcript = Transcript.ouvrir("sys").utilisateur("observation")
        avant = transcript
        apres, intervention = self.superviseur.intervenir(
            transcript, "stagnation", "mes notes", "grille"
        )
        self.assertTrue(apres.prolonge(avant))
        dernier = apres.pour_api()[-1]
        self.assertEqual(dernier["role"], "user")
        self.assertTrue(dernier["content"].startswith(BALISE))
        self.assertIn(self.client.directive, dernier["content"])
        self.assertEqual(intervention.motif, "stagnation")

    def test_le_superviseur_ne_recoit_pas_l_historique_de_l_acteur(self) -> None:
        """§H10.3 : contexte propre — hériter du contexte, c'est hériter de l'ornière."""
        transcript = Transcript.ouvrir("sys").utilisateur("SECRET DE L ACTEUR")
        self.superviseur.intervenir(transcript, "motif", "notes", "grille")
        envoye = str(self.client.appels[0])
        self.assertNotIn("SECRET DE L ACTEUR", envoye)
        self.assertIn("Motif du déclenchement", envoye)

    def test_le_superviseur_ne_dispose_d_aucun_outil(self) -> None:
        """§H10.1 : il ne joue jamais d'action ; il n'a pas d'outil du tout."""
        self.superviseur.intervenir(Transcript.ouvrir("sys"), "m", "n", "o")
        self.assertEqual(len(self.client.appels), 1)
        self.assertFalse(hasattr(self.superviseur, "registre"))

    def test_le_resume_porte_les_motifs_sans_le_contenu(self) -> None:
        self._stagner(5)
        self.superviseur.intervenir(Transcript.ouvrir("sys"), "stagnation", "n", "o")
        resume = self.superviseur.resume()
        self.assertEqual(resume["interventions"], 1)
        self.assertEqual(resume["motifs"], ["stagnation"])
        self.assertNotIn(self.client.directive, str(resume))


class TestEmpreinte(unittest.TestCase):
    def test_deux_observations_identiques_ont_la_meme_empreinte(self) -> None:
        self.assertEqual(empreinte_frame("grille"), empreinte_frame("grille"))

    def test_une_observation_differente_change_l_empreinte(self) -> None:
        self.assertNotEqual(empreinte_frame("grille"), empreinte_frame("grille "))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
